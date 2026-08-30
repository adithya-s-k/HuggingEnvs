#!/usr/bin/env python3
"""Render the deck's social-preview card -> public/og.png (1200x630).

The card mirrors the title slide (src/slides/00_Title.tsx): the tile field, the
forge palette from src/theme.ts, and the same eyebrow / title / subtitle / byline.
Regenerate after changing the talk title:

    python3 scripts/make_og.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "public" / "og.png"
W, H = 1200, 630

# src/theme.ts — dark palette
BG = (7, 9, 15)
BORDER = (40, 49, 73)
WHITE = (255, 255, 255)
TEXT_MUTED = (208, 216, 230)
TEXT_DIM = (151, 161, 181)
LAVENDER = (176, 107, 255)
EMERALD = (16, 240, 164)

SFNS = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"
FALLBACK = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(path: str, size: int, weight: str | None = None) -> ImageFont.FreeTypeFont:
    try:
        f = ImageFont.truetype(path, size)
        if weight:
            try:
                f.set_variation_by_name(weight)
            except Exception:
                pass  # non-variable build of the font — the default weight is fine
        return f
    except OSError:
        return ImageFont.truetype(FALLBACK, size)


def text_width(draw, s, f, tracking=0.0):
    return sum(draw.textlength(ch, font=f) + tracking for ch in s) - (tracking if s else 0)


def draw_tracked(draw, xy, s, f, fill, tracking=0.0):
    """PIL has no letter-spacing, so step through the string one glyph at a time."""
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + tracking
    return x


def draw_runs(draw, y, runs, tracking=0.0, center=True, x_start=0):
    """Draw [(text, font, color)] on one baseline; returns the run bounding boxes."""
    total = sum(text_width(draw, s, f, tracking) for s, f, _ in runs)
    x = (W - total) / 2 if center else x_start
    boxes = []
    for s, f, color in runs:
        x0 = x
        x = draw_tracked(draw, (x, y), s, f, color, tracking)
        boxes.append((x0, x))
    return boxes


def tile_field(img):
    """The accreting 'environment tiles' backdrop, scaled from the 1280x720 stage."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cols, rows, cell_w, cell_h = 22, 11, 56, 62
    sx, sy = W / 1280, H / 720
    for r in range(rows):
        for c in range(cols):
            x = (40 + c * cell_w) * sx
            y = (30 + r * cell_h) * sy
            w, h = 38 * sx, 30 * sy
            d.rounded_rectangle([x, y, x + w, y + h], radius=5, outline=BORDER + (150,), width=1)
            d.rounded_rectangle([x, y, x + w, y + 5 * sy], radius=3, fill=LAVENDER + (110,))
    img.alpha_composite(layer)


def scrim(img):
    """Radial vignette over the tiles: 50% bg at the centre, 94% at the edges —
    the same ramp the title slide uses, so the tiles read as texture, not content."""
    import numpy as np

    ys, xs = np.mgrid[0:H, 0:W]
    # normalised elliptical distance from centre (1.0 at the ellipse the slide fades to)
    t = np.sqrt(((xs - W / 2) / (W * 0.5)) ** 2 + ((ys - H / 2) / (H * 0.5)) ** 2)
    ramp = np.clip((t - 0.30) / 0.48, 0.0, 1.0)  # 0 in the middle, 1 by the edges
    alpha = (0.50 + 0.44 * ramp) * 255

    dark = Image.new("RGBA", (W, H), BG + (0,))
    dark.putalpha(Image.fromarray(alpha.astype("uint8"), "L"))
    img.alpha_composite(dark)


def glow(img, draw_fn, radius=18, passes=2):
    """Approximate the deck's text-shadow glow with a blurred copy underneath."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    for _ in range(passes):
        img.alpha_composite(blurred)


def main():
    img = Image.new("RGBA", (W, H), BG + (255,))
    tile_field(img)
    scrim(img)
    d = ImageDraw.Draw(img)

    f_eyebrow = font(MONO, 20, "Bold")
    f_title = font(SFNS, 92, "Heavy")
    f_sub = font(SFNS, 34, "Medium")
    f_by = font(MONO, 23, "Regular")

    eyebrow = "AMD AI DEV DAY · HUGGING FACE"
    ey_w = text_width(d, eyebrow, f_eyebrow, 6)
    draw_tracked(d, ((W - ey_w) / 2, 118), eyebrow, f_eyebrow, LAVENDER, 6)

    title = [("Scaling RL ", f_title, WHITE), ("for LLMs", f_title, EMERALD)]
    glow(img, lambda dd: draw_runs(dd, 186, [("Scaling RL ", f_title, (0, 0, 0, 0)), ("for LLMs", f_title, EMERALD)], -2))
    d = ImageDraw.Draw(img)
    draw_runs(d, 186, title, -2)

    sub = [
        ("RL Environments", f_sub, LAVENDER),
        ("  ·  ", f_sub, TEXT_DIM),
        ("RL Training", f_sub, LAVENDER),
    ]
    draw_runs(d, 330, sub)

    byline = "Adithya S Kolavi  ·  @AdithyaSK"
    by_w = text_width(d, byline, f_by, 1)
    draw_tracked(d, ((W - by_w) / 2, 452), byline, f_by, TEXT_DIM, 1)

    # emerald hairline under the byline, echoing the deck's progress bar
    d.rectangle([W / 2 - 150, 512, W / 2 + 150, 514], fill=EMERALD + (90,))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
