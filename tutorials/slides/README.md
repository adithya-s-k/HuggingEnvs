# Slides

Three decks live here, one folder each. They are independent projects — separate
`package.json`, `node_modules`, themes and exports — so install and run whichever
one you're presenting.

> 📚 **All decks on the Hub:** [Talks / Slides collection](https://huggingface.co/collections/AdithyaSK/talks-slides-6a7454392540983bfc2414f4)

## The decks

| Deck | Folder | Live | Talk |
| --- | --- | --- | --- |
| **Scaling RL for LLMs** | [`rl-environments-101-amd/`](rl-environments-101-amd/) | [▶️ Space](https://huggingface.co/spaces/AdithyaSK/scaling-rl-for-llms-amd-ai-dev-day) · [direct](https://adithyask-scaling-rl-for-llms-amd-ai-dev-day.static.hf.space) | "RL Environments and RL Training" — the 20-minute cut for **[AMD AI Dev Day](https://amd.indiadevday.com/)**. Forked from the deck below and edited down. |
| **RL Environments 101** | [`rl-environments-101/`](rl-environments-101/) | [▶️ Space](https://huggingface.co/spaces/AdithyaSK/rl-environments-101-slides) · [direct](https://adithyask-rl-environments-101-slides.static.hf.space) | "From 'What Is an Env?' to Training Your Own" — the original 30-minute talk: RL fundamentals → env anatomy → OpenEnv → training with TRL. |
| **Multi-Harness Training** | [`multi-harness-training/`](multi-harness-training/) | — | "OpenEnv × Harbor" — why an env's failure model decides whether it can be trained against: in-process agent loops vs. an HTTP boundary, and what it takes to capture trainable tokens. |

## Run one

```bash
cd tutorials/slides/rl-environments-101-amd     # or any other deck folder
npm install
npm run dev                                     # http://localhost:5173
```

All three decks bind port 5173, so run one at a time (or pass `--port` to the second).

Shared conventions: React components on a fixed **1280×720** canvas that scales to
any projector, dark/light themes, arrow-key navigation, and `npm run export` for
PPTX + PDF. Each deck's own README has the details.

## Controls

| Key | Action |
| --- | --- |
| `→` / `Space` / `PgDn` | Next slide |
| `←` / `PgUp` | Previous slide |
| `t` | Toggle dark / light |
| `f` | Fullscreen |

## Deploying a deck to a Space

The Spaces above are **static** SDK — the Vite build is uploaded to the repo root.

```bash
cd tutorials/slides/<deck>
npm run build                                   # → dist/
hf upload <user>/<space-name> dist . --repo-type space
```

The Space needs a `README.md` at its root with `sdk: static` and
`app_file: index.html` frontmatter; it is not part of `dist/`, so keep it in the
Space repo rather than regenerating it on each upload.
