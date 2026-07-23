# RL Environments 101: From "What Is an Env?" to Training Your Own

Hands-on notebooks that **train an LLM against an RL environment** with GRPO — running on a GPU you
spin up in one command. No cluster, no local GPU, no setup. **All you need is a free Hugging Face token.**

---

## ▶️ Run it (any OS — macOS, Linux, Windows)

**1. Get a token** (free): https://huggingface.co/settings/tokens → "New token" → copy it.

**2. One command** — paste this in a terminal. It installs the tool, asks for your token, and launches a
GPU with the notebooks loaded:

```bash
curl -sSL https://raw.githubusercontent.com/adithya-s-k/RL_Envs_101/main/tutorials/launch_jupyter.sh | bash
```

<sub>**Windows:** open **Git Bash** (comes with [git](https://git-scm.com/download/win)) or **WSL**, then paste the same line. No repo cloning needed.</sub>

**3. Open the link** it prints (`https://…--8888.hf.jobs/lab`) — be logged into huggingface.co in the same
browser — and open a notebook. That's it. 🎉

> The GPU is pay-as-you-go and auto-stops after 4h (or `hf jobs cancel <id>`). Default hardware: A10G 24 GB.

---

## 📓 The notebooks

- **[`notebooks/01_latex_ocr_grpo.ipynb`](notebooks/01_latex_ocr_grpo.ipynb)** — teach **Qwen3-VL-2B** to read
  math images → LaTeX. Reward comes from an **OpenEnv** environment (served as an HF Space).
- **[`notebooks/02_lipogram_grpo.ipynb`](notebooks/02_lipogram_grpo.ipynb)** — teach **Qwen3.5-2B** to answer
  **without the letter “e”**. Reward is a plain **Python function** — and you'll watch a lazy reward get
  *hacked*, then fix it.

Two notebooks, two ways rewards enter GRPO: an environment server (#1) vs. a function you own (#2).

## 🖥️ Prefer to run locally?

If you already have a GPU + Python, clone the repo and open the notebooks directly — they run the same:

```bash
git clone https://github.com/adithya-s-k/RL_Envs_101 && cd RL_Envs_101/tutorials/notebooks
```

## 🎞️ Slides

Talk slides live in [`slides/`](slides/).
