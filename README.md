<div align="center">

<img src="./assets/banner.png" alt="HuggingEnvs — open environments for training agents" width="100%">

# HuggingEnvs

**Open source RL environments for training agents — built, deployed, and trained end to end.**

[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hub-HuggingEnvs-yellow)](https://huggingface.co/HuggingEnvs)
[![Guide](https://img.shields.io/badge/Read-The%20Guide-blue)](https://huggingface.co/spaces/AdithyaSK/rl-environments-guide)
[![Slides](https://img.shields.io/badge/Watch-The%20Talk-green)](https://huggingface.co/spaces/AdithyaSK/rl-environments-101-slides)
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey)](./LICENSE)

**[🤗 huggingface.co/HuggingEnvs](https://huggingface.co/HuggingEnvs)** — the environments, datasets, models and demos live on the Hub. Everything reproducible lives here.

</div>

---

## What this is

RL has moved from games to language agents, and the bottleneck moved with it. The algorithm is no
longer the hard part — the **environment** is: the sandbox that hands an agent a task, lets it act,
and returns a reward.

This repo is a working answer to what that takes. Not a survey. Every environment here runs, every
rollout here has been executed, and every training curve here came from a job you can launch yourself.

## How it's split

| | |
|---|---|
| **This repo** | Environment source, rollout scripts, training configs, notebooks, article and slide sources — everything you'd want to read, run, fork, or reproduce. |
| **[🤗 HuggingEnvs](https://huggingface.co/HuggingEnvs)** | The artifacts those produce — deployed environment Spaces, task datasets, trained models, dashboards, and the published articles and decks. |

Each project below names the Hub repos it owns, and each Hub card links back to the exact folder here.

## Projects

Each numbered folder is a self-contained project: its own README, its own environments, its own
results. They read in order but stand alone.

<!-- BEGIN:projects -->
| # | Project | What you get | Status |
|---|---|---|---|
| **00** | **[RL Environments 101](./00-environments-101/)** | Three environments, six frameworks, side by side. | ✅ stable |
| **01** | **[LaTeX OCR](./01-latex-ocr/)** | Train Qwen3-VL-2B to read math images into LaTeX, with a verifiable reward. | 📓 notebook |
<!-- END:projects -->

## Start here

**Just want to understand environments?** → [The guide](https://huggingface.co/spaces/AdithyaSK/rl-environments-guide) (source in [`content/articles/`](./content/articles/)), then [project 00's README](./00-environments-101/).

**Want to run one?**

```bash
git clone https://github.com/adithya-s-k/HuggingEnvs
cd HuggingEnvs
cp .env.example .env          # HF_TOKEN, and E2B_API_KEY for sandbox-backed envs

cd 00-environments-101/envs/wordle/verifiers
uv sync && uv run python rollout.py
```

Wordle is pure Python with no external backend — the fastest way to see a full rollout.

**Want to train against one?** No GPU or cluster needed — one command spins up a GPU with the
notebooks loaded:

```bash
curl -sSL https://raw.githubusercontent.com/adithya-s-k/HuggingEnvs/main/tools/jupyter_launch.py | python3 -
```

<sub>Windows (PowerShell): `irm https://raw.githubusercontent.com/adithya-s-k/HuggingEnvs/main/tools/jupyter_launch.py | python -`. Set `FLAVOR=t4-small` for a cheaper GPU. Track jobs at [huggingface.co/settings/jobs](https://huggingface.co/settings/jobs).</sub>

## Build your own — agent skills

Five [SKILL.md](https://github.com/anthropics/skills)-spec agent skills that turn a plain-English
description into a runnable environment across four frameworks. They work in **any** project, not
just this one, with Claude Code, Cursor, Codex, OpenCode, Gemini CLI and others.

```bash
npx skills add adithya-s-k/HuggingEnvs
```

| Skill | What it builds |
|---|---|
| `rl-env-from-description` | Orchestrator — interviews you, then ports across all four frameworks |
| `generate-openenv-env` | OpenEnv (Hugging Face) — HTTP + MCP |
| `generate-ors-env` | OpenReward (ORS) — per-tool-call rewards |
| `generate-verifiers-env` | Verifiers (Prime Intellect) — in-process + rubrics |
| `generate-nemo-gym-env` | NeMo Gym (NVIDIA) — HTTP + post-episode `/verify` |

## Repository layout

```
HuggingEnvs/
├── 00-environments-101/     3 envs × 6 frameworks
├── 01-latex-ocr/            train a VLM against a served reward
├── content/                 articles, slides, talk material
│   ├── articles/            research-article sources (Astro → Docker Space)
│   └── slides/              decks (Vite → static Space)
├── tools/                   launcher, deploy, index generation
├── assets/                  brand + shared images
└── .claude/skills/          the five agent skills
```

Inside a project, the folders always mean the same thing: `envs/` (implementations,
with shared logic in `core/`), `train/` (configs + launch), `notebooks/`, `results/`.

## Contributing

New environments, new framework ports, and reproductions that disagree with ours are all welcome.
See [CONTRIBUTING.md](./CONTRIBUTING.md) — the fastest path is the `rl-env-from-description` skill.

## License

[Apache 2.0](./LICENSE)
