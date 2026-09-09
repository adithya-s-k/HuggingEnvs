# SPDX-License-Identifier: BSD-3-Clause

"""Assemble tasks from a harvested sequence pool.

`harvest_tiles.py` enumerates panorama sequences worldwide; this turns a
selection of them into playable tasks. The two steps are separate because
harvesting is fast and assembly is not: a task costs about 27 Graph API
requests, so you harvest once and sample from the pool as often as you like.

Balance is enforced before assembly, not after. Panorama coverage clusters
hard — sixteen sequences from one hit are usually one contributor's drive — so
candidates are capped per country *and* per creator using the anchor
coordinates the pool already carries, before a single frame is fetched. Doing it
the other way round cost 14.4 s per accepted task instead of 3.

Offline mode: `--mirror all` downloads every frame, so the finished dataset
needs no network at rollout time at all. Rough sizes at 2,500 tasks:

    --mirror start                ~0.7 GB    guessing only
    --mirror all                   ~16 GB    look and move offline
    --mirror all --originals       ~20 GB    plus sharp zoom at the start frame

Measured over 964 cached files: mean 0.26 MB per 2048x1024 derivative (median
0.24, p90 0.34) and 1.8 MB per full-resolution original.

The run is resumable. Tasks are appended to the index as they complete, and a
restart with the same --out picks up where it stopped, skipping every sequence
already used. A 2,500-task build costs ~68,000 Graph API requests; losing that
to a dropped connection at task 2,400 is not acceptable.

Usage:
    export MAPILLARY_API_KEY_TRAIN="MLY|..."
    python dataset/build_tasks.py --tasks 2500 --mirror all --workers 8
    python dataset/build_tasks.py --tasks 50 --mirror start   # quick trial
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import functools
import hashlib
import json
import logging
import pathlib
import random
import shutil
import sys
import threading
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "env"))

from build_pano_tasks import (  # noqa: E402
    _get,
    _month,
    _token,
    frame_detail,
    sequence_frames,
    TIMEOUT_S,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("build_tasks")


@functools.lru_cache(maxsize=1)
def _country_paths():
    """Country name and outline for each admin-0 polygon."""
    from matplotlib.path import Path as MplPath

    root = pathlib.Path(__file__).resolve().parents[1] / "env"
    features = json.loads(
        (root / "data" / "geo" / "ne_110m_admin_0_countries.geojson").read_text()
    )["features"]
    out = []
    for feature in features:
        geometry = feature["geometry"]
        rings = (
            [geometry["coordinates"][0]]
            if geometry["type"] == "Polygon"
            else [poly[0] for poly in geometry["coordinates"]]
        )
        for ring in rings:
            out.append((feature["properties"]["ADMIN"], MplPath(ring)))
    return out


def country_of(lat: float, lon: float) -> str | None:
    """Country containing a coordinate, or `None` over water."""
    for name, path in _country_paths():
        if path.contains_point((lon, lat)):
            return name
    return None


def choose_candidates(
    pool: list[dict],
    wanted: int,
    per_country: int,
    per_creator: int,
    density_exponent: float,
    seed: int,
    already: list[dict] | None = None,
) -> list[dict]:
    """
    Order the pool so the first N candidates are worth assembling.

    Applies the sampling weight from the OSV-5M paper: proportional to local
    image density raised to `density_exponent`, negative by default, which sits
    between density-proportional sampling (biased to cities) and
    area-proportional sampling (biased to large countries). Then caps per
    country and per creator, which matters as much: without a creator cap a
    "global" set can be a few hundred drives.

    Args:
        pool (`list[dict]`):
            Harvested sequences with `lat`, `lon`, `creator_id`.
        wanted (`int`):
            How many candidates to return, before assembly losses.
        per_country (`int`):
            Maximum tasks per country.
        per_creator (`int`):
            Maximum tasks per contributor.
        density_exponent (`float`):
            Exponent on local density; `-0.75` follows OSV-5M.
        seed (`int`):
            Seed for the weighted draw.
        already (`list[dict]`, *optional*):
            Tasks a resumed run already holds. Their countries and creators
            count against the caps, so resuming cannot exceed a limit that a
            single run would have respected.

    Returns:
        `list[dict]`: Candidates in the order they should be assembled.
    """
    rng = random.Random(seed)
    cells = collections.Counter((round(row["lat"]), round(row["lon"])) for row in pool)
    weighted = []
    for row in pool:
        cell = (round(row["lat"]), round(row["lon"]))
        weight = cells[cell] ** density_exponent
        # One exponential draw per item, ordered ascending, is a weighted
        # sample without replacement.
        weighted.append((rng.expovariate(1.0) / max(weight, 1e-9), row))
    weighted.sort(key=lambda pair: pair[0])

    country_count: collections.Counter = collections.Counter(
        task["country"] for task in already or []
    )
    creator_count: collections.Counter = collections.Counter(
        task["attribution"]["creator_id"] for task in already or []
    )
    chosen: list[dict] = []
    unknown = 0
    for _, row in weighted:
        if len(chosen) >= wanted:
            break
        country = country_of(row["lat"], row["lon"])
        if country is None:
            unknown += 1
            continue
        creator = str(row.get("creator_id") or "")
        if country_count[country] >= per_country:
            continue
        if creator and creator_count[creator] >= per_creator:
            continue
        country_count[country] += 1
        creator_count[creator] += 1
        row["__country"] = country
        chosen.append(row)
    logger.info(
        "selected %d candidates across %d countries and %d creators "
        "(%d anchors fell over water)",
        len(chosen),
        len(country_count),
        len(creator_count),
        unknown,
    )
    return chosen


def mirror(
    token: str,
    image_ids: list[str],
    cache: pathlib.Path,
    workers: int,
    originals: bool = False,
) -> dict[str, str]:
    """Download and hash frames concurrently; returns sha256 by image id."""

    def one(image_id: str) -> tuple[str, str | None]:
        path = cache / f"{image_id}.jpg"
        if not path.exists():
            fields = "thumb_2048_url"
            meta = _get(token, image_id, fields=fields)
            url = meta.get(fields) if "__error" not in meta else None
            if not url:
                return image_id, None
            try:
                with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
                    path.write_bytes(response.read())
            except Exception as exc:  # noqa: BLE001
                logger.warning("  %s: %r", image_id, exc)
                return image_id, None
        return image_id, hashlib.sha256(path.read_bytes()).hexdigest()

    checksums: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for image_id, digest in pool.map(one, image_ids):
            if digest:
                checksums[image_id] = digest

    if originals and image_ids:
        # Only the starting frame gets its full-resolution original: zoom needs
        # it, and every frame would be 3.3 MB each.
        first = image_ids[0]
        path = cache / f"{first}.orig.jpg"
        if not path.exists():
            meta = _get(token, first, fields="thumb_original_url")
            url = meta.get("thumb_original_url") if "__error" not in meta else None
            if url:
                try:
                    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
                        path.write_bytes(response.read())
                except Exception as exc:  # noqa: BLE001
                    logger.warning("  original for %s: %r", first, exc)
    return checksums


def assemble(token: str, candidate: dict, args: argparse.Namespace) -> dict | None:
    """Turn one candidate sequence into a task, or `None` if it does not qualify."""
    sequence_id = candidate["sequence_id"]
    ids = sequence_frames(token, sequence_id)
    if len(ids) < args.min_frames:
        return None
    anchor_id = str(candidate.get("image_id") or "")
    position = ids.index(anchor_id) if anchor_id in ids else len(ids) // 2
    low = max(0, position - args.frames // 2)
    window = ids[low : low + args.frames]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.frame_workers) as pool:
        details = list(pool.map(lambda i: frame_detail(token, i), window))

    frames = []
    for detail in details:
        if not detail or not detail.get("is_pano"):
            continue
        geometry = detail.get("computed_geometry") or detail.get("geometry")
        if not geometry:
            continue
        lon, lat = geometry["coordinates"]
        captured = _month(detail.get("captured_at"))
        if captured and captured[:4] < "2010":
            continue  # a zero captured_at renders as 1980 and breaks temporal splits
        frames.append(
            {
                "image_id": str(detail["id"]),
                "lat": lat,
                "lon": lon,
                "compass_angle": detail.get("computed_compass_angle")
                or detail.get("compass_angle")
                or 0.0,
                "captured_at": captured,
                "is_pano": True,
            }
        )
    if len(frames) < args.min_frames:
        return None

    start = min(len(frames) // 2, len(frames) - 1)
    start_frame = frames[start]
    anchor_detail = next(
        (d for d in details if d and str(d["id"]) == start_frame["image_id"]), {}
    )

    if args.mirror == "all":
        wanted = [start_frame["image_id"]] + [
            f["image_id"] for f in frames if f["image_id"] != start_frame["image_id"]
        ]
    else:
        wanted = [start_frame["image_id"]]
    checksums = mirror(
        token, wanted, args.cache, args.frame_workers, originals=args.originals
    )
    if start_frame["image_id"] not in checksums:
        return None

    creator = anchor_detail.get("creator", {}) or {}
    return {
        "country": candidate["__country"],
        "sequence_id": sequence_id,
        "provider": "mapillary",
        "start_frame": start,
        "frames": frames,
        "attribution": {
            "creator_username": creator.get("username", ""),
            "creator_id": creator.get("id", "") or candidate.get("creator_id", ""),
            "licence": "CC-BY-SA-4.0",
            "source": "Mapillary",
        },
        "meta": {
            "camera_make": anchor_detail.get("make", ""),
            "camera_model": anchor_detail.get("model", ""),
            "quality_score": anchor_detail.get("quality_score")
            or candidate.get("quality_score"),
            "pool_tile": candidate.get("tile", ""),
            "sha256": checksums,
            "mirrored_frames": len(checksums),
            "offline_ready": len(checksums) >= len(frames),
        },
    }


MEAN_FRAME_BYTES = 0.26e6
"""Mean size of a 2048x1024 derivative, measured over 964 cached files."""

MEAN_ORIGINAL_BYTES = 1.8e6
"""Mean size of a full-resolution original, measured over 29 cached files."""


def resume(out: pathlib.Path) -> list[dict]:
    """
    Return the tasks already written to an index, ignoring a torn last line.

    A run killed mid-write can leave a partial JSON object at the end of the
    file. That line is dropped rather than raising, because the alternative is
    discarding a complete 40-minute build over one truncated task.
    """
    if not out.exists():
        return []
    tasks = []
    for number, line in enumerate(out.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            tasks.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("dropping torn line %d of %s", number, out)
    for index, task in enumerate(tasks):
        task["task_index"] = index
        task["task_id"] = f"mly-{index:05d}"
    return tasks


def task_bytes(task: dict, cache: pathlib.Path) -> int:
    """Bytes this task added to the cache, counted from its own frames only."""
    total = 0
    for frame in task["frames"]:
        for name in (f"{frame['image_id']}.jpg", f"{frame['image_id']}.orig.jpg"):
            path = cache / name
            if path.exists():
                total += path.stat().st_size
    return total


def check_disk(cache: pathlib.Path, remaining: int, args) -> None:
    """
    Refuse to start a mirror that cannot fit, before spending any API quota.

    Raises:
        SystemExit: When projected growth exceeds free space minus a 10 GB
            headroom margin.
    """
    per_task = MEAN_FRAME_BYTES * (args.frames if args.mirror == "all" else 1)
    if args.originals:
        per_task += MEAN_ORIGINAL_BYTES
    projected = per_task * remaining
    free = shutil.disk_usage(cache).free
    logger.info(
        "mirror '%s' projects %.1f GB for %d tasks; %.1f GB free on %s",
        args.mirror,
        projected / 1e9,
        remaining,
        free / 1e9,
        cache,
    )
    if projected + 10e9 > free:
        raise SystemExit(
            f"not enough space: need ~{projected / 1e9:.0f} GB plus 10 GB "
            f"headroom, have {free / 1e9:.0f} GB free. Use --mirror start, "
            f"lower --frames, or point --cache at a larger volume."
        )


def build(args: argparse.Namespace) -> None:
    """Select, assemble and write the task index."""
    token = _token()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    pool = [
        json.loads(line) for line in args.pool.read_text().splitlines() if line.strip()
    ]
    logger.info("pool holds %d panorama sequences", len(pool))

    done_tasks = resume(args.out)
    if done_tasks:
        logger.info(
            "resuming: %d tasks already in %s, need %d more",
            len(done_tasks),
            args.out,
            max(0, args.tasks - len(done_tasks)),
        )
        used = {t["sequence_id"] for t in done_tasks}
        pool = [entry for entry in pool if entry["sequence_id"] not in used]

    remaining = args.tasks - len(done_tasks)
    if remaining <= 0:
        logger.info("%s already holds %d tasks; nothing to do", args.out, args.tasks)
        return
    check_disk(args.cache, remaining, args)

    # Over-select: some candidates lose their sequence listing, fall short on
    # frames, or fail to mirror.
    candidates = choose_candidates(
        pool,
        int(remaining * args.oversample),
        args.per_country,
        args.per_creator,
        args.density_exponent,
        args.seed,
        already=done_tasks,
    )

    results: list[dict] = list(done_tasks)
    lock = threading.Lock()
    stats = {"tried": 0, "failed": 0, "mirrored": 0, "bytes": 0}
    handle = args.out.open("a")

    def work(candidate):
        with lock:
            if len(results) >= args.tasks:
                return None
        task = assemble(token, candidate, args)
        with lock:
            stats["tried"] += 1
            if task is None:
                stats["failed"] += 1
                return None
            if len(results) >= args.tasks:
                return None
            task["task_index"] = len(results)
            task["task_id"] = f"mly-{len(results):05d}"
            results.append(task)
            stats["mirrored"] += task["meta"]["mirrored_frames"]
            stats["bytes"] += task_bytes(task, args.cache)
            # Append-and-flush so a killed run loses at most one task.
            handle.write(json.dumps(task) + "\n")
            handle.flush()
        return task

    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )

    progress = Progress(
        TextColumn("[cyan]assembling tasks"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn(
            "rejected={task.fields[failed]} · images={task.fields[mirrored]} · "
            "{task.fields[gb]:.2f} GB"
        ),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )
    with progress:
        task_id = progress.add_task(
            "tasks",
            total=args.tasks,
            completed=len(results),
            failed=0,
            mirrored=0,
            gb=0.0,
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool_x:
            for _ in pool_x.map(work, candidates):
                done = len(results)
                progress.update(
                    task_id,
                    completed=min(done, args.tasks),
                    failed=stats["failed"],
                    mirrored=stats["mirrored"],
                    gb=stats["bytes"] / 1e9,
                )
                if done >= args.tasks:
                    break
    handle.close()

    results.sort(key=lambda t: t["task_index"])
    args.out.write_text("".join(json.dumps(task) + "\n" for task in results))

    countries = collections.Counter(t["country"] for t in results)
    creators = {t["attribution"]["creator_id"] for t in results}
    offline = sum(1 for t in results if t["meta"]["offline_ready"])
    logger.info(
        "\nwrote %d tasks to %s (%.0f KB)",
        len(results),
        args.out,
        args.out.stat().st_size / 1024,
    )
    logger.info(
        "countries %d · creators %d · fully offline %d/%d · candidates rejected %d",
        len(countries),
        len(creators),
        offline,
        len(results),
        stats["failed"],
    )
    logger.info(
        "cache now %.2f GB",
        sum(p.stat().st_size for p in args.cache.glob("*.jpg")) / 1e9,
    )
    logger.info("next: python dataset/split_tasks.py %s --eval 200", args.out)


def main() -> None:
    """Command-line entry point."""
    root = pathlib.Path(__file__).resolve().parents[1] / "env"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=2500)
    parser.add_argument("--per-country", type=int, default=60)
    parser.add_argument("--per-creator", type=int, default=25)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--min-frames", type=int, default=8)
    parser.add_argument("--mirror", choices=["start", "all"], default="all")
    parser.add_argument(
        "--originals",
        action="store_true",
        help="Also mirror the start frame's 7680px original, so zoom works offline.",
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="Tasks assembled at once."
    )
    parser.add_argument(
        "--frame-workers", type=int, default=6, help="Fetches within a task."
    )
    parser.add_argument("--oversample", type=float, default=2.0)
    parser.add_argument("--density-exponent", type=float, default=-0.75)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--pool", type=pathlib.Path, default=root / "data" / "pool" / "sequences.jsonl"
    )
    parser.add_argument(
        "--out", type=pathlib.Path, default=root / "tasks" / "pool_v1.jsonl"
    )
    parser.add_argument("--cache", type=pathlib.Path, default=root / "data" / "panos")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
