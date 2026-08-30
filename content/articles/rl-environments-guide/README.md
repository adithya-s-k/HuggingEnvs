---
title: "The ultimate guide to RL environments: building and scaling them in the LLM era"
short_description: "Building and scaling RL environments for LLM training"
emoji: 📝
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8080
header: mini
pinned: false
tags:
  - research-article-template
  - rl-environments
  - llm-training
  - reinforcement-learning
thumbnail: >-
  https://raw.githubusercontent.com/adithya-s-k/HuggingEnvs/refs/heads/main/assets/social/blog-thumbnail.png
---

# RL_environments

A research article built with [research-article-template](https://huggingface.co/spaces/tfrere/research-article-template).

## Quick start

```bash
cd app
npm run dev           # dev server at http://localhost:4321
```

## Deploy to Hugging Face

```bash
# 1. Create a Space at huggingface.co/new-space (select Docker SDK)
# 2. Push to it:
git remote add space git@hf.co:spaces/<your-username>/<your-space>
git push space main
```

That's it. The Dockerfile and nginx config are included.

## Edit your content

| File | What |
|------|------|
| `app/src/content/article.mdx` | Main article (metadata + chapter imports) |
| `app/src/content/chapters/` | Your chapters (one .mdx per section) |
| `app/src/content/bibliography.bib` | BibTeX references |
| `app/src/content/embeds/` | D3.js HTML visualizations |
| `app/src/content/assets/data/` | CSV/JSON data files |
| `app/src/content/assets/image/` | Images |

## Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server |
| `npm run build` | Production build |
| `npm run export:pdf` | Export as PDF |
| `npm run export:latex` | Export as LaTeX |
| `npm run sync:template` | Pull latest template updates |

## License

CC-BY-4.0
