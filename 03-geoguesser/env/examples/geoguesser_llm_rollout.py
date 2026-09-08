# SPDX-License-Identifier: BSD-3-Clause

"""Run real rollouts against a vision model and report the rewards.

Two providers, one action protocol, so the same episode can be compared across
models:

- `anthropic` talks to the Messages API directly.
- `hf` talks to any OpenAI-compatible endpoint, defaulting to the Hugging Face
  router, which serves open models such as Qwen.

Two modes:

- `single_shot` is one view, one guess. This is the shape a GRPO run wants and
  the cheapest way to compare models.
- `agentic` gives the model the tool surface and lets it look around, walk,
  and pin candidates before committing, one JSON action per turn.

Usage:
    export ANTHROPIC_API_KEY=... HF_TOKEN=...

    python examples/geoguesser_llm_rollout.py \\
        --provider anthropic --model claude-sonnet-5 --episodes 5

    python examples/geoguesser_llm_rollout.py \\
        --provider hf --model "Qwen/Qwen3.5-9B:together" --episodes 5

    python examples/geoguesser_llm_rollout.py \\
        --provider anthropic --mode agentic --episodes 3 --max-turns 8
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import pathlib
import re
import statistics
import sys
import threading
import time
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from geoguesser_env.models import (  # noqa: E402
    GuessAction,
    LookAction,
    MeasureAction,
    MoveAction,
    PanAction,
    PinAction,
    to_wire,
    ViewMapAction,
    ZoomAction,
)
from geoguesser_env.server.geoguesser_environment import (  # noqa: E402
    GeoGuesserEnvironment,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]

SINGLE_SHOT_PROMPT = """You are playing a geolocation game. This is a street-level
photograph taken somewhere in the world. Work out where it was taken.

Reason briefly about the evidence: language and script on signage, which side of
the road traffic drives on, vegetation and climate, road markings, architecture,
utility poles, vehicle number plates, terrain.

Then give your answer as coordinates on the last line, exactly like this:
<guess>LATITUDE, LONGITUDE</guess>"""

AGENTIC_PROMPT = """You are playing a geolocation game. You have been dropped at
an unknown street-level location and must work out where you are.

Reply with exactly one JSON object per turn, and nothing else:

  {{"action": "look", "heading_deg": 90, "fov_deg": 90}}   look in a direction
  {{"action": "zoom", "fov_deg": 30}}                      zoom to read signage
  {{"action": "move", "direction": "forward", "meters": 20}} walk along the road
  {{"action": "pin", "lat": 12.34, "lon": 56.78, "span_deg": 2}} check a candidate;
      span_deg is the map zoom, and below about 4 you get roads and town names
  {{"action": "guess", "lat": 12.34, "lon": 56.78}}        commit, ends the episode

Looking, zooming and pinning each cost a little reward, so gather what you need
and then commit.

Pinning is worth using before you guess: it tells you what is actually at a
coordinate — the country, the nearest city, and how far your candidate is from
your previous one — which catches a coordinate that lands in the sea or in the
wrong country. It does not tell you whether you are right.

You have {max_turns} turns. Available tools: {tools}

Output rules, which matter more than they look:
- Reply with the JSON object and nothing else. No explanation, no markdown, no
  code fence, no commentary before or after.
- One action per turn. An action that does not parse wastes the turn.
- Coordinates are decimal degrees, negative for south and west."""


AGENTIC_PROMPT_V2 = """You are dropped at a random street-level location on Earth.
Work out where you are, then commit to coordinates.

You have {max_turns} turns left. Each turn, reply with one JSON object.

{{"action": "look", "heading_deg": 0-359, "fov_deg": 90}}
  Turn the camera. This is how you gather evidence: script and language on
  signage, which side traffic drives on, number plates, road markings,
  vegetation, architecture, utility poles, terrain.
{{"action": "zoom", "fov_deg": 30}}
  Narrow the view to read distant detail - a shop name, a road number, a plate.
  A 90 degree view almost never resolves text.
{{"action": "move", "direction": "forward", "meters": 20}}
  Walk along the road, to reach a sign or junction you cannot read from here.
{{"action": "pin", "lat": 48.1, "lon": 11.6, "span_deg": 2}}
  Test a candidate on the map. It tells you what is actually at that
  coordinate: the country, the nearest city, and how far it is from your last
  pin. span_deg is the zoom; below about 4 you also get roads and town names.
  It does NOT tell you whether you are right.
  Pin as often as you like. This is the main tool: pin a rough candidate, read
  back the country and nearest city, then pin a better one. Iterating this way
  is how "somewhere in southern Germany" becomes a real coordinate, and it also
  catches a guess that lands in the sea or in the wrong country.
{{"action": "guess", "lat": 48.14, "lon": 11.58}}
  Your final answer. Ends the episode, scored on distance from the truth.

Every action costs a little reward, so gather what you need and then commit.
Running out of turns without guessing scores zero, so guess before you must.

Available this episode: {tools}

Coordinates are decimal degrees, negative for south and west. Think as briefly
as you like, but the JSON object must be the last thing in your reply."""
"""Version 2. Differences from v1, each fixing an observed failure:

- v1 said "no explanation, no markdown, no code fence" while the parser
  *prefers* a fenced block and takes the last object. Small models obeyed the
  instruction, reasoning models ignored it, and neither was what the parser
  wanted. v2 permits brief reasoning and asks only that the JSON come last.
- v1 listed no evidence to look for, though the single-shot prompt did. The
  multi-turn agent is the one that can act on "zoom to read the plate", so the
  list belongs here more than there.
- v1 mentioned pinning once, in passing. It is the tool that converts a vague
  region into a coordinate, and it is repeatable, so v2 says so explicitly.
"""

PROMPTS = {"v1": AGENTIC_PROMPT, "v2": AGENTIC_PROMPT_V2}
"""Prompts by version. An eval number is only comparable within one version, so
the version is recorded on every episode."""


# ---------------------------------------------------------------- providers


def media_type(image_b64: str) -> str:
    """
    Detect an encoded image's media type from its own bytes.

    Views come back as JPEG and maps as PNG, so a hardcoded type is wrong half
    the time — and Anthropic rejects a mislabelled image outright rather than
    sniffing it.

    Args:
        image_b64 (`str`):
            Base64-encoded image.

    Returns:
        `str`: Either `"image/png"` or `"image/jpeg"`.
    """
    try:
        head = base64.b64decode(image_b64[:24], validate=False)
    except Exception:  # noqa: BLE001 - fall back rather than fail a rollout
        return "image/jpeg"
    return "image/png" if head.startswith(b"\x89PNG") else "image/jpeg"


class AnthropicChat:
    """Thin wrapper over the Anthropic Messages API."""

    def __init__(self, model: str, max_tokens: int = 1024):
        from anthropic import Anthropic

        self._client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = model
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return f"anthropic/{self._model}"

    def __call__(self, prompt: str, images: list[str]) -> str:
        content: list[dict[str, Any]] = []
        for image in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type(image),
                        "data": image,
                    },
                }
            )
        content.append({"type": "text", "text": prompt})
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        return "".join(
            block.text
            for block in message.content
            if getattr(block, "type", "") == "text"
        )


class OpenAICompatChat:
    """Thin wrapper over any OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        model: str,
        base_url: str = "https://router.huggingface.co/v1",
        api_key_env: str = "HF_TOKEN",
        max_tokens: int = 1024,
    ):
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=os.environ[api_key_env])
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = base_url
        self.last_finish_reason = None

    @property
    def name(self) -> str:
        return f"{self._base_url.split('//')[-1].split('/')[0]}/{self._model}"

    def __call__(self, prompt: str, images: list[str]) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type(image)};base64,{image}"},
                }
            )
        completion = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        choice = completion.choices[0]
        text = choice.message.content or ""
        # Reasoning models put their chain of thought in a separate field and
        # can exhaust the token budget before emitting any content at all, so a
        # short max_tokens looks exactly like a model that cannot see images.
        # Fall back to the reasoning text, which usually still carries the
        # answer, and say so when the budget was the limit.
        if not text.strip():
            reasoning = getattr(choice.message, "reasoning_content", None) or getattr(
                choice.message, "reasoning", None
            )
            if reasoning:
                text = str(reasoning)
            elif choice.finish_reason == "length":
                text = ""
        self.last_finish_reason = choice.finish_reason
        return text


def build_chat(args: argparse.Namespace):
    """Construct the provider named on the command line."""
    if args.provider == "anthropic":
        return AnthropicChat(args.model, max_tokens=args.max_tokens)
    return OpenAICompatChat(
        args.model,
        base_url=args.base_url,
        api_key_env=args.api_key_env,
        max_tokens=args.max_tokens,
    )


# ------------------------------------------------------------------ rollouts


_JSON_OBJECT = re.compile(r"\{[^{}]*\}", re.DOTALL)


def parse_action(reply: str) -> dict[str, Any] | None:
    """
    Pull the intended JSON action out of a model reply.

    A fenced block wins, since a model that formats its answer means it. Failing
    that, the *last* action object in the text is taken rather than the first:
    when the reply is a reasoning trace, earlier objects are usually drafts the
    model then argued itself out of, and the decision comes last.

    Args:
        reply (`str`):
            The raw model reply, possibly a chain of thought.

    Returns:
        `dict` or `None`: The action object, or `None` when none is present.
    """
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", reply, re.DOTALL)
    for candidate in reversed(fenced):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "action" in parsed:
            return parsed

    for candidate in reversed(_JSON_OBJECT.findall(reply)):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "action" in parsed:
            return parsed
    return None


# The observation advertises `available_tools` using the environment's MCP tool
# names, while the JSON action protocol uses the wire op names. A model that
# reads `available_tools` and believes it therefore emits `place_pin` where the
# parser wants `pin`, and gets its turn rejected for being obedient. Measured
# over a 36-episode smoke run: 11 of 302 turns lost to exactly this, and 52% of
# Qwen3.5-2B's turns rejected in total. Accept both spellings.
ACTION_ALIASES = {
    "place_pin": "pin",
    "submit_guess": "guess",
    "final_guess": "guess",
    # Same question -- what is at this coordinate -- and view_map answers it
    # with the country plus a map, so it subsumes the MCP-only tool.
    "reverse_geocode": "view_map",
    "turn": "pan",
    "rotate": "pan",
    "close_pins": "clear_pins",
}

# Advertised over MCP but genuinely inexpressible as a one-shot JSON action.
# Named in the error so the transcript tells the model what to use instead.
UNMAPPABLE = {
    "list_pins": "the pins are already listed in every observation",
    "clear_pins": "pins cannot be cleared; place a new one instead",
}


def to_env_action(spec: dict[str, Any]):
    """
    Translate a model action into a typed environment action.

    Forgiving on names, strict on effect: an alias or an out-of-range number is
    corrected rather than rejected, because a wasted turn is scored the same as
    bad geolocation and so hides one failure inside another. An action that
    cannot be expressed at all still raises, with a message naming the
    alternative.
    """
    kind = str(spec.get("action", "")).lower()
    kind = ACTION_ALIASES.get(kind, kind)
    if kind in UNMAPPABLE:
        raise ValueError(f"{kind!r} is not a JSON action: {UNMAPPABLE[kind]}")

    def _need(*names: str) -> list[float]:
        """Required numeric fields, or an error that names what was missing.

        A bare `KeyError: 'lat_a'` reaches the model as an opaque failure. The
        transcript feeds these errors back, so saying which fields the action
        needs is the difference between a model correcting itself next turn and
        repeating the same malformed call.
        """
        missing = [n for n in names if spec.get(n) is None]
        if missing:
            raise ValueError(
                f"{kind!r} needs {', '.join(names)}; missing {', '.join(missing)}."
            )
        try:
            return [float(spec[n]) for n in names]
        except (TypeError, ValueError):
            got = {n: spec.get(n) for n in names}
            raise ValueError(
                f"{kind!r} needs numbers for {names}, got {got}."
            ) from None

    def _clamp(value: float, low: float, high: float) -> float:
        """Numbers the model got slightly wrong are clamped, not rejected.

        A field of view of 5 degrees is a clear request for maximum zoom, and
        failing the turn over it teaches the model nothing about geography.
        """
        return max(low, min(high, value))

    if kind == "pan":
        return PanAction(
            delta_deg=_clamp(float(spec.get("delta_deg", 90.0)), -3600, 3600)
        )
    if kind == "measure":
        lat_a, lon_a, lat_b, lon_b = _need("lat_a", "lon_a", "lat_b", "lon_b")
        return MeasureAction(
            lat_a=_clamp(lat_a, -90, 90),
            lon_a=_clamp(lon_a, -180, 180),
            lat_b=_clamp(lat_b, -90, 90),
            lon_b=_clamp(lon_b, -180, 180),
        )
    if kind == "look":
        return LookAction(
            heading_deg=_clamp(float(spec.get("heading_deg", 0.0)), -3600, 3600),
            pitch_deg=_clamp(float(spec.get("pitch_deg", 0.0)), -90, 90),
            fov_deg=_clamp(float(spec.get("fov_deg", 90.0)), 10, 120),
        )
    if kind == "zoom":
        return ZoomAction(fov_deg=_clamp(float(spec.get("fov_deg", 30.0)), 10, 120))
    if kind == "move":
        return MoveAction(
            direction=str(spec.get("direction", "forward")),
            meters=_clamp(float(spec.get("meters", 20.0)), 0.1, 500),
        )
    if kind == "pin":
        lat, lon = _need("lat", "lon")
        return PinAction(
            lat=_clamp(lat, -90, 90),
            lon=_clamp(lon, -180, 180),
            span_deg=_clamp(float(spec.get("span_deg", 7.0)), 0.03, 180),
        )
    if kind == "view_map":
        lat, lon = _need("lat", "lon")
        return ViewMapAction(
            lat=_clamp(lat, -90, 90),
            lon=_clamp(lon, -180, 180),
            span_deg=_clamp(float(spec.get("span_deg", 7.0)), 0.06, 180),
        )
    if kind == "guess":
        lat, lon = _need("lat", "lon")
        return GuessAction(
            lat=_clamp(lat, -90, 90),
            lon=_clamp(lon, -180, 180),
            confidence=spec.get("confidence"),
            reasoning=spec.get("reasoning"),
        )
    raise ValueError(
        f"unknown action: {kind!r}. Valid actions: look, pan, zoom, move, pin, "
        f"view_map, measure, guess."
    )


def _turn_record(
    index: int,
    action: Any,
    reply: str,
    observation: Any,
) -> dict[str, Any]:
    """One row of a trace: what the model saw, said, did and got back."""
    return {
        "turn": index,
        "reply": reply.strip(),
        "action": action,
        "feedback": getattr(observation, "feedback", ""),
        "heading_deg": getattr(observation, "heading_deg", None),
        "fov_deg": getattr(observation, "fov_deg", None),
        "steps_remaining": getattr(observation, "steps_remaining", None),
        "action_cost": getattr(observation, "action_cost", None),
        "image_kind": getattr(observation, "image_kind", "none"),
        "image_base64": getattr(observation, "image_base64", None),
        "reward": getattr(observation, "reward", None),
        "distance_km": getattr(observation, "distance_km", None),
    }


def run_single_shot(env, chat, task_index: int, verbose: bool) -> dict[str, Any]:
    """One view, one guess."""
    observation = env.reset(task_index=task_index)
    opening = _turn_record(0, {"action": "reset"}, "", observation)
    started = time.time()
    reply = chat(SINGLE_SHOT_PROMPT, [observation.image_base64])
    latency = time.time() - started
    result = env.step(to_wire(GuessAction(response=reply)))
    trace = [opening, _turn_record(1, {"action": "guess"}, reply, result)]
    return {
        "trace": trace,
        "task_index": task_index,
        "country": env._task.country,
        "reward": result.reward or 0.0,
        "distance_km": result.distance_km,
        "parsed_ok": result.parsed_ok,
        "latency_s": latency,
        "turns": 1,
        "reply": reply.strip(),
    }


def run_agentic(
    env, chat, task_index: int, max_turns: int, verbose: bool
) -> dict[str, Any]:
    """Let the model look around and pin before committing."""
    observation = env.reset(task_index=task_index)
    trace: list[dict[str, Any]] = [
        _turn_record(0, {"action": "reset"}, "", observation)
    ]
    transcript: list[str] = []
    started = time.time()
    turns = 0

    for turn in range(max_turns):
        turns = turn + 1
        prompt = AGENTIC_PROMPT.format(
            max_turns=max_turns - turn,
            tools=", ".join(observation.available_tools),
        )
        if transcript:
            prompt += "\n\nWhat has happened so far:\n" + "\n".join(transcript[-8:])
        prompt += (
            f"\n\nYou are facing {observation.heading_deg:.0f} degrees with a "
            f"{observation.fov_deg:.0f} degree field of view. "
            f"{observation.steps_remaining} actions remain."
        )
        turns_left = max_turns - turn
        if turns_left <= 2:
            # Exploring until the budget runs out scores zero, which is a
            # prompting failure rather than a capability one. Open models
            # routinely need to be told the deadline is now.
            prompt += (
                f"\n\nWARNING: only {turns_left} turn(s) left. You must reply "
                'with {"action": "guess", "lat": ..., "lon": ...} now, or you '
                "score zero. Give your best estimate even if you are unsure."
            )

        images = [observation.image_base64] if observation.image_base64 else []
        reply = chat(prompt, images)
        spec = parse_action(reply)
        if spec is None:
            transcript.append(f"turn {turns}: reply was not a JSON action, ignored")
            if verbose:
                print(
                    f"    turn {turns}: unparseable -> {reply.strip()[:90]!r}",
                    flush=True,
                )
            continue

        try:
            action = to_env_action(spec)
        except (KeyError, ValueError, TypeError) as exc:
            transcript.append(f"turn {turns}: invalid action {spec} ({exc})")
            if verbose:
                print(
                    f"    turn {turns}: invalid   {spec} ({exc})",
                    flush=True,
                )
            continue

        result = env.step(to_wire(action))
        observation = result
        trace.append(_turn_record(turns, spec, reply, result))
        transcript.append(f"turn {turns}: {spec} -> {result.feedback}")
        if verbose:
            print(
                f"    turn {turns}: {spec.get('action'):9s} {result.feedback[:88]}",
                flush=True,
            )
        if result.done:
            return {
                "trace": trace,
                "task_index": task_index,
                "country": env._task.country,
                "reward": result.reward or 0.0,
                "distance_km": result.distance_km,
                "parsed_ok": result.parsed_ok,
                "latency_s": time.time() - started,
                "turns": turns,
                "action_cost": result.action_cost,
                "reply": reply.strip(),
            }

    # Out of turns without a guess: score it, because a policy that never
    # commits should not be rewarded with a missing sample.
    result = env.step(to_wire(GuessAction(response="")))
    trace.append(_turn_record(turns + 1, {"action": "forced guess"}, "", result))
    return {
        "trace": trace,
        "task_index": task_index,
        "country": env._task.country,
        "reward": result.reward or 0.0,
        "distance_km": result.distance_km,
        "parsed_ok": False,
        "latency_s": time.time() - started,
        "turns": turns,
        "action_cost": result.action_cost,
        "reply": "never committed to a guess",
    }


class Worker:
    """One environment and one chat client, owned by a single thread.

    An episode is stateful, so concurrent rollouts cannot share an environment
    instance — they would interleave resets and steps into one episode. Each
    worker therefore builds its own environment over the same read-only task
    index and panorama cache, which is how a distributed rollout is arranged
    too.
    """

    def __init__(self, args: argparse.Namespace):
        self.env = GeoGuesserEnvironment(
            index_path=str(args.index),
            cache_dir=str(args.cache),
            episode_mode="agentic" if args.mode == "agentic" else "single_shot",
            max_steps=args.max_turns,
        )
        self.chat = build_chat(args)


def run_episodes(args: argparse.Namespace, tasks: list[int]) -> list[dict[str, Any]]:
    """
    Run every task, optionally several at a time.

    Args:
        args (`argparse.Namespace`):
            Parsed command line.
        tasks (`list[int]`):
            Task indices to play, one episode each.

    Returns:
        `list[dict]`: One record per episode, in task order.
    """
    local = threading.local()
    lock = threading.Lock()
    finished = {"n": 0}

    def worker() -> Worker:
        if not hasattr(local, "worker"):
            local.worker = Worker(args)
        return local.worker

    def play(task_index: int) -> dict[str, Any]:
        own = worker()
        if args.mode == "single_shot":
            record = run_single_shot(own.env, own.chat, task_index, args.verbose)
        else:
            record = run_agentic(
                own.env, own.chat, task_index, args.max_turns, args.verbose
            )
        with lock:
            finished["n"] += 1
            distance = record["distance_km"]
            shown = "unparsed" if not record["parsed_ok"] else f"{distance:8.0f} km"
            print(
                f"[{finished['n']:>3}/{len(tasks)}] task {record['task_index']:3d}  "
                f"{record['country'][:20]:20s} reward {record['reward']:.3f}  "
                f"{shown}  {record['turns']} turn(s)  {record['latency_s']:5.1f}s",
                flush=True,
            )
        return record

    if args.concurrency <= 1:
        return [play(task_index) for task_index in tasks]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        return list(pool.map(play, tasks))


def main() -> None:
    """Run the rollouts and print a summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["anthropic", "hf"], default="anthropic")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--base-url", default="https://router.huggingface.co/v1")
    parser.add_argument("--api-key-env", default="HF_TOKEN")
    parser.add_argument(
        "--mode", choices=["single_shot", "agentic"], default="single_shot"
    )
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--start-task", type=int, default=0)
    parser.add_argument("--stride", type=int, default=7)
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=3000,
        help="Reasoning models need several thousand; 1024 truncates them mid-thought.",
    )
    parser.add_argument(
        "--index", type=pathlib.Path, default=ROOT / "tasks" / "pano_v1.jsonl"
    )
    parser.add_argument("--cache", type=pathlib.Path, default=ROOT / "data" / "panos")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Episodes to run at once; each gets its own environment.",
    )
    parser.add_argument(
        "--trace-dir",
        type=pathlib.Path,
        default=pathlib.Path("rollouts"),
        help="Where to write per-turn traces and their images.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    probe = GeoGuesserEnvironment(
        index_path=str(args.index), cache_dir=str(args.cache), allow_fetch=False
    )
    n_tasks = probe._backend.n_tasks
    tasks = [
        (args.start_task + i * args.stride) % n_tasks for i in range(args.episodes)
    ]

    print(
        f"{args.provider}/{args.model}  mode={args.mode}  "
        f"episodes={len(tasks)}  concurrency={args.concurrency}  "
        f"tasks={tasks}",
        flush=True,
    )
    print("-" * 88, flush=True)

    wall_start = time.time()
    records = run_episodes(args, tasks)
    wall = time.time() - wall_start
    rewards = [r["reward"] for r in records]
    distances = [r["distance_km"] for r in records if r["distance_km"] is not None]
    parsed = sum(1 for r in records if r["parsed_ok"])
    print("-" * 88)
    print(f"mean reward     {statistics.mean(rewards):.3f}")
    if len(rewards) > 1:
        print(f"stdev reward    {statistics.stdev(rewards):.3f}")
    if distances:
        print(f"median distance {statistics.median(distances):.0f} km")
        print(
            f"within 200 km   {sum(1 for d in distances if d < 200)}/{len(distances)}"
        )
        print(
            f"within 1000 km  {sum(1 for d in distances if d < 1000)}/{len(distances)}"
        )
    print(f"parsed          {parsed}/{len(records)}")
    latencies = [r["latency_s"] for r in records]
    print(f"wall clock      {wall:.1f}s for {len(records)} episodes")
    print(f"sum of latency  {sum(latencies):.1f}s")
    if args.concurrency > 1:
        print(f"speedup         {sum(latencies) / max(wall, 1e-9):.2f}x")

    slug = f"{args.provider}_{args.mode}"
    out_dir = pathlib.Path(args.trace_dir) / slug
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Images live beside the trace rather than inside it: a six-episode agentic
    # run carries about 30 views, and inlining them makes the JSONL unreadable
    # and unloadable.
    manifest = []
    for record in records:
        trace = record.pop("trace", [])
        rows = []
        for row in trace:
            payload = row.pop("image_base64", None)
            if payload:
                name = f"t{record['task_index']:03d}_turn{row['turn']:02d}.jpg"
                suffix = ".png" if row.get("image_kind") == "map" else ".jpg"
                name = name.replace(".jpg", suffix)
                (images_dir / name).write_bytes(base64.b64decode(payload))
                row["image"] = f"images/{name}"
            rows.append(row)
        record["trace"] = rows
        manifest.append(record)

    out = out_dir / "trace.jsonl"
    with out.open("w") as handle:
        for record in manifest:
            handle.write(json.dumps(record) + "\n")
    summary = {
        "provider": args.provider,
        "model": args.model,
        "mode": args.mode,
        "episodes": len(manifest),
        "concurrency": args.concurrency,
        "max_turns": args.max_turns,
        "mean_reward": statistics.mean(rewards),
        "median_distance_km": statistics.median(distances) if distances else None,
        "within_200km": sum(1 for d in distances if d < 200),
        "within_1000km": sum(1 for d in distances if d < 1000),
        "parsed": parsed,
        "wall_clock_s": wall,
        "sum_latency_s": sum(latencies),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"trace -> {out}  ({len(list(images_dir.iterdir()))} images)")
    print(f"render it with: python video/render_trace.py {out_dir}")


if __name__ == "__main__":
    main()
