# RL Environments 101: From "What Is an Env?" to Training Your Own

Hands-on notebooks that **train an LLM against an RL environment** with GRPO, on a GPU you spin up in one
command. No cluster, no local GPU, no environment setup. **All you need is a free Hugging Face token.**

> 🎞️ **Talk slides:** https://huggingface.co/spaces/AdithyaSK/rl-environments-101-slides
> — the companion deck for this material (source in [`slides/`](slides/)).

---

## ⚡ Setup (once, ~30 seconds)

You need **Python** and one package — `huggingface_hub` (which also gives you the `hf` command):

```bash
pip install -U huggingface_hub
```

**Get a token** (free): https://huggingface.co/settings/tokens → **New token** → *Read* is enough. Then log in:

```bash
hf auth login          # paste the token; check with: hf whoami
```

That's the whole setup — the same on **Windows, macOS, and Linux**.

---

## ▶️ Run it — one command

Spin up a GPU with the notebooks loaded and get a JupyterLab URL. **No cloning:**

**macOS / Linux:**
```bash
curl -sSL https://raw.githubusercontent.com/adithya-s-k/RL_Envs_101/main/tutorials/jupyter_launch.py | python3 -
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/adithya-s-k/RL_Envs_101/main/tutorials/jupyter_launch.py | python -
```

It pops a quick **GPU menu** (pick a number — Enter takes the A100 default), launches the job, **waits
until JupyterLab is actually up**, then prints the URL. **Open it** (be logged into huggingface.co in the
same browser), open a notebook, and run it. 🎉

**Skip the menu** — name the GPU with the `FLAVOR` env var (full list + prices: `hf jobs hardware`):
```bash
FLAVOR=t4-small  curl -sSL .../jupyter_launch.py | python3 -
# PowerShell:  $env:FLAVOR="t4-small"; irm .../jupyter_launch.py | python -
```

> **Your work is saved.** The notebooks are the JupyterLab root and live on a personal HF **storage
> bucket** (`<you>/rl-envs-101-notebooks`, created automatically) — anything you edit or add persists
> across sessions. Pass `--no-bucket` for a throwaway session.
>
> Needs the `huggingface_hub` **package** (`pip install -U huggingface_hub` — not the standalone `hf`
> binary). The GPU is pay-as-you-go and auto-stops after 4h; track / stop jobs anytime at
> **https://huggingface.co/settings/jobs**. Uses the SDK (not the `hf` CLI), so CLI version quirks
> don't matter. The URL is gated to your HF login.

---

## 🛠️ Dev setup (clone the repo)

Prefer to have the files locally, tweak them, or run on your own GPU? Clone and go:

```bash
git clone https://github.com/adithya-s-k/RL_Envs_101
cd RL_Envs_101/tutorials
python3 jupyter_launch.py --flavor a100-large
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
