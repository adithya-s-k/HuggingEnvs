#!/usr/bin/env bash
# RL Envs 101 — spin up a JupyterLab on Hugging Face Jobs with the tutorial notebooks loaded.
# Pure bash: uses ONLY the `hf` CLI (no Python needed). Works on macOS / Linux / WSL / Git Bash.
#
# Prereqs (once):
#   curl -LsSf https://hf.co/cli/install.sh | bash    # or: pip install -U huggingface_hub
#   hf auth login                                      # paste a free token from hf.co/settings/tokens
#
# Run:   bash launch.sh [FLAVOR]      e.g.  bash launch.sh t4-small
#        FLAVOR env also works.   Default: a100-large (A100 80GB).   List: hf jobs hardware
set -e

FLAVOR="${1:-${FLAVOR:-a100-large}}"
TIMEOUT="${TIMEOUT:-4h}"
REPO="${REPO_URL:-https://github.com/adithya-s-k/RL_Envs_101.git}"
IMAGE="${IMAGE:-pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel}"
PORT=8888

command -v hf >/dev/null 2>&1 || {
  echo "❌ 'hf' CLI not found. Install it first:"
  echo "     curl -LsSf https://hf.co/cli/install.sh | bash   # or: pip install -U huggingface_hub"
  echo "   then:  hf auth login"
  exit 1
}
TOKEN="${HF_TOKEN:-$(hf auth token 2>/dev/null || true)}"
[ -z "$TOKEN" ] && { echo "❌ Not logged in. Run:  hf auth login"; exit 1; }

# Single-line container bootstrap (no newlines — the CLI mangles multi-line commands).
BOOT="set -e; command -v git >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq git >/dev/null 2>&1); pip install -q jupyterlab ipywidgets >/dev/null 2>&1; rm -rf /workspace; git clone --depth 1 $REPO /workspace >/dev/null 2>&1; cd /workspace/tutorials 2>/dev/null || cd /workspace; echo '=== JupyterLab starting on :$PORT ==='; exec jupyter lab --ip 0.0.0.0 --port $PORT --no-browser --allow-root --ServerApp.token= --ServerApp.password= --ServerApp.disable_check_xsrf=True --ServerApp.allow_origin=* --ServerApp.trust_xheaders=True"

echo "🚀 Launching JupyterLab on HF Jobs (flavor=$FLAVOR) ..."
# NOTE: the `--` before the command is REQUIRED so the CLI stops parsing flags and forwards bash -c intact.
OUT=$(hf jobs run --flavor "$FLAVOR" --timeout "$TIMEOUT" --expose "$PORT" -s HF_TOKEN="$TOKEN" -d \
        "$IMAGE" -- bash -c "$BOOT" 2>&1) || { echo "$OUT"; exit 1; }
JID=$(echo "$OUT" | grep -oE '[0-9a-f]{24}' | head -1)

echo "────────────────────────────────────────────────────────────"
echo "⏳ Ready in ~1-2 min at:"
echo "     https://${JID}--${PORT}.hf.jobs/lab"
echo "   (log into huggingface.co in the same browser first)"
echo "   logs:  hf jobs logs -f $JID"
echo "   stop:  hf jobs cancel $JID"
echo "────────────────────────────────────────────────────────────"
