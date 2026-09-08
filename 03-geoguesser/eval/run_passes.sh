#!/usr/bin/env bash
# Run N sequential pass@1 sweeps over every arm, sharded, reporting after each.
#
# One pass at a time across all arms, rather than all attempts of one arm then
# the next: after pass 1 you already have a complete pass@1 for everything, and
# each further pass refines it into pass@2, pass@3, ... So a useful answer
# arrives in minutes and sharpens, instead of nothing until the end.
#
# `--sample-offset` is what makes that compose: each pass records its attempts
# under a distinct sample index, so pooling passes yields a clean pass@k with no
# episode claiming to be the same attempt at the same task twice.
#
# The env servers are started once and reused across passes -- they take ~20s
# each to load the task index and are the thing that must not be a bottleneck.
#
# Usage:
#   RUN=passk PASSES=4 MODELS=$SP/passk_models.json bash run_passes.sh
set -uo pipefail

# Where results land, and where the environment checkout lives. Both were
# absolute paths to one machine's scratch directory, which made this script
# unusable by anyone else; they are now overridable and default to sensible
# locations relative to this file.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SP="${SP:-$HERE/results}"
# The env checkout supplies serve.sh, which brings up one server per shard.
# The rollout collector lives beside this script and talks to those servers over
# HTTP, so it needs no checkout of its own.
ENV_DIR="${OPENENV_GEOGUESSER:-$HERE/../env}"
if [ ! -f "$ENV_DIR/serve.sh" ]; then
  echo "cannot find the geoguesser environment at: $ENV_DIR" >&2
  echo "set OPENENV_GEOGUESSER to its path (it must contain serve.sh)" >&2
  exit 1
fi
mkdir -p "$SP"
RUN=${RUN:-passk}
PASSES=${PASSES:-4}
SHARDS=${SHARDS:-6}
WORKERS=${WORKERS:-8}
TASKS=${TASKS:-200}
MAX_TURNS=${MAX_TURNS:-12}
MODELS=${MODELS:-$SP/passk_models.json}
BASE_PORT=${BASE_PORT:-8141}
BASELINE=${BASELINE:-base}

cd "$ENV_DIR"
mkdir -p "$SP/$RUN"

# Reuse servers if they are already answering; only start what is missing.
for i in $(seq 0 $((SHARDS-1))); do
  PORT=$((BASE_PORT+i))
  code=$(curl -s -m 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/web/" 2>/dev/null)
  if [ "$code" != "200" ]; then
    PORT=$PORT STREET_DETAIL=1 GEOGUESSER_MAX_STEPS=$MAX_TURNS MAX_CONCURRENT_ENVS=64 \
      nohup bash "$ENV_DIR/serve.sh" > "$SP/$RUN/server-$i.log" 2>&1 &
  fi
done
for i in $(seq 0 $((SHARDS-1))); do
  PORT=$((BASE_PORT+i))
  for _ in $(seq 1 60); do
    code=$(curl -s -m 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/web/" 2>/dev/null)
    [ "$code" = "200" ] && break
    sleep 2
  done
  [ "$code" = "200" ] || { echo "env server :$PORT never came up" >&2; exit 1; }
done
echo "$SHARDS env servers ready on $BASE_PORT-$((BASE_PORT+SHARDS-1))"

for p in $(seq 0 $((PASSES-1))); do
  echo
  echo "===== pass $((p+1))/$PASSES (sample offset $p) ====="
  START=$(date +%s)
  SHARD_PIDS=()
  for i in $(seq 0 $((SHARDS-1))); do
    IDX=$(python3 -c "print(','.join(str(t) for t in range($i,$TASKS,$SHARDS)))")
    PORT=$((BASE_PORT+i))
    OUT="$SP/$RUN/pass-$p"
    mkdir -p "$OUT"
    nohup uv run --with openai --with anthropic python "$HERE/geoeval.py" run \
      --models "$MODELS" \
      --base-url "http://127.0.0.1:$PORT" \
      --split eval --indices "$IDX" --repeats 1 --sample-offset "$p" \
      --max-turns "$MAX_TURNS" --concurrency "$WORKERS" \
      --out-dir "$OUT" --run-id "shard-$i" \
      > "$OUT/shard-$i.log" 2>&1 &
    SHARD_PIDS+=($!)
  done
  # Wait for the shards only, never a bare `wait`. The env servers above are
  # also background children of this shell and never exit, so a bare `wait`
  # blocks forever once this script has started them itself -- the sweep
  # completes pass 1 and then hangs. It went unnoticed for a long time because
  # the checkpoint driver always found servers already listening and spawned
  # none, so its `wait` only ever had shards to wait for. Two multi-pass sweeps
  # stopped dead at exactly 1/4 of their episodes before this was found.
  for pid in "${SHARD_PIDS[@]}"; do wait "$pid"; done
  echo "pass $((p+1)) finished in $(( $(date +%s) - START ))s"
  # Cumulative: every pass so far, pooled into pass@(p+1).
  python3 "$HERE/geoeval.py" report "$SP/$RUN" --baseline "$BASELINE"
done
