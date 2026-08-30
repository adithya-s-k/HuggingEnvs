#!/usr/bin/env python3
"""Render the social-preview card -> public/og.png (1200x630).

Reads presentation.config.json and the active theme's tokens, so the card
matches the title slide without maintaining a second copy of the design.
Regenerate after editing the config:

    npm run og
"""

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

W, H = 1200, 630


def main():
    cfg = load_config()
    P = palette(cfg.get("theme", "forge"), cfg.get("defaultMode", "dark"))
    size = (W, H)

    title = cfg["title"]
    accent_part = cfg.get("titleAccent") or ""
    head = title[: -len(accent_part)] if accent_part and title.endswith(accent_part) else title

    img = Image.new("RGBA", size, P["bg"] + (255,))
    tile_field(img, P, size)
    scrim(img, P, size)
    d = ImageDraw.Draw(img)

    f_eyebrow = font(MONO, 20, "Bold")
    f_title = font(SANS, 92, "Heavy")
    f_sub = font(SANS, 32, "Medium")
    f_by = font(MONO, 23, "Regular")

    if cfg.get("venue"):
        eyebrow = cfg["venue"].upper()
        w = text_width(d, eyebrow, f_eyebrow, 6)
        draw_tracked(d, ((W - w) / 2, 118), eyebrow, f_eyebrow, P["accent"], 6)

    runs = [(head, f_title, P["white"])]
    if accent_part:
        runs.append((accent_part, f_title, P["accent2"]))
        glow(
            img,
            lambda dd: draw_runs(
                dd, 186, [(head, f_title, (0, 0, 0, 0)), (accent_part, f_title, P["accent2"])], size, -2
            ),
            size,
        )
        d = ImageDraw.Draw(img)
    draw_runs(d, 186, runs, size, -2)

    if cfg.get("subtitle"):
        draw_runs(d, 330, [(cfg["subtitle"], f_sub, P["textMuted"])], size)

    byline = "  ·  ".join(filter(None, [", ".join(cfg["authors"]), cfg.get("handle", "")]))
    w = text_width(d, byline, f_by, 1)
    draw_tracked(d, ((W - w) / 2, 452), byline, f_by, P["textDim"], 1)

    d.rectangle([W / 2 - 150, 512, W / 2 + 150, 514], fill=P["accent2"] + (90,))

    save(img, ROOT / "public" / "og.png")


if __name__ == "__main__":
    main()
