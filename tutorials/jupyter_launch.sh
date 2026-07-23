#!/usr/bin/env bash
# RL Envs 101 — spin up a JupyterLab on Hugging Face Jobs with the tutorial notebooks loaded.
# Pure bash: uses ONLY the `hf` CLI (no Python needed). Works on macOS / Linux / WSL / Git Bash.
#
# Prereqs (once):
#   curl -LsSf https://hf.co/cli/install.sh | bash    # or: pip install -U huggingface_hub
#   hf auth login                                      # paste a free token from hf.co/settings/tokens
#
# Run:
#   curl -sSL .../tutorials/jupyter_launch.sh | bash           # interactive GPU picker
#   bash jupyter_launch.sh t4-small                            # or name the GPU directly (arg / FLAVOR env)
#   FLAVOR=t4-small curl -sSL .../tutorials/jupyter_launch.sh | bash
# Full flavor list + prices:  hf jobs hardware
set -e

TIMEOUT="${TIMEOUT:-4h}"
REPO="${REPO_URL:-https://github.com/adithya-s-k/RL_Envs_101.git}"
IMAGE="${IMAGE:-huggingface/trl}"   # TRL image: torch + CUDA + trl preinstalled (same as the experiments)
PORT=8888

command -v hf >/dev/null 2>&1 || {
  echo "❌ 'hf' CLI not found. Install it first:"
  echo "     curl -LsSf https://hf.co/cli/install.sh | bash   # or: pip install -U huggingface_hub"
  echo "   then:  hf auth login"
  exit 1
}
TOKEN="${HF_TOKEN:-$(hf auth token 2>/dev/null || true)}"
[ -z "$TOKEN" ] && { echo "❌ Not logged in. Run:  hf auth login"; exit 1; }

# --- pick the GPU -----------------------------------------------------------
# Curated menu (name | description). Full list: `hf jobs hardware`.
MENU_NAMES=(t4-small      l4x1          a10g-large    l40sx1        a100-large              h200)
MENU_DESC=("1x T4  16GB  · \$0.40/hr · cheapest, slow"
           "1x L4  24GB  · \$0.80/hr · good budget pick"
           "1x A10G 24GB · \$1.50/hr"
           "1x L40S 48GB · \$1.80/hr · roomy VRAM"
           "1x A100 80GB · \$2.50/hr · recommended for these tutorials"
           "1x H200 141GB · \$5.00/hr · fastest")
DEFAULT_INDEX=5   # a100-large

FLAVOR="${1:-${FLAVOR:-}}"
if [ -z "$FLAVOR" ]; then
  if [ -r /dev/tty ]; then                       # interactive: show the picker (works under curl | bash via /dev/tty)
    echo "Select a GPU  (Enter = ${MENU_NAMES[$((DEFAULT_INDEX-1))]}, the default):" >&2
    for i in "${!MENU_NAMES[@]}"; do
      star=" "; [ $((i+1)) -eq "$DEFAULT_INDEX" ] && star="*"
      printf "  %s%d) %-12s %s\n" "$star" "$((i+1))" "${MENU_NAMES[$i]}" "${MENU_DESC[$i]}" >&2
    done
    printf "  %d) other      (type any flavor name — see: hf jobs hardware)\n" "$(( ${#MENU_NAMES[@]} + 1 ))" >&2
    printf "> " >&2; read -r choice </dev/tty || choice=""
    if [ -z "$choice" ]; then
      FLAVOR="${MENU_NAMES[$((DEFAULT_INDEX-1))]}"
    elif [ "$choice" -eq "$(( ${#MENU_NAMES[@]} + 1 ))" ] 2>/dev/null; then
      printf "flavor name > " >&2; read -r FLAVOR </dev/tty
    elif [ "$choice" -ge 1 ] 2>/dev/null && [ "$choice" -le "${#MENU_NAMES[@]}" ] 2>/dev/null; then
      FLAVOR="${MENU_NAMES[$((choice-1))]}"
    else
      FLAVOR="$choice"                            # user typed a flavor name directly
    fi
  else
    FLAVOR="${MENU_NAMES[$((DEFAULT_INDEX-1))]}"   # non-interactive, none given -> default
  fi
fi
FLAVOR="${FLAVOR:-a100-large}"

# Single-line container bootstrap (no newlines — the CLI mangles multi-line commands).
BOOT="set -e; cd /; command -v git >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq git >/dev/null 2>&1); pip install -q jupyterlab ipywidgets >/dev/null 2>&1; rm -rf /workspace; git clone --depth 1 $REPO /workspace >/dev/null 2>&1; cd /workspace/tutorials 2>/dev/null || cd /workspace; echo '=== JupyterLab starting on :$PORT ==='; exec jupyter lab --ip 0.0.0.0 --port $PORT --no-browser --allow-root --ServerApp.token= --ServerApp.password= --ServerApp.disable_check_xsrf=True --ServerApp.allow_origin=* --ServerApp.trust_xheaders=True"

echo "🚀 Launching JupyterLab on HF Jobs (flavor=$FLAVOR) ..."
# NOTE: the `--` before the command is REQUIRED so the CLI stops parsing flags and forwards bash -c intact.
OUT=$(hf jobs run --flavor "$FLAVOR" --timeout "$TIMEOUT" --expose "$PORT" -s HF_TOKEN="$TOKEN" -d \
        "$IMAGE" -- bash -c "$BOOT" 2>&1) || { echo "$OUT"; exit 1; }
JID=$(echo "$OUT" | grep -oE '[0-9a-f]{24}' | head -1)
LAB="https://${JID}--${PORT}.hf.jobs/lab"

# Wait until JupyterLab answers (image pull + clone can take a few min), while also
# watching the job's status so a cancel / error from the dashboard is reflected here immediately.
printf "   job %s  ·  waiting for JupyterLab to come up " "$JID"
READY=""; STOPPED=""
for _ in $(seq 1 90); do          # up to ~7.5 min
  stage=$(hf jobs inspect "$JID" 2>/dev/null | grep -oE "'stage': '[A-Za-z_]+'" | head -1 | cut -d"'" -f4)
  case "$stage" in
    CANCELED|CANCELLED|ERROR|FAILED|COMPLETED|DELETED) STOPPED="$stage"; break ;;
  esac
  code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$LAB" 2>/dev/null || true)
  [ "$code" = "200" ] && { READY=1; break; }
  printf "."; sleep 5
done
echo

echo "────────────────────────────────────────────────────────────"
if [ -n "$STOPPED" ]; then
  echo "❌ Job is no longer running (status: $STOPPED)."
  echo "   📋 dashboard:  https://huggingface.co/settings/jobs"
  echo "   logs:         hf jobs logs $JID"
  echo "────────────────────────────────────────────────────────────"
  exit 1
fi
if [ -n "$READY" ]; then
  echo "✅ JupyterLab is READY — open it:"
else
  echo "⏳ Still starting — it should come up shortly at:"
fi
echo "     $LAB"
echo "   (log into huggingface.co in the same browser first)"
echo
echo "   📋 Track this & all your jobs:  https://huggingface.co/settings/jobs"
echo "   logs:  hf jobs logs -f $JID"
echo "   stop:  hf jobs cancel $JID"
echo "────────────────────────────────────────────────────────────"
