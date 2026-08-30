# 01 · LaTeX OCR

**Train Qwen3-VL-2B to read math images into LaTeX — with a reward served by a real environment.**

[![Hub](https://img.shields.io/badge/%F0%9F%A4%97%20Hub-HuggingEnvs-yellow)](https://huggingface.co/HuggingEnvs)
[![Env](https://img.shields.io/badge/Space-latex--ocr--env-blue)](https://huggingface.co/spaces/AdithyaSK/latex-ocr-env)

Project 00 shows you what an environment *is*. This one takes a single environment all the way to a
trained model: a verifiable reward, a GRPO run, and a curve that goes up.

The task is deliberately clean. A model sees a rendered image of a mathematical expression and must
emit the LaTeX that produced it. Correctness is checkable — render the prediction, compare — so the
reward is honest and there's very little room for the model to game it. That makes it the right first
training run: when the curve moves, you know why.

## Status

📓 **Notebook-first.** The full run lives in
[`notebooks/01_latex_ocr_grpo.ipynb`](./notebooks/01_latex_ocr_grpo.ipynb) and is reproducible today.
Extracting the environment into `envs/latex_ocr/` and the training config into `train/` is the next
step for this project — the folders will appear as that lands.

## Run it

No GPU, no cluster, no local setup. One command spins up a GPU with the notebook loaded and prints a
JupyterLab URL:

```bash
curl -sSL https://raw.githubusercontent.com/adithya-s-k/HuggingEnvs/main/tools/jupyter_launch.py | python3 -
```

<sub>Windows (PowerShell): `irm https://raw.githubusercontent.com/adithya-s-k/HuggingEnvs/main/tools/jupyter_launch.py | python -`. A GPU menu appears — Enter takes the A100 default; `FLAVOR=t4-small` picks a cheaper one (`hf jobs hardware` lists them all). Track and stop jobs at [huggingface.co/settings/jobs](https://huggingface.co/settings/jobs).</sub>

You need a free [Hugging Face token](https://huggingface.co/settings/tokens) (read scope is enough)
and `pip install -U huggingface_hub`, then `hf auth login`.

**Your work persists.** The notebooks are the JupyterLab root and live on a personal HF storage
bucket (`<you>/rl-envs-101-notebooks`, created for you), so edits survive across sessions. Pass
`--no-bucket` for a throwaway run. The GPU is pay-as-you-go and auto-stops after 4 hours.

Prefer your own GPU? Clone and open the notebook directly, or:

```bash
python3 tools/jupyter_launch.py --flavor a100-large
```

## The environment

The reward comes from [`AdithyaSK/latex-ocr-env`](https://huggingface.co/spaces/AdithyaSK/latex-ocr-env),
an OpenEnv environment deployed as a Space. The training script calls it per rollout — the same
pattern as the HTTP environments in [project 00](../00-environments-101/), just pointed at a
scoring task instead of an agentic one.

This is the part worth internalising: **the environment is a service your trainer talks to.** Once
that boundary is clean, swapping the task means swapping the URL.

## Read next

- **[00 · RL Environments 101](../00-environments-101/)** — how the six frameworks model this differently
- **[The guide](https://huggingface.co/spaces/AdithyaSK/rl-environments-guide)** — the long-form write-up
