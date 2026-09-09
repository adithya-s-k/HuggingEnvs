# SPDX-License-Identifier: BSD-3-Clause

"""Check that a task index is fully mirrored, and top up whatever is missing.

An interrupted build leaves tasks whose start frame is cached but whose later
frames are not, so the episode is playable but `move` walks into a hole. The
`offline_ready` flag in the index records what was true at build time, which
stops being true the moment a build is interrupted or a frame is deleted, so
this checks the filesystem instead of trusting the flag -- and rewrites the flag
to match what it found.

Run it before syncing to a bucket. `GEOGUESSER_ALLOW_FETCH=0` turns a missing
frame into a hard error at rollout time, which is the point, but it is a much
better error to hit here.

Usage:
    python ../dataset/verify_offline.py tasks/pool_offline_5k.jsonl
    python ../dataset/verify_offline.py tasks/pool_offline_5k.jsonl --check
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import logging
import pathlib
import sys
import threading
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "env"))

from build_pano_tasks import _get, _token, TIMEOUT_S  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify_offline")


def missing_frames(tasks: list[dict], cache: pathlib.Path) -> dict[int, list[str]]:
    """
    Map task index to the image ids absent from the cache.

    Args:
        tasks (`list[dict]`):
            Parsed task index.
        cache (`pathlib.Path`):
            Directory holding `<image_id>.jpg`.

    Returns:
        `dict[int, list[str]]`: Only tasks with at least one absent frame.
    """
    gaps: dict[int, list[str]] = {}
    for task in tasks:
        absent = [
            frame["image_id"]
            for frame in task["frames"]
            if not (cache / f"{frame['image_id']}.jpg").exists()
        ]
        if absent:
            gaps[task["task_index"]] = absent
    return gaps


def fetch_one(token: str, image_id: str, cache: pathlib.Path) -> bool:
    """Download one frame into the cache. Returns whether it landed."""
    path = cache / f"{image_id}.jpg"
    if path.exists():
        return True
    field = "thumb_2048_url"
    meta = _get(token, image_id, fields=field)
    url = meta.get(field) if "__error" not in meta else None
    if not url:
        return False
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            payload = response.read()
    except Exception as exc:  # noqa: BLE001
        logger.warning("  %s: %r", image_id, exc)
        return False
    # Write via a temporary name so an interrupted download cannot leave a
    # truncated JPEG that later looks like a cache hit.
    tmp = path.with_suffix(".partial")
    tmp.write_bytes(payload)
    tmp.replace(path)
    return True


def repair(
    tasks: list[dict], gaps: dict[int, list[str]], cache: pathlib.Path, workers: int
) -> set[str]:
    """Fetch every absent frame concurrently. Returns the ids still missing."""
    wanted = sorted({image_id for ids in gaps.values() for image_id in ids})
    token = _token()
    still: set[str] = set()
    lock = threading.Lock()
    done = 0

    def one(image_id: str) -> None:
        nonlocal done
        ok = fetch_one(token, image_id, cache)
        with lock:
            done += 1
            if not ok:
                still.add(image_id)
            if done % 25 == 0 or done == len(wanted):
                logger.info("  %d/%d fetched", done, len(wanted))

    logger.info("fetching %d missing frames with %d workers", len(wanted), workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, wanted))
    return still


def main() -> None:
    """Command-line entry point."""
    root = pathlib.Path(__file__).resolve().parents[1] / "env"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=pathlib.Path)
    parser.add_argument("--cache", type=pathlib.Path, default=root / "data" / "panos")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report only; never fetch and never rewrite the index.",
    )
    args = parser.parse_args()

    tasks = [
        json.loads(line) for line in args.index.read_text().splitlines() if line.strip()
    ]
    total_frames = sum(len(t["frames"]) for t in tasks)
    gaps = missing_frames(tasks, args.cache)
    absent = sum(len(v) for v in gaps.values())
    logger.info(
        "%d tasks · %d frames · %d tasks incomplete · %d frames absent",
        len(tasks),
        total_frames,
        len(gaps),
        absent,
    )

    starts = [
        t["task_index"]
        for t in tasks
        if not (
            args.cache / f"{t['frames'][t['start_frame']]['image_id']}.jpg"
        ).exists()
    ]
    if starts:
        logger.warning(
            "%d tasks are missing their START frame and cannot be played "
            "offline at all: %s",
            len(starts),
            starts[:10],
        )

    if not gaps:
        logger.info("index is fully mirrored")
        return

    if args.check:
        for index, ids in sorted(gaps.items())[:20]:
            logger.info("  task %5d: %d absent", index, len(ids))
        raise SystemExit(f"{absent} frames absent from {args.cache}")

    still = repair(tasks, gaps, args.cache, args.workers)

    # Rewrite offline_ready from what is actually on disk, so downstream
    # consumers -- the eval split especially -- can trust the flag.
    remaining = missing_frames(tasks, args.cache)
    changed = 0
    for task in tasks:
        ready = task["task_index"] not in remaining
        if task["meta"].get("offline_ready") != ready:
            task["meta"]["offline_ready"] = ready
            changed += 1
    args.index.write_text("".join(json.dumps(t) + "\n" for t in tasks))

    ready_now = sum(1 for t in tasks if t["meta"]["offline_ready"])
    logger.info(
        "\nrepaired: %d frames still absent · %d tasks still incomplete",
        sum(len(v) for v in remaining.values()),
        len(remaining),
    )
    logger.info(
        "offline_ready %d/%d (%d flags corrected)", ready_now, len(tasks), changed
    )
    if still:
        by_task = collections.Counter(
            task["task_index"]
            for task in tasks
            for frame in task["frames"]
            if frame["image_id"] in still
        )
        logger.warning(
            "unfetchable frames belong to tasks %s -- these are usually images "
            "deleted upstream; exclude them from eval",
            sorted(by_task)[:10],
        )


if __name__ == "__main__":
    main()
