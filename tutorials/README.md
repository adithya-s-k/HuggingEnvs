# RL Environments 101: From "What Is an Env?" to Training Your Own

Hands-on notebooks that **train an LLM against an RL environment** with GRPO, on a GPU you spin up in one
command. No cluster, no local GPU, no environment setup. **All you need is a free Hugging Face token.**

---

## ⚡ Setup (once, ~30 seconds)

**1. Install the Hugging Face CLI** (`hf`). Pick either:

```bash
# Standalone installer — no Python needed (recommended)
# macOS / Linux:
curl -LsSf https://hf.co/cli/install.sh | bash
# Windows (PowerShell):
powershell -ExecutionPolicy ByPass -c "irm https://hf.co/cli/install.ps1 | iex"
```
```bash
# …or via pip, if you already have Python:
pip install -U huggingface_hub
```

**2. Get a token** (free): https://huggingface.co/settings/tokens → **New token** → *Read* is enough → copy it.

**3. Log in** (paste the token when asked):

```bash
hf auth login
```

Check it worked with `hf whoami`. That's the whole setup — the same on **Windows, macOS, and Linux**.

---

## ▶️ Run it — one command

Spin up a GPU with the notebooks loaded and get a JupyterLab URL. Just the `hf` CLI — **no cloning:**

**macOS / Linux** (Windows via Git Bash / WSL — or use the Python one-liner below):
```bash
curl -sSL https://raw.githubusercontent.com/adithya-s-k/RL_Envs_101/main/tutorials/launch.sh | bash
```

It pops a quick **GPU menu** (pick a number — Enter takes the A100 default), launches the job, **waits
until JupyterLab is actually up**, then prints the URL. **Open it** (be logged into huggingface.co in the
same browser), open a notebook, and run it. 🎉

**Skip the menu** — name the GPU directly (full list + prices: `hf jobs hardware`):
```bash
FLAVOR=t4-small  curl -sSL .../launch.sh | bash          # or, if cloned:  bash launch.sh t4-small
```

**On Windows, or if you have Python** — same thing via the SDK, no bash needed:
```bash
curl -sSL https://raw.githubusercontent.com/adithya-s-k/RL_Envs_101/main/tutorials/launch.py | python3 -
# Windows PowerShell:  irm https://raw.githubusercontent.com/adithya-s-k/RL_Envs_101/main/tutorials/launch.py | python -
# pick the GPU with the FLAVOR env var, e.g.  FLAVOR=t4-small curl -sSL .../launch.py | python3 -
```

> The GPU is pay-as-you-go and auto-stops after 4h. Track / stop your jobs anytime at
> **https://huggingface.co/settings/jobs** (or `hf jobs cancel <id>`). Under the hood the script calls
> `hf jobs run --expose 8888` — a GPU container that clones this repo and serves JupyterLab through the
> HF Jobs proxy (the URL is gated to your HF login). No files touch your machine.

---

## 🛠️ Dev setup (clone the repo)

Prefer to have the files locally, tweak them, or run on your own GPU? Clone and go:

```bash
git clone https://github.com/adithya-s-k/RL_Envs_101
cd RL_Envs_101/tutorials
bash launch.sh a100-large               # Windows / no bash:  python launch.py --flavor a100-large
# …or just open notebooks/*.ipynb in your own Jupyter if you already have a GPU
```

---

## 📓 The notebooks

| notebook | what you train | reward comes from | the lesson |
|---|---|---|---|
| **[`notebooks/01_latex_ocr_grpo.ipynb`](notebooks/01_latex_ocr_grpo.ipynb)** | **Qwen3-VL-2B** — read math images → LaTeX | an **OpenEnv** environment (served as an HF Space) | a *verifiable* reward + a clean upward curve |
| **[`notebooks/02_lipogram_grpo.ipynb`](notebooks/02_lipogram_grpo.ipynb)** | **Qwen3.5-2B** — answer **without the letter “e”** | a plain **Python function** you own | **reward design + reward hacking** (watch a lazy reward get gamed, then fix it) |

Two notebooks, the two ways rewards enter GRPO: an environment server (#1) vs. a function you own (#2).

## 🎞️ Slides

Talk slides live in [`slides/`](slides/).
