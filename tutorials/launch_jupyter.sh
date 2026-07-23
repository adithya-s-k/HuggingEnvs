#!/usr/bin/env bash
# RL Envs 101 — thin wrapper around the cross-platform launcher (launch_jupyter.py).
# Prereqs (once):  pip install -U huggingface_hub  &&  hf auth login
# Run:             bash launch_jupyter.sh [--flavor a100-large]   (list: hf jobs hardware)
set -e
command -v hf >/dev/null 2>&1 || pip install -q -U huggingface_hub || python -m pip install -q -U huggingface_hub
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python "$DIR/launch_jupyter.py" "$@"
