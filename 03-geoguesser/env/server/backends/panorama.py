# SPDX-License-Identifier: BSD-3-Clause

"""Mapillary-backed panoramas, read from a frozen index and a local cache.

The index (`tasks/pano_v1.jsonl`) is self-contained: it carries every frame's
coordinates, heading and capture date, so the movement graph resolves with no
network access at all. Only image *bytes* may need fetching, and only on a
cache miss, because Mapillary's `thumb_*_url` values are expiring signed CDN
URLs and cannot be stored in the index.

Once a task's frames are cached, episodes are byte-identical on repeat — the
property a GRPO group depends on.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import urllib.parse
import urllib.request

from PIL import Image

from ..render.pano import look
from .base import Frame, Task


logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.mapillary.com"
FETCH_TIMEOUT_S = 60.0

# Zooming into a 2048x1024 panorama is resolution-starved: a 30-degree view
# samples only ~170 source pixels, so narrowing the field of view barely adds
# detail (measured mean gradient 6.60 at 90 degrees against 7.03 at 30). The
# 7680x3840 original roughly doubles it instead (10.23 against 14.87), which is
# what makes reading a distant sign possible at all.
#
# So two derivatives are cached per panorama: the 2048 for wide views, which
# renders in ~30 ms, and the original for zoomed views at ~70 ms and 3.3 MB.
THUMB_VARIANT = "thumb_2048_url"
ORIGINAL_VARIANT = "thumb_original_url"
HIRES_FOV_DEG = 45.0


class MissingImageError(RuntimeError):
    """A frame is absent from the cache and cannot be fetched."""


_INDEX_CACHE: dict[tuple[str, float, int], list[Task]] = {}
"""Parsed indexes keyed by path, mtime and size, so edits invalidate the entry."""


def load_index(index_path: str | pathlib.Path) -> list[Task]:
    """
    Parse a task index, reusing an already-parsed copy when possible.

    The Task API routes construct a throwaway environment per request and a
    5,000-task index is roughly 31 MB, so re-parsing it on every call is not
    affordable. Keying on mtime and size means rebuilding an index in place
    invalidates the entry instead of serving stale tasks.

    Args:
        index_path (`str` or `pathlib.Path`):
            JSONL index written by `dataset/build_tasks.py`.

    Returns:
        `list[Task]`: Tasks ordered by `task_index`. The list is shared between
            callers, so treat it as read-only.

    Raises:
        FileNotFoundError: When the index does not exist.
        ValueError: When the index is empty, or its task indices are not
            contiguous from zero.
    """
    path = pathlib.Path(index_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Task index not found: {path}. Build one with dataset/build_tasks.py."
        )
    stat = path.stat()
    key = (str(path.resolve()), stat.st_mtime, stat.st_size)
    cached = _INDEX_CACHE.get(key)
    if cached is not None:
        return cached

    tasks: list[Task] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        frames = [
            Frame(
                image_id=str(f["image_id"]),
                lat=float(f["lat"]),
                lon=float(f["lon"]),
                compass_angle=float(f.get("compass_angle", 0.0)),
                captured_at=str(f.get("captured_at", "")),
                is_pano=bool(f.get("is_pano", True)),
            )
            for f in row["frames"]
        ]
        tasks.append(
            Task(
                task_index=int(row["task_index"]),
                task_id=str(row["task_id"]),
                frames=frames,
                start_frame=int(row.get("start_frame", 0)),
                country=str(row.get("country", "")),
                sequence_id=str(row.get("sequence_id", "")),
                provider=str(row.get("provider", "mapillary")),
                attribution=row.get("attribution", {}),
                meta=row.get("meta", {}),
            )
        )
    if not tasks:
        raise ValueError(f"Task index {path} is empty.")
    tasks.sort(key=lambda t: t.task_index)
    for position, task in enumerate(tasks):
        if task.task_index != position:
            raise ValueError(
                "Task indices must be contiguous from 0; found "
                f"{task.task_index} at position {position}."
            )
    _INDEX_CACHE[key] = tasks
    return tasks


class PanoramaBackend:
    """Serve panoramas from a frozen task index plus a disk cache.

    Args:
        index_path (`str` or `pathlib.Path`):
            JSONL task index produced by `dataset/build_pano_tasks.py`.
        cache_dir (`str` or `pathlib.Path`):
            Directory holding cached JPEGs, named `<image_id>.jpg`.
        access_token (`str`, *optional*):
            Mapillary token, used only to fill cache misses. When absent, a
            miss raises [`MissingImageError`] instead of reaching the network.
        allow_fetch (`bool`, *optional*, defaults to `True`):
            Set `False` to guarantee an episode never touches the network.
        hires_zoom (`bool`, *optional*, defaults to `True`):
            Render fields of view at or below `hires_fov_deg` from the
            full-resolution original, so zooming actually resolves detail.
            Falls back to the 2048 derivative when no original exists.
        hires_fov_deg (`float`, *optional*, defaults to `45.0`):
            Field of view at or below which the original is used.
        verify_checksums (`bool`, *optional*, defaults to `False`):
            Verify each cached start frame against the sha256 recorded at build
            time. Used by frozen evals to detect drift.

    Examples:

    ```python
    backend = PanoramaBackend("tasks/pano_v1.jsonl", "data/panos")
    task = backend.task(0)
    view = backend.render_view(task, task.start_frame, 90.0, 0.0, 90.0)
    ```
    """

    def __init__(
        self,
        index_path: str | pathlib.Path,
        cache_dir: str | pathlib.Path,
        access_token: str | None = None,
        allow_fetch: bool = True,
        verify_checksums: bool = False,
        hires_zoom: bool = True,
        hires_fov_deg: float = HIRES_FOV_DEG,
    ):
        self._index_path = pathlib.Path(index_path)
        self._cache_dir = pathlib.Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._token = access_token or os.environ.get("MAPILLARY_API_KEY")
        self._allow_fetch = allow_fetch
        self._verify_checksums = verify_checksums
        self._hires_zoom = hires_zoom
        self._hires_fov_deg = hires_fov_deg
        self._tasks = self._load_index()
        logger.info(
            "loaded %d tasks from %s (cache: %s, fetch: %s)",
            len(self._tasks),
            self._index_path,
            self._cache_dir,
            "on" if self._allow_fetch and self._token else "off",
        )

    # -- index ------------------------------------------------------------

    def _load_index(self) -> list[Task]:
        return load_index(self._index_path)

    # -- capabilities -----------------------------------------------------

    @property
    def n_tasks(self) -> int:
        """Number of tasks in the frozen index."""
        return len(self._tasks)

    @property
    def supports_look(self) -> bool:
        """True — every task in this index is a 360-degree panorama."""
        return True

    @property
    def supports_move(self) -> bool:
        """Whether any task has more than one frame to walk between."""
        return any(len(t.frames) > 1 for t in self._tasks)

    def task(self, task_index: int) -> Task:
        """
        Return the task at `task_index`.

        Args:
            task_index (`int`):
                Position in the frozen index.

        Returns:
            [`Task`]: The task, including its full frame list.
        """
        if not 0 <= task_index < len(self._tasks):
            raise IndexError(
                f"task_index {task_index} out of range for {len(self._tasks)} tasks."
            )
        return self._tasks[task_index]

    # -- imagery ----------------------------------------------------------

    def _cache_path(self, image_id: str, hires: bool = False) -> pathlib.Path:
        suffix = ".orig.jpg" if hires else ".jpg"
        return self._cache_dir / f"{image_id}{suffix}"

    def _fetch(self, image_id: str, hires: bool = False) -> bytes:
        if not self._allow_fetch:
            raise MissingImageError(
                f"Image {image_id} is not cached and fetching is disabled. "
                "Warm the cache with dataset/build_pano_tasks.py --prefetch-frames."
            )
        if not self._token:
            raise MissingImageError(
                f"Image {image_id} is not cached and MAPILLARY_API_KEY is unset, "
                "so it cannot be fetched."
            )
        variant = ORIGINAL_VARIANT if hires else THUMB_VARIANT
        meta_url = f"{GRAPH_API}/{image_id}?" + urllib.parse.urlencode(
            {"fields": variant, "access_token": self._token}
        )
        with urllib.request.urlopen(meta_url, timeout=FETCH_TIMEOUT_S) as response:
            thumb_url = json.loads(response.read()).get(variant)
        if not thumb_url:
            raise MissingImageError(
                f"Mapillary returned no {variant} for {image_id}; its "
                "derivatives may have been removed."
            )
        with urllib.request.urlopen(thumb_url, timeout=FETCH_TIMEOUT_S) as response:
            return response.read()

    def load_pano(
        self,
        image_id: str,
        expected_sha256: str | None = None,
        hires: bool = False,
    ) -> Image.Image:
        """
        Return a panorama, fetching and caching it if necessary.

        Args:
            image_id (`str`):
                Provider-side image identifier.
            expected_sha256 (`str`, *optional*):
                Checksum recorded at build time. Verified only when the backend
                was constructed with `verify_checksums=True`, and only for
                the 2048 derivative, which is what the index records.
            hires (`bool`, *optional*, defaults to `False`):
                Load the full-resolution original instead of the 2048
                derivative.

        Returns:
            `PIL.Image.Image`: The equirectangular panorama.
        """
        path = self._cache_path(image_id, hires=hires)
        if not path.exists():
            payload = self._fetch(image_id, hires=hires)
            path.write_bytes(payload)
            logger.info(
                "cached %s%s (%.0f KB)",
                image_id,
                " at full resolution" if hires else "",
                len(payload) / 1024,
            )
        if self._verify_checksums and expected_sha256 and not hires:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected_sha256:
                raise MissingImageError(
                    f"Checksum mismatch for {image_id}: index recorded "
                    f"{expected_sha256[:12]}, cache holds {actual[:12]}. The "
                    "upstream image changed; this task is no longer comparable."
                )
        return Image.open(path)

    def render_view(
        self,
        task: Task,
        frame_index: int,
        heading_deg: float,
        pitch_deg: float = 0.0,
        fov_deg: float = 90.0,
    ) -> Image.Image:
        """
        Render what the camera sees from one frame of a task.

        Headings are absolute: `0` is true north, obtained by offsetting the
        request by the frame's own `compass_angle`. That keeps `look(0)`
        meaning the same thing in every task.

        Args:
            task ([`Task`]):
                The task being played.
            frame_index (`int`):
                Which frame of the sequence the agent stands on.
            heading_deg (`float`):
                Absolute compass heading in degrees.
            pitch_deg (`float`, *optional*, defaults to `0.0`):
                Vertical angle in degrees.
            fov_deg (`float`, *optional*, defaults to `90.0`):
                Horizontal field of view in degrees.

        Returns:
            `PIL.Image.Image`: The rendered view.
        """
        frame = task.frames[frame_index]
        checksums = task.meta.get("sha256", {})
        want_hires = self._hires_zoom and fov_deg <= self._hires_fov_deg
        try:
            pano = self.load_pano(
                frame.image_id, checksums.get(frame.image_id), hires=want_hires
            )
        except MissingImageError:
            if not want_hires:
                raise
            # A missing original must not end an episode; a soft view beats a
            # failed step.
            logger.warning(
                "no full-resolution original for %s; zooming on the 2048 "
                "derivative instead",
                frame.image_id,
            )
            pano = self.load_pano(frame.image_id, checksums.get(frame.image_id))
        return look(pano, heading_deg + frame.compass_angle, pitch_deg, fov_deg)

    # -- navigation -------------------------------------------------------

    def step_along(
        self, task: Task, frame_index: int, direction: str, meters: float
    ) -> tuple[int, float]:
        """
        Walk the sequence and report where the agent actually ended up.

        Frame spacing is irregular — measured around 3.3 m on Mapillary
        sequences — so the requested distance is consumed frame by frame and
        the realised distance is returned rather than assumed.

        Args:
            task ([`Task`]):
                The task being played.
            frame_index (`int`):
                Current position in `task.frames`.
            direction (`str`):
                `"forward"` or `"backward"`.
            meters (`float`):
                Requested distance in metres.

        Returns:
            `tuple[int, float]` with:
                - the new frame index, unchanged at a dead end
                - metres actually travelled
        """
        from ..scoring import haversine_km

        step = 1 if direction == "forward" else -1
        current = frame_index
        travelled = 0.0
        while travelled < meters:
            nxt = current + step
            if not 0 <= nxt < len(task.frames):
                break
            a, b = task.frames[current], task.frames[nxt]
            travelled += haversine_km(a.lat, a.lon, b.lat, b.lon) * 1000.0
            current = nxt
        return current, travelled

    def can_move(self, task: Task, frame_index: int, direction: str) -> bool:
        """Whether a frame exists in `direction` from the current position."""
        step = 1 if direction == "forward" else -1
        return 0 <= frame_index + step < len(task.frames)
