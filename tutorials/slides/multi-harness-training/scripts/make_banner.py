#!/usr/bin/env python3
"""Render a wide banner image -> .github/banner.png (2400x760).

Defaults to your talk (from presentation.config.json), so a fork gets a banner
for its own deck:

    npm run banner

Override anything for a project/repo banner:

    python3 scripts/make_banner.py \
        --title research-presentation-template \
        --tagline "Research talks as code." \
        --mono-title --out .github/banner.png
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from _card import (
    MONO,
    ROOT,
    SANS,
    draw_runs,
    draw_tracked,
    font,
    glow,
    load_config,
    palette,
    save,
    scrim,
    text_width,
    tile_field,
)

W, H = 2400, 760  # ~3.16:1 — reads well at README width, crisp on retina


def mini_slides(img, P, x: int, y: int, w: int, h: int, n: int = 3, step: int = 74):
    """A small stack of 16:9 frames — says 'slide deck' faster than any words."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in reversed(range(n)):
        ox, oy = x + i * step, y + i * (step // 2)
        fade = 1 - i * 0.28
        d.rounded_rectangle(
            [ox, oy, ox + w, oy + h],
            radius=16,
            fill=P["bgRaised"] + (int(255 * fade),),
            outline=P["border"] + (int(230 * fade),),
            width=2,
        )
        # a title bar and two text lines, so the frames read as slides
        d.rounded_rectangle(
            [ox + 26, oy + 26, ox + 26 + int(w * 0.42), oy + 40],
            radius=6,
            fill=P["accent"] + (int(210 * fade),),
        )
        for k, frac in enumerate((0.62, 0.48)):
            ly = oy + 68 + k * 26
            d.rounded_rectangle(
                [ox + 26, ly, ox + 26 + int(w * frac), ly + 10],
                radius=5,
                fill=P["textDim"] + (int(150 * fade),),
            )
        d.rounded_rectangle(
            [ox + 26, oy + h - 44, ox + 26 + 54, oy + h - 34],
            radius=5,
            fill=P["accent2"] + (int(220 * fade),),
        )
    img.alpha_composite(layer)


def main():
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default=None)
    # Only inherit the config's accent when the title also comes from the config —
    # otherwise an overridden --title gets the old accent word glued onto it.
    ap.add_argument("--accent", default=None, help="trailing part of the title, in the accent colour")
    ap.add_argument("--tagline", default=cfg.get("subtitle", ""))
    ap.add_argument("--eyebrow", default=cfg.get("venue", ""))
    ap.add_argument("--theme", default=cfg.get("theme", "forge"))
    ap.add_argument("--mode", default=cfg.get("defaultMode", "dark"))
    ap.add_argument("--mono-title", action="store_true", help="set the title in mono (right for a repo name)")
    ap.add_argument("--out", default=".github/banner.png")
    args = ap.parse_args()
    if args.title is None:
        args.title, args.accent = cfg["title"], args.accent or cfg.get("titleAccent") or ""
    args.accent = args.accent or ""

    P = palette(args.theme, args.mode)
    size = (W, H)

    img = Image.new("RGBA", size, P["bg"] + (255,))
    tile_field(img, P, size, cols=30, rows=9)
    scrim(img, P, size, centre=0.58, edge=0.38)

    # frames on the right, text on the left
    mini_slides(img, P, x=1540, y=196, w=560, h=316)

    d = ImageDraw.Draw(img)
    LEFT = 150

    head = args.title
    if args.accent and head.endswith(args.accent):
        head = head[: -len(args.accent)]

    # Shrink the title until it clears the frames on the right — a long repo name
    # must not run under them.
    MAX_TITLE_W = 1330
    face = MONO if args.mono_title else SANS
    weight = "Bold" if args.mono_title else "Heavy"
    probe = ImageDraw.Draw(img)
    title_size = 96 if args.mono_title else 118
    while title_size > 42:
        f_try = font(face, title_size, weight)
        if text_width(probe, args.title, f_try, -2) <= MAX_TITLE_W:
            break
        title_size -= 4
    f_title = font(face, title_size, weight)
    f_eyebrow = font(MONO, 26, "Bold")
    f_tag = font(SANS, 40, "Medium")
    f_foot = font(MONO, 26, "Regular")

    y = 214
    if args.eyebrow:
        draw_tracked(d, (LEFT, 148), args.eyebrow.upper(), f_eyebrow, P["accent"], 8)
    else:
        y = 236

    runs = [(head, f_title, P["white"])]
    if args.accent:
        runs.append((args.accent, f_title, P["accent2"]))
        glow(
            img,
            lambda dd: draw_runs(
                dd, y, [(head, f_title, (0, 0, 0, 0)), (args.accent, f_title, P["accent2"])], size, -2, x=LEFT
            ),
            size,
        )
        d = ImageDraw.Draw(img)
    draw_runs(d, y, runs, size, -2, x=LEFT)

    if args.tagline:
        draw_runs(d, y + title_size + 44, [(args.tagline, f_tag, P["textMuted"])], size, 0, x=LEFT)

    foot = "npm run dev  ·  npm run export → pptx + pdf"
    draw_tracked(d, (LEFT, H - 150), foot, f_foot, P["textDim"], 1)
    d.rectangle([LEFT, H - 96, LEFT + 300, H - 93], fill=P["accent2"] + (110,))

    save(img, ROOT / args.out)


if __name__ == "__main__":
    main()
