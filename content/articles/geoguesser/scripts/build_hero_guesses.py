#!/usr/bin/env python3
"""Where the untrained model guessed, and where the trained one guessed.

One record per eval task: the true location, the base model's guess and the
final checkpoint's guess, taken from the same pass so the pairing is real. This
is the article's whole result as 200 pairs of coordinates.

    python scripts/build_hero_guesses.py ../../../03-geoguesser/results/raw/passk-run1-full
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def collect(root: Path, model: str, sample: int) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for f in sorted(glob.glob(str(root / "pass-*" / "shard-*" / "episodes.jsonl"))):
        for line in open(f):
            try:
                ep = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ep.get("model_name") != model:
                continue
            task, o = ep.get("task") or {}, ep.get("outcome") or {}
            if task.get("sample") != sample or not o.get("guess"):
                continue
            out.setdefault(
                int(task["index"]),
                {
                    "guess": [round(c, 3) for c in o["guess"]],
                    "truth": [round(c, 3) for c in o["truth"]],
                    "km": round(o["distance_km"], 1),
                },
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="a pass@k run directory")
    ap.add_argument("--base", default="base")
    ap.add_argument("--trained", default="ckpt1000")
    ap.add_argument("--sample", type=int, default=0, help="which pass to take")
    ap.add_argument(
        "--out", type=Path, default=Path("app/src/content/assets/data/hero-guesses.json")
    )
    args = ap.parse_args()

    base = collect(args.root, args.base, args.sample)
    trained = collect(args.root, args.trained, args.sample)
    shared = sorted(set(base) & set(trained))

    rows = [
        {
            "i": i,
            "truth": base[i]["truth"],
            "from": base[i]["guess"],
            "to": trained[i]["guess"],
            "km_from": base[i]["km"],
            "km_to": trained[i]["km"],
        }
        for i in shared
    ]

    med = lambda key: sorted(r[key] for r in rows)[len(rows) // 2]  # noqa: E731
    payload = {
        "tasks": rows,
        "median_from": med("km_from"),
        "median_to": med("km_to"),
    }
    args.out.write_text(json.dumps(payload))
    print(
        f"{len(rows)} paired tasks, median {payload['median_from']:.0f} km -> "
        f"{payload['median_to']:.0f} km ({args.out.stat().st_size / 1024:.0f} KiB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
