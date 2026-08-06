# Slides

Two decks live here, one folder each. They are independent projects — separate
`package.json`, `node_modules`, themes and exports — so install and run whichever
one you're presenting.

| Deck | Folder | Talk |
| --- | --- | --- |
| **RL Environments 101** | [`rl-environments-101/`](rl-environments-101/) | "From 'What Is an Env?' to Training Your Own" — the full conference talk: RL fundamentals → env anatomy → OpenEnv → training with TRL. |
| **RL Environments 101 (AMD)** | [`rl-environments-101-amd/`](rl-environments-101-amd/) | The AMD cut of the same talk — forked from the deck above, edited for that audience. Exports as `RL-Environments-101-AMD.{pptx,pdf}`. |
| **Multi-Harness Training** | [`multi-harness-training/`](multi-harness-training/) | "OpenEnv × Harbor" — why an env's failure model decides whether it can be trained against: in-process agent loops vs. an HTTP boundary, and what it takes to capture trainable tokens. |

## Run one

```bash
cd tutorials/slides/rl-environments-101     # or multi-harness-training
npm install
npm run dev                                 # http://localhost:5173
```

Both decks bind port 5173, so run one at a time (or pass `--port` to the second).

Shared conventions across both: React components on a fixed **1280×720** canvas
that scales to any projector, dark/light themes, arrow-key navigation, and
`npm run export` for PPTX + PDF. Each deck's own README has the details.

## Controls

| Key | Action |
| --- | --- |
| `→` / `Space` / `PgDn` | Next slide |
| `←` / `PgUp` | Previous slide |
| `t` | Toggle dark / light |
| `f` | Fullscreen |
