#!/usr/bin/env bash
# RL Envs 101 — one command → a JupyterLab running on Hugging Face Jobs, with these tutorial
# notebooks already loaded. The ONLY thing you need is a Hugging Face token.
#
#   1. pip install -U huggingface_hub          # gives you the `hf` CLI
#   2. hf auth login                           # paste a token from https://huggingface.co/settings/tokens
#   3. bash tutorials/launch_jupyter.sh        # prints a JupyterLab URL in ~1-2 min
#
# Then open the printed URL (be logged into huggingface.co in the same browser) and run a notebook.
# Jobs is pay-as-you-go GPU — the job auto-stops at --timeout (default 4h) or `hf jobs cancel <id>`.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/adithya-s-k/RL_Envs_101.git}"
FLAVOR="${FLAVOR:-a10g-large}"                 # 1x A10G 24GB ($1.50/h). GPUs: hf jobs hardware
IMAGE="${IMAGE:-pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel}"
TIMEOUT="${TIMEOUT:-4h}"
PORT=8888

# Make sure the `hf` CLI exists (installs it if this is a fresh machine).
command -v hf >/dev/null 2>&1 || pip install -q -U huggingface_hub || python -m pip install -q -U huggingface_hub

# HF token: env → RL_Envs_101/.env (if run from a checkout) → logged-in CLI → interactive login.
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/../.env" ]; then
  set -a; source "$(dirname "${BASH_SOURCE[0]}")/../.env"; set +a
fi
: "${HF_TOKEN:=$(hf auth token 2>/dev/null || true)}"
if [ -z "${HF_TOKEN:-}" ]; then
  echo "🔑 Need a Hugging Face token (free): https://huggingface.co/settings/tokens"
  hf auth login
  HF_TOKEN="$(hf auth token 2>/dev/null || true)"
fi
[ -n "${HF_TOKEN:-}" ] || { echo "❌ Still no token — aborting." >&2; exit 1; }

# In-container startup: install JupyterLab, clone this repo, serve on :8888 with proxy-friendly flags
# (the HF Jobs proxy needs XSRF disabled + open origin, else the kernel/websocket is blocked).
START="set -e
pip install -q jupyterlab ipywidgets >/dev/null 2>&1
git clone --depth 1 ${REPO_URL} /workspace >/dev/null 2>&1 || mkdir -p /workspace
cd /workspace/tutorials 2>/dev/null || cd /workspace
echo '=== JupyterLab starting on :${PORT} ==='
exec jupyter lab --ip=0.0.0.0 --port=${PORT} --no-browser --allow-root \
  --ServerApp.token='' --ServerApp.password='' \
  --ServerApp.allow_origin='*' --ServerApp.disable_check_xsrf=True --ServerApp.trust_xheaders=True"

echo "🚀 Launching JupyterLab on HF Jobs (flavor=$FLAVOR, image=$IMAGE) ..."
OUT="$(hf jobs run --detach --expose "$PORT" --flavor "$FLAVOR" --timeout "$TIMEOUT" \
  --secrets HF_TOKEN="$HF_TOKEN" \
  ${E2B_API_KEY:+--secrets E2B_API_KEY="$E2B_API_KEY"} \
  "$IMAGE" bash -lc "$START" 2>&1)"
echo "$OUT"

URL="$(printf '%s\n' "$OUT" | grep -oE "https://[a-f0-9]+--${PORT}\.hf\.jobs" | head -1)"
JOB="$(printf '%s\n' "$OUT" | grep -oE "id=[a-f0-9]+" | head -1 | cut -d= -f2)"
echo
echo "────────────────────────────────────────────────────────────"
echo "⏳ JupyterLab will be ready in ~1-2 min at:"
echo "     ${URL:-<see 'Exposed ports' line above>}/lab"
echo "   (log into huggingface.co in the same browser first — the URL is auth'd to your token)"
echo "   logs:  hf jobs logs -f AdithyaSK/${JOB:-<job-id>}"
echo "   stop:  hf jobs cancel AdithyaSK/${JOB:-<job-id>}"
echo "────────────────────────────────────────────────────────────"
