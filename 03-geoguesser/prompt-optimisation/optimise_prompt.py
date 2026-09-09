# SPDX-License-Identifier: BSD-3-Clause

"""Evolve the agentic prompt with GEPA, optimising for the models that need it.

Small models are the reason this exists. A prompt that a frontier model follows
regardless is not doing much work; a 0.8B model that emits prose instead of JSON,
or explores until the turn budget is gone, is failing for prompt reasons that are
fixable. So the optimisation set is weighted towards the small endpoints and the
result is checked on the large ones for regression.

Two things about this task make GEPA a good fit rather than a fashionable one:
the environment returns a scalar reward *and* legible textual feedback ("Pin 1
placed at ... nearest major city ..."), and its failures are self-describing --
unparseable reply, never committed, guessed the wrong hemisphere. That is exactly
the diagnostic material GEPA's reflection step consumes.

Two hazards, both handled here rather than discovered later:

- **Contamination.** Optimising on the eval split would tune the prompt to the
  200 tasks the benchmark is measured on. This uses the *train* split, and
  `--validate` then scores the winner on eval.
- **Placeholder loss.** The prompt is a format string with `{max_turns}` and
  `{tools}`, and the JSON examples inside need doubled braces. A mutation that
  drops them would crash every episode, so a candidate is validated before it is
  run and scored zero with an explanation if it is malformed -- which teaches the
  reflection model the contract instead of failing the run.

Usage:
    export ANTHROPIC_API_KEY=...            # reflection model
    python eval/optimise_prompt.py --models small_models.json \\
        --budget 120 --tasks 8
    python eval/optimise_prompt.py --validate optimised_prompt.txt
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import pathlib
import random
import statistics
import sys
import threading
import types
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
# collect_eval is a sibling in this directory; PROMPTS lives with the
# environment's rollout example.
# The rollout driver and the prompts it uses live one directory over.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "eval"))

from geoeval import build_chat, run_episode  # noqa: E402
from geoguesser_env.client import GeoGuesserEnv  # noqa: E402
from geoeval import PROMPTS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("optimise_prompt")

FORMAT_KEYS = {"max_turns": 12, "tools": "look, zoom, move, pin, guess"}
"""The substitutions the environment makes. A candidate must survive them."""

REQUIRED_ACTIONS = ("look", "pin", "guess")
"""A prompt that stops naming these stops being a prompt for this task."""

BACKGROUND = """The parameter is the system prompt for an agent playing a
geolocation game. Each turn the agent receives a street-level image and must
reply with exactly one JSON action object. Available actions are look (turn the
camera), zoom (narrow the field of view to read text), move (walk along the
road), pin (test a candidate coordinate on a map and read back the country and
nearest city), and guess (commit, ends the episode, scored on distance from the
truth in kilometres).

Hard constraints on the parameter, which the system enforces:

- It is a Python format string. It MUST contain the placeholders {max_turns} and
  {tools} exactly once each, and MUST NOT introduce any other single-braced
  placeholder.
- Literal JSON braces must be DOUBLED: write {{"action": "look"}} so that
  formatting produces {"action": "look"}.
- It must still name the look, pin and guess actions.

A candidate violating any of these scores zero.

The agent's reply is parsed by taking the last JSON object in the text,
preferring one inside a fenced code block. So the prompt should ask for the JSON
object last, rather than forbidding all prose.

Score is the environment reward: roughly exp(-distance_km / 1492.7), minus a
small per-action cost, and zero if no parsable guess was ever made. Failing to
commit before the turn budget runs out therefore scores zero regardless of how
good the reasoning was."""

OBJECTIVE = """Maximise the mean environment reward. The dominant failure modes
to fix, in order of cost: never committing to a guess before the turn budget
runs out; replying with something that is not a parsable JSON action; and
guessing a coordinate in the wrong country or hemisphere when pinning would have
caught it."""


def validate(candidate: str) -> str | None:
    """
    Return a reason the candidate is unusable, or None when it is fine.

    Checked before any episode runs: a malformed format string would raise
    identically on every task, burning the budget and teaching nothing.
    """
    if not isinstance(candidate, str) or len(candidate.strip()) < 80:
        return "the prompt is empty or far too short to describe the task"
    for key in FORMAT_KEYS:
        if "{" + key + "}" not in candidate:
            return (
                f"the placeholder {{{key}}} is missing; it must appear exactly "
                "once so the environment can substitute it"
            )
    try:
        rendered = candidate.format(**FORMAT_KEYS)
    except (KeyError, IndexError, ValueError) as exc:
        return (
            f"the prompt is not a valid format string ({type(exc).__name__}: "
            f"{exc}); literal JSON braces must be doubled, as in "
            '{{"action": "look"}}'
        )
    # Check the action names against a render whose {tools} is a placeholder.
    # Substituting the real tools list ("look, zoom, move, pin, guess") would
    # satisfy this check on its own, so a prompt that had dropped every action
    # description still passed.
    neutral = candidate.format(**{**FORMAT_KEYS, "tools": "<tools>"})
    missing = [a for a in REQUIRED_ACTIONS if a not in neutral]
    if missing:
        return f"the rendered prompt no longer names these actions: {missing}"
    if '{"action"' not in rendered:
        return (
            'the rendered prompt contains no {"action": ...} example, so the '
            "model has no idea what shape to reply in; remember to double the "
            "braces in the source"
        )
    return None


def episode_args(candidate: str, args: argparse.Namespace):
    """A namespace shaped like collect_eval's, so its runner can be reused.

    The candidate travels on this per-call namespace rather than through the
    shared PROMPTS registry: with parallel workers, registry mutation raced and
    a thread could score another thread's candidate.
    """
    return types.SimpleNamespace(
        mode="agentic",
        prompt="v2",
        prompt_text=candidate,
        max_turns=args.max_turns,
        retries=2,
        retry_delay=2.0,
        base_url=args.base_url,
        env_retries=4,
    )


class Runner:
    """Runs one episode per evaluator call, reusing clients per thread."""

    def __init__(self, specs: list[dict[str, Any]], args: argparse.Namespace):
        self._specs = {s["name"]: s for s in specs}
        self._args = args
        self._local = threading.local()
        # Every cached client holds a server session. Tracked centrally so the
        # run can hand them all back; a long search otherwise accumulates one
        # per (thread, model) until the server refuses new ones.
        self._opened: list[Any] = []
        self._opened_lock = threading.Lock()

    def _clients(self, name: str):
        # A client per thread: sharing an environment across threads interleaves
        # resets and silently corrupts every episode in flight.
        cache = getattr(self._local, "cache", None)
        if cache is None:
            cache = self._local.cache = {}
        if name not in cache:
            env = GeoGuesserEnv(base_url=self._args.base_url)
            with self._opened_lock:
                self._opened.append(env)
            cache[name] = (env, build_chat(self._specs[name]))
        return cache[name]

    def close(self) -> None:
        """Hand every session back to the server."""
        with self._opened_lock:
            envs, self._opened = self._opened, []
        for env in envs:
            try:
                env.close()
            except Exception:  # noqa: BLE001 - best effort on teardown
                pass

    def play(self, candidate: str, model_name: str, index: int) -> dict[str, Any]:
        """One episode with the candidate prompt in place of a registered one."""
        env, chat = self._clients(model_name)
        return run_episode(
            env,
            chat,
            self._specs[model_name],
            self._args.split,
            index,
            episode_args(candidate, self._args),
            None,
        )


def describe(record: dict[str, Any]) -> str:
    """
    Turn one episode into the diagnostic text GEPA reflects on.

    The reward alone says a prompt was bad; this says *how*, which is the whole
    reason to use reflective optimisation rather than a scalar search.
    """
    outcome = record["outcome"]
    lines = [
        f"model={record['model_name']} task={record['task']['index']} "
        f"country={record['task'].get('country')}",
        f"reward={outcome['reward']:.3f} distance="
        f"{outcome['distance_km'] if outcome['distance_km'] is not None else '-'} km "
        f"turns_used={outcome['turns_used']} "
        f"unparseable={outcome['turns_unparseable']} "
        f"forced_guess={outcome['forced_guess']} "
        f"pins={outcome.get('n_pins')} looks={outcome.get('n_looks')}",
    ]
    if outcome["forced_guess"]:
        lines.append(
            "FAILURE: ran out of turns without ever guessing, which scores zero."
        )
    if outcome["turns_unparseable"]:
        bad = [t for t in record["turns"] if t["status"] == "unparseable"]
        lines.append(
            f"FAILURE: {len(bad)} replies were not parsable JSON actions. "
            f"First offending reply: {(bad[0].get('model') or {}).get('reply', '')[:300]!r}"
        )
    if outcome.get("guess_country") and not outcome.get("country_hit"):
        lines.append(
            f"MISS: guessed in {outcome['guess_country']} but the truth was in "
            f"{record['task'].get('country')}."
        )
    if outcome.get("n_pins") == 0 and not outcome["forced_guess"]:
        lines.append(
            "NOTE: never pinned. Pinning reads back the country and nearest city "
            "for a candidate and would have caught a wrong-country guess."
        )
    for turn in record["turns"][1:]:
        action = (turn.get("action") or {}).get("action")
        if action:
            lines.append(f"  turn {turn['turn']}: {action} -> {turn.get('feedback')}")
    return "\n".join(lines)


# The search is scored on a two-scale curve, not the shipped one. Measured over
# 2,600 episodes on the eval split, 30-38% of these models' guesses land where
# the action cost exceeds exp(-d/1492.7), so the reward is clamped to exactly 0.0
# -- and on those tasks every candidate prompt scores identically and GEPA is
# choosing blind. The long scale keeps a gradient on the wrong continent, which
# is precisely where a small model needs the prompt to help it.
SEARCH_DECAY_KM = 1492.7
SEARCH_LONG_DECAY_KM = 5000.0


def search_score(record: dict[str, Any]) -> float:
    """Reward GEPA optimises against. Reported scores still use the game curve."""
    outcome = record.get("outcome") or {}
    distance = outcome.get("distance_km")
    if distance is None:
        # No usable guess at all. Worse than any guess, and the one failure a
        # prompt can most directly fix.
        return 0.0
    short = math.exp(-distance / SEARCH_DECAY_KM)
    long = math.exp(-distance / SEARCH_LONG_DECAY_KM)
    cost = outcome.get("action_cost") or 0.0
    return 0.5 * (short + long) * (1.0 - min(max(cost, 0.0), 0.5))


def build_dataset(args: argparse.Namespace, specs: list[dict[str, Any]]):
    """(model, task) pairs drawn from the TRAIN split, never eval."""
    rng = random.Random(args.seed)
    env = GeoGuesserEnv(base_url=args.base_url)
    total = env.num_tasks(args.split)
    indices = rng.sample(range(total), min(args.tasks * 2, total))
    train_idx, val_idx = indices[: args.tasks], indices[args.tasks : args.tasks * 2]
    dataset = [{"model": s["name"], "index": i} for s in specs for i in train_idx]
    valset = [{"model": s["name"], "index": i} for s in specs for i in val_idx]
    rng.shuffle(dataset)
    return dataset, valset


def optimise(args: argparse.Namespace) -> None:
    """Run the search and write the winning prompt out."""
    import gepa
    from gepa.optimize_anything import GEPAConfig, log, optimize_anything

    specs = json.loads(pathlib.Path(args.models).read_text())
    runner = Runner(specs, args)
    dataset, valset = build_dataset(args, specs)
    logger.info(
        "optimising on %d (model, task) pairs from the %s split, "
        "validating on %d, budget %d evaluations",
        len(dataset),
        args.split,
        len(valset),
        args.budget,
    )

    def evaluator(candidate, example=None, **_: Any):
        reason = validate(candidate if isinstance(candidate, str) else str(candidate))
        if reason is not None:
            log(f"REJECTED: {reason}")
            return 0.0
        try:
            record = runner.play(candidate, example["model"], example["index"])
        except Exception as exc:  # noqa: BLE001 - a bad episode is a datum
            log(f"episode raised {type(exc).__name__}: {str(exc)[:200]}")
            return 0.0
        log(describe(record))
        return search_score(record)

    config = GEPAConfig()
    config.engine.max_metric_calls = args.budget
    config.engine.display_progress_bar = True
    config.engine.raise_on_exception = False
    config.engine.max_workers = args.workers
    config.engine.run_dir = str(args.out_dir / "gepa")
    config.reflection.reflection_lm = gepa.optimize_anything.make_litellm_lm(
        args.reflection_lm, max_tokens=8192
    )

    try:
        result = optimize_anything(
            seed_candidate=PROMPTS[args.seed_prompt],
            evaluator=evaluator,
            dataset=dataset,
            valset=valset,
            objective=OBJECTIVE,
            background=BACKGROUND,
            config=config,
        )
    finally:
        runner.close()

    best = result.best_candidate
    text = best if isinstance(best, str) else json.dumps(best)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "optimised_prompt.txt"
    out.write_text(text)
    logger.info("\nbest score: %s", getattr(result, "best_score", "?"))
    logger.info("prompt -> %s (%d chars)", out, len(text))
    reason = validate(text)
    if reason:
        logger.error("the winning prompt does not validate: %s", reason)


def validate_prompt_file(args: argparse.Namespace) -> None:
    """Score a saved prompt against the seed on the eval split."""
    specs = json.loads(pathlib.Path(args.models).read_text())
    candidate = pathlib.Path(args.validate).read_text()
    reason = validate(candidate)
    if reason:
        raise SystemExit(f"prompt does not validate: {reason}")
    runner = Runner(specs, args)
    rng = random.Random(args.seed)
    env = GeoGuesserEnv(base_url=args.base_url)
    indices = rng.sample(range(env.num_tasks("eval")), args.tasks)

    logger.info("scoring on %d eval tasks per model", len(indices))
    for label, prompt in (
        ("seed", PROMPTS[args.seed_prompt]),
        ("optimised", candidate),
    ):
        for spec in specs:
            rewards = []
            for index in indices:
                try:
                    record = runner.play(prompt, spec["name"], index)
                    rewards.append(float(record["outcome"]["reward"] or 0.0))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "  %s %s task %d: %r", label, spec["name"], index, exc
                    )
            if rewards:
                logger.info(
                    "  %-10s %-18s mean reward %.3f (n=%d)",
                    label,
                    spec["name"],
                    statistics.fmean(rewards),
                    len(rewards),
                )


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default=str(ROOT / "eval" / "models.example.json"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8130")
    parser.add_argument(
        "--split",
        default="train",
        help="Split to optimise on. Deliberately NOT eval: tuning on the "
        "benchmark is contamination.",
    )
    parser.add_argument("--tasks", type=int, default=8, help="Tasks per model.")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--budget", type=int, default=120)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--seed-prompt", default="v2", choices=sorted(PROMPTS))
    parser.add_argument("--reflection-lm", default="anthropic/claude-sonnet-5")
    parser.add_argument(
        "--out-dir", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent / "runs"
    )
    parser.add_argument("--validate", default=None, help="Score a saved prompt file.")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY") and "anthropic" in args.reflection_lm:
        raise SystemExit("ANTHROPIC_API_KEY is needed for the reflection model")
    if args.validate:
        validate_prompt_file(args)
    else:
        optimise(args)


if __name__ == "__main__":
    main()
