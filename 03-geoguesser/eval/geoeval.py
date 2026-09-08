# SPDX-License-Identifier: BSD-3-Clause
"""
Score a model on the GeoGuesser environment.

    geoeval run    --models board_models.json --split eval    drive rollouts
    geoeval report results/raw/board-passk                    pass@k table
    geoeval probe  --models board_models.json                 check endpoints
    geoeval replay episodes.jsonl                             check a recording

`run` talks to a served environment over HTTP and never imports it, so it works
against a URL with no checkout of the environment source. `replay` is the one
exception and imports the environment lazily, only when called.

Two reward scales exist and must not be mixed. An episode's stored
`outcome.reward` is the environment's own curve; everything reported here is
recomputed from `distance_km` through the pinned curve at the top of this file.
The same guess can score 0.0107 on one and 0.135 on the other.
"""

from __future__ import annotations

import argparse
import base64
import collections
import concurrent.futures
import dataclasses
import glob
import hashlib
import io
import json
import logging
import math
import os
import pathlib
import queue
import random
import re
import statistics
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from collections.abc import Mapping
from typing import Any, Callable, NamedTuple

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("geoeval")

# This file's own directory, and the project root above it. Sources used to
# derive these separately; they are defined once here.
HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent
ROOT = PROJECT


# --------------------------------------------------------------------------
# The reward curve reports are scored on
#   (was training_reward.py)
# --------------------------------------------------------------------------

# Run 1's curve. Pinned -- see the module docstring before changing anything here.
DECAY_KM = 1492.7
LONG_DECAY_KM = 5000.0
MIXTURE_SHORT_WEIGHT = 0.5
# Capped well below the game's 0.5: the turn budget is training's real
# efficiency constraint, so this term only breaks ties. See the training script
# for the measurement behind the number.
MAX_COST_FRACTION = 0.2


def training_reward(
    distance_km: float | None,
    cost: float = 0.0,
    max_cost_fraction: float = MAX_COST_FRACTION,
) -> float:
    """
    Reward for one episode, on the curve the policy is trained against.

    Args:
        distance_km (`float` or `None`):
            Kilometres between guess and truth. `None` means the episode ended
            without a usable guess, which scores zero.
        cost (`float`, *optional*, defaults to `0.0`):
            Accumulated action cost reported by the environment.
        max_cost_fraction (`float`, *optional*, defaults to `0.2`):
            Largest fraction of the distance score the cost may remove.

    Returns:
        `float`: Reward in `[0, 1]`.

    Examples:

    ```python
    training_reward(1348.5, cost=0.05)
    ```
    """
    if distance_km is None:
        return 0.0
    short = math.exp(-distance_km / DECAY_KM)
    long = math.exp(-distance_km / LONG_DECAY_KM)
    score = MIXTURE_SHORT_WEIGHT * short + (1.0 - MIXTURE_SHORT_WEIGHT) * long
    return min(1.0, score) * (1.0 - min(max(cost, 0.0), max_cost_fraction))


def episode_reward(outcome: dict) -> float:
    """
    Training reward for a stored eval episode's `outcome` block.

    Args:
        outcome (`dict`):
            An episode's `outcome`, carrying `distance_km` and `action_cost`.

    Returns:
        `float`: Reward in `[0, 1]`.
    """
    return training_reward(
        outcome.get("distance_km"), float(outcome.get("action_cost") or 0.0)
    )

# --------------------------------------------------------------------------
# Where the environment is
# --------------------------------------------------------------------------

# The hosted environment. Anything that can reach it needs no checkout, no
# imagery and no GPU.
SPACE_URL = "https://huggingenvs-geoguesser-env.hf.space"
LOCAL_URL = "http://127.0.0.1:8000"


def resolve_env_url(value: str) -> str:
    """
    Turn what a person types into a base URL.

    Accepts three shapes, so the same flag works whether the environment is
    served on this machine or on the Hub:

        space                       the hosted Space
        local                       127.0.0.1:8000
        local:8161                  127.0.0.1 on another port
        http://host:port            used as given
        huggingenvs-geoguesser-env.hf.space     https:// is assumed

    Args:
        value (`str`):
            The `--env` argument.

    Returns:
        `str`: a base URL with no trailing slash.
    """
    v = value.strip().rstrip("/")
    if v == "space":
        return SPACE_URL
    if v == "local":
        return LOCAL_URL
    if v.startswith("local:"):
        return f"http://127.0.0.1:{v.split(':', 1)[1]}"
    if v.startswith(("http://", "https://")):
        return v
    return f"https://{v}"


def add_env_argument(parser: argparse.ArgumentParser, default: str = "local") -> None:
    """Attach the `--env` flag, so every subcommand names the target the same way."""
    parser.add_argument(
        "--env",
        default=default,
        metavar="TARGET",
        help="where the environment is: 'space', 'local', 'local:PORT', or a URL "
        f"(default: {default})",
    )



# --------------------------------------------------------------------------
# Prompts, and parsing a model's reply into an action
#   (was agent.py)
# --------------------------------------------------------------------------

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


def to_wire_action(spec: dict[str, Any]) -> dict[str, Any]:
    """
    Translate a model's action object into the environment's wire action.

    The wire schema is flat with an `op` discriminator and forbids unknown
    fields, so anything absent is simply omitted rather than sent as null.

    Args:
        spec (`dict`):
            The parsed action from the model, keyed on `action`.

    Returns:
        `dict`: The wire action.

    Raises:
        ValueError: On an unknown action name.
        KeyError: When a required coordinate is missing.
    """
    kind = str(spec.get("action", "")).lower()
    if kind == "look":
        return {
            "op": "look",
            "heading_deg": float(spec.get("heading_deg", 0.0)),
            "pitch_deg": float(spec.get("pitch_deg", 0.0)),
            "fov_deg": float(spec.get("fov_deg", 90.0)),
        }
    if kind == "pan":
        return {"op": "pan", "delta_deg": float(spec.get("delta_deg", 45.0))}
    if kind == "zoom":
        return {"op": "zoom", "fov_deg": float(spec.get("fov_deg", 30.0))}
    if kind == "move":
        return {
            "op": "move",
            "direction": str(spec.get("direction", "forward")),
            "meters": float(spec.get("meters", 20.0)),
        }
    if kind in {"pin", "view_map"}:
        return {
            "op": kind,
            "lat": float(spec["lat"]),
            "lon": float(spec["lon"]),
            "span_deg": float(spec.get("span_deg", 7.0)),
        }
    if kind == "measure":
        return {"op": "measure", "lat": float(spec["lat"]), "lon": float(spec["lon"])}
    if kind == "guess":
        action: dict[str, Any] = {"op": "guess"}
        if spec.get("response") is not None:
            action["response"] = str(spec["response"])
        if spec.get("lat") is not None and spec.get("lon") is not None:
            action["lat"] = float(spec["lat"])
            action["lon"] = float(spec["lon"])
        for key in ("confidence", "reasoning"):
            if spec.get(key) is not None:
                action[key] = spec[key]
        return action
    raise ValueError(f"unknown action: {kind!r}")


# --------------------------------------------------------------------------
# Talking to a served environment over HTTP
#   (was env_client.py)
# --------------------------------------------------------------------------

ENV_NAME = "geoguesser_env"
"""Task API routes are namespaced by the name the server registers itself under."""


class Step(NamedTuple):
    """One step's result, shaped like the framework's own so callers match."""

    observation: dict[str, Any]
    reward: float | None
    done: bool


class GeoGuesserClient:
    """One episode at a time against a served environment.

    Args:
        base_url (`str`):
            Where the environment is. The hosted Space, or a local server.
        timeout_s (`float`, *optional*, defaults to `120.0`):
            Per-message timeout. Panorama reprojection plus a map render is a
            few hundred milliseconds locally and slower over the network.

    Examples:

    ```python
    with GeoGuesserClient("https://huggingenvs-geoguesser-env.hf.space") as env:
        observation = env.reset(split="eval", index=42)
        observation, reward, done = env.step({"op": "look", "heading_deg": 90})
    ```
    """

    def __init__(self, base_url: str, timeout_s: float = 120.0):
        from openenv import GenericEnvClient

        self.base_url = base_url.rstrip("/")
        self._client = GenericEnvClient(
            base_url=self.base_url, message_timeout_s=timeout_s
        )
        self._session = self._client.sync()
        self._env = self._session.__enter__()

    def __enter__(self) -> GeoGuesserClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Hand the session back. Servers cap concurrent sessions."""
        try:
            self._session.__exit__(None, None, None)
        except Exception:  # noqa: BLE001 - best effort on teardown
            pass

    def reset(
        self, split: str | None = None, index: int | None = None
    ) -> dict[str, Any]:
        """Start an episode and return the opening observation."""
        kwargs: dict[str, Any] = {}
        if split is not None:
            kwargs["split"] = split
        if index is not None:
            kwargs["index"] = index
        return self._client_result(self._env.reset(**kwargs)).observation

    def step(self, action: dict[str, Any]) -> Step:
        """
        Apply one action.

        Args:
            action (`dict`):
                The flat wire action, e.g. `{"op": "look", "heading_deg": 90}`.
                The environment declares a single action schema with an `op`
                discriminator, so no typed classes are needed.

        Returns:
            [`Step`]: The observation dict, the reward, and whether it ended.
        """
        from openenv import GenericAction

        return self._client_result(self._env.step(GenericAction(**action)))

    @staticmethod
    def _client_result(result: Any) -> Step:
        """Unpack a StepResult whose observation already arrives as a dict."""
        observation = getattr(result, "observation", result)
        if not isinstance(observation, dict):
            observation = (
                observation.model_dump()
                if hasattr(observation, "model_dump")
                else dict(observation)
            )
        return Step(
            observation=observation,
            reward=getattr(result, "reward", None),
            done=bool(getattr(result, "done", False)),
        )

    # -- Task API ---------------------------------------------------------

    def _task_api(self, route: str, payload: dict[str, Any] | None = None) -> Any:
        """Call one Task API route. GET when there is nothing to send."""
        url = f"{self.base_url}/{ENV_NAME}/{route}"
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            url,
            data=data,
            method="GET" if data is None else "POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())

    def list_splits(self) -> list[dict[str, Any]]:
        """Which splits the server offers, and how many tasks each holds."""
        return self._task_api("splits")

    def num_tasks(self, split: str) -> int:
        """Task count in one split."""
        return int(self._task_api("num_tasks", {"split": split})["num_tasks"])

    def get_task(self, split: str, index: int) -> dict[str, Any]:
        """
        Describe one task without playing it.

        Carries no coordinates and no country: task specs travel to whatever
        orchestrates a run, and a label sitting in one can reach a prompt.
        """
        return self._task_api("task", {"split": split, "index": index})["task"]


# --------------------------------------------------------------------------
# Providers, and driving one episode to a guess
#   (was collect_eval.py)
# --------------------------------------------------------------------------

sys.path.insert(0, str(PROJECT / "envs" / "geoguesser" / "openenv"))
sys.path.insert(0, str(PROJECT / "envs" / "geoguesser"))


# Prompts and reply parsing live in `agent.py`; the wire client in
# `env_client.py`. Neither imports the environment, which is what lets this run
# against a URL with no checkout of the environment source.


SCHEMA_VERSION = 2
"""Bumped when the episode record shape changes."""

# One `thinking` field per model spec, mapped to whatever each provider calls
# it. The four mechanisms are genuinely different and there is no common
# vocabulary, so the config names the *intent* and the adapters translate:
#
#   Anthropic          thinking={"type":"enabled","budget_tokens":N}
#   OpenAI gpt-5.x     reasoning_effort in none|minimal|low|medium|high
#   vLLM / Qwen3.5     extra_body.chat_template_kwargs.enable_thinking (bool)
#   Qwen3-VL-Instruct  no thinking mode at all; a separate -Thinking model exists
#
# Levels map to Anthropic budgets, since it is the only one that wants a number.
THINKING_BUDGETS = {"on": 4096, "low": 2048, "medium": 8192, "high": 16384}

EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
"""Levels Anthropic's `output_config.effort` accepts, for adaptive thinking."""

# Thinking output is stripped from `content`, so a budget that truncates before
# the closing tag returns an empty string -- indistinguishable from a model that
# cannot see. Never send thinking with less headroom than this.
MIN_THINKING_TOKENS = 8192

RETRY_STATUSES = (408, 409, 425, 429, 500, 502, 503, 504)
"""Transient HTTP statuses worth a retry. 400 and 401 are not."""

ENV_RETRY_MARKERS = (
    "CAPACITY_REACHED",
    "Server at capacity",
    "ConnectionClosed",
    "session not found",
    "Connection reset",
)
"""Environment-side failures that are worth waiting out rather than recording.

A sweep that asks for more sessions than the server allows loses whole episodes
to a condition that clears in seconds. Losing the episode is far worse than
waiting for it, because the model was never the problem and the gap is invisible
in the aggregate.
"""


# --------------------------------------------------------------- chat backends


@dataclasses.dataclass
class ChatResult:
    """One model call, with everything the provider was willing to tell us.

    Attributes:
        text (`str`):
            The reply the action parser sees.
        reasoning (`str`, *optional*):
            Chain of thought, when the provider exposes it separately.
        finish_reason (`str`, *optional*):
            Why generation stopped. `"length"` is the difference between a model
            that cannot see images and one that ran out of budget.
        tokens (`dict`):
            Whatever usage the provider reported, verbatim.
        latency_s (`float`):
            Wall-clock time of the successful attempt.
        attempts (`int`):
            How many calls it took, including the one that worked.
        errors (`list[str]`):
            One entry per failed attempt.
        model_reported (`str`, *optional*):
            Model id the provider echoed back, which is not always the one asked
            for -- routers substitute.
        response_id (`str`, *optional*):
            Provider-side identifier, for correlating with their logs.
        raw (`dict`):
            Extra provider-specific fields worth keeping.
    """

    text: str = ""
    reasoning: str | None = None
    finish_reason: str | None = None
    tokens: dict[str, Any] = dataclasses.field(default_factory=dict)
    latency_s: float = 0.0
    attempts: int = 0
    errors: list[str] = dataclasses.field(default_factory=list)
    model_reported: str | None = None
    response_id: str | None = None
    raw: dict[str, Any] = dataclasses.field(default_factory=dict)


def _retry(
    call: Callable[[], ChatResult], attempts: int, base_delay: float
) -> ChatResult:
    """
    Call with exponential backoff, recording every failure.

    A failed episode with no explanation is worthless when the point of the run
    is comparing endpoints, so errors are collected onto the result rather than
    raised away.
    """
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        started = time.time()
        try:
            result = call()
            result.attempts = attempt
            result.errors = errors
            result.latency_s = time.time() - started
            return result
        except Exception as exc:  # noqa: BLE001 - every failure must be recorded
            label = f"{type(exc).__name__}: {str(exc)[:300]}"
            errors.append(label)
            status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "response", None), "status_code", None
            )
            retryable = status is None or status in RETRY_STATUSES
            if attempt >= attempts or not retryable:
                return ChatResult(attempts=attempt, errors=errors)
            # Jitter, so a fleet of workers hitting a 429 does not retry in
            # lockstep and trip the limit again.
            delay = base_delay * (2 ** (attempt - 1)) * (0.5 + random.random())
            logger.warning(
                "    retry %d/%d in %.1fs: %s", attempt, attempts, delay, label
            )
            time.sleep(delay)
    return ChatResult(attempts=attempts, errors=errors)


_ANTHROPIC_CAPS: dict[str, tuple[bool, bool, bool]] = {}
_CAPS_LOCK = threading.Lock()


def anthropic_thinking_shape(client, model: str) -> tuple[bool, bool, bool]:
    """
    Which thinking mechanism a model accepts: (adaptive, enabled, effort).

    Asked of the API rather than hardcoded, because the two shapes are mutually
    exclusive and models disagree: claude-sonnet-5 takes `adaptive` plus
    `output_config.effort` and rejects `enabled`, while claude-haiku-4-5 takes
    `enabled` with a token budget and supports no effort level at all. Guessing
    either way produces a 400 on every call, which -- measured the hard way --
    reads as the model scoring zero on 50 straight episodes.

    Cached per model id; the lookup is one extra request per process.
    """
    with _CAPS_LOCK:
        if model in _ANTHROPIC_CAPS:
            return _ANTHROPIC_CAPS[model]
    adaptive = enabled = effort = False
    try:
        caps = getattr(client.models.retrieve(model), "capabilities", None)
        thinking = getattr(caps, "thinking", None)
        types = getattr(thinking, "types", None)
        adaptive = bool(getattr(getattr(types, "adaptive", None), "supported", False))
        enabled = bool(getattr(getattr(types, "enabled", None), "supported", False))
        effort = bool(getattr(getattr(caps, "effort", None), "supported", False))
    except Exception as exc:  # noqa: BLE001 - fall back to the older shape
        logger.warning(
            "could not read thinking capabilities for %s (%s); assuming the "
            "budget_tokens shape",
            model,
            type(exc).__name__,
        )
        enabled = True
    with _CAPS_LOCK:
        _ANTHROPIC_CAPS[model] = (adaptive, enabled, effort)
    return adaptive, enabled, effort


def _thinking_budget(spec: dict[str, Any]) -> int | None:
    """Token budget for Anthropic extended thinking, or None for off."""
    value = spec.get("thinking", spec.get("thinking_budget"))
    if value in (None, "off", False):
        return None
    if isinstance(value, bool):
        return THINKING_BUDGETS["on"]
    if isinstance(value, int):
        return value
    return THINKING_BUDGETS.get(str(value), THINKING_BUDGETS["on"])


def _max_tokens_for(spec: dict[str, Any], thinking: bool) -> int:
    """
    Token cap, raised when thinking is on.

    A thinking block that does not fit returns empty content, which reads as a
    model that cannot see rather than one that ran out of room, so the floor is
    enforced here rather than left to whoever wrote the config.
    """
    requested = int(spec.get("max_tokens", 4096))
    if not thinking:
        return requested
    if requested < MIN_THINKING_TOKENS:
        logger.warning(
            "%s: max_tokens %d is too low for thinking; raising to %d",
            spec.get("name") or spec.get("model"),
            requested,
            MIN_THINKING_TOKENS,
        )
        return MIN_THINKING_TOKENS
    return requested


def spec_thinking_label(budget: int | None) -> str:
    """How the run report should describe a thinking setting."""
    return "off" if not budget else f"{budget} tokens"


class AnthropicChat:
    """The Anthropic Messages API."""

    provider = "anthropic"

    def __init__(self, spec: dict[str, Any]):
        from anthropic import Anthropic

        key_env = spec.get("api_key_env", "ANTHROPIC_API_KEY")
        self._client = Anthropic(api_key=os.environ[key_env])
        self._model = spec["model"]
        self._level = spec.get("thinking")
        self._adaptive = self._enabled = self._effort = False
        self._temperature = spec.get("temperature")
        self._thinking = _thinking_budget(spec)
        self._max_tokens = _max_tokens_for(spec, bool(self._thinking))
        if self._thinking:
            self._adaptive, self._enabled, self._effort = anthropic_thinking_shape(
                self._client, self._model
            )
            if not (self._adaptive or self._enabled):
                logger.warning(
                    "%s declares no thinking support; running without it",
                    self._model,
                )
                self._thinking = None

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "thinking": spec_thinking_label(self._thinking),
            "thinking_budget": self._thinking,
            "thinking_shape": (
                "adaptive" if self._adaptive else ("enabled" if self._enabled else None)
            ),
        }

    def __call__(self, prompt: str, images: list[str]) -> ChatResult:
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type(image),
                    "data": image,
                },
            }
            for image in images
        ]
        content.append({"type": "text", "text": prompt})
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._thinking:
            # Anthropic rejects a temperature alongside thinking of either shape.
            kwargs.pop("temperature", None)
            if self._adaptive:
                kwargs["thinking"] = {"type": "adaptive"}
                if self._effort:
                    level = self._level if isinstance(self._level, str) else "medium"
                    kwargs["output_config"] = {
                        "effort": level if level in EFFORT_LEVELS else "medium"
                    }
            else:
                kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self._thinking,
                }
        message = self._client.messages.create(**kwargs)

        text_blocks, thinking_blocks = [], []
        for block in message.content:
            kind = getattr(block, "type", "")
            if kind == "text":
                text_blocks.append(block.text)
            elif kind == "thinking":
                thinking_blocks.append(getattr(block, "thinking", ""))
        usage = message.usage
        return ChatResult(
            text="".join(text_blocks),
            reasoning="\n".join(thinking_blocks) or None,
            finish_reason=message.stop_reason,
            tokens={
                "input": usage.input_tokens,
                "output": usage.output_tokens,
                "cache_read": getattr(usage, "cache_read_input_tokens", None),
                "cache_write": getattr(usage, "cache_creation_input_tokens", None),
            },
            model_reported=message.model,
            response_id=message.id,
            raw={"stop_sequence": message.stop_sequence},
        )


class OpenAICompatChat:
    """Any OpenAI-compatible endpoint: OpenAI, the HF router, or vLLM."""

    provider = "openai"

    def __init__(self, spec: dict[str, Any]):
        from openai import OpenAI

        self._base_url = spec.get("base_url", "https://api.openai.com/v1")
        key_env = spec.get("api_key_env", "OPENAI_API_KEY")
        self._client = OpenAI(
            base_url=self._base_url,
            api_key=os.environ.get(key_env, "not-needed"),
            timeout=float(spec.get("timeout_s", 300)),
        )
        self._model = spec["model"]
        self._temperature = spec.get("temperature")
        self._thinking = spec.get("thinking")
        self._openai_native = self._base_url.startswith("https://api.openai.com")
        self._max_tokens = _max_tokens_for(
            spec, self._thinking not in (None, "off", False)
        )
        self._extra = dict(spec.get("extra_body") or {})
        # Translate the intent into this endpoint's own mechanism, unless the
        # spec already set it explicitly in extra_body.
        if self._thinking is not None and not self._openai_native:
            template = dict(self._extra.get("chat_template_kwargs") or {})
            template.setdefault("enable_thinking", self._thinking not in ("off", False))
            self._extra["chat_template_kwargs"] = template

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self._model,
            "base_url": self._base_url,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "thinking": self._thinking,
            "extra_body": self._extra or None,
        }

    def __call__(self, prompt: str, images: list[str]) -> ChatResult:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type(image)};base64,{image}"},
                }
            )
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": content}],
        }
        # Newer OpenAI reasoning models reject max_tokens in favour of
        # max_completion_tokens; every other compatible endpoint wants the old
        # name, so pick by host rather than sending both.
        if self._base_url.startswith("https://api.openai.com"):
            kwargs["max_completion_tokens"] = self._max_tokens
        else:
            kwargs["max_tokens"] = self._max_tokens
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        # OpenAI's own reasoning models take an effort level rather than a
        # chat-template flag, and gpt-5.1+ defaults to no reasoning at all.
        if self._openai_native and self._thinking is not None:
            kwargs["reasoning_effort"] = (
                "none" if self._thinking in ("off", False) else str(self._thinking)
            )
        if self._extra:
            kwargs["extra_body"] = self._extra
        completion = self._client.chat.completions.create(**kwargs)

        choice = completion.choices[0]
        text = choice.message.content or ""
        reasoning = getattr(choice.message, "reasoning_content", None) or getattr(
            choice.message, "reasoning", None
        )
        # Reasoning models put their chain of thought in a separate field and can
        # exhaust the budget before emitting content, which looks exactly like a
        # model that cannot see images. Fall back to the reasoning text.
        if not text.strip() and reasoning:
            text = str(reasoning)
        usage = completion.usage
        tokens: dict[str, Any] = {}
        if usage is not None:
            details = getattr(usage, "completion_tokens_details", None)
            tokens = {
                "input": usage.prompt_tokens,
                "output": usage.completion_tokens,
                "total": usage.total_tokens,
                "reasoning": getattr(details, "reasoning_tokens", None),
            }
        return ChatResult(
            text=text,
            reasoning=str(reasoning) if reasoning else None,
            finish_reason=choice.finish_reason,
            tokens=tokens,
            model_reported=completion.model,
            response_id=completion.id,
            raw={"system_fingerprint": getattr(completion, "system_fingerprint", None)},
        )


def build_chat(spec: dict[str, Any]):
    """Construct the backend named in a model spec."""
    provider = str(spec.get("provider", "openai")).lower()
    if provider == "anthropic":
        return AnthropicChat(spec)
    if provider in {"openai", "openai-compatible", "hf", "vllm"}:
        return OpenAICompatChat(spec)
    raise SystemExit(f"unknown provider {provider!r} for model {spec.get('name')!r}")


# ------------------------------------------------------------------ recording


def field(observation: Any, name: str, default: Any = None) -> Any:
    """
    Read one field from an observation, whether it is a mapping or an object.

    [`~env_client.Step`] carries the observation as a `dict`, but this module was
    written against an earlier client that handed back pydantic models. On a dict
    a plain `getattr` silently returns the default, which is worse than the
    `AttributeError` its siblings raise: every camera field, the tool list and
    the feedback quietly become `None`, and the eval still prints scores.

    Args:
        observation (`dict` or `object`):
            One observation, as returned by the environment client.
        name (`str`):
            Field to read.
        default (`Any`, *optional*):
            Returned when the field is absent.

    Returns:
        `Any`: The field's value, or `default`.
    """
    if isinstance(observation, Mapping):
        return observation.get(name, default)
    return getattr(observation, name, default)


def camera_of(observation: Any) -> dict[str, Any]:
    """
    The viewport state, which is what makes a rollout re-renderable.

    `frame_index` lives in metadata rather than on the observation, and it is
    the field that tells a renderer *which* panorama to reproject.
    """
    metadata = field(observation, "metadata") or {}
    return {
        "heading_deg": field(observation, "heading_deg"),
        "pitch_deg": field(observation, "pitch_deg"),
        "fov_deg": field(observation, "fov_deg"),
        "frame_index": metadata.get("frame_index"),
    }


def image_digest(image_b64: str | None) -> str | None:
    """sha256 of the decoded image, so a re-render can be verified against it."""
    if not image_b64:
        return None
    try:
        return hashlib.sha256(base64.b64decode(image_b64)).hexdigest()
    except Exception:  # noqa: BLE001
        return None


def pins_of(observation: Any) -> list[list[float]]:
    """Pins placed so far, as plain triples the renderer can redraw."""
    out = []
    for pin in field(observation, "pins") or []:
        lat = getattr(pin, "lat", None) if not isinstance(pin, dict) else pin.get("lat")
        lon = getattr(pin, "lon", None) if not isinstance(pin, dict) else pin.get("lon")
        if lat is not None and lon is not None:
            out.append([float(lat), float(lon)])
    return out


def _guessed_coords(turns: list[dict[str, Any]]) -> list[float] | None:
    """
    The coordinates actually guessed, taken from the last guess action.

    The observation reveals the truth after a guess but never echoes the guess
    itself, so it has to come from the action that was sent.
    """
    for record in reversed(turns):
        action = record.get("action") or {}
        if str(action.get("action", "")).endswith("guess"):
            lat, lon = action.get("lat"), action.get("lon")
            if lat is not None and lon is not None:
                return [float(lat), float(lon)]
            # A free-text guess was parsed inside the environment, so the
            # coordinates are not in the action at all.
            return None
    return None


def turn_record(
    turn: int,
    camera_before: dict[str, Any],
    action: dict[str, Any] | None,
    result: Any,
    chat: ChatResult | None,
    prompt: str | None,
    status: str,
    frames_dir: pathlib.Path | None,
    episode_id: str,
) -> dict[str, Any]:
    """One turn, with everything needed to score it, debug it and animate it."""
    observation = getattr(result, "observation", result)
    record: dict[str, Any] = {
        "turn": turn,
        "status": status,
        "camera_before": camera_before,
        "action": action,
        "camera_after": camera_of(observation),
        "pins": pins_of(observation),
        "image_kind": field(observation, "image_kind"),
        "image_sha256": image_digest(field(observation, "image_base64")),
        "feedback": field(observation, "feedback"),
        "action_cost": field(observation, "action_cost"),
        "steps_remaining": field(observation, "steps_remaining"),
        "moved_meters": field(observation, "moved_meters"),
        "total_moved_meters": field(observation, "total_moved_meters"),
        "available_tools": list(field(observation, "available_tools") or []),
        "reward": getattr(result, "reward", None),
        "done": getattr(result, "done", None),
    }
    if chat is not None:
        record["model"] = {
            "reply": chat.text,
            "reasoning": chat.reasoning,
            "finish_reason": chat.finish_reason,
            "tokens": chat.tokens,
            "latency_s": round(chat.latency_s, 3),
            "attempts": chat.attempts,
            "errors": chat.errors,
            "model_reported": chat.model_reported,
            "response_id": chat.response_id,
            "raw": chat.raw,
        }
    if prompt is not None:
        record["prompt"] = prompt
    if frames_dir is not None:
        image = field(observation, "image_base64")
        if image:
            frames_dir.mkdir(parents=True, exist_ok=True)
            path = (
                frames_dir
                / f"{episode_id}-{turn:03d}.{('png' if field(observation, 'image_kind', '') == 'map' else 'jpg')}"
            )
            path.write_bytes(base64.b64decode(image))
            record["image_path"] = str(path.relative_to(frames_dir.parents[0]))
    return record


# ------------------------------------------------------------------- episodes


def run_episode(
    env: GeoGuesserClient,
    chat: Any,
    spec: dict[str, Any],
    split: str,
    index: int,
    args: argparse.Namespace,
    frames_dir: pathlib.Path | None,
    sample: int = 0,
) -> dict[str, Any]:
    """
    Play one episode and return its complete record.

    Never raises for a model-side problem: an endpoint that errors, refuses or
    rambles is a result to compare, not a run to abort.
    """
    episode_id = uuid.uuid4().hex[:12]
    single_shot = args.mode == "single_shot"
    max_turns = 1 if single_shot else args.max_turns
    started = time.time()

    observation = env.reset(split=split, index=index)
    task_meta = dict(field(observation, "metadata") or {})
    turns = [
        turn_record(
            0,
            camera_of(observation),
            {"action": "reset"},
            observation,
            None,
            None,
            "ok",
            frames_dir,
            episode_id,
        )
    ]
    transcript: list[str] = []
    result = None
    turn = 0

    for turn in range(1, max_turns + 1):
        remaining = max_turns - turn + 1
        if single_shot:
            prompt = SINGLE_SHOT_PROMPT
        else:
            template = getattr(args, "prompt_text", None) or PROMPTS[args.prompt]
            prompt = template.format(
                max_turns=remaining,
                tools=", ".join(field(observation, "available_tools") or []),
            )
            if transcript:
                prompt += "\n\nWhat has happened so far:\n" + "\n".join(transcript[-8:])
            prompt += (
                f"\n\nYou are facing {field(observation, 'heading_deg') or 0.0:.0f} degrees with a "
                f"{field(observation, 'fov_deg') or 0.0:.0f} degree field of view. "
                f"{field(observation, 'steps_remaining')} actions remain."
            )
            if remaining <= 2:
                prompt += (
                    f"\n\nWARNING: only {remaining} turn(s) left. You must reply "
                    'with {"action": "guess", "lat": ..., "lon": ...} now, or you '
                    "score zero. Give your best estimate even if you are unsure."
                )

        camera_before = camera_of(observation)
        image_b64 = field(observation, "image_base64")
        images = [image_b64] if image_b64 else []
        reply = _retry(lambda: chat(prompt, images), args.retries, args.retry_delay)

        if reply.errors and not reply.text.strip():
            turns.append(
                turn_record(
                    turn,
                    camera_before,
                    None,
                    observation,
                    reply,
                    prompt,
                    "provider_error",
                    frames_dir,
                    episode_id,
                )
            )
            transcript.append(f"turn {turn}: provider error, no reply")
            continue

        if single_shot:
            action_spec = {"action": "guess", "response": reply.text}
            result = env.step({"op": "guess", "response": reply.text})
            turns.append(
                turn_record(
                    turn,
                    camera_before,
                    action_spec,
                    result,
                    reply,
                    prompt,
                    "ok",
                    frames_dir,
                    episode_id,
                )
            )
            break

        action_spec = parse_action(reply.text)
        if action_spec is None:
            turns.append(
                turn_record(
                    turn,
                    camera_before,
                    None,
                    observation,
                    reply,
                    prompt,
                    "unparseable",
                    frames_dir,
                    episode_id,
                )
            )
            transcript.append(f"turn {turn}: reply was not a JSON action, ignored")
            continue

        try:
            action = to_wire_action(action_spec)
        except (KeyError, ValueError, TypeError) as exc:
            turns.append(
                turn_record(
                    turn,
                    camera_before,
                    action_spec,
                    observation,
                    reply,
                    prompt,
                    f"invalid_action: {exc}",
                    frames_dir,
                    episode_id,
                )
            )
            transcript.append(f"turn {turn}: invalid action {action_spec} ({exc})")
            continue

        result = env.step(action)
        observation = result.observation
        turns.append(
            turn_record(
                turn,
                camera_before,
                action_spec,
                result,
                reply,
                prompt,
                "ok",
                frames_dir,
                episode_id,
            )
        )
        transcript.append(
            f"turn {turn}: {action_spec} -> {field(observation, 'feedback')}"
        )
        if result.done:
            break

    forced = False
    if result is None or not getattr(result, "done", False):
        # A policy that never commits should not vanish from the sample; score
        # the empty guess so the zero is visible.
        forced = True
        result = env.step({"op": "guess", "response": ""})
        turns.append(
            turn_record(
                turn + 1,
                camera_of(observation),
                {"action": "forced_guess"},
                result,
                None,
                None,
                "forced_guess",
                frames_dir,
                episode_id,
            )
        )

    final = result.observation
    # Ground truth, including the country, only exists on the terminal
    # observation. Reading it from the reset one left every record's country
    # null and the regional breakdown impossible.
    final_meta = dict(field(final, "metadata") or {})
    used = [t for t in turns if t["turn"] > 0]
    return {
        "schema_version": SCHEMA_VERSION,
        "episode_id": episode_id,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_name": spec.get("name") or spec.get("model"),
        "model": chat.identity,
        "task": {
            "split": split,
            "index": index,
            # Which attempt at this task this is. Passes compose into pass@k by
            # each run recording a distinct range of these, so an attempt from
            # one pass is never mistaken for an attempt from another.
            "sample": sample,
            "task_id": task_meta.get("task_id"),
            "country": final_meta.get("country"),
            "sequence_id": task_meta.get("sequence_id"),
            "captured_at": task_meta.get("captured_at"),
            "attribution": task_meta.get("attribution"),
        },
        "config": {
            "mode": args.mode,
            # An eval number is only comparable within one prompt version, so
            # the version travels with the episode rather than the run.
            "prompt_version": args.prompt if args.mode == "agentic" else "single_shot",
            "max_turns": max_turns,
            "retries": args.retries,
            "base_url": args.base_url,
            "street_detail": task_meta.get("street_detail"),
        },
        "turns": turns,
        "outcome": {
            # `reward` is the environment's own -- the game's curve, which the
            # public leaderboard ranks on. `train_reward` is the curve the
            # policy is optimised against; they are not interchangeable.
            "reward": result.reward,
            "train_reward": round(
                training_reward(
                    field(final, "distance_km"),
                    float(field(final, "action_cost") or 0.0),
                ),
                4,
            ),
            "distance_km": field(final, "distance_km"),
            "parsed_ok": field(final, "parsed_ok"),
            "guess": final_meta.get("guess") or _guessed_coords(turns),
            "guess_country": final_meta.get("guess_country"),
            "verdict": final_meta.get("verdict"),
            "country_hit": final_meta.get("country_hit"),
            "region_hit": final_meta.get("region_hit"),
            "score_before_cost": field(final, "score"),
            "n_looks": final_meta.get("n_looks"),
            "n_maps": final_meta.get("n_maps"),
            "n_pins": final_meta.get("n_pins"),
            "n_moves": final_meta.get("n_moves"),
            "truth": [
                field(final, "true_lat"),
                field(final, "true_lon"),
            ],
            "action_cost": field(final, "action_cost"),
            "total_moved_meters": field(final, "total_moved_meters"),
            "forced_guess": forced,
            "turns_used": len(used),
            "turns_ok": sum(1 for t in used if t["status"] == "ok"),
            "turns_unparseable": sum(1 for t in used if t["status"] == "unparseable"),
            "turns_provider_error": sum(
                1 for t in used if t["status"] == "provider_error"
            ),
            "wall_clock_s": round(time.time() - started, 3),
            "model_latency_s": round(
                sum(t.get("model", {}).get("latency_s", 0.0) for t in used), 3
            ),
            "tokens_in": sum(
                (t.get("model", {}).get("tokens", {}) or {}).get("input") or 0
                for t in used
            ),
            "tokens_out": sum(
                (t.get("model", {}).get("tokens", {}) or {}).get("output") or 0
                for t in used
            ),
        },
    }


# ----------------------------------------------------------------------- runs


def load_models(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Model specs from a config file, or a single one from the command line."""
    if args.models:
        specs = json.loads(pathlib.Path(args.models).read_text())
        if not isinstance(specs, list):
            raise SystemExit("--models must contain a JSON list of specs")
        return specs
    if not args.model:
        raise SystemExit("pass --model, or --models with a config file")
    return [
        {
            "name": args.model,
            "provider": args.provider,
            "model": args.model,
            "base_url": args.model_base_url,
            "api_key_env": args.api_key_env,
            "max_tokens": args.max_tokens,
            "concurrency": args.concurrency,
        }
    ]


def already_done(path: pathlib.Path) -> set[tuple[str, str, str, int, int]]:
    """
    Episodes already recorded, so a run can resume.

    The attempt number is part of the key. Without it a second pass over the
    same tasks is skipped entirely as "already recorded", and pass@k can never
    accumulate past 1.
    """
    done: set[tuple[str, str, str, int, int]] = set()
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        task = row.get("task") or {}
        index = task.get("index")
        if index is None:
            continue
        config = row.get("config") or {}
        done.add(
            (
                str(row.get("model_name")),
                str(config.get("prompt_version")),
                str(task.get("split")),
                int(index),
                int(task.get("sample") or 0),
            )
        )
    return done


def run_model(
    spec: dict[str, Any],
    indices: list[int],
    args: argparse.Namespace,
    out: pathlib.Path,
    frames_dir: pathlib.Path | None,
    write_lock: threading.Lock,
    done: set[tuple[str, str, str, int]],
) -> list[dict[str, Any]]:
    """Play every task for one model, at that endpoint's own concurrency."""
    name = spec.get("name") or spec["model"]
    version = args.prompt if args.mode == "agentic" else "single_shot"
    # Attempts are interleaved rather than grouped -- sample 0 of every task,
    # then sample 1 of every task -- so an interrupted run yields a complete
    # pass@1 over all tasks instead of pass@4 over the first quarter.
    todo = [
        (i, k)
        for k in range(args.sample_offset, args.sample_offset + args.repeats)
        for i in indices
        if (name, version, args.split, i, k) not in done
    ]
    if not todo:
        logger.info(
            "%s: nothing to do (all %d already recorded)",
            name,
            len(indices) * args.repeats,
        )
        return []
    workers = max(1, int(spec.get("concurrency", args.concurrency)))
    logger.info("%s: %d episodes, %d workers", name, len(todo), workers)

    pending: queue.Queue[tuple[int, int]] = queue.Queue()
    for item in todo:
        pending.put(item)
    records: list[dict[str, Any]] = []
    # One environment client and one chat client per worker: sharing an
    # environment across threads interleaves resets and silently corrupts every
    # episode in flight.
    local = threading.local()
    counter = {"n": 0}

    def work() -> None:
        try:
            _work()
        finally:
            # Each worker holds a websocket session for the life of the thread.
            # Leaving them open leaks server capacity: a sweep of six endpoints
            # exhausted a 64-session cap that its own arithmetic never reached,
            # and later episodes died with CAPACITY_REACHED.
            env = getattr(local, "env", None)
            if env is not None:
                try:
                    env.close()
                except Exception:  # noqa: BLE001 - best effort on teardown
                    pass

    def _work() -> None:
        while True:
            try:
                index, sample = pending.get_nowait()
            except queue.Empty:
                return
            if not hasattr(local, "env"):
                local.env = GeoGuesserClient(base_url=args.base_url)
                local.chat = build_chat(spec)
            record: dict[str, Any] | None = None
            last_error = ""
            last_trace = ""
            for attempt in range(1, args.env_retries + 1):
                try:
                    record = run_episode(
                        local.env, local.chat, spec, args.split, index, args,
                        frames_dir, sample,
                    )
                    break
                except Exception as exc:  # noqa: BLE001 - one bad episode, not a run
                    last_error = f"{type(exc).__name__}: {exc}"
                    last_trace = traceback.format_exc(limit=6)
                    transient = any(m in last_error for m in ENV_RETRY_MARKERS)
                    if not transient or attempt >= args.env_retries:
                        break
                    delay = 2.0 * attempt * (0.5 + random.random())
                    logger.warning(
                        "  %s task %d: env busy (%s), retry %d/%d in %.1fs",
                        name,
                        index,
                        last_error[:60],
                        attempt,
                        args.env_retries,
                        delay,
                    )
                    # A closed session cannot be reused, so rebuild the client.
                    local.env = GeoGuesserClient(base_url=args.base_url)
                    time.sleep(delay)
            if record is None:
                record = {
                    "schema_version": SCHEMA_VERSION,
                    "episode_id": uuid.uuid4().hex[:12],
                    "model_name": name,
                    "task": {"split": args.split, "index": index, "sample": sample},
                    "config": {
                        "prompt_version": (
                            args.prompt if args.mode == "agentic" else "single_shot"
                        )
                    },
                    "error": last_error,
                    "traceback": last_trace,
                }
                logger.warning("  %s task %d FAILED: %s", name, index, last_error[:90])
            with write_lock:
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open("a") as handle:
                    handle.write(json.dumps(record) + "\n")
                    handle.flush()
                records.append(record)
                counter["n"] += 1
                outcome = record.get("outcome") or {}
                logger.info(
                    "  [%3d/%3d] %-18s task %-5d train %-6s game %-6s %s",
                    counter["n"],
                    len(todo),
                    name,
                    index,
                    (
                        f"{outcome['train_reward']:.3f}"
                        if outcome.get("train_reward") is not None
                        else "-"
                    ),
                    (
                        f"{outcome['reward']:.3f}"
                        if outcome.get("reward") is not None
                        else "-"
                    ),
                    (
                        f"{outcome.get('distance_km'):.0f} km"
                        if outcome.get("distance_km") is not None
                        else record.get("error", "")[:60]
                    ),
                )

    threads = [threading.Thread(target=work, daemon=True) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return records


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics per model, from the records actually collected."""
    by_model: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in records:
        version = (row.get("config") or {}).get("prompt_version")
        key = f"{row.get('model_name')}" + (f" [{version}]" if version else "")
        by_model[key].append(row)
    summary = {}
    for name, rows in by_model.items():
        scored = [r for r in rows if (r.get("outcome") or {}).get("reward") is not None]
        rewards = [r["outcome"]["reward"] for r in scored]
        train_rewards = [episode_reward(r["outcome"]) for r in scored]
        distances = [
            r["outcome"]["distance_km"]
            for r in scored
            if r["outcome"].get("distance_km") is not None
        ]
        summary[name] = {
            "episodes": len(rows),
            "scored": len(scored),
            "errored": sum(1 for r in rows if r.get("error")),
            "mean_train_reward": (
                round(statistics.fmean(train_rewards), 4) if train_rewards else None
            ),
            "mean_reward": round(statistics.fmean(rewards), 4) if rewards else None,
            "median_distance_km": (
                round(statistics.median(distances), 1) if distances else None
            ),
            "within_1km": sum(1 for d in distances if d <= 1),
            "within_25km": sum(1 for d in distances if d <= 25),
            "within_200km": sum(1 for d in distances if d <= 200),
            "within_750km": sum(1 for d in distances if d <= 750),
            "parsed_ok": sum(
                1 for r in scored if (r["outcome"] or {}).get("parsed_ok")
            ),
            "forced_guess": sum(
                1 for r in scored if (r["outcome"] or {}).get("forced_guess")
            ),
            "mean_turns": (
                round(
                    statistics.fmean([r["outcome"]["turns_used"] for r in scored]),
                    2,
                )
                if scored
                else None
            ),
            "tokens_in": sum(r["outcome"].get("tokens_in") or 0 for r in scored),
            "tokens_out": sum(r["outcome"].get("tokens_out") or 0 for r in scored),
            "model_latency_s": round(
                sum(r["outcome"].get("model_latency_s") or 0 for r in scored), 1
            ),
        }
    return summary


def _main_collect() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_env_argument(parser)
    parser.add_argument("--base-url", default=None,
                        help=argparse.SUPPRESS)  # superseded by --env
    parser.add_argument("--split", default="eval")
    parser.add_argument("--limit", type=int, default=None, help="First N tasks.")
    parser.add_argument("--indices", default=None, help="Comma-separated task indices.")
    parser.add_argument("--mode", choices=["agentic", "single_shot"], default="agentic")
    parser.add_argument(
        "--prompt",
        choices=sorted(PROMPTS),
        default="v2",
        help="Agentic prompt version. Recorded on every episode.",
    )
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--env-retries",
        type=int,
        default=5,
        help="Retries for transient environment-side failures (session capacity, "
        "dropped websocket). These are not model failures and must not be "
        "recorded as one.",
    )
    parser.add_argument("--retry-delay", type=float, default=2.0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--sample-offset",
        type=int,
        default=0,
        help="Number the attempts from here instead of 0. Lets a second "
        "independent run merge with a first into pass@2 without two episodes "
        "claiming to be the same attempt at the same task.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Attempts per task, for pass@k. Also the only way to measure "
        "reward spread within a single task, which is what a GRPO group sees.",
    )
    parser.add_argument("--models", default=None, help="JSON file of model specs.")
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument("--model-base-url", default="https://router.huggingface.co/v1")
    parser.add_argument("--api-key-env", default="ANTHROPIC_API_KEY")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out-dir", type=pathlib.Path, default=PROJECT / "rollouts")
    parser.add_argument(
        "--save-frames",
        action="store_true",
        help="Also write the literal observation images. Replay verifies against "
        "the recorded sha256 either way, so this is only for auditing.",
    )
    args = parser.parse_args()
    # `--env` is the documented way to name the target; an explicit
    # `--base-url` still wins, so existing scripts keep working. Only the
    # subcommands that actually reach the environment define `--env`.
    if getattr(args, "env", None) and getattr(args, "base_url", None) is None:
        args.base_url = resolve_env_url(args.env)

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = args.out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    episodes = run_dir / "episodes.jsonl"
    frames_dir = (run_dir / "frames") if args.save_frames else None

    env = GeoGuesserClient(base_url=args.base_url)
    total = env.num_tasks(args.split)
    if args.indices:
        indices = [int(v) for v in args.indices.split(",") if v.strip()]
    else:
        indices = list(range(total if args.limit is None else min(args.limit, total)))

    specs = load_models(args)
    done = already_done(episodes)
    logger.info(
        "run %s · split %s (%d tasks) · %d task(s) x %d attempt(s) "
        "= %d episodes each · %d model(s)%s",
        run_id,
        args.split,
        total,
        len(indices),
        args.repeats,
        len(indices) * args.repeats,
        len(specs),
        f" · resuming, {len(done)} already recorded" if done else "",
    )

    write_lock = threading.Lock()
    collected: list[dict[str, Any]] = []
    started = time.time()
    for spec in specs:
        collected += run_model(
            spec, indices, args, episodes, frames_dir, write_lock, done
        )

    # Summarise from the file, not just this process, so a resumed run reports
    # the whole picture rather than the tail of it.
    everything = [
        json.loads(line) for line in episodes.read_text().splitlines() if line.strip()
    ]
    summary = summarise(everything)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "schema_version": SCHEMA_VERSION,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "wall_clock_s": round(time.time() - started, 1),
                "base_url": args.base_url,
                "split": args.split,
                "indices": indices,
                "config": vars(args) | {"out_dir": str(args.out_dir)},
                "models": [
                    build_chat(s).identity | {"name": s.get("name")} for s in specs
                ],
                "summary": summary,
            },
            indent=2,
            default=str,
        )
    )

    logger.info(
        "\n%-18s %7s %7s %9s %8s %8s",
        "model",
        "n",
        "reward",
        "median km",
        "<=25km",
        "parsed",
    )
    for name, s in summary.items():
        logger.info(
            "%-18s %7d %7s %9s %8d %8d",
            name,
            s["episodes"],
            f"{s['mean_reward']:.3f}" if s["mean_reward"] is not None else "-",
            f"{s['median_distance_km']:.0f}"
            if s["median_distance_km"] is not None
            else "-",
            s["within_25km"],
            s["parsed_ok"],
        )
    logger.info("\nepisodes -> %s", episodes)
    logger.info("summary  -> %s", run_dir / "run.json")


# --------------------------------------------------------------------------
# Pooling passes into pass@k
#   (was report_passes.py)
# --------------------------------------------------------------------------

# training_reward.py sits beside this file; an absolute path here tied the
# script to one machine.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def load(root: pathlib.Path) -> list[dict]:
    """Every episode under a run root, across passes and shards."""
    rows = []
    for path in glob.glob(str(root / "**" / "episodes.jsonl"), recursive=True):
        with open(path) as handle:
            for line in handle:
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # a torn last line while a pass is still writing
    return rows


def _main_report() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    # Several roots, so a finished arm is never re-run: point this at the old
    # run plus the new one and they pool into one table. base and ckpt50 cost
    # 1600 episodes to measure; re-measuring them to compare a new checkpoint
    # would triple every subsequent eval for no information.
    parser.add_argument("roots", type=pathlib.Path, nargs="+")
    parser.add_argument("--baseline", default="base")
    args = parser.parse_args()
    # `--env` is the documented way to name the target; an explicit
    # `--base-url` still wins, so existing scripts keep working. Only the
    # subcommands that actually reach the environment define `--env`.
    if getattr(args, "env", None) and getattr(args, "base_url", None) is None:
        args.base_url = resolve_env_url(args.env)

    rows = [
        r
        for root in args.roots
        for r in load(root)
        if (r.get("outcome") or {}).get("reward") is not None
    ]
    if not rows:
        raise SystemExit(f"no scored episodes under {args.roots}")

    # arm -> task -> list of per-attempt training rewards
    by: dict[str, dict[int, list[float]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    dist: dict[str, list[float]] = collections.defaultdict(list)
    for r in rows:
        arm = r.get("model_name")
        by[arm][r["task"]["index"]].append(episode_reward(r["outcome"]))
        if r["outcome"].get("distance_km") is not None:
            dist[arm].append(r["outcome"]["distance_km"])

    # Everything else worth averaging, per arm. Kept separate from the scoring
    # table because these describe *behaviour* -- how the reward was earned --
    # and reading them beside the score is what distinguished "learned to
    # commit early" from "stopped doing the task".
    behaviour: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        behaviour[r.get("model_name")].append(r["outcome"])

    attempts = {a: statistics.fmean(len(v) for v in t.values()) for a, t in by.items()}
    print(f"{len(rows)} episodes over {len(by)} arm(s)\n")
    header = (
        f"{'arm':22} {'tasks':>6} {'k':>4} {'mean-of-k':>10} "
        f"{'best-of-k':>10} {'median km':>10}"
    )
    print(header)
    print("-" * len(header))
    ranked = sorted(
        by, key=lambda a: -statistics.fmean(statistics.fmean(v) for v in by[a].values())
    )
    for arm in ranked:
        tasks = by[arm]
        mean_k = statistics.fmean(statistics.fmean(v) for v in tasks.values())
        best_k = statistics.fmean(max(v) for v in tasks.values())
        med = statistics.median(dist[arm]) if dist[arm] else float("nan")
        print(
            f"{arm:22} {len(tasks):6d} {attempts[arm]:4.1f} {mean_k:10.4f} "
            f"{best_k:10.4f} {med:10.0f}"
        )

    # Behaviour table.
    def rate(arm: str, key: str) -> float:
        vals = [bool(o.get(key)) for o in behaviour[arm] if o.get(key) is not None]
        return 100.0 * sum(vals) / len(vals) if vals else float("nan")

    def avg(arm: str, key: str) -> float:
        vals = [o[key] for o in behaviour[arm] if isinstance(o.get(key), (int, float))]
        return statistics.fmean(vals) if vals else float("nan")

    def within(arm: str, km: float) -> float:
        vals = [
            o["distance_km"] for o in behaviour[arm] if o.get("distance_km") is not None
        ]
        return (
            100.0 * sum(1 for v in vals if v <= km) / len(vals)
            if vals
            else float("nan")
        )

    head = (
        f"\n{'arm':22} {'turns':>6} {'looks':>6} {'moves':>6} {'pins':>5} "
        f"{'cost':>6} {'country%':>9} {'<=200km':>8} {'<=750km':>8} "
        f"{'zero%':>6} {'forced%':>8} {'tok_out':>8}"
    )
    print(head)
    print("-" * len(head))
    for arm in ranked:
        zero = (
            100.0
            * sum(1 for o in behaviour[arm] if o.get("reward") == 0)
            / len(behaviour[arm])
        )
        print(
            f"{arm:22} {avg(arm, 'turns_used'):6.1f} {avg(arm, 'n_looks'):6.1f} "
            f"{avg(arm, 'n_moves'):6.1f} {avg(arm, 'n_pins'):5.1f} "
            f"{avg(arm, 'action_cost'):6.3f} {rate(arm, 'country_hit'):8.1f}% "
            f"{within(arm, 200):7.1f}% {within(arm, 750):7.1f}% "
            f"{zero:5.1f}% {rate(arm, 'forced_guess'):7.1f}% "
            f"{avg(arm, 'tokens_out'):8.0f}"
        )

    if args.baseline not in by:
        return
    print(f"\npaired against {args.baseline!r}, tasks both arms attempted:")
    base = by[args.baseline]
    for arm in ranked:
        if arm == args.baseline:
            continue
        shared = sorted(set(base) & set(by[arm]))
        if len(shared) < 2:
            continue
        diffs = [
            statistics.fmean(by[arm][t]) - statistics.fmean(base[t]) for t in shared
        ]
        m = statistics.fmean(diffs)
        se = statistics.pstdev(diffs) / math.sqrt(len(diffs))
        verdict = "SIGNIFICANT" if abs(m) > 1.96 * se else "not significant"
        print(
            f"  {arm:20} n={len(shared):3d}  delta {m:+.4f} +/- {se:.4f}  "
            f"95% CI [{m - 1.96 * se:+.4f}, {m + 1.96 * se:+.4f}]  {verdict}"
        )
        print(
            f"  {'':20} better on {sum(1 for d in diffs if d > 0)}/{len(diffs)} tasks"
        )


# --------------------------------------------------------------------------
# Checking an endpoint answers, and can see
#   (was probe_endpoints.py)
# --------------------------------------------------------------------------

def swatch(colour: tuple[int, int, int]) -> str:
    """A solid 64x64 PNG, base64. Small enough to be cheap, big enough to see."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), colour).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def client_for(spec: dict[str, Any]):
    """An OpenAI-compatible client, or None for providers that need their own."""
    from openai import OpenAI

    base_url = spec.get("base_url")
    key_env = spec.get("api_key_env", "OPENAI_API_KEY")
    return OpenAI(
        base_url=base_url,
        api_key=os.environ.get(key_env, "not-needed"),
        timeout=float(spec.get("probe_timeout_s", 120)),
    )


def ask(
    spec: dict[str, Any],
    text_prompt: str,
    images: list[str],
    max_tokens: int,
    thinking: bool | None,
):
    """
    One chat call, returning (text, finish_reason, usage, elapsed).

    Content blocks are built per provider. Anthropic and the OpenAI-compatible
    APIs disagree on the image block entirely, and sending the wrong shape gets
    a 400 that looks exactly like a text-only model -- which is how this probe
    first reported two models that read images perfectly well as blind.
    """
    provider = str(spec.get("provider", "openai")).lower()
    started = time.time()
    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(
            api_key=os.environ[spec.get("api_key_env", "ANTHROPIC_API_KEY")]
        )
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": image},
            }
            for image in images
        ]
        content.append({"type": "text", "text": text_prompt})
        message = client.messages.create(
            model=spec["model"],
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(
            b.text for b in message.content if getattr(b, "type", "") == "text"
        )
        return text, message.stop_reason, dict(message.usage), time.time() - started

    client = client_for(spec)
    oai: list[dict[str, Any]] = [{"type": "text", "text": text_prompt}]
    for image in images:
        oai.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image}"},
            }
        )
    kwargs: dict[str, Any] = {
        "model": spec["model"],
        "messages": [{"role": "user", "content": oai}],
    }
    if str(spec.get("base_url", "")).startswith("https://api.openai.com"):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
    # Three providers, three switches. OpenAI's own API rejects
    # chat_template_kwargs outright as an unknown parameter, so sending the
    # vLLM-shaped flag there fails the *image* test too and looks like
    # blindness -- the same confusion this probe exists to prevent.
    extra = dict(spec.get("extra_body") or {})
    if thinking is not None:
        if str(spec.get("base_url", "")).startswith("https://api.openai.com"):
            kwargs["reasoning_effort"] = "low" if thinking else "none"
        else:
            template = dict(extra.get("chat_template_kwargs") or {})
            template["enable_thinking"] = thinking
            extra["chat_template_kwargs"] = template
    if extra:
        kwargs["extra_body"] = extra
    completion = client.chat.completions.create(**kwargs)
    choice = completion.choices[0]
    reasoning = getattr(choice.message, "reasoning_content", None) or getattr(
        choice.message, "reasoning", None
    )
    usage = completion.usage
    return (
        (choice.message.content or ""),
        choice.finish_reason,
        {
            "in": getattr(usage, "prompt_tokens", None),
            "out": getattr(usage, "completion_tokens", None),
            "reasoning_content_len": len(reasoning or ""),
            "model_reported": completion.model,
        },
        time.time() - started,
    )


def probe_one(spec: dict[str, Any]) -> dict[str, Any]:
    """Everything we can learn about one endpoint without burning much."""
    name = spec.get("name") or spec["model"]
    report: dict[str, Any] = {
        "name": name,
        "provider": spec.get("provider", "openai"),
        "model": spec["model"],
        "base_url": spec.get("base_url"),
        "reachable": False,
        "served_models": None,
        "text": None,
        "image_accepted": None,
        "image_understood": None,
        "thinking": None,
        "notes": [],
    }

    # What does the server say it serves? vLLM answers /v1/models; hosted
    # providers generally do not, which is fine.
    base_url = spec.get("base_url")
    if base_url:
        try:
            import urllib.request

            request = urllib.request.Request(
                base_url.rstrip("/") + "/models",
                headers={
                    "Authorization": f"Bearer {os.environ.get(spec.get('api_key_env', ''), 'x')}"
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read())
            report["served_models"] = [m.get("id") for m in data.get("data", [])][:6]
        except Exception as exc:  # noqa: BLE001
            report["notes"].append(f"/models unavailable: {type(exc).__name__}")

    # 1. Plain text.
    try:
        text, finish, usage, elapsed = ask(
            spec, "Reply with the single word: ready", [], 32, None
        )
        report["reachable"] = True
        report["text"] = {
            "reply": text.strip()[:60],
            "finish": finish,
            "latency_s": round(elapsed, 2),
            "usage": usage,
        }
    except Exception as exc:  # noqa: BLE001
        report["notes"].append(
            f"text call failed: {type(exc).__name__}: {str(exc)[:200]}"
        )
        return report

    # 2. Does it accept an image at all, and 3. can it read one? A solid swatch
    # is unambiguous: a model that names the colour is genuinely looking, and one
    # that guesses is caught by using a colour it cannot infer from the prompt.
    image = swatch((16, 120, 220))  # a distinctly blue square
    try:
        # A generous budget, with thinking off where the endpoint honours it. A
        # 32-token budget truncated the thinking block on four reasoning models,
        # returning empty content that this probe then reported as blindness.
        # Truncation is not evidence of blindness.
        text, finish, usage, elapsed = ask(
            spec,
            "What colour is this image? Answer with one word.",
            [image],
            int(spec.get("probe_image_tokens", 2048)),
            False if spec.get("probe_thinking", True) else None,
        )
        report["image_accepted"] = True
        answer = text.strip().lower()
        report["image"] = {
            "reply": text.strip()[:60],
            "finish": finish,
            "latency_s": round(elapsed, 2),
            "usage": usage,
        }
        if "blue" in answer:
            report["image_understood"] = True
        elif finish == "length" or not answer:
            # Inconclusive, not negative.
            report["image_understood"] = None
            report["notes"].append(
                f"image test inconclusive: finish={finish!r}, empty or truncated "
                f"reply after {(usage or {}).get('out')} tokens with "
                f"{(usage or {}).get('reasoning_content_len')} chars of reasoning. "
                "Raise probe_image_tokens or disable thinking for this endpoint."
            )
        else:
            report["image_understood"] = False
            report["notes"].append(
                f"accepted an image but named the wrong colour ({answer[:40]!r}) -- "
                "likely text-only with the image silently dropped"
            )
    except Exception as exc:  # noqa: BLE001
        report["image_accepted"] = False
        report["image_understood"] = False
        report["notes"].append(
            f"image rejected: {type(exc).__name__}: {str(exc)[:200]}"
        )

    # 4. Thinking, with a budget big enough not to truncate. A truncated
    # thinking block returns empty content, which is indistinguishable from a
    # blind model unless you look at finish_reason.
    if spec.get("probe_thinking", True) and report["provider"] != "anthropic":
        # Measure thinking rather than assume it. The old check only asked
        # whether a reply came back, which "passes" for a model that has no
        # thinking mode at all -- vLLM accepts an unknown chat-template kwarg
        # and ignores it. Compare output length with the flag off and on: real
        # thinking costs materially more tokens.
        question = "What is 17 times 23? Answer with the number."
        budget = int(spec.get("probe_thinking_tokens", 8192))
        measured: dict[str, Any] = {}
        for label, flag in (("off", False), ("on", True)):
            try:
                text, finish, usage, elapsed = ask(spec, question, [], budget, flag)
                measured[label] = {
                    "out_tokens": usage.get("out"),
                    "reasoning_content_len": usage.get("reasoning_content_len"),
                    "finish": finish,
                    "content_empty": not text.strip(),
                    "latency_s": round(elapsed, 2),
                    "reply": text.strip()[:40],
                }
            except Exception as exc:  # noqa: BLE001
                measured[label] = {"error": f"{type(exc).__name__}: {str(exc)[:140]}"}
        report["thinking_probes"] = measured
        off, on = measured.get("off", {}), measured.get("on", {})
        if off.get("error") or on.get("error"):
            report["thinking"] = "error"
        elif on.get("content_empty"):
            report["thinking"] = "empty"
            report["notes"].append(
                f"thinking returned empty content at {budget} tokens "
                f"(finish={on.get('finish')!r}); raise probe_thinking_tokens"
            )
        elif (on.get("out_tokens") or 0) > (off.get("out_tokens") or 0) * 2 + 20:
            report["thinking"] = "yes"
        else:
            # Accepted the flag and produced no more output: the switch is a
            # no-op here, which is what a model with no thinking mode does.
            report["thinking"] = "ignored"
            report["notes"].append(
                f"enable_thinking made no difference to output length "
                f"({off.get('out_tokens')} -> {on.get('out_tokens')} tokens); "
                "this endpoint appears to have no thinking mode"
            )
    return report


def _main_probe() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", required=True, type=pathlib.Path)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--json", type=pathlib.Path, default=None)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any endpoint is blind or inconclusive, so a "
        "sweep can be gated on it.",
    )
    args = parser.parse_args()
    # `--env` is the documented way to name the target; an explicit
    # `--base-url` still wins, so existing scripts keep working. Only the
    # subcommands that actually reach the environment define `--env`.
    if getattr(args, "env", None) and getattr(args, "base_url", None) is None:
        args.base_url = resolve_env_url(args.env)

    specs = json.loads(args.models.read_text())
    logger.info("probing %d endpoint(s) with %d workers\n", len(specs), args.workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        reports = list(pool.map(probe_one, specs))

    header = f"{'name':22} {'up':>3} {'img ok':>7} {'reads img':>10} {'think':>14} {'lat':>6}"
    logger.info(header)
    logger.info("-" * len(header))
    for r in reports:
        logger.info(
            "%-22s %3s %7s %10s %14s %6s",
            r["name"][:22],
            "yes" if r["reachable"] else "NO",
            {True: "yes", False: "NO", None: "-"}[r["image_accepted"]],
            {True: "yes", False: "NO", None: "?"}[r["image_understood"]],
            str(r.get("thinking") or "-"),
            (r.get("text") or {}).get("latency_s", "-"),
        )
    logger.info("")
    for r in reports:
        for note in r["notes"]:
            logger.info("  %s: %s", r["name"], note)

    if args.json:
        args.json.write_text(json.dumps(reports, indent=2, default=str))
        logger.info("\nfull report -> %s", args.json)

    blind = [r["name"] for r in reports if r["image_understood"] is False]
    unclear = [
        r["name"] for r in reports if r["reachable"] and r["image_understood"] is None
    ]
    if blind:
        logger.warning(
            "\n%d endpoint(s) cannot read images: %s\n"
            "Running a geolocation eval on these measures guessing, not "
            "geolocation. Keep them only as a deliberate blind baseline.",
            len(blind),
            ", ".join(blind),
        )
    if unclear:
        logger.warning(
            "\n%d endpoint(s) inconclusive: %s\n"
            "Not established as blind -- the test was truncated or empty. "
            "Resolve before excluding them.",
            len(unclear),
            ", ".join(unclear),
        )
    # Exit non-zero so this can gate a sweep. A text-only model in a
    # geolocation eval does not fail loudly -- it scores near the
    # guess-from-prior floor and reads as a weak model rather than a
    # misconfiguration, which is worth catching before hours of rollouts.
    down = [r["name"] for r in reports if not r["reachable"]]
    if down:
        logger.warning(
            "\n%d endpoint(s) unreachable: %s\n"
            "A sweep would record errors for every task on these.",
            len(down),
            ", ".join(down),
        )
    if args.strict and (blind or unclear or down):
        raise SystemExit(1)


# --------------------------------------------------------------------------
# Checking a recorded episode replays frame for frame
#   (was verify_replay.py)
# --------------------------------------------------------------------------

# `replay` is the one subcommand that needs the environment itself: it
# re-renders a recorded camera pose and compares the image hash. The import is
# deliberately lazy, so that `run`, `report` and `probe` keep working against a
# URL with no checkout of the environment source installed.
def _env_renderers():
    """Import the environment's panorama backend and encoder, on demand."""
    try:
        from geoguesser_env.server.backends.panorama import PanoramaBackend
        from geoguesser_env.server.render.pano import to_base64
    except ImportError as exc:  # noqa: BLE001 - the message is the point
        raise SystemExit(
            "replay needs the environment installed: run it as\n"
            "  uv run --with ./env python eval/geoeval.py replay ...\n"
            f"({exc})"
        ) from exc
    return PanoramaBackend, to_base64


INDEX_FOR_SPLIT = {
    "eval": "eval_pano_v3.jsonl",
    "train": "train_pano_v3.jsonl",
}


def rendered_digest(backend, task, camera: dict, view_size: tuple[int, int]) -> str:
    """sha256 of the view the environment would have produced for this camera."""
    image = backend.render_view(
        task,
        int(camera["frame_index"]),
        float(camera["heading_deg"]),
        float(camera["pitch_deg"]),
        float(camera["fov_deg"]),
    )
    if image.size != view_size:
        image = image.resize(view_size)
    _, to_base64 = _env_renderers()
    return hashlib.sha256(base64.b64decode(to_base64(image))).hexdigest()


def _main_replay() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episodes", type=pathlib.Path)
    parser.add_argument("--view-size", type=int, default=640)
    parser.add_argument("--cache", type=pathlib.Path, default=ROOT / "data" / "panos")
    parser.add_argument("--tasks-dir", type=pathlib.Path, default=ROOT / "tasks")
    parser.add_argument("--limit", type=int, default=None, help="First N episodes.")
    args = parser.parse_args()
    # `--env` is the documented way to name the target; an explicit
    # `--base-url` still wins, so existing scripts keep working. Only the
    # subcommands that actually reach the environment define `--env`.
    if getattr(args, "env", None) and getattr(args, "base_url", None) is None:
        args.base_url = resolve_env_url(args.env)

    rows = [
        json.loads(line)
        for line in args.episodes.read_text().splitlines()
        if line.strip()
    ]
    rows = [r for r in rows if not r.get("error")]
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit(f"no usable episodes in {args.episodes}")

    size = (args.view_size, args.view_size)
    PanoramaBackend, _ = _env_renderers()
    backends: dict = {}
    stats = collections.Counter()
    failures: list[str] = []

    for row in rows:
        split = row["task"]["split"]
        if split not in backends:
            name = INDEX_FOR_SPLIT.get(split)
            if name is None:
                logger.warning("no index known for split %r, skipping", split)
                stats["skipped_split"] += 1
                continue
            backends[split] = PanoramaBackend(
                index_path=args.tasks_dir / name,
                cache_dir=args.cache,
                allow_fetch=False,
            )
        backend = backends[split]
        task = backend.task(int(row["task"]["index"]))
        for turn in row["turns"]:
            if turn.get("image_kind") != "view" or not turn.get("image_sha256"):
                # Maps depend on the OSM cache and the Overpass response of the
                # moment, so they are not reproducible by construction and are
                # not claimed to be.
                stats["not_a_view"] += 1
                continue
            camera = turn["camera_after"]
            if camera.get("frame_index") is None:
                stats["no_camera"] += 1
                continue
            try:
                digest = rendered_digest(backend, task, camera, size)
            except Exception as exc:  # noqa: BLE001
                stats["render_error"] += 1
                failures.append(
                    f"{row['episode_id']} turn {turn['turn']}: {type(exc).__name__}: {exc}"
                )
                continue
            if digest == turn["image_sha256"]:
                stats["match"] += 1
            else:
                stats["mismatch"] += 1
                failures.append(
                    f"{row['episode_id']} turn {turn['turn']} "
                    f"(split {split} index {row['task']['index']}, "
                    f"h={camera['heading_deg']} fov={camera['fov_deg']}): "
                    f"rendered {digest[:12]} != recorded {turn['image_sha256'][:12]}"
                )

    checked = stats["match"] + stats["mismatch"]
    logger.info(
        "%d episodes · %d view turns checked · %d match · %d mismatch",
        len(rows),
        checked,
        stats["match"],
        stats["mismatch"],
    )
    for label in ("not_a_view", "no_camera", "render_error", "skipped_split"):
        if stats[label]:
            logger.info("  %s: %d", label, stats[label])
    for line in failures[:20]:
        logger.error("  %s", line)

    if stats["mismatch"] or stats["render_error"]:
        raise SystemExit(
            f"{stats['mismatch']} mismatched and {stats['render_error']} unrenderable "
            "turns: a video of this run would not show what the model saw"
        )
    if not checked:
        raise SystemExit("nothing was verified; check --view-size and the paths")
    logger.info("every view turn reproduces byte-for-byte")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main() -> None:
    """Dispatch to one of the four things this file does."""
    parser = argparse.ArgumentParser(
        prog="geoeval",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", add_help=False, help="drive rollouts against a served environment")
    sub.add_parser("report", add_help=False, help="pool passes into a pass@k table")
    sub.add_parser("probe", add_help=False, help="check endpoints answer, and can see")
    sub.add_parser("replay", add_help=False, help="check a recording replays frame for frame")

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        parser.print_help()
        raise SystemExit(0)

    command, rest = sys.argv[1], sys.argv[2:]
    handlers = {
        "run": _main_collect,
        "report": _main_report,
        "probe": _main_probe,
        "replay": _main_replay,
    }
    if command not in handlers:
        parser.error(f"unknown command {command!r}; choose from {', '.join(handlers)}")

    # Each handler parses its own arguments, so hand it a clean argv.
    sys.argv = [f"geoeval {command}", *rest]
    handlers[command]()


if __name__ == "__main__":
    main()
