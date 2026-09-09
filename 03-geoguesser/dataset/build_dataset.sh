#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
#
# Build the offline task pool: every frame of every task mirrored to disk, so
# both training and eval run with the network off.
#
# Eval is NOT carved here. Sample it afterwards with split_tasks.py, which
# enforces the separation (shared sequences, plus a 1 km buffer) in one place
# rather than trusting two independent builds not to collide.
#
# Usage:
#   ./dataset/build_dataset.sh              # 5000 tasks, the default
#   TASKS=100 ./dataset/build_dataset.sh    # trial
#   ./dataset/build_dataset.sh --seed 12    # extra args reach build_tasks.py
#
# Resumable: Ctrl-C and re-run the identical command. It continues where it
# stopped and skips every sequence already used.

set -euo pipefail

TASKS="${TASKS:-5000}"
FRAMES="${FRAMES:-24}"

# Only reject sequences too short to navigate at all. Demanding a full 24
# everywhere would drop ~22% of candidates, and short sequences cluster in
# sparsely mapped regions, so that filter quietly costs geographic diversity.
# Tasks therefore carry 8-24 frames; filter to 24 when sampling eval, where a
# uniform movement budget is what makes scores comparable.
MIN_FRAMES="${MIN_FRAMES:-8}"

# workers x frame-workers is the concurrent fetch count. Measured on an
# 18-core machine: 24->7.7 img/s, 48->16.1, 96->27.0, 144->37.0, zero failures,
# and 144 sits at ~7% of Mapillary's 60k/min entity limit.
WORKERS="${WORKERS:-12}"
FRAME_WORKERS="${FRAME_WORKERS:-12}"

# Loose country cap: this pool feeds training, where breadth beats balance, and
# eval balance is enforced at sampling time instead. The per-creator cap stays
# tight because one contributor holds 99,167 pool sequences (8% of the pool).
PER_COUNTRY="${PER_COUNTRY:-150}"
PER_CREATOR="${PER_CREATOR:-25}"

OUT="${OUT:-tasks/pool_offline_5k.jsonl}"

cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")/.."
ENV_DIR="$PWD"
REPO_ROOT="$(cd ../.. && pwd)"
PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
  echo "no interpreter at $PYTHON — run 'uv sync --all-extras' first, or set PYTHON=" >&2
  exit 1
fi

# Read the token in Python, never by sourcing .env: the "|" in "MLY|..." is a
# pipe to the shell, which leaks the token into the terminal.
if [ -z "${MAPILLARY_API_KEY_TRAIN:-}" ] && [ -z "${MAPILLARY_API_KEY:-}" ]; then
  MAPILLARY_API_KEY_TRAIN="$("$PYTHON" - "$REPO_ROOT/.env" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
if path.exists():
    for line in path.read_text().splitlines():
        for name in ("MAPILLARY_API_KEY_TRAIN", "MAPILLARY_API_KEY"):
            if line.startswith(name + "="):
                print(line.split("=", 1)[1].strip().strip('"').strip("'"))
                sys.exit()
PY
)"
  export MAPILLARY_API_KEY_TRAIN
fi
if [ -z "${MAPILLARY_API_KEY_TRAIN:-}" ] && [ -z "${MAPILLARY_API_KEY:-}" ]; then
  echo "no Mapillary token: set MAPILLARY_API_KEY_TRAIN or add it to $REPO_ROOT/.env" >&2
  exit 1
fi

"$PYTHON" -c "import matplotlib, rich, PIL, numpy" 2>/dev/null || {
  echo "missing dependencies — install with:" >&2
  echo "  uv pip install --python $PYTHON matplotlib rich pillow numpy" >&2
  exit 1
}

POOL="$ENV_DIR/data/pool/sequences.jsonl"
if [ ! -s "$POOL" ]; then
  echo "no sequence pool at $POOL — run dataset/harvest_tiles.py first" >&2
  exit 1
fi

DONE=0
[ -f "$OUT" ] && DONE=$(grep -c . "$OUT" || true)
TODO=$((TASKS - DONE))

# 0.52 s/task and 0.256 MB/frame, both measured on the 200-task build.
"$PYTHON" - "$TODO" "$FRAMES" "$((WORKERS * FRAME_WORKERS))" "$DONE" <<'PY'
import sys
todo, frames, conc, done = (int(v) for v in sys.argv[1:5])
if done:
    print(f"resuming: {done} tasks already built")
if todo <= 0:
    raise SystemExit(0)
secs = todo * 0.52
print(
    f"{todo} tasks to build · {frames} frames each · {conc} concurrent fetches\n"
    f"estimated {secs / 60:.0f} min "
    f"({int(secs // 3600)}h{int(secs % 3600 // 60):02d}m) "
    f"and {todo * frames * 0.256 / 1000:.1f} GB of imagery"
)
PY

echo "pool: $(grep -c . "$POOL") sequences · out: $OUT"
echo

"$PYTHON" dataset/build_tasks.py \
  --tasks "$TASKS" \
  --frames "$FRAMES" \
  --min-frames "$MIN_FRAMES" \
  --mirror all \
  --workers "$WORKERS" \
  --frame-workers "$FRAME_WORKERS" \
  --per-country "$PER_COUNTRY" \
  --per-creator "$PER_CREATOR" \
  --out "$OUT" \
  "$@"

echo
"$PYTHON" - "$OUT" "$ENV_DIR/data/panos" <<'PY'
import collections, json, pathlib, sys

tasks = [
    json.loads(line)
    for line in pathlib.Path(sys.argv[1]).read_text().splitlines()
    if line.strip()
]
cache = pathlib.Path(sys.argv[2])
if not tasks:
    raise SystemExit("no tasks were written")

missing = [
    frame["image_id"]
    for task in tasks
    for frame in task["frames"]
    if not (cache / f"{frame['image_id']}.jpg").exists()
]
countries = collections.Counter(task["country"] for task in tasks)
creators = collections.Counter(task["attribution"]["creator_id"] for task in tasks)
full = sum(1 for task in tasks if len(task["frames"]) >= 24)
total_frames = sum(len(task["frames"]) for task in tasks)

print(f"{len(tasks)} tasks · {len(countries)} countries · {len(creators)} contributors")
print(f"frames: {total_frames} total · {full} tasks have the full 24")
top, top_n = countries.most_common(1)[0]
print(f"largest country: {top} at {top_n} ({100 * top_n / len(tasks):.1f}%)")
print(f"largest contributor: {creators.most_common(1)[0][1]} tasks")
print(f"eval candidates with 24 frames: {full}")

if missing:
    raise SystemExit(f"NOT fully offline: {len(missing)} frames absent from the cache")
print(f"fully offline: all {total_frames} frames are on disk")
PY

echo
echo "next: sample eval out of the pool, which enforces the separation:"
echo "  $PYTHON dataset/split_tasks.py $OUT --eval 200"
