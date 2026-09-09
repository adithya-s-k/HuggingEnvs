#!/usr/bin/env python3
"""Extract paired episodes for the rollout comparison figure.

One example is two episodes on the same task, normally the untrained base
model against a trained checkpoint. Pulled straight from the pass@k records so
the figure cannot drift from them: the action sequence, the pins in the order
they were dropped, and the outcome.

    python scripts/build_rollout_compare.py results/raw/passk-run1-full \
        --example "18:base=13535,ckpt1000=505" \
        --example "100:base=16995,ckpt1000=22"
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

PIN_ACTIONS = {"place_pin", "guess", "submit_guess"}


def find(root: Path, index: int, model: str, distance: float, tol: float = 40.0) -> dict:
    for f in sorted(glob.glob(str(root / "pass-*" / "shard-*" / "episodes.jsonl"))):
        for line in open(f):
            try:
                ep = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "turns" not in ep or ep.get("model_name") != model:
                continue
            if ep["task"].get("index") != index:
                continue
            if abs((ep["outcome"].get("distance_km") or 0) - distance) <= tol:
                return ep
    raise SystemExit(f"no {model} episode on task {index} near {distance} km")


def summarise(ep: dict) -> dict:
    turns, pins = [], []
    for t in ep["turns"]:
        action = t.get("action") or {}
        kind = action.get("action")
        if kind == "reset":
            continue
        if kind in PIN_ACTIONS and "lat" in action:
            pins.append(
                {
                    "lat": action["lat"],
                    "lon": action["lon"],
                    "final": kind != "place_pin",
                    "turn": t["turn"],
                }
            )
        turns.append(
            {
                "turn": t["turn"],
                "kind": kind or "unparseable",
                # The pin index this turn produced, so the animation can light
                # up a marker on exactly the turn that dropped it.
                "pin": len(pins) - 1 if kind in PIN_ACTIONS and "lat" in action else None,
                "status": t.get("status"),
                "reply": ((t.get("model") or {}).get("reply") or "").strip()[:180] or None,
            }
        )
    o = ep["outcome"]
    return {
        "model": ep["model_name"],
        "turns": turns,
        "pins": pins,
        "tokens": o.get("tokens_out") or 0,
        "distance_km": round(o["distance_km"], 1),
        "reward": round(o["reward"], 4),
        "guess": [round(c, 4) for c in o["guess"]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="a pass@k run directory")
    ap.add_argument(
        "--example",
        action="append",
        required=True,
        help='"<index>:<model>=<km>,<model>=<km>", repeatable',
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("app/src/content/assets/data/rollout-compare.json"),
    )
    args = ap.parse_args()

    examples = []
    for spec in args.example:
        index, arms_spec = spec.split(":", 1)
        arms, task, truth = [], None, None
        for arm in arms_spec.split(","):
            model, km = arm.split("=")
            ep = find(args.root, int(index), model.strip(), float(km))
            task, truth = ep["task"], ep["outcome"]["truth"]
            arms.append(summarise(ep))
        examples.append(
            {
                "task": {
                    "index": int(index),
                    "country": task.get("country"),
                    # Truth is on the outcome, not the task spec: the task the
                    # agent sees withholds it.
                    "truth": [round(c, 4) for c in truth],
                },
                "arms": arms,
            }
        )

    args.out.write_text(json.dumps({"examples": examples}, indent=1))
    print(f"{len(examples)} examples -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
