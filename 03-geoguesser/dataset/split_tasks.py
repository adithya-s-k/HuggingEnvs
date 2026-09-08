# SPDX-License-Identifier: BSD-3-Clause

"""Split one harvested pool into a frozen eval set and a training pool.

Splitting after harvesting is the safer order. If the two sets are harvested
separately you have to reason about contamination across two runs; if they come
from one pool you can enforce disjointness exactly once, here, and check it.

Two rules, both from the OSV-5M paper, which built its train/test split from the
same Mapillary source:

- no shared `sequence_id`
- no eval task within `--buffer-km` of any training task

The buffer matters because frames sit about 3.3 m apart. Holding out an image
while keeping its neighbour holds out nothing at all.

Eval is carved first and balanced by country, because at a couple of hundred
tasks balance decides what the number means. Training takes everything left over
that clears the buffer.

Usage:
    python dataset/split_tasks.py tasks/pool_v1.jsonl --eval 200
    python dataset/split_tasks.py tasks/pool_v1.jsonl --eval 200 --buffer-km 2
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import math
import pathlib

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("split_tasks")


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle distance in kilometres."""
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    d_phi, d_lambda = phi_b - phi_a, math.radians(lon_b - lon_a)
    h = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * 6371.0088 * math.asin(math.sqrt(min(1.0, h)))


def start_point(task: dict) -> tuple[float, float]:
    """The coordinate a task is scored against."""
    frame = task["frames"][task["start_frame"]]
    return frame["lat"], frame["lon"]


def renumber(tasks: list[dict], prefix: str) -> list[dict]:
    """Rewrite indices so the backend's contiguity requirement holds."""
    out = []
    for index, task in enumerate(tasks):
        task = dict(task)
        task["task_index"] = index
        task["task_id"] = f"{prefix}-{index:05d}"
        out.append(task)
    return out


def split(args: argparse.Namespace) -> None:
    """Carve the eval set, then hand the remainder to training."""
    pool = [
        json.loads(line) for line in args.pool.read_text().splitlines() if line.strip()
    ]
    logger.info("pool holds %d tasks", len(pool))

    # Eval first, balanced by country. Ordering is by completeness before
    # quality: a task missing frames is unusable in a set whose whole purpose is
    # to run with the network off, and no quality score compensates for that.
    def eval_rank(task: dict) -> tuple[int, float]:
        complete = 1 if task["meta"].get("offline_ready") else 0
        return (-complete, -(task["meta"].get("quality_score") or 0.0))

    incomplete = sum(1 for t in pool if not t["meta"].get("offline_ready"))
    if incomplete:
        logger.info(
            "%d pool tasks are not fully mirrored; they sort last for eval "
            "(run dataset/verify_offline.py to repair)",
            incomplete,
        )
    by_quality = sorted(pool, key=eval_rank)
    per_country: collections.Counter = collections.Counter()
    eval_tasks: list[dict] = []
    for task in by_quality:
        if len(eval_tasks) >= args.eval:
            break
        country = task["country"]
        if per_country[country] >= args.eval_per_country:
            continue
        per_country[country] += 1
        eval_tasks.append(task)

    eval_sequences = {t["sequence_id"] for t in eval_tasks}
    eval_points = [start_point(t) for t in eval_tasks]

    train_tasks: list[dict] = []
    dropped_sequence = 0
    dropped_buffer = 0
    for task in pool:
        if task["sequence_id"] in eval_sequences:
            dropped_sequence += 1
            continue
        lat, lon = start_point(task)
        if any(
            haversine_km(lat, lon, e_lat, e_lon) < args.buffer_km
            for e_lat, e_lon in eval_points
        ):
            dropped_buffer += 1
            continue
        train_tasks.append(task)

    eval_out = args.out_dir / args.eval_name
    train_out = args.out_dir / args.train_name
    for path, tasks, prefix in (
        (eval_out, eval_tasks, "eval"),
        (train_out, train_tasks, "train"),
    ):
        with path.open("w") as handle:
            for task in renumber(tasks, prefix):
                handle.write(json.dumps(task) + "\n")

    # Verify rather than assert in a comment.
    train_sequences = {t["sequence_id"] for t in train_tasks}
    overlap = eval_sequences & train_sequences
    closest = min(
        (
            haversine_km(*start_point(t), *point)
            for t in train_tasks
            for point in eval_points
        ),
        default=float("inf"),
    )

    countries_eval = collections.Counter(t["country"] for t in eval_tasks)
    logger.info(
        "\neval  %4d tasks -> %s  (%d countries, max %d per country)",
        len(eval_tasks),
        eval_out.name,
        len(countries_eval),
        max(countries_eval.values()) if countries_eval else 0,
    )
    logger.info(
        "train %4d tasks -> %s  (dropped %d on shared sequence, %d on the %.1f km buffer)",
        len(train_tasks),
        train_out.name,
        dropped_sequence,
        dropped_buffer,
        args.buffer_km,
    )
    logger.info(
        "\ncontamination check: %d shared sequences, closest train task is %.2f km "
        "from an eval task",
        len(overlap),
        closest,
    )
    if overlap or closest < args.buffer_km:
        raise SystemExit("split failed its own contamination check")
    mirrored = sum(1 for t in eval_tasks if t["meta"].get("offline_ready"))
    logger.info(
        "eval tasks fully mirrored for offline use: %d/%d", mirrored, len(eval_tasks)
    )
    if mirrored < len(eval_tasks):
        raise SystemExit(
            f"{len(eval_tasks) - mirrored} eval tasks are not fully mirrored. "
            "A frozen eval set must run offline; repair with "
            "dataset/verify_offline.py or lower --eval."
        )


def main() -> None:
    """Command-line entry point."""
    root = pathlib.Path(__file__).resolve().parents[1] / "env"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pool", type=pathlib.Path)
    parser.add_argument("--eval", type=int, default=200)
    parser.add_argument("--eval-per-country", type=int, default=4)
    parser.add_argument("--buffer-km", type=float, default=1.0)
    parser.add_argument("--eval-name", default="eval_pano_v3.jsonl")
    parser.add_argument("--train-name", default="train_pano_v3.jsonl")
    parser.add_argument("--out-dir", type=pathlib.Path, default=root / "tasks")
    split(parser.parse_args())


if __name__ == "__main__":
    main()
