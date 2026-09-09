#!/usr/bin/env python3
"""Render one small preview per eval task, for the banner's hover card.

Each thumbnail is the view the agent gets on its first observation: the
starting frame of the sequence, reprojected at the frame's own compass
heading. Needs the panorama bucket synced locally; see 03-geoguesser/README.md.

    python scripts/build_task_thumbs.py --env ../../../03-geoguesser/env
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", type=Path, required=True, help="03-geoguesser/env checkout")
    ap.add_argument("--tasks", default="tasks/eval_pano_v3.jsonl")
    ap.add_argument("--out", type=Path, default=Path("app/public/thumbs"))
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--height", type=int, default=200)
    ap.add_argument("--fov", type=float, default=90.0)
    ap.add_argument("--quality", type=int, default=58)
    args = ap.parse_args()

    sys.path.insert(0, str(args.env.resolve()))
    from server.render.pano import look

    tasks = [json.loads(l) for l in (args.env / args.tasks).open() if l.strip()]
    args.out.mkdir(parents=True, exist_ok=True)

    total = 0
    for i, task in enumerate(tasks):
        frame = task["frames"][task.get("start_frame", 0)]
        src = args.env / "data" / "panos" / f"{frame['image_id']}.jpg"
        if not src.exists():
            print(f"skip {i}: {src.name} not synced", file=sys.stderr)
            continue
        view = look(
            Image.open(src),
            heading_deg=float(frame.get("compass_angle") or 0.0),
            fov_deg=args.fov,
            size=(args.width, args.height),
        )
        dst = args.out / f"{i}.jpg"
        view.save(dst, "JPEG", quality=args.quality, optimize=True)
        total += dst.stat().st_size

    print(f"{len(tasks)} tasks, {total / 1024:.0f} KiB in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
