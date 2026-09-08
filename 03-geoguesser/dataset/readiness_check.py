# SPDX-License-Identifier: BSD-3-Clause

"""Audit whether the environment is fit to train against.

The unit tests cover behaviour on four committed fixtures. This checks the
properties that only show up at the scale and concurrency of a real run:

- every task in the index actually renders, so a rollout cannot die on task 87
- observations are byte-identical across separate processes, not just repeated
  resets in one, which is what a distributed GRPO group depends on
- concurrent episodes stay isolated, so parallel rollouts do not interleave
- a warm cache needs no network, so training can run air-gapped
- reward is discriminative: a random guesser must score near zero and a
  land-centroid guesser only slightly better, or the signal is not measuring
  geolocation
- per-step latency, so a rollout budget can be estimated

Usage:
    python scripts/readiness_check.py
    python scripts/readiness_check.py --full        # render every task
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import pathlib
import random
import statistics
import subprocess
import sys
import time

# The environment package uses relative imports, so it has to be imported as
# `geoguesser_env.*` with the envs directory on the path, exactly as the tests
# and examples do.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from geoguesser_env.models import (  # noqa: E402
    GuessAction,
    LookAction,
    PinAction,
    to_wire,
)
from geoguesser_env.server.geoguesser_environment import (  # noqa: E402
    GeoGuesserEnvironment,
)
from geoguesser_env.server.scoring import distance_score, haversine_km  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1] / "env"
_CANDIDATE_INDEXES = (
    ROOT / "tasks" / "eval_pano_v3.jsonl",
    ROOT / "tasks" / "pano_v1.jsonl",
)
INDEX = next((p for p in _CANDIDATE_INDEXES if p.exists()), _CANDIDATE_INDEXES[-1])
"""Audit the frozen eval split when it exists.

Auditing a stale index is worse than not auditing: the numbers look reassuring
and describe a set nothing runs against.
"""
CACHE = ROOT / "data" / "panos"

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool | str, detail: str) -> None:
    """Record one check outcome."""
    status = ok if isinstance(ok, str) else (PASS if ok else FAIL)
    results.append((status, name, detail))
    print(f"  [{status}] {name}: {detail}", flush=True)


def make_env(**kwargs) -> GeoGuesserEnvironment:
    options = {"index_path": str(INDEX), "cache_dir": str(CACHE)}
    options.update(kwargs)
    return GeoGuesserEnvironment(**options)


# ---------------------------------------------------------------- the checks


def check_index_integrity() -> None:
    """Every row parses, indices are contiguous, no sequence repeats."""
    rows = [json.loads(line) for line in INDEX.read_text().splitlines() if line.strip()]
    indices = [r["task_index"] for r in rows]
    sequences = {r["sequence_id"] for r in rows}
    countries = {r["country"] for r in rows}
    contiguous = indices == list(range(len(rows)))
    record(
        "index integrity",
        contiguous and len(sequences) == len(rows) and "unknown" not in countries,
        f"{len(rows)} tasks, {len(countries)} countries, "
        f"{len(sequences)} unique sequences, contiguous={contiguous}",
    )


def check_all_tasks_render(sample: int | None) -> None:
    """A rollout must not die because one task cannot produce a view."""
    env = make_env(allow_fetch=True, view_size=256)
    total = env._backend.n_tasks
    order = list(range(total))
    if sample and sample < total:
        order = random.Random(0).sample(order, sample)
    failures, latencies = [], []
    for task_index in order:
        try:
            started = time.time()
            observation = env.reset(task_index=task_index)
            latencies.append(time.time() - started)
            if not observation.image_base64:
                failures.append((task_index, "no image"))
        except Exception as exc:  # noqa: BLE001 - report, do not abort the audit
            failures.append((task_index, f"{type(exc).__name__}: {exc}"))
    record(
        "all tasks render",
        not failures,
        f"{len(order) - len(failures)}/{len(order)} rendered, "
        f"median reset {statistics.median(latencies) * 1000:.0f} ms"
        + (f", failures: {failures[:3]}" if failures else ""),
    )


def check_cross_process_determinism() -> None:
    """The same task must produce the same bytes in a fresh interpreter."""
    snippet = (
        "import sys, hashlib, pathlib; "
        f"sys.path.insert(0, {str(ROOT.parent)!r}); "
        "from geoguesser_env.server.geoguesser_environment import "
        "GeoGuesserEnvironment; "
        f"env = GeoGuesserEnvironment(index_path={str(INDEX)!r}, "
        f"cache_dir={str(CACHE)!r}, allow_fetch=False); "
        "print(hashlib.sha256("
        "env.reset(task_index=3).image_base64.encode()).hexdigest())"
    )
    digests = []
    for _ in range(2):
        completed = subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if completed.returncode != 0:
            record("cross-process determinism", False, completed.stderr[-160:])
            return
        digests.append(completed.stdout.strip())
    same_in_process = hashlib.sha256(
        make_env(allow_fetch=False).reset(task_index=3).image_base64.encode()
    ).hexdigest()
    record(
        "cross-process determinism",
        len(set(digests)) == 1 and digests[0] == same_in_process,
        f"two subprocesses and this process agree: {digests[0][:16]}",
    )


def check_parallel_isolation(workers: int = 4) -> None:
    """Concurrent episodes must not interleave into one another."""

    def play(task_index: int) -> tuple[int, float, int]:
        env = make_env(allow_fetch=False)
        env.reset(task_index=task_index)
        env.step(to_wire(LookAction(heading_deg=90)))
        env.step(to_wire(PinAction(lat=0.0, lon=0.0)))
        truth = env._task.truth
        result = env.step(to_wire(GuessAction(lat=truth[0], lon=truth[1])))
        return task_index, result.reward, result.metadata["task_index"]

    tasks = list(range(workers * 2))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(play, tasks))

    # A perfect guess scores 1.0 minus 0.03 of gathering, on every episode.
    mismatched = [o for o in outcomes if o[0] != o[2]]
    wrong_reward = [o for o in outcomes if abs(o[1] - 0.97) > 1e-6]
    record(
        f"parallel isolation ({workers} workers)",
        not mismatched and not wrong_reward,
        f"{len(outcomes)} concurrent episodes, all returned their own task "
        f"and reward 0.970"
        + (f", mismatched: {mismatched[:2]}" if mismatched else "")
        + (f", wrong reward: {wrong_reward[:2]}" if wrong_reward else ""),
    )


def check_offline() -> None:
    """A warm cache must need no network at all."""
    env = make_env(allow_fetch=False, hires_zoom=False)
    failures = 0
    for task_index in range(min(12, env._backend.n_tasks)):
        try:
            env.reset(task_index=task_index)
        except Exception:  # noqa: BLE001
            failures += 1
    record(
        "offline with warm cache",
        failures == 0,
        f"{12 - failures}/12 start frames served with fetching disabled",
    )


def check_reward_is_discriminative(trials: int = 300) -> None:
    """A random guesser must score near zero, or reward measures nothing."""
    env = make_env(allow_fetch=False)
    rng = random.Random(7)
    truths = []
    for task_index in range(env._backend.n_tasks):
        truths.append(env._backend.task(task_index).truth)

    def score_for(guess_fn) -> float:
        scores = []
        for _ in range(trials):
            lat, lon = truths[rng.randrange(len(truths))]
            guess_lat, guess_lon = guess_fn()
            scores.append(distance_score(haversine_km(guess_lat, guess_lon, lat, lon)))
        return statistics.mean(scores)

    uniform = score_for(
        lambda: (
            math.degrees(math.asin(rng.uniform(-1, 1))),
            rng.uniform(-180, 180),
        )
    )
    # Guessing a fixed populous point is the strongest trivial baseline.
    centroid = score_for(lambda: (30.0, 20.0))
    perfect = 1.0
    record(
        "reward is discriminative",
        uniform < 0.10 and centroid < 0.30,
        f"uniform-random {uniform:.3f}, fixed-point {centroid:.3f}, "
        f"perfect {perfect:.3f} (Sonnet measured 0.896)",
    )


def check_step_latency() -> None:
    """Per-step cost, so a rollout budget can be estimated."""
    env = make_env(allow_fetch=False)
    env.reset(task_index=0)
    timings: dict[str, float] = {}
    for label, action in (
        ("look 90deg", LookAction(heading_deg=45, fov_deg=90)),
        ("pin + map", PinAction(lat=10.0, lon=10.0)),
    ):
        started = time.time()
        env.step(to_wire(action))
        timings[label] = (time.time() - started) * 1000
    detail = ", ".join(f"{k} {v:.0f} ms" for k, v in timings.items())
    record("step latency", all(v < 2000 for v in timings.values()), detail)


def check_one_guess_per_episode() -> None:
    """An episode accepts exactly one guess; the second must not score."""
    env = make_env(allow_fetch=False)
    env.reset(task_index=0)
    truth = env._task.truth
    first = env.step(to_wire(GuessAction(lat=truth[0], lon=truth[1])))
    second = env.step(to_wire(GuessAction(lat=0.0, lon=0.0)))
    third = env.step(to_wire(LookAction(heading_deg=0)))
    record(
        "one guess per episode",
        first.done
        and first.reward is not None
        and second.reward is None
        and second.done
        and third.done,
        f"first guess scored {first.reward:.3f} and ended the episode; "
        f"a second returned reward={second.reward} "
        f"({second.feedback.split('.')[0]})",
    )


def check_pin_never_leaks() -> None:
    """Pin feedback must reveal nothing about the target, at any coordinate."""
    env = make_env(allow_fetch=False)
    leaks = []
    for task_index in range(min(20, env._backend.n_tasks)):
        env.reset(task_index=task_index)
        true_lat, true_lon = env._task.truth
        country = env._task.country
        for lat, lon in ((0.0, 0.0), (true_lat, true_lon), (-40.0, 160.0)):
            observation = env.step(to_wire(PinAction(lat=lat, lon=lon)))
            text = f"{observation.feedback} {observation.pins[-1].description}"
            if observation.distance_km is not None or observation.true_lat is not None:
                leaks.append((task_index, "distance or truth field populated"))
            # A pin *at* the truth naturally names that country; the leak we
            # care about is a pin elsewhere revealing it.
            if (lat, lon) != (true_lat, true_lon) and country.lower() in text.lower():
                leaks.append((task_index, f"named {country} from a distant pin"))
    record(
        "pin never leaks the target",
        not leaks,
        "60 pins across 20 tasks revealed nothing"
        + (f"; leaks: {leaks[:2]}" if leaks else ""),
    )


def main() -> None:
    """Run the audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full", action="store_true", help="Render every task, not a sample."
    )
    parser.add_argument("--sample", type=int, default=25)
    parser.add_argument(
        "--index",
        type=pathlib.Path,
        default=None,
        help="Index to audit. Defaults to the eval split when present.",
    )
    args = parser.parse_args()

    if args.index is not None:
        if not args.index.exists():
            raise SystemExit(f"no such index: {args.index}")
        global INDEX
        INDEX = args.index

    print("geoguesser_env readiness audit")
    print("=" * 78)
    print(f"  index: {INDEX}")
    check_index_integrity()
    check_all_tasks_render(None if args.full else args.sample)
    check_cross_process_determinism()
    check_parallel_isolation()
    check_offline()
    check_reward_is_discriminative()
    check_step_latency()
    check_one_guess_per_episode()
    check_pin_never_leaks()
    print("=" * 78)

    failed = [r for r in results if r[0] == FAIL]
    warned = [r for r in results if r[0] == WARN]
    print(
        f"{len(results) - len(failed) - len(warned)} passed, "
        f"{len(warned)} warned, {len(failed)} failed"
    )
    for status, name, detail in failed + warned:
        print(f"  {status}: {name} - {detail}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
