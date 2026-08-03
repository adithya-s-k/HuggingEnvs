# AGENTS.md

This repo is a fixed-canvas React slide deck for research talks.

**The authoring rules live in [`CLAUDE.md`](./CLAUDE.md) — read that file first.**
It is not Claude-specific; it covers the slide anatomy, the theme tokens, the
layout conventions, how animation interacts with the PPTX/PDF export, and the
definition of done. Everything in it applies to any agent or human working here.

Quick orientation:

| Task | Where |
| --- | --- |
| Change the title, authors, venue, links, theme | `presentation.config.json` |
| Add or reorder slides | `src/slides/` + `src/slides/index.ts` |
| Reusable slide building blocks | `src/primitives/` |
| Deck shell, navigation, print mode, settings | `src/deck/` |
| Colour tokens / add a theme | `src/themes/index.ts` |
| Export to PPTX + PDF | `scripts/export-deck.mjs` |
| Social preview card | `scripts/make_og.py` |
| A complete real talk to copy patterns from | `examples/` |

```bash
npm run dev      # http://localhost:5173
npm run build    # tsc + vite build
npm run export   # PPTX + PDF -> export/
```

Before reporting a slide done: `npx tsc --noEmit` is clean, it renders in dark
**and** light, and the dev-only overflow guard shows no badge.
