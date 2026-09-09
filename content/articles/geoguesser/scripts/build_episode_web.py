#!/usr/bin/env python3
"""Slim one rendered rollout down to web weight for the article's step-through.

`03-geoguesser/video/render_rollout.py` renders an episode at video fidelity:
every intermediate frame of every pan, plus a second wide canvas. That is 16 MB
for a ten-turn episode, which is not something to put in an article. This keeps
the same verified frames, subsamples each pan to a handful, re-encodes small,
and writes a compact `episode.json` the embed can drive itself from.

    python scripts/build_episode_web.py <rendered-dir> --out app/public/episode
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


def pick(frames: list[str], keep: int) -> list[str]:
    """Evenly subsample a pan, always keeping the first and last frame."""
    if len(frames) <= keep:
        return frames
    idx = [round(i * (len(frames) - 1) / (keep - 1)) for i in range(keep)]
    return [frames[i] for i in sorted(set(idx))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path, help="a render_rollout.py output directory")
    ap.add_argument("--out", type=Path, default=Path("app/public/episode"))
    ap.add_argument("--keep", type=int, default=7, help="frames kept per pan")
    ap.add_argument("--width", type=int, default=440)
    ap.add_argument("--quality", type=int, default=52)
    args = ap.parse_args()

    timeline = json.loads((args.src / "timeline.json").read_text())
    out = args.out / args.src.name
    if out.exists():
        shutil.rmtree(out)
    (out / "frames").mkdir(parents=True)

    written: dict[str, str] = {}

    sizes: dict[str, tuple[int, int]] = {}

    def convert(rel: str) -> str:
        if rel in written:
            return written[rel]
        img = Image.open(args.src / rel)
        if img.width > args.width:
            h = round(img.height * args.width / img.width)
            img = img.resize((args.width, h), Image.LANCZOS)
        name = f"frames/{len(written):03d}.jpg"
        img.convert("RGB").save(out / name, "JPEG", quality=args.quality, optimize=True)
        written[rel] = name
        sizes[name] = img.size
        return name

    segments = []
    for seg in timeline["segments"]:
        frames = [convert(f) for f in pick(seg["frames"], args.keep)]
        w, h = sizes[frames[0]]
        segments.append(
            {
                "turn": seg["turn"],
                "kind": seg.get("kind"),
                "imageKind": seg.get("imageKind"),
                "verb": seg.get("verb"),
                "label": seg.get("label"),
                "toolCall": seg.get("toolCall"),
                "caption": seg.get("caption"),
                "feedback": seg.get("feedback"),
                "note": seg.get("note") or None,
                "pins": seg.get("pins") or [],
                "minimap": convert(seg["minimap"]) if seg.get("minimap") else None,
                "hud": seg.get("hud"),
                "frames": frames,
                # Written here rather than measured in the browser, so the
                # frame takes the right shape before the image decodes.
                "aspect": round(w / h, 3),
            }
        )

    payload = {
        "episode": timeline["episode"],
        "outcome": timeline["outcome"],
        "segments": segments,
    }
    (out / "episode.json").write_text(json.dumps(payload, indent=1))

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"{len(written)} images, {total / 1024:.0f} KiB in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
