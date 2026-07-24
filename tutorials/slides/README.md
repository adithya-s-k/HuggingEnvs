# Slides — RL Environments 101

Talk slides for **"RL Environments 101: From 'What Is an Env?' to Training Your Own"**
by Adithya S Kolavi.

A self-contained **React** deck. Each slide is its own component. Dark/light
theme, arrow-key navigation, fully static → deployable to a Hugging Face Space.

## Run locally

```bash
cd tutorials/slides
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

## Deploy to Hugging Face Spaces

Static build → static Space (added in a later step):

```bash
npm run build      # → dist/
```
