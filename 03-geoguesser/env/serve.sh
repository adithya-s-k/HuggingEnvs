#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
#
# Run the environment locally with the same configuration the Space uses, so a
# client cannot tell the two apart.
#
# The only differences from the Space are where the files live: locally the
# indexes and imagery are in the repo, on the Space they arrive through a
# Storage Bucket mounted read-only at /data. Everything else -- splits, step
# budget, street labels, offline enforcement -- is identical, and verified so.
#
# Usage:
#   ./serve.sh                 # http://localhost:8000/web/
#   PORT=8141 ./serve.sh
#   ALLOW_FETCH=1 ./serve.sh   # let cache misses reach Mapillary

set -euo pipefail

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

# This script sits at the environment root, so its own directory is the
# environment. `uv sync` here creates .venv and installs the package, which is
# what makes `geoguesser_env` importable -- the directory is named `env`, so a
# PYTHONPATH-based import would not resolve the package name.
cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
ENV_DIR="$PWD"
PYTHON="${PYTHON:-$ENV_DIR/.venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
  echo "no interpreter at $PYTHON" >&2
  echo "run 'uv sync' in $ENV_DIR, or set PYTHON= to an interpreter that has" >&2
  echo "openenv-geoguesser-env installed" >&2
  exit 1
fi

if ! "$PYTHON" -c "import geoguesser_env" 2>/dev/null; then
  echo "geoguesser_env is not importable by $PYTHON" >&2
  echo "run 'uv sync' in $ENV_DIR" >&2
  exit 1
fi

"$PYTHON" -c "import matplotlib, gradio, PIL, numpy, fastmcp" 2>/dev/null || {
  echo "missing dependencies — install with:" >&2
  echo "  uv pip install --python $PYTHON matplotlib gradio pillow numpy fastmcp" >&2
  exit 1
}

if [ ! -s "$ENV_DIR/tasks/eval_pano_v3.jsonl" ]; then
  echo "no eval split at tasks/eval_pano_v3.jsonl." >&2
  echo "It is committed, so this checkout looks incomplete. Rebuild with:" >&2
  echo "  python dataset/split_tasks.py tasks/pool_offline_5k.jsonl --eval 200" >&2
  exit 1
fi

# Core keeps the web UI behind this flag and defaults it off, so without it the
# play tab is a 404 and the server looks broken.
export ENABLE_WEB_INTERFACE=true

# Splits resolve from repo-relative defaults; a split whose file is absent is
# simply not offered, so a checkout with only the eval index still works.
export GEOGUESSER_DEFAULT_SPLIT="${GEOGUESSER_DEFAULT_SPLIT:-train}"
export GEOGUESSER_MAX_STEPS="${GEOGUESSER_MAX_STEPS:-24}"

# 0 means a cache miss raises instead of quietly reaching for Mapillary, which
# is what turns "offline" from a hope into an assertion. Independent of street
# detail, which uses Overpass and caches locally.
export GEOGUESSER_ALLOW_FETCH="${ALLOW_FETCH:-0}"
export GEOGUESSER_STREET_DETAIL="${STREET_DETAIL:-1}"

# Core defaults to 4 concurrent sessions, which is a demo setting: a sweep of
# six endpoints at eight workers each asks for 48 and the rest fail outright
# with CAPACITY_REACHED. Sessions are cheap here -- the parsed index is shared
# process-wide and only the camera state is per-session.
export MAX_CONCURRENT_ENVS="${MAX_CONCURRENT_ENVS:-64}"

echo "geoguesser_env  ->  http://$HOST:$PORT/web/"
"$PYTHON" - <<'PY'
from geoguesser_env.server.app import resolve_splits, ACTIVE_DEFAULT_SPLIT
splits, _ = resolve_splits()
for name, path in splits.items():
    print(f"  {name:6} {path}")
print(f"  default split: {ACTIVE_DEFAULT_SPLIT}")
PY
echo

exec "$PYTHON" -m uvicorn geoguesser_env.server.app:app --host "$HOST" --port "$PORT"
