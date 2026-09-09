# SPDX-License-Identifier: BSD-3-Clause

"""The contract every imagery backend implements.

Backends differ only in where pixels come from and whether the location can be
walked. Everything above them — scoring, parsing, the pin loop, the map — is
shared, so a policy trained against one backend runs unmodified against
another.

A backend that cannot do something reports it through `supports_look` or
`supports_move`; the environment then simply does not register the
corresponding tools. Registering a tool that always fails would only teach a
policy to spend its step budget discovering that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from PIL import Image


@dataclass(frozen=True)
class Frame:
    """One captured position within a sequence.

    Attributes:
        image_id (`str`):
            Provider-side identifier, also the cache filename.
        lat (`float`):
            Latitude in degrees.
        lon (`float`):
            Longitude in degrees.
        compass_angle (`float`):
            Heading the camera faced, in degrees clockwise from true north.
        captured_at (`str`):
            Capture month as `YYYY-MM`.
        is_pano (`bool`, *optional*, defaults to `True`):
            Whether this frame is a full 360-degree panorama.
    """

    image_id: str
    lat: float
    lon: float
    compass_angle: float
    captured_at: str
    is_pano: bool = True


@dataclass(frozen=True)
class Task:
    """One episode's location, frozen at index build time.

    Attributes:
        task_index (`int`):
            Position in the task list. Stable, and what `reset` selects on.
        task_id (`str`):
            Human-readable identifier, unique within the index.
        frames (`list[Frame]`):
            Ordered frames of the captured sequence, walkable with `move`.
        start_frame (`int`):
            Index into `frames` where the episode begins.
        country (`str`):
            ISO-3166 alpha-2 code of the true location. Ground truth — never
            placed in an observation before the guess.
        sequence_id (`str`):
            Provider-side sequence identifier.
        provider (`str`, *optional*, defaults to `"mapillary"`):
            Which backend can resolve this task's imagery.
        attribution (`dict`, *optional*):
            Creator credit, required by the CC-BY-SA licence on the imagery.
        meta (`dict`, *optional*):
            Anything else the builder recorded — camera make and model,
            quality score, checksums.
    """

    task_index: int
    task_id: str
    frames: list[Frame]
    start_frame: int
    country: str
    sequence_id: str
    provider: str = "mapillary"
    attribution: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def truth(self) -> tuple[float, float]:
        """Ground-truth `(lat, lon)` of the starting frame."""
        frame = self.frames[self.start_frame]
        return frame.lat, frame.lon


@runtime_checkable
class PanoramaBackend(Protocol):
    """Resolves tasks to imagery and answers what the agent may do."""

    @property
    def n_tasks(self) -> int:
        """Number of tasks in the frozen index."""
        ...

    @property
    def supports_look(self) -> bool:
        """Whether views can be rendered at arbitrary headings."""
        ...

    @property
    def supports_move(self) -> bool:
        """Whether the location can be walked along a sequence."""
        ...

    def task(self, task_index: int) -> Task:
        """Return the task at `task_index`."""
        ...

    def render_view(
        self,
        task: Task,
        frame_index: int,
        heading_deg: float,
        pitch_deg: float,
        fov_deg: float,
    ) -> Image.Image:
        """Render what the camera sees from one frame."""
        ...
