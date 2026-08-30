# Slides — RL Environments 101

Talk slides for **"RL Environments 101: From 'What Is an Env?' to Training Your Own"**
by Adithya S Kolavi.

> ▶️ **Live deck:** https://huggingface.co/spaces/AdithyaSK/rl-environments-101-slides
> ([direct link](https://adithyask-rl-environments-101-slides.static.hf.space)) — arrow keys / clicker / swipe to navigate.

A self-contained **React** deck. Each slide is its own component. Dark/light
theme, arrow-key navigation, fully static → deployable to a Hugging Face Space.

## Run locally

```bash
cd content/slides/rl-environments-101
npm install
npm run dev        # http://localhost:5173
```

## Controls

| Key                     | Action                |
| ----------------------- | --------------------- |
| `→` / `Space` / `PgDn`  | Next slide            |
| `←` / `PgUp`            | Previous slide        |
| `Home` / `End`          | First / last slide    |
| `t`                     | Toggle dark / light   |
| `f`                     | Fullscreen            |

On-screen controls (bottom-right) mirror these: prev, next, theme toggle, and a
slide counter. A progress bar runs along the top.

## Adding / editing slides

1. Create `src/slides/NN_Name.tsx` exporting a component.
2. Register it in `src/slides/index.ts` — the deck order, counts, nav, and
   progress bar all derive from that array.

Use the shared building blocks so every slide stays on-theme:

- `SlideShell` — kicker + big title + footer chrome (for content slides).
- `Stagger` / `Rise` — staggered enter animations.
- `Panel`, `Chip`, `Bullet`, `Accent` — themed primitives.
- `useTheme()` — the resolved palette `T` + `glow` for the current mode.

**House style:** less text, huge fonts, one idea per slide, lean on animation.
Slides are authored against a fixed **1280×720** canvas (`STAGE_W`/`STAGE_H`)
that scales to fit any screen, so layout is identical on any projector.

## Theme

The "forge" palette (near-black bg · lavender · emerald) is ported from
`hf-motion/src/AdithyaSK`. See `src/theme.ts` for dark + light values.

## `reference/` (git-ignored)

Scratch space for source material cloned locally (the article Space, framework
repos). Not committed. Currently holds the
[rl-environments-guide](https://huggingface.co/spaces/AdithyaSK/rl-environments-guide)
article the talk draws from.

## Export to PPTX / PDF

```bash
npm run export                          # -> export/RL-Environments-101.{pptx,pdf}
npm run export -- --theme light         # light deck
npm run export -- --scale 1.5           # 1920×1080 frames (~half the file size)
npm run export -- --pdf-only            # or --pptx-only
```

`scripts/export-deck.mjs` serves `dist/`, drives the real deck in headless
Chromium through the `window.__DECK__` hook, waits for each slide's entrance
animation to finish, and screenshots the `[data-stage]` element at 2× (2560×1440).
The frames become a 16:9 PPTX (one full-bleed image per slide, slide title as a
speaker note) and a same-size PDF. Frames are kept in `export/slides/`.

**Slides export as images, not editable shapes** — the deck is React +
framer-motion, so there is nothing to map onto PowerPoint text boxes. What you
get opens anywhere and projects identically.

Slides with continuous motion (CartPole, the D3 embeds, the repo2rlenv reveal)
have no final state, so they get a longer dwell in the `DWELL` map at the top of
the script and are captured on a representative frame. Adjust the numbers there
if a frame lands somewhere unflattering. Requires `npx playwright install chromium`
once; the deck's own chrome (progress bar, arrows, gear) is tagged `data-chrome`
and hidden during capture.

## Deploy to Hugging Face Spaces

Static build → static Space (added in a later step):

```bash
npm run build      # → dist/
```
