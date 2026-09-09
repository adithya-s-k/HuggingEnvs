#!/usr/bin/env bash
# Score the whole board -- frontier APIs, HF-router Qwens and any local vLLM
# arms -- on the same eval split, turn budget and prompt as the trained
# checkpoints, so the numbers drop straight into the same table.
#
# Comparability is the whole point, so these are fixed to match how run 1/2/3
# checkpoints were scored: --split eval, indices 0..TASKS-1, --max-turns 12,
# prompt v2, pass@k built from K single-attempt passes with distinct
# --sample-offset values.
#
# Usage:
#   bash board_sweep.sh pilot          # 12 tasks x 1 pass  -- price it first
#   bash board_sweep.sh full           # 200 tasks x 4 passes (pass@4)
#   TASKS=50 PASSES=2 bash board_sweep.sh custom
#
# Env:
#   MODELS   arm spec JSON            (default board_models.json beside this file)
#   TASKS    task indices 0..TASKS-1  (default 200)
#   PASSES   passes to pool into pass@k (default 4)
#   SHARDS   local env servers        (default 6)
#   WORKERS  concurrent episodes per shard (default 4)
#   BASE_PORT first env server port   (default 8161, clear of the eval driver's 8141)
#   ONLY     comma-separated arm names to include
#   QUIET    set to 1 to suppress the progress line
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SP="${SP:-$HERE/results}"
# .env is read for API keys; override if the checkout lives elsewhere.
# Where the API keys live. Searched in order so this works from a standalone
# checkout; secrets are never copied into this repository. Parsed in Python
# below, never sourced: the '|' in a Mapillary key is a shell pipe.
ENV_FILE="${GEO_ENV_FILE:-}"
if [ -z "$ENV_FILE" ]; then
  # Repo-relative only. A path into a sibling checkout on one machine is not a
  # default anyone else can use; set GEO_ENV_FILE if your keys live elsewhere.
  for c in "$HERE/../.env" "$HERE/../../.env"; do
    [ -f "$c" ] && { ENV_FILE="$c"; break; }
  done
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "no .env found; set GEO_ENV_FILE to a file holding the API keys" >&2
  exit 2
fi
mkdir -p "$SP"

MODE="${1:-full}"
case "$MODE" in
  pilot) TASKS="${TASKS:-12}";  PASSES="${PASSES:-1}"; SHARDS="${SHARDS:-3}"; RUN="${RUN:-board-pilot}" ;;
  full)  TASKS="${TASKS:-200}"; PASSES="${PASSES:-4}"; SHARDS="${SHARDS:-6}"; RUN="${RUN:-board-passk}" ;;
  *)     TASKS="${TASKS:-200}"; PASSES="${PASSES:-4}"; SHARDS="${SHARDS:-6}"; RUN="${RUN:-board-$MODE}" ;;
esac
WORKERS="${WORKERS:-4}"
BASE_PORT="${BASE_PORT:-8161}"
MODELS="${MODELS:-$HERE/board_models.json}"
MAX_TURNS=12
LOG="$SP/board.log"

[ -f "$MODELS" ] || { echo "no arm spec at $MODELS" >&2; exit 1; }

# Keys come out of .env parsed in Python, never sourced: MAPILLARY_API_KEY's
# value contains a '|', which a shell would read as a pipe. That leaked a token
# into a transcript once.
KEYS=$(python3 - "$ENV_FILE" <<'PY'
import pathlib, shlex, sys
want = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "HF_TOKEN", "VLLM_API_KEY")
env = {}
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
for k in want:
    if env.get(k):
        print(f"export {k}={shlex.quote(env[k])}")
# vLLM arms authenticate with any non-empty string; give them one if unset.
if not env.get("VLLM_API_KEY"):
    print("export VLLM_API_KEY=local")
PY
)
eval "$KEYS"
unset KEYS

# Optionally narrow the board to a few arms.
if [ -n "${ONLY:-}" ]; then
  MODELS_FILTERED="$SP/$RUN-arms.json"
  # `set -e` is deliberately off (one failed arm should not kill a sweep), so
  # this exit status is checked by hand: without it a typo in ONLY left a stale
  # spec in place and the sweep ran to completion with no scored episodes
  # instead of stopping.
  if ! python3 - "$MODELS" "$MODELS_FILTERED" "$ONLY" <<'PY'
import json, sys
src, dst, only = sys.argv[1], sys.argv[2], set(sys.argv[3].split(","))
allarms = json.load(open(src))
arms = [a for a in allarms if a["name"] in only]
missing = only - {a["name"] for a in allarms}
if missing:
    names = ", ".join(sorted(a["name"] for a in allarms))
    sys.exit(f"unknown arm(s): {', '.join(sorted(missing))}; available: {names}")
json.dump(arms, open(dst, "w"), indent=1)
print(f"{len(arms)} of {len(allarms)} arms selected")
PY
  then
    echo "ONLY did not resolve; nothing was run." >&2
    exit 1
  fi
  MODELS="$MODELS_FILTERED"
fi

NARMS=$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "$MODELS")
EXPECTED=$(( TASKS * PASSES * NARMS ))
OUT="$SP/$RUN"

# One sweep per output directory. Two concurrent sweeps writing the same $RUN
# interleave their episodes: the pooled report then shows k>1 with PASSES=1 and
# paired stats computed over whichever tasks happened to overlap. That produced
# a table with "SIGNIFICANT" verdicts on n=4 that contradicted the mean-of-k
# column, so this is a hard failure rather than a warning.
LOCK="$OUT.lock"
mkdir -p "$SP"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "refusing to start: $LOCK exists, so another sweep is writing $RUN." >&2
  echo "  if no sweep is running:  rmdir '$LOCK'" >&2
  echo "  to run a second sweep:   RUN=other-name bash $0 $MODE" >&2
  exit 1
fi
cleanup () { [ -n "${PROG_PID:-}" ] && kill "$PROG_PID" 2>/dev/null; rmdir "$LOCK" 2>/dev/null; }
trap cleanup EXIT INT TERM

echo "$(date -u +%H:%M:%S) $RUN: $TASKS tasks x $PASSES pass(es) x $NARMS arms, split=eval, max_turns=$MAX_TURNS" | tee -a "$LOG"
echo "  expecting $EXPECTED episodes -> $OUT" | tee -a "$LOG"

# Progress line, driven by episodes actually on disk rather than by anything the
# sweep claims. Reports per-arm counts so a stalled or rate-limited arm is
# visible while there is still time to react, instead of turning up as an
# uneven task count in the final table.
if [ "${QUIET:-0}" != "1" ]; then
  (
    START=$(date +%s); LAST=-1
    while true; do
      sleep 15
      N=$(cat "$OUT"/pass-*/shard-*/episodes.jsonl 2>/dev/null | wc -l | tr -d ' ')
      [ -z "$N" ] && N=0
      [ "$N" = "$LAST" ] && continue
      LAST=$N
      EL=$(( $(date +%s) - START ))
      if [ "$N" -gt 0 ] && [ "$EL" -gt 0 ]; then
        RATE=$(python3 -c "print(f'{$N/$EL*60:.1f}')")
        ETA=$(python3 -c "
n,exp,el=$N,$EXPECTED,$EL
print('--' if n>=exp else f'{(exp-n)*el/n/60:.0f}m')")
      else
        RATE="0.0"; ETA="--"
      fi
      PCT=$(python3 -c "print(f'{100*$N/$EXPECTED:.0f}')")
      SLOW=$(python3 - "$OUT" <<'PYP'
import json,pathlib,sys,collections
c=collections.Counter()
for f in pathlib.Path(sys.argv[1]).rglob("*.jsonl"):
    for line in f.open():
        line=line.strip()
        if line:
            try: c[json.loads(line).get("model_name")]+=1
            except Exception: pass
print(" ".join(f"{k}:{v}" for k,v in sorted(c.items(), key=lambda kv: kv[1]))[:150] or "-")
PYP
)
        printf '  [progress] %s/%s episodes (%s%%) · %s/min · eta %s · %s\n' \
          "$N" "$EXPECTED" "$PCT" "$RATE" "$ETA" "$SLOW"
    done
  ) &
  PROG_PID=$!
fi

RUN="$RUN" PASSES="$PASSES" SHARDS="$SHARDS" WORKERS="$WORKERS" TASKS="$TASKS" \
  MAX_TURNS="$MAX_TURNS" MODELS="$MODELS" BASELINE="${BASELINE:-sonnet-5}" \
  BASE_PORT="$BASE_PORT" \
  bash "$HERE/run_passes.sh" 2>&1 | tee -a "$LOG"

echo "$(date -u +%H:%M:%S) $RUN finished" | tee -a "$LOG"

# Integrity gate, mirroring the checkpoint driver's. A turn with no
# `finish_reason` is a request that got no completion -- a dead endpoint, an
# outage, a rate-limit wall. The harness records it as an *empty reply*, so the
# episode burns its turns, never submits and scores 0, which is indistinguishable
# from a model that will not commit. That produced a fully plausible table off a
# dead gradio tunnel earlier, so it is checked here rather than trusted.
python3 - "$SP/$RUN" <<'PY' | tee -a "$LOG"
import json, pathlib, sys, collections
root = pathlib.Path(sys.argv[1])
tot = collections.Counter(); dead = collections.Counter()
eps = collections.Counter(); k = collections.defaultdict(collections.Counter)
for f in root.rglob("*.jsonl"):
    for line in f.open():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        arm = r.get("model_name")
        if not arm:
            continue
        eps[arm] += 1
        t = r.get("task") or {}
        k[arm][(t.get("index"), t.get("sample"))] += 1
        for turn in r.get("turns") or []:
            m = turn.get("model")
            if isinstance(m, dict):
                tot[arm] += 1
                if m.get("finish_reason") is None:
                    dead[arm] += 1
LIMIT = 0.02
bad = []
print("\nintegrity check (share of model turns with no completion):")
for arm in sorted(eps, key=lambda a: -(dead[a] / tot[a] if tot[a] else 0)):
    frac = dead[arm] / tot[arm] if tot[arm] else 0.0
    dupes = sum(v - 1 for v in k[arm].values() if v > 1)
    flag = ""
    if frac > LIMIT:
        flag = "  <-- DISCARD, endpoint was not answering"
        bad.append(arm)
    if dupes:
        flag += f"  <-- {dupes} duplicated (task,sample)"
        if arm not in bad:
            bad.append(arm)
    print(f"  {arm:22} {eps[arm]:5} eps  {frac:6.2%} dead{flag}")
if bad:
    print("\nNOT TRUSTWORTHY: " + ", ".join(bad))
    print("re-run those arms:  ONLY=" + ",".join(bad) + " RUN=<fresh-name> bash board_sweep.sh full")
    sys.exit(3)
print("  all arms clean")
PY
GATE=${PIPESTATUS[0]}

echo
echo "pooled report:"
python3 "$HERE/geoeval.py" report "$SP/$RUN" --baseline "${BASELINE:-sonnet-5}"

if [ "${GATE:-0}" = "3" ]; then
  echo
  echo "the report above includes arms that failed the integrity check -- see above." >&2
  exit 3
fi
