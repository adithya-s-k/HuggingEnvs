"""Shared drawing helpers for the generated images (social card, banner).

Both cards read the *same* palette the deck uses, so nothing drifts: the theme
tokens are parsed out of src/themes/index.ts rather than duplicated here.

Requires Pillow and numpy (`pip install pillow numpy`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

# macOS system fonts, with fallbacks so this also runs on Linux CI.
SANS = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"
FALLBACKS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

GREYS = {
    "dark": {
        "white": "#ffffff",
        "text": "#f8fafd",
        "textMuted": "#d0d8e6",
        "textDim": "#97a1b5",
    },
    "light": {
        "white": "#0b1020",
        "text": "#161d2b",
        "textMuted": "#3d4657",
        "textDim": "#616c80",
    },
}


def load_config() -> dict:
    return json.loads((ROOT / "presentation.config.json").read_text())


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def palette(theme: str, mode: str) -> dict[str, tuple[int, int, int]]:
    """Pull one theme's tokens straight out of src/themes/index.ts.

    Parsing TS from Python isn't elegant, but it keeps ONE definition of the
    palette. If this breaks, the theme file changed shape — fix the regex rather
    than pasting colours in here.
    """
    src = (ROOT / "src" / "themes" / "index.ts").read_text()
    block = re.search(rf"\b{theme}:\s*{{(.*?)\n  }},\n", src, re.S)
    if not block:
        raise SystemExit(f"theme '{theme}' not found in src/themes/index.ts")
    mode_block = re.search(rf"\b{mode}:\s*{{(.*?)}},", block.group(1), re.S)
    if not mode_block:
        raise SystemExit(f"mode '{mode}' not found for theme '{theme}'")
    found = dict(re.findall(r'(\w+):\s*"(#[0-9a-fA-F]{6})"', mode_block.group(1)))
    return {k: hex_to_rgb(v) for k, v in {**GREYS[mode], **found}.items()}


def font(path: str, size: int, weight: str | None = None) -> ImageFont.FreeTypeFont:
    for candidate in (path, *FALLBACKS):
        try:
            f = ImageFont.truetype(candidate, size)
        except OSError:
            continue
        if weight:
            try:
                f.set_variation_by_name(weight)
            except Exception:
                pass  # static build of the font — default weight is fine
        return f
    raise SystemExit("no usable font found — install DejaVu or edit FALLBACKS")


def text_width(draw, s: str, f, tracking: float = 0.0) -> float:
    if not s:
        return 0.0
    return sum(draw.textlength(ch, font=f) + tracking for ch in s) - tracking


def draw_tracked(draw, xy, s: str, f, fill, tracking: float = 0.0) -> float:
    """PIL has no letter-spacing, so step through the string a glyph at a time."""
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + tracking
    return x


def draw_runs(draw, y: float, runs, size: tuple[int, int], tracking: float = 0.0, x: float | None = None):
    """Draw [(text, font, colour)] on one baseline; centred unless x is given."""
    W, _ = size
    total = sum(text_width(draw, s, f, tracking) for s, f, _ in runs)
    cursor = (W - total) / 2 if x is None else x
    for s, f, colour in runs:
        cursor = draw_tracked(draw, (cursor, y), s, f, colour, tracking)
    return cursor


def tile_field(img, P, size: tuple[int, int], cols: int = 22, rows: int = 11):
    """The faint 'structure' tiles from the title slide, scaled to any canvas."""
    W, H = size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    sx, sy = W / 1280, H / 720
    for r in range(rows):
        for c in range(cols):
            x, y = (40 + c * 56) * sx, (30 + r * 62) * sy
            w, h = 38 * sx, 30 * sy
            d.rounded_rectangle([x, y, x + w, y + h], radius=5, outline=P["border"] + (150,), width=1)
            d.rounded_rectangle([x, y, x + w, y + 5 * sy], radius=3, fill=P["accent"] + (110,))
    img.alpha_composite(layer)


def scrim(img, P, size: tuple[int, int], centre: float = 0.50, edge: float = 0.44):
    """Radial vignette over the tiles so the centre stays legible."""
    import numpy as np

    W, H = size
    ys, xs = np.mgrid[0:H, 0:W]
    t = np.sqrt(((xs - W / 2) / (W * 0.5)) ** 2 + ((ys - H / 2) / (H * 0.5)) ** 2)
    ramp = np.clip((t - 0.30) / 0.48, 0.0, 1.0)
    alpha = (centre + edge * ramp) * 255
    dark = Image.new("RGBA", (W, H), P["bg"] + (0,))
    dark.putalpha(Image.fromarray(alpha.astype("uint8"), "L"))
    img.alpha_composite(dark)


def glow(img, draw_fn, size: tuple[int, int], radius: int = 18, passes: int = 2):
    """Approximate the deck's text-shadow glow with a blurred copy underneath."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    for _ in range(passes):
        img.alpha_composite(blurred)


def save(img, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"wrote {out.relative_to(ROOT)}  ({out.stat().st_size // 1024} KB)")
