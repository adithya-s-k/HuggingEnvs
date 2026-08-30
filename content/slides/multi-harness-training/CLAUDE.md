# CLAUDE.md — authoring this deck

You are helping build a **research talk**. This repo is a fixed-canvas React
deck: every slide is a component authored against a 1280×720 stage that scales
to any projector. Read this before writing a slide.

`AGENTS.md` points here; both files describe the same rules.

## The three things people get wrong

1. **Too much on one slide.** A slide is one idea. If it needs a paragraph, it's
   two slides. The `OverflowGuard` will scream (red badge, dev only) when
   content spills past the canvas — that's a design signal, not a bug to
   suppress by shrinking type.
2. **Type too small.** Body text ≥ 22px, bullets ~34px, slide titles ~46px, big
   claims 54–92px. The canvas is 1280 wide, so 22px here reads like 14pt in
   PowerPoint — from the back of a lecture hall that's already the floor.
3. **Editing the wrong file.** Title, authors, venue, links, theme, social card:
   all in `presentation.config.json`. Never hard-code them in a slide.

## Where things live

```
presentation.config.json   the only file to edit per talk
src/config.ts              typed view of it
src/themes/index.ts        THEMES — token sets (dark + light per theme)
src/ThemeContext.tsx       useTheme() -> { T, glow, mode, name }
src/deck/                  Deck, SlideShell, PrintMode, Settings, Backdrop, OverflowGuard
src/primitives/            Panel Chip Bullet Accent Stat Figure Quote Rise Stagger CodeBlock
src/slides/                one file per slide + index.ts (the deck order)
scripts/export-deck.mjs    PPTX + PDF capture
scripts/make_og.py         social card
examples/                  a real, complete talk you can run and copy from
```

## Adding a slide

1. Create `src/slides/NN_Name.tsx` exporting one component.
2. Add one line to the `slides` array in `src/slides/index.ts`.
3. Section numbers derive themselves — never hard-code a kicker number. Set
   `bare: true` for title / divider / closing slides so they don't consume one.

A content slide is always `SlideShell` + absolutely-positioned content:

```tsx
import { SlideShell } from "../deck/SlideShell";
import { Bullet, Rise, Stagger } from "../primitives";

export function MethodSlide() {
  return (
    <SlideShell kicker="Method" title="What we actually did">
      <Stagger style={{ position: "absolute", top: 210, left: 96, right: 96, display: "flex", flexDirection: "column", gap: 22 }}>
        <Rise><Bullet>First thing</Bullet></Rise>
        <Rise><Bullet>Second thing</Bullet></Rise>
      </Stagger>
    </SlideShell>
  );
}
```

Layout conventions: content starts at `top: 200–250`, side margins `left/right: 96`,
`SlideShell` owns the header and the page number. Use `Stagger` + `Rise` for
entrances rather than hand-written `initial`/`animate` on every element.

## Colour rules

Use theme tokens — **never a raw hex in a slide**. A slide with `#10f0a4` in it
breaks every other theme and light mode.

- `T.bg` / `T.bgRaised` — surfaces
- `T.white` — titles and max-contrast text; `T.text` body; `T.textMuted`
  secondary; `T.textDim` labels, captions, chrome
- `T.accent` — structure and chrome (progress bar, dividers, kicker numbers)
- `T.accent2` — in-text emphasis, "the verified thing". `<Accent>` defaults here.
- `glow.accent` / `glow.accent2` for box-shadows, `glow.*Text` for text-shadow.
  Glow is off by default in body text on purpose; light mode returns `"none"`
  for text glows, which is why you must go through `glow` rather than inventing
  shadows.

Every theme ships a dark **and** light palette, so slide code never branches on
mode. If you find yourself writing `mode === "dark" ? … : …` inside a slide, the
token set is missing something — add it to `Palette` instead.

## Animation, and how it interacts with export

`spring` from `primitives` is the house transition. Entrances only — nothing
should still be moving while the speaker talks about it.

Both exports capture a **still frame** per slide:

- Entrance animations are waited out, so they land at their final state.
- **Continuously animating** figures (a live simulation, a loop) have no final
  state. Give the slide id a longer dwell in the `DWELL` map in
  `scripts/export-deck.mjs` so it's captured on a representative frame.
- `PrintMode` (browser "Save as PDF") forces final states with a zero-duration
  `MotionConfig` + `reducedMotion="always"`.

Two traps worth knowing, both already handled — don't undo them:

- Playwright's element screenshot is a **viewport clip**, not an element render,
  so anything overlaying the stage lands in the frame. Deck UI is tagged
  `data-chrome` and hidden during capture. Tag any new overlay the same way.
- framer-motion springs are rAF-driven and never report `finished` to
  `document.getAnimations()`, which is why the export waits on a settle
  predicate **and** a fixed floor.

## Commands

```bash
npm run dev        # http://localhost:5173
npm run build      # tsc + vite build -> dist/
npm run export     # PPTX + PDF -> export/   (also wired to the drawer buttons in dev)
npm run og         # regenerate public/og.png from the config
```

Keys: `←/→` navigate, `t` theme, `f` fullscreen, `p` print/PDF, `Esc` close drawer.

## Definition of done

Before saying a slide is finished:

1. `npx tsc --noEmit` clean.
2. It renders in **both** modes (press `t`) and in at least one other theme.
3. No `OverflowGuard` badge in dev.
4. No raw hex, no hard-coded title/author, no hard-coded section number.
