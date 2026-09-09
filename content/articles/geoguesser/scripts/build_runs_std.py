#!/usr/bin/env python3
"""Per-step within-group reward spread for each run, from the Trackio database.

GRPO divides the advantage by the group's own standard deviation, so this one
series decides how hard each step pushes. Run 1 saw one task per step and its
spread collapsed; run 2 saw two and it never did. Both facts are in here.

    python scripts/build_runs_std.py geoguesser.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

RUNS = {
    "run1-4b": {"label": "run 1", "tasks_per_step": 1, "gain": 0.1620},
    "run2-4b": {"label": "run 2", "tasks_per_step": 2, "gain": 0.0326},
    "run3-4b": {"label": "run 3", "tasks_per_step": 2, "gain": 0.0717},
}
KEYS = ("train/reward_std", "train/grad_norm", "train/frac_reward_zero_std")


def series(db: sqlite3.Connection, run: str) -> list[dict]:
    rows: dict[int, dict] = {}
    for step, blob in db.execute(
        "select step, metrics from metrics where run_name=?", (run,)
    ):
        rows.setdefault(step, {}).update(json.loads(blob))
    to_global = {s: d["train/global_step"] for s, d in rows.items() if "train/global_step" in d}

    out = []
    for step in sorted(rows):
        d = rows[step]
        if "train/reward_std" not in d:
            continue
        gs = to_global.get(step, to_global.get(step + 1))
        if gs is None:
            continue
        out.append(
            {
                "step": int(gs),
                "std": round(d["train/reward_std"], 4),
                "grad": round(d.get("train/grad_norm", 0.0), 3),
                "zero": round(d.get("train/frac_reward_zero_std", 0.0), 3),
            }
        )
    out.sort(key=lambda p: p["step"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("db", type=Path)
    ap.add_argument(
        "--out", type=Path, default=Path("app/src/content/assets/data/runs-std.json")
    )
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    runs = []
    for name, meta in RUNS.items():
        pts = series(db, name)
        if not pts:
            print(f"skip {name}: nothing logged")
            continue
        stds = [p["std"] for p in pts]
        runs.append(
            {
                "run": name,
                **meta,
                "points": pts,
                "median_std": round(sorted(stds)[len(stds) // 2], 4),
                "min_std": min(stds),
                "max_grad": max(p["grad"] for p in pts),
                "max_zero": max(p["zero"] for p in pts),
            }
        )

    args.out.write_text(json.dumps({"runs": runs}))
    for r in runs:
        print(
            f"{r['label']}: {len(r['points'])} steps, median std {r['median_std']}, "
            f"min {r['min_std']}, max grad {r['max_grad']}, max zero-std {r['max_zero']}"
        )
    print(f"-> {args.out} ({args.out.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
