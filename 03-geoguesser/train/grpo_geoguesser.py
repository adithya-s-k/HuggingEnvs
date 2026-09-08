# /// script
# requires-python = ">=3.11"
# dependencies = [
#   # The vllm extra, not a bare "vllm": TRL 1.12 requires vllm<=0.27.1, and
#   # letting uv resolve vllm independently picked a newer release whose
#   # weight_transfer module no longer exports NCCLTrainerSendWeightsArgs, so
#   # importing GRPOTrainer failed outright. `hf jobs uv run` builds a fresh
#   # environment from this header and does not inherit the --image's curated
#   # versions, so the pin has to live here.
#   "trl[vllm]>=1.12.0,<1.13",
#   "transformers>=5.2.0",
#   "peft",
#   "trackio",
#   "datasets",
#   "accelerate",
#   # Pinned to a commit, not a branch. uv keys its environment cache on the
#   # dependency spec, so an unpinned git URL is resolved once and then reused
#   # forever: a redeployed Space produced a byte-identical spec, uv served the
#   # cached build of the *old* commit, and the job failed twice with a bug that
#   # had already been fixed. A pin also makes the run reproducible.
#   "openenv-geoguesser-env @ git+https://huggingface.co/spaces/HuggingEnvs/geoguesser-env@da0ad01a0e39844030c6d2ad1ced25286a46ede9#subdirectory=geoguesser_env",
# ]
# ///
"""Multi-turn GRPO on the GeoGuesser environment, for Hugging Face Jobs.

The model plays the game: it looks around a street-level panorama, zooms in on
signage, walks along the road, pins candidate coordinates on a map, and finally
commits to a latitude and longitude. It is scored on how many kilometres it was
off. Every one of those is a tool call, so the environment is queried between
generations -- this is genuinely multi-turn, not a single-shot task with a
scoring step.

The environment arrives as a dependency, not a checkout. The PEP 723 header
above pip-installs `openenv-geoguesser-env` from the Space repo, which brings
the typed client and typed actions with it, so `GuessAction(lat=..., lon=...)`
is a real class and `result.done` is a real field rather than a dict lookup that
might silently return `None`.

TRL's `environment_factory` drives the loop: every public method of the
environment class below becomes a tool the model may call during generation, and
`get_reward` is called once per completed rollout. Tool results may be
multimodal content blocks, which is what makes a *visual* agent loop possible --
each `look` hands the new view back as an image. Verified against Qwen3.5-4B's
own chat template, which renders it as
`<tool_response><|vision_start|><|image_pad|><|vision_end|>...</tool_response>`.

Run it:

    hf jobs uv run \\
        --flavor a100-large \\
        --timeout 6h \\
        --secrets HF_TOKEN \\
        --image huggingface/trl \\
        train/grpo_geoguesser.py

Before spending a GPU, exercise everything except the gradient from a laptop
against any served copy of the model -- see `simulate_rollout.py`. That is how
both of the bugs described in `README.md` were found.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import math
import os
import pathlib
import random
import re
import sys
import threading
import time

import torch
from datasets import Dataset
from geoguesser_env.models import (
    GuessAction,
    LookAction,
    MoveAction,
    PinAction,
    to_wire,
    ZoomAction,
)
from geoguesser_env.client import GeoGuesserEnv
from geoguesser_env.server.geoguesser_environment import GeoGuesserEnvironment
from geoguesser_env.server.render.minimap import set_street_detail
from peft import LoraConfig
from PIL import Image
from transformers import TrainerCallback
from trl import GRPOConfig, GRPOTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("grpo_geoguesser")

# ---------------------------------------------------------------- settings

MODEL = os.getenv("MODEL", "Qwen/Qwen3.5-4B")
# Where the environment runs.
#
# "hosted" is the default and talks to the Space over HTTP -- the same
# deployment anyone reproducing this would use, which is the point: a training
# run that only works against a private in-process copy is not reproducible.
#
# "inprocess" runs the environment in this process against a mounted panorama
# store. It is faster per turn (12.5s against 16.0s per turn measured at the
# same batch size) because TRL's tool loop walks a batch's rollouts one at a
# time and calls a synchronous tool immediately, so 16 rollouts x 24 turns is up
# to 384 sequential round trips. It is not the default because generation, not
# the environment, turned out to dominate a step -- the mode buys about 20s of a
# 280s step, which does not justify diverging from what users run.
ENV_MODE = os.getenv("ENV_MODE", "hosted")
ENV_URL = os.getenv("ENV_URL", "https://huggingenvs-geoguesser-env.hf.space")
PANO_CACHE = os.getenv("PANO_CACHE", "/panos/panos")
TASK_INDEX = os.getenv("TASK_INDEX", "/panos/tasks/train_pano_v3.jsonl")
SPLIT = os.getenv("SPLIT", "train")
HUB_MODEL_ID = os.getenv("HUB_MODEL_ID", "HuggingEnvs/geoguesser-qwen3.5-4b-grpo")

# Matches the eval harness, where models average 7-11 turns. It must also be the
# *only* budget the model is told about; see `_blocks`.
MAX_TURNS = int(os.getenv("MAX_TURNS", "24"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "200"))
NUM_GENERATIONS = int(os.getenv("NUM_GENERATIONS", "8"))
# Kept low deliberately. Each concurrent rollout holds one environment session,
# and the hosted Space caps concurrent sessions (64 as deployed). This is the
# number that decides whether a run dies with CAPACITY_REACHED an hour in.
GENERATION_BATCH_SIZE = int(os.getenv("GENERATION_BATCH_SIZE", "16"))
# The environment renders at 640px. Downscaled to 448 the view costs 196 tokens
# (16px patches, 2x2 merge), the largest size that leaves twelve turns of images
# comfortably inside the completion budget. 336px would halve it to 110, but
# reading a road sign is the task, so resolution is not the first thing to trade.
VIEW_PX = int(os.getenv("VIEW_PX", "448"))
MAX_MODEL_LEN = int(os.getenv("MAX_MODEL_LEN", "32768"))
SEED = int(os.getenv("SEED", "0"))

# Every run gets its own name and its own output directory. Trackio resumes a
# run when the name matches (`resume="allow"`), so a fixed name would silently
# interleave two experiments into one set of curves, and a fixed output
# directory would have a later run's checkpoints overwrite an earlier one's on
# the shared bucket. The Job id makes it unique without needing a counter.
RUN_NAME = os.getenv(
    "RUN_NAME",
    "{}-{}-{}".format(
        MODEL.split("/")[-1].lower(),
        time.strftime("%Y%m%d-%H%M", time.gmtime()),
        os.getenv("JOB_ID", "local")[:6],
    ),
)
OUTPUT_ROOT = os.getenv("OUTPUT_ROOT", os.getenv("OUTPUT_DIR", "runs"))
OUTPUT_DIR = f"{OUTPUT_ROOT.rstrip('/')}/{RUN_NAME}"
# One project for every run, so runs land on a single comparable axis. The
# first three runs predate this and were logged to `geoguesser-grpo` and
# `geoguesser-v2`; their scalar metrics were merged into `geoguesser`, which is
# what the unified dashboard reads.
TRACKIO_PROJECT = os.getenv("TRACKIO_PROJECT", "geoguesser")
# The public dashboard, alongside the model it produces. Trackio grants this
# Space read/write on the bucket behind it and stores the job's token there as a
# Space secret, so it is deliberately a repo the project owns, not a personal one.
TRACKIO_SPACE = "HuggingEnvs/geoguesser-trackio"
TRACKIO_BUCKET = "HuggingEnvs/geoguesser-trackio-bucket"

# Rollout traces, for rendering video afterwards. Images are deliberately not
# stored: the environment is deterministic, so a camera pose plus the task
# identity re-renders the same frame byte for byte (verified against recorded
# checksums). A trace is therefore a few kB of numbers instead of ~90 kB of
# JPEG per turn -- about 2 MB per 100 rollouts rather than 2 GB.
TRACE_ROLLOUTS = os.getenv("TRACE_ROLLOUTS", "1") not in ("0", "false", "False")
# Number of GPUs to shard the rollouts across. `hf jobs uv run` insists on a
# .py entrypoint, so `accelerate launch` cannot be the command -- instead the
# script re-executes itself under `torchrun` (see `_relaunch_distributed`),
# which keeps the PEP 723 header as the single source of dependencies.
NPROC = int(os.getenv("NPROC", "1"))
WORLD_SIZE = int(os.getenv("WORLD_SIZE", str(NPROC)))

# ---------------------------------------------------------------- reward

DECAY_KM = 1492.7
# Raising MIXTURE_SHORT_WEIGHT and lowering LONG_DECAY_KM make precision pay
# relative to being roughly in the right region. At the shipped 0.5/5000 a guess
# 534 km out scores 0.699, so naming a region's largest city is nearly as good
# as pinpointing -- which is exactly the policy the first run converged on.
# Defaults are left as run 1 used them so the reward never changes silently.
LONG_DECAY_KM = float(os.getenv("LONG_DECAY_KM", "5000.0"))
MIXTURE_SHORT_WEIGHT = float(os.getenv("MIXTURE_SHORT_WEIGHT", "0.5"))
# Scales the environment's action cost before it is applied. Run 1 measured a
# mean cost of 0.002 on the converged policy, so cost was never what suppressed
# exploration -- but a smaller value removes any residual disincentive.
COST_SCALE = float(os.getenv("COST_SCALE", "1.0"))
# How much of the distance score the action cost is allowed to remove. The
# environment ships 0.5 for the *game*, where an episode can run
# as long as the player likes and the cost is the only thing discouraging a
# 50-action grind. Training already caps an episode at MAX_TURNS, so the budget
# is the real efficiency constraint and this term only has to break ties.
# Measured over 42 smoke episodes: exploring above the median cost is worth
# +0.147 reward in accuracy alone, but only +0.016 once a 0.5 cap is applied --
# the cost term erases 89% of the signal that exploring pays. At 0.2 it keeps
# +0.113 of it while still preferring the cheaper of two equally good rollouts.
MAX_COST_FRACTION = float(os.getenv("MAX_COST_FRACTION", "0.2"))


def training_reward(distance_km: float | None, cost: float) -> float:
    """
    The reward the policy is actually optimising.

    Computed here rather than read off the environment, for two reasons. The
    hosted Space is configured for play, so one deployment serves both this and
    the published leaderboard. And a reward function that lives in the training
    script is one you can read and change without redeploying anything.

    Two departures from the game's own curve, both measured over 3,037 recorded
    episodes:

    - **Two decay scales.** `exp(-d/1492.7)` is worth 0.018 across the entire
      6,000-20,000 km range, and about a third of a 4B model's guesses land
      there, so getting *less* wrong on the wrong continent earns almost
      nothing. The 5,000 km scale makes that span worth 0.150.
    - **Multiplicative cost.** `max(0, score - cost)` floored 77 of 200
      episodes at exactly 0.0 with zero variance between them -- a 3,324 km miss
      scoring the same as an 18,723 km miss. A GRPO group drawn from those has
      no advantage and yields no gradient. Scaling by a positive factor cannot
      collapse an ordering.

    Args:
        distance_km (`float` or `None`):
            Kilometres between guess and truth. `None` means the episode ended
            without a usable guess.
        cost (`float`):
            Accumulated action cost reported by the environment.

    Returns:
        `float`: Reward in `[0, 1]`. Any guess anywhere on Earth scores above
        zero, so committing always beats running out of turns -- the dominant
        failure of small models on this task.
    """
    if distance_km is None:
        return 0.0
    short = math.exp(-distance_km / DECAY_KM)
    long = math.exp(-distance_km / LONG_DECAY_KM)
    score = MIXTURE_SHORT_WEIGHT * short + (1.0 - MIXTURE_SHORT_WEIGHT) * long
    charged = max(cost, 0.0) * COST_SCALE
    return min(1.0, score) * (1.0 - min(charged, MAX_COST_FRACTION))


# ---------------------------------------------------------------- prompt

INSTRUCTION = """You are dropped at a random street location on Earth. Work out where you are.

Use the tools to gather evidence before committing:
- `look` to turn the camera. Road signs, licence plates, which side of the road
  traffic drives on, vegetation, architecture and language all narrow it down.
- `zoom` to read something distant, like a shop name or a road number.
- `move` to walk along the road toward a sign you cannot read from here.
- `pin` to drop a candidate on the map. It tells you what country and city are
  actually at that coordinate, so you can turn a hunch into a real location. It
  never tells you whether you are close to the answer.
- `guess` to commit. This ends the episode and is scored on distance.

You may pin several candidates and refine before guessing.

You have {max_turns} tool calls and every result tells you how many are left.
Budget them: spend the first few gathering evidence, then commit. You MUST call
`guess` before they run out -- an episode that never guesses scores zero, which
is worse than any guess, however rough. When you are down to a couple of
actions, stop looking and guess."""

# The environment's own step counter, stripped from feedback before the model
# sees it so there is exactly one turn budget in play. See `_blocks`.
_ENV_BUDGET = re.compile(r"\s*\d+\s+actions?\s+left\.?", re.I)

# Fields the environment sends that identify the task rather than describe it.
# The Mapillary contributor determines the country outright for 74% of training
# tasks ("amsterdam" only maps the Netherlands), and task_index/task_id/
# sequence_id are a few thousand memorisable keys straight to a coordinate.
# Either lets a policy score without ever looking at the image.
IDENTITY_FIELDS = ("attribution", "sequence_id", "task_id", "task_index", "captured_at")


# One writer for the whole process. TRL drives tool calls from the main thread,
# but environment instances are pooled and reused across rollouts, so a lock is
# cheap insurance against a future async rollout worker interleaving lines.
_TRACE_LOCK = threading.Lock()
_TRACE_PATH: pathlib.Path | None = None
# The training step each rollout belongs to, so a video can contrast step 0 with
# step 100. The environment cannot see the trainer, so a callback publishes it.
_TRAIN_STEP = {"value": 0}


class _StepRecorder(TrainerCallback):
    """Publish the global step so rollout traces can be grouped by it."""

    def on_step_begin(self, args, state, control, **kwargs):  # noqa: D102
        _TRAIN_STEP["value"] = int(state.global_step)


def _trace_path() -> pathlib.Path | None:
    """Where rollout traces are appended, created on first use."""
    global _TRACE_PATH
    if not TRACE_ROLLOUTS:
        return None
    if _TRACE_PATH is None:
        directory = pathlib.Path(OUTPUT_DIR) / "traces"
        directory.mkdir(parents=True, exist_ok=True)
        # One file per rank under DDP. `_TRACE_LOCK` only serialises threads
        # inside one process, so four ranks appending to a single file on a
        # bucket mount would interleave and tear lines.
        rank = os.getenv("RANK")
        suffix = f"-rank{rank}" if rank is not None and WORLD_SIZE > 1 else ""
        _TRACE_PATH = directory / f"rollouts{suffix}.jsonl"
    return _TRACE_PATH


def _write_trace(record: dict) -> None:
    """Append one rollout as a single JSON line.

    Appended per rollout rather than buffered: a line is under 4 kB, and a run
    that dies at hour six should still have its first six hours of traces.
    """
    path = _trace_path()
    if path is None:
        return
    line = json.dumps(record, separators=(",", ":")) + "\n"
    try:
        with _TRACE_LOCK, path.open("a") as handle:
            handle.write(line)
    except Exception as exc:  # noqa: BLE001 - never fail a rollout over telemetry
        logger.warning("could not write rollout trace: %s", exc)


def _view(image_base64: str | None) -> Image.Image | None:
    """Decode and downscale an observation's image."""
    if not image_base64:
        return None
    image = Image.open(io.BytesIO(base64.b64decode(image_base64))).convert("RGB")
    if max(image.size) > VIEW_PX:
        image.thumbnail((VIEW_PX, VIEW_PX), Image.LANCZOS)
    return image


# ---------------------------------------------------------------- environment


class GeoGuesserTrainingEnv:
    """One episode of GeoGuesser, exposed to TRL as a set of tools.

    Every public method here becomes a tool the model may call during
    generation, so everything that is not a tool is underscore-prefixed.
    Docstrings and type hints are not decoration: TRL turns them into the tool
    schema the model sees, via `transformers.utils.get_json_schema`.

    Reached over HTTP through the environment's own typed client, so this works
    identically against the hosted Space and a local server.
    """

    def __init__(self) -> None:
        self._env: GeoGuesserEnvironment | None = None
        self._done = True
        self._distance_km: float | None = None
        self._cost = 0.0
        self._turns = 0
        self._trace: list[dict] = []
        self._task: dict = {}
        self._camera: dict = {}

    # -- not tools --------------------------------------------------------

    def _connect(self):
        """One environment per instance, reused across resets.

        Either backend answers `reset` and `step` with a `GeoGuesserObservation`;
        they differ only in where `done` lives, which `_step` normalises.
        """
        if self._env is None:
            if ENV_MODE == "inprocess":
                self._env = GeoGuesserEnvironment(
                    index_path=TASK_INDEX,
                    cache_dir=PANO_CACHE,
                    # A cache miss must be an error, not a silent network call:
                    # the store is complete, so a miss means the mount is wrong.
                    allow_fetch=False,
                    view_size=VIEW_PX,
                    max_steps=MAX_TURNS,
                    # Withheld at the source rather than scrubbed afterwards.
                    hide_task_identity=True,
                    # Only a person looks at the reveal map, and it costs 270ms
                    # on every terminal step.
                    reveal_map=False,
                )
            else:
                self._env = GeoGuesserEnv(
                    base_url=ENV_URL,
                    message_timeout_s=180.0,
                    # The websocket keepalive runs on a background thread that
                    # competes with generation and the backward pass for the
                    # GIL. At the 20s default a starved loop misses its own
                    # pong deadline and the client tears down a healthy
                    # connection, so the deadline is well clear of one
                    # optimizer step (~130s on the 4B at ACCUM=4).
                    websocket_ping_interval_s=20.0,
                    websocket_ping_timeout_s=300.0,
                )
        return self._env

    def _reconnect(self) -> None:
        """Drop the current client so the next call builds a fresh one."""
        env = self._env
        self._env = None
        if env is None or ENV_MODE == "inprocess":
            self._env = env
            return
        try:
            env.close()
        except Exception:  # noqa: BLE001 - it is already broken
            pass

    @staticmethod
    def _transport_died(error: Exception) -> bool:
        """Whether this exception means the websocket is gone, not the task.

        Matched on the exception name and message rather than by importing
        `websockets`, so the check still holds if the client's transport is
        swapped.
        """
        text = f"{type(error).__name__}: {error}"
        return any(
            mark in text
            for mark in (
                "ConnectionClosed",
                "close frame",
                "ConnectionResetError",
                "ConnectionRefusedError",
                "Connection is closed",
                "no running event loop",
                "Broken pipe",
            )
        )

    def _apply(self, action):
        """Send one action and return `(observation, done)`.

        The client wraps its observation in a `StepResult` that carries `done`
        separately; the in-process environment puts `done` on the observation.
        Reading it from the wrong one left every episode unterminated and every
        reward at 0.0, so the two are reconciled in exactly one place.
        """
        result = self._env.step(action)
        observation = getattr(result, "observation", result)
        done = bool(getattr(result, "done", False)) or bool(
            getattr(observation, "done", False)
        )
        return observation, done

    @staticmethod
    def _camera_of(observation) -> dict:
        """The pose a later re-render needs, and nothing else.

        Heading, pitch and field of view plus the frame index fully determine
        the rendered view for a given task, so a trace of these replays the
        episode exactly without storing a single pixel.
        """
        metadata = observation.metadata or {}
        return {
            "heading_deg": observation.heading_deg,
            "pitch_deg": observation.pitch_deg,
            "fov_deg": observation.fov_deg,
            "frame_index": metadata.get("frame_index"),
        }

    def _record(self, action: dict, observation, image_base64: str | None) -> None:
        """Append one turn to the rollout trace."""
        if not TRACE_ROLLOUTS:
            return
        after = self._camera_of(observation)
        self._trace.append(
            {
                "turn": self._turns,
                "action": action,
                "camera_before": self._camera,
                "camera_after": after,
                # Lets a re-render be verified byte-identical rather than
                # assumed so. Hashed before downscaling, which is what the
                # environment actually returned.
                "image_sha256": (
                    hashlib.sha256(image_base64.encode()).hexdigest()[:16]
                    if image_base64
                    else None
                ),
                "image_kind": observation.image_kind,
                "feedback": observation.feedback,
                "pins": [[p.lat, p.lon] for p in (observation.pins or [])],
                "steps_remaining": observation.steps_remaining,
                "moved_meters": observation.moved_meters,
                "action_cost": observation.action_cost,
            }
        )
        self._camera = after

    def _blocks(self, observation, note: str = "") -> list[dict]:
        """An observation as multimodal content blocks for a tool result.

        TRL passes a list of blocks straight through to the processor, which is
        what lets a tool hand back an image rather than a description of one.
        """
        text = note or observation.feedback or ""
        # The environment counts down its own step budget (24 as deployed), but
        # TRL stops the rollout at `max_tool_calling_iterations`. Reporting the
        # environment's number told the model it had 24 actions when it had 12,
        # so it paced itself for a budget it did not have and was cut off before
        # guessing: 0 of 6 simulated episodes ever called `guess`, every reward
        # exactly 0.0, and no advantage in any GRPO group. Only the training
        # loop's budget is ever shown.
        text = _ENV_BUDGET.sub("", text).strip()
        left = max(0, MAX_TURNS - self._turns)
        if left <= 1:
            text = (
                f"{text} THIS IS YOUR FINAL ACTION. Call guess now with your "
                "best estimate -- a rough guess scores far more than none."
            ).strip()
        else:
            text = f"{text} {left} actions left.".strip()

        blocks: list[dict] = []
        image = _view(observation.image_base64)
        if image is not None:
            blocks.append({"type": "image", "image": image})
        blocks.append({"type": "text", "text": text or "(no feedback)"})
        return blocks

    def _step(self, action, note: str = "") -> list[dict]:
        """Apply one typed action, tracking cost and terminal state."""
        if self._done:
            return [{"type": "text", "text": "The episode is over."}]
        self._turns += 1
        try:
            observation, done = self._apply(action)
        except Exception as exc:  # noqa: BLE001 - one bad rollout, not a run
            self._done = True
            logger.warning("step failed: %s", exc)
            # Ending the rollout is right, but a dead socket would otherwise be
            # handed to the next episode's reset, which is what turned one
            # dropped connection into a dead run.
            if self._transport_died(exc):
                self._reconnect()
            return [{"type": "text", "text": f"The environment errored: {exc}"}]
        # The flat wire form, so the record names the operation: a typed
        # action's own `model_dump` gives the fields but not which action it
        # was, which is the one thing a renderer cannot infer.
        self._record(
            to_wire(action).model_dump(exclude_none=True, exclude={"metadata"}),
            observation,
            observation.image_base64,
        )
        self._cost = observation.action_cost or self._cost
        # The distance is kept as a backstop alongside `done`, since its
        # presence is what actually defines a scored guess.
        if done or observation.distance_km is not None:
            self._done = True
            self._distance_km = observation.distance_km
        return self._blocks(observation, note)

    # -- reset and reward -------------------------------------------------

    def reset(
        self, split: str = SPLIT, index: int | None = None, **kwargs
    ) -> list[dict]:
        """
        Start an episode and return the opening view.

        Receives the whole dataset row, so `split` and `index` come from the
        example. That matters for GRPO: every generation in a group comes from
        the same row, so all rollouts in a group play the *same* location and
        their rewards are comparable.

        Returns:
            `list[dict]`: Content blocks appended to the last user message --
            the opening panorama plus the instruction.
        """
        env = self._connect()
        self._done = False
        self._distance_km = None
        self._cost = 0.0
        self._turns = 0
        # The client keeps one websocket per rank for the whole run and reuses
        # it for every episode, so a single drop is otherwise terminal. Run 2
        # died three times here: `ConnectionClosedError: no close frame
        # received or sent`, raised by reset's very first `send` on a socket
        # that had gone away while the rank was busy in the backward pass. The
        # environment Space was healthy each time -- still serving other ranks,
        # and it logged the connection closed only *after* the job exited -- so
        # the drop is an intermediary's and reconnecting is the right response.
        # `_step` already tolerates a mid-episode failure by ending that
        # rollout, but it left the dead client in place, so the next reset
        # inherited it and killed the run.
        for attempt in range(1, 4):
            try:
                result = env.reset(split=split, index=index)
                break
            except Exception as error:  # noqa: BLE001 - re-raised below
                if attempt == 3 or not self._transport_died(error):
                    raise
                logger.warning(
                    "reset failed on a dead environment connection "
                    "(%s: %s); reconnecting, attempt %d of 3",
                    type(error).__name__,
                    error,
                    attempt,
                )
                self._reconnect()
                time.sleep(2.0 * attempt)
                env = self._connect()
        observation = getattr(result, "observation", result)
        self._trace = []
        self._task = {"split": split, "index": index}
        self._camera = self._camera_of(observation)
        self._record({"op": "reset"}, observation, observation.image_base64)
        blocks = self._blocks(observation, note="You are here.")
        blocks.append({"type": "text", "text": INSTRUCTION.format(max_turns=MAX_TURNS)})
        return blocks

    def get_reward(self) -> float:
        """Score the finished rollout, and flush its trace.

        Called once per completed rollout, which makes it the one place that
        knows the episode is over and what it scored.
        """
        reward = training_reward(self._distance_km, self._cost)
        if TRACE_ROLLOUTS and self._trace:
            _write_trace(
                {
                    "run": RUN_NAME,
                    "step": _TRAIN_STEP["value"],
                    "model": MODEL,
                    "env": ENV_URL if ENV_MODE == "hosted" else PANO_CACHE,
                    "task": self._task,
                    "outcome": {
                        "reward": reward,
                        "distance_km": self._distance_km,
                        "action_cost": self._cost,
                        "turns_used": self._turns,
                        "guessed": self._distance_km is not None,
                        "max_turns": MAX_TURNS,
                    },
                    "turns": self._trace,
                }
            )
            self._trace = []
        return reward

    # -- tools ------------------------------------------------------------

    def look(
        self, heading_deg: float, fov_deg: float = 90.0, pitch_deg: float = 0.0
    ) -> list[dict]:
        """Turn the camera to an absolute compass heading and return the view.

        Args:
            heading_deg: Compass heading in degrees, 0 being north, 90 east.
            fov_deg: Horizontal field of view, 10 (zoomed in) to 120 (wide).
                Defaults to 90. Turning and zooming together saves a turn.
            pitch_deg: Vertical angle; positive looks up. Defaults to 0.
        """
        # `fov_deg` is exposed because `LookAction` has always accepted it and
        # omitting it hid a capability the environment already had: a simulated
        # rollout called look(heading_deg=..., fov_deg=...), raised TypeError and
        # burned a turn on a request the environment could have served. It also
        # lets a turn-and-zoom happen in one call instead of two.
        return self._step(
            LookAction(
                heading_deg=float(heading_deg),
                fov_deg=max(10.0, min(120.0, float(fov_deg))),
                pitch_deg=max(-90.0, min(90.0, float(pitch_deg))),
            )
        )

    def zoom(self, fov_deg: float) -> list[dict]:
        """Narrow the field of view to read something distant, and return the view.

        Args:
            fov_deg: New horizontal field of view, 10 (max zoom) to 120 (wide).
        """
        return self._step(ZoomAction(fov_deg=max(10.0, min(120.0, float(fov_deg)))))

    def move(self, direction: str = "forward", meters: float = 20.0) -> list[dict]:
        """Walk along the road and return the view from the new position.

        Args:
            direction: Either "forward" or "backward".
            meters: How far to try to travel. Frame spacing is irregular, so the
                reply says how far you actually moved.
        """
        return self._step(
            MoveAction(
                direction="backward" if str(direction).startswith("b") else "forward",
                meters=max(1.0, min(500.0, float(meters))),
            )
        )

    def pin(self, lat: float, lon: float) -> list[dict]:
        """Drop a candidate coordinate on the map and see what is actually there.

        Returns the country, the nearest major city and a map image. It does not
        say whether the candidate is close to the true location.

        Args:
            lat: Candidate latitude, -90 to 90.
            lon: Candidate longitude, -180 to 180.
        """
        return self._step(
            PinAction(
                lat=max(-90.0, min(90.0, float(lat))),
                lon=max(-180.0, min(180.0, float(lon))),
                span_deg=7.0,
            )
        )

    def guess(self, lat: float, lon: float) -> list[dict]:
        """Commit a final answer. Ends the episode and scores it on distance.

        Args:
            lat: Final latitude, -90 to 90.
            lon: Final longitude, -180 to 180.
        """
        return self._step(
            GuessAction(
                lat=max(-90.0, min(90.0, float(lat))),
                lon=max(-180.0, min(180.0, float(lon))),
            ),
            # Deliberately overrides the environment's feedback, which names the
            # true location and country: the reward is the only channel the
            # outcome travels through.
            note="Guess submitted. The episode is over.",
        )


# ---------------------------------------------------------------- dataset


def build_dataset(split: str, seed: int) -> Dataset:
    """One row per task, shuffled. The row is what `reset` receives."""
    if ENV_MODE == "inprocess":
        total = sum(1 for line in open(TASK_INDEX) if line.strip())
        source = TASK_INDEX
    else:
        total = GeoGuesserEnv(base_url=ENV_URL).num_tasks(split)
        source = ENV_URL
    logger.info("%s split: %d tasks from %s", split, total, source)
    indices = list(range(total))
    random.Random(seed).shuffle(indices)
    return Dataset.from_list(
        [
            {
                # The environment supplies the image and the instruction through
                # `reset`, so the prompt only has to exist for TRL to duplicate
                # it `num_generations` times.
                "prompt": [{"role": "user", "content": [{"type": "text", "text": ""}]}],
                "split": split,
                "index": index,
            }
            for index in indices
        ]
    )


# ---------------------------------------------------------------- main


def main() -> None:
    """Configure and run the trainer, then push the adapter to the Hub."""
    # A long completion against a 248k vocabulary allocates and frees very large
    # logits tensors, which fragments the caching allocator; the OOM this run
    # first hit reported 189 MB reserved-but-unallocated alongside 1.1 GB free.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    # Street labels on the pin map come from Overpass, cached to disk. A Job has
    # no warm cache and its egress gets 504s from Overpass, so leaving this on
    # buys two failed network calls per pin and no labels: `pin` measured 0.714s
    # with it on against 0.207s off. Turned off deliberately rather than left to
    # fail. Note that the eval ran against a Space with a warm cache, so its pin
    # maps did carry street names -- a small difference in what the model sees.
    if ENV_MODE == "inprocess" and os.getenv("STREET_DETAIL", "0") in (
        "0",
        "false",
        "False",
    ):
        set_street_detail(False)
    logger.info(
        "model %s · env %s (%s) · %d turns",
        MODEL,
        ENV_URL if ENV_MODE == "hosted" else PANO_CACHE,
        ENV_MODE,
        MAX_TURNS,
    )

    logger.info("run %s -> %s", RUN_NAME, OUTPUT_DIR)
    # TRL writes its completions parquet into `<output_dir>/completions/` but
    # never creates that directory, and the Trainer only creates `output_dir`
    # itself when it first saves -- which is 25 steps away. Run 1 survived on
    # luck; with two jobs mounting the same bucket read-write, one lost the race
    # and died at step 1 with
    #   OSError: Cannot save file into a non-existent directory: .../completions
    # Creating them up front costs nothing and removes the dependency on both
    # TRL's ordering and the mount's consistency.
    for directory in ("", "completions", "traces"):
        path = pathlib.Path(OUTPUT_DIR) / directory
        path.mkdir(parents=True, exist_ok=True)
        # `mkdir` alone is not enough on a bucket mount: an object store has no
        # real directories, so an *empty* one does not persist and a later
        # `open()` fails with "Cannot save file into a non-existent directory".
        # Writing a file materialises the prefix. This is why `traces/` always
        # worked (we write into it) while `completions/` failed intermittently
        # depending on whether the mount still had the mkdir cached.
        (path / ".keep").write_text("")

    trainer = GRPOTrainer(
        model=MODEL,
        train_dataset=build_dataset(SPLIT, SEED),
        environment_factory=GeoGuesserTrainingEnv,
        # No `reward_funcs`: the environment owns the reward through
        # `get_reward`, which TRL registers as a reward source in its own right.
        peft_config=LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            task_type="CAUSAL_LM",
        ),
        args=GRPOConfig(
            output_dir=OUTPUT_DIR,
            # Same Trackio project, one run per launch. Trackio resumes on a
            # matching name, so without this two experiments would merge into
            # one set of curves.
            project=TRACKIO_PROJECT,
            run_name=RUN_NAME,
            # Synchronous GRPO with vLLM in-process, sharing the training GPU.
            use_vllm=True,
            vllm_mode="colocate",
            # vLLM's share is reserved up front, so this is taken away from
            # training. 0.25 leaves ~60 GB for the logits above.
            vllm_gpu_memory_utilization=float(os.getenv("VLLM_MEM", "0.25")),
            vllm_max_model_length=MAX_MODEL_LEN,
            num_generations=NUM_GENERATIONS,
            generation_batch_size=GENERATION_BATCH_SIZE,
            # This also sets the chunk size TRL uses when it recomputes
            # logprobs over a rollout (grpo_trainer.py:2523), and that is the
            # memory bottleneck rather than the model. Qwen3.5's vocabulary is
            # ~248k, so one chunk's logits are
            # batch x completion_length x 248064 -- at batch 4 and 8,192
            # tokens that is ~16 GB in bf16 before `logsumexp` upcasts, and it
            # OOM'd an 80 GB A100 with vLLM colocated beside it. Keep this at 1
            # and buy the effective batch back through accumulation.
            per_device_train_batch_size=int(os.getenv("BATCH", "1")),
            gradient_accumulation_steps=int(os.getenv("ACCUM", "16")),
            # The turn limit. Without it, generation stops only when the model
            # emits no tool call or fills the context.
            max_tool_calling_iterations=MAX_TURNS,
            # This bounds the WHOLE rollout -- every assistant turn plus every
            # tool result, images included -- not one turn. That is the trap:
            # the eval's per-call `max_tokens` of 4096 is a different quantity
            # about 10x smaller in effect, because there each turn is its own
            # request. Measured on Qwen3.5-4B over 200 eval episodes: 1,497
            # output tokens per episode on average but 5,174 at p95, plus 7.6
            # turns x 196 image tokens and ~30 tokens of feedback per turn.
            # That is ~3,200 typical and ~6,900 at p95. TRL drops a tool result
            # that would exceed the budget and exits the loop, so anything
            # smaller silently ends long episodes without a guess: reward 0,
            # indistinguishable from a model that cannot learn.
            # Scaled with MAX_TURNS, from what the model actually emits rather
            # than from the eval harness. Measured on a real training step:
            # 1,028 output tokens over 11 tool calls, so ~93 per turn -- not the
            # 198 per turn the JSON-action eval suggested, because a tool call
            # is terser than a prose reply. At 24 turns that is
            # 24 x (196 image + 30 feedback + 93 output) = ~7,700 tokens.
            # 12,288 leaves 60% headroom; 16,384 was over-provisioned and cost
            # 2 GB more of logits for nothing.
            max_completion_length=int(os.getenv("MAX_COMPLETION", "12288")),
            # Token-level truncated importance sampling, not the default
            # `sequence_mask`. The default sums per-token logprob differences
            # over the whole completion and exponentiates:
            # `ratio = exp(sum(old - sampling))`. Our completions run ~1,078
            # tokens with a mean per-token difference of 0.15, so the sum is
            # ~160 and the ratio underflows to zero -- and the ratio multiplies
            # the loss directly (grpo_trainer.py:3236). The smoke run reported
            # `importance_sampling_ratio/mean 0.00013, max 0.001`, meaning the
            # whole batch's gradient was scaled to about a ten-thousandth. Two
            # steps of nothing. Per-token ratios stay near exp(-0.15) = 0.86 and
            # are clipped into a sane band instead.
            # Off, which skips a whole extra forward pass over the batch --
            # 16 rollouts x ~7,700 tokens x a 248k vocabulary. The audit run
            # measured the correction's own ratio at a mean of 0.991, so it was
            # multiplying the loss by essentially one at the price of about a
            # quarter of the step's compute. When it is on, `token_truncate`
            # with these bounds is the mode to use: the default `sequence_mask`
            # exponentiates a sum over the whole completion and underflowed the
            # gradient to 0.0001.
            vllm_importance_sampling_correction=(
                os.getenv("IS_CORRECTION", "0") not in ("0", "false", "False")
            ),
            vllm_importance_sampling_mode="token_truncate",
            vllm_importance_sampling_clip_min=float(os.getenv("IS_CLIP_MIN", "0.2")),
            vllm_importance_sampling_clip_max=float(os.getenv("IS_CLIP_MAX", "3.0")),
            max_steps=MAX_STEPS,
            # LoRA tolerates roughly an order of magnitude more than full
            # fine-tuning, and at 100 steps a 1e-5 adapter barely moves. 3e-5
            # is still conservative for r=16; GRPO destabilises well before
            # the 1e-4 a supervised LoRA run would use.
            learning_rate=float(os.getenv("LR", "3e-5")),
            temperature=float(os.getenv("TEMPERATURE", "1.0")),
            # Thinking off: it was not measured in the eval this is calibrated
            # against, and a reasoning block per turn does not fit twelve turns
            # of images in the context window.
            chat_template_kwargs={"enable_thinking": False},
            # A rollout cut off mid-tool-call is not evidence about the policy.
            mask_truncated_completions=True,
            bf16=torch.cuda.is_bf16_supported(),
            gradient_checkpointing=True,
            logging_steps=1,
            save_steps=int(os.getenv("SAVE_STEPS", "25")),
            # Print a couple of rollouts each logging step. On a run this long
            # the metrics say whether it is learning; the completions say why.
            log_completions=True,
            num_completions_to_print=int(os.getenv("PRINT_COMPLETIONS", "2")),
            report_to=os.getenv("REPORT_TO", "trackio"),
            # Without a space or bucket, Trackio writes to
            # ~/.cache/huggingface/trackio -- which is deleted with the Job, so
            # every metric would be lost the moment the run ended. A space_id
            # syncs to a dashboard that outlives the machine and auto-creates a
            # bucket for the history behind it.
            trackio_space_id=os.getenv("TRACKIO_SPACE", TRACKIO_SPACE),
            # Pinned rather than derived. Trackio names the bucket after the
            # Space, so leaving this unset would work -- but the bucket holds the
            # whole metric history, and it should be as explicit as the Space.
            trackio_bucket_id=os.getenv("TRACKIO_BUCKET", TRACKIO_BUCKET),
            # Disables the *static* space export, which is what crashed a
            # completed run: it serialises the run config to Parquet, and PEFT's
            # `LoraConfig` carries `rank_pattern={}` -- an empty dict, hence a
            # struct with no child fields, which Parquet cannot represent.
            trackio_static_space_id=False,
            # `advantages / (std_rewards + 1e-4)` is what destabilised run 1: with
            # one task per optimizer step a group's std collapses as the policy
            # converges, amplifying advantages up to 10,000x and driving grad_norm
            # from 0.18 to 6.3 with nothing to damp it. "none" removes the
            # division; pair it with several tasks per step (ACCUM >= 8) so the
            # advantage is still comparable across a batch.
            scale_rewards=os.getenv("SCALE_REWARDS", "none"),
            # Free with LoRA: TRL sets `ref_model = None` for a PEFT model and
            # gets reference logprobs by disabling the adapters, so a KL anchor
            # costs no extra memory. Off by default because it changes the
            # objective; 0.02 is a reasonable first value.
            beta=float(os.getenv("BETA", "0.0")),
            # Epsilon clipping is inert at one iteration: `old_per_token_logps`
            # equals `per_token_logps` on the only gradient pass, so the ratio is
            # identically 1 and the clamp never binds (run 1 logged
            # clip_ratio 0.000 throughout). Raise this to make the trust region
            # real, at the cost of an extra gradient pass per generation batch.
            num_iterations=int(os.getenv("NUM_ITERATIONS", "1")),
            seed=SEED,
            # Deliberately off, and pushed by hand after training instead.
            # The Trainer's automatic push fires `on_push_begin`, which makes
            # Trackio sync the run to a Space, which serialises the run config
            # to Parquet -- and PEFT's LoraConfig carries `rank_pattern={}`,
            # an empty dict that becomes a struct with no child fields:
            #   ArrowNotImplementedError: Cannot write struct type
            #   'rank_pattern' with no child field to Parquet
            # That killed a run *after* both training steps had succeeded. The
            # checkpoint still reached the mounted bucket, so nothing was lost,
            # but the adapter never reached the Hub.
            push_to_hub=False,
            hub_model_id=HUB_MODEL_ID,
            # Governs the Trackio Space's visibility as well as the model repo's.
            # `None` means "public unless the organization's default is private",
            # so for an org-owned dashboard that is meant to be public, say so
            # rather than inheriting whatever the org is configured to do.
            hub_private_repo=False,
        ),
    )
    trainer.add_callback(_StepRecorder())
    # Resume from a saved checkpoint, e.g. RESUME=/outputs/<run>/checkpoint-300.
    # The checkpoints carry optimizer, scheduler, RNG and trainer state, not just
    # the adapter, so a resumed run continues the LR schedule and the dataset
    # position rather than restarting them -- which matters here because the
    # dataset position is what stops tasks being re-sampled.
    #
    # `MAX_STEPS` is absolute, not relative: resuming a step-300 checkpoint with
    # MAX_STEPS=1000 runs steps 301-1000. Keep MAX_STEPS at whatever the
    # original run used, because the LR schedule decays toward it -- lowering it
    # on resume makes the learning rate jump.
    resume = os.getenv("RESUME") or None
    if resume:
        logger.info("resuming from %s", resume)
    trainer.train(resume_from_checkpoint=resume)
    _publish(trainer)
    path = _trace_path()
    if path is not None and path.exists():
        rollouts = sum(1 for line in path.open() if line.strip())
        logger.info("%d rollout traces at %s", rollouts, path)


def _publish(trainer) -> None:
    """Save the adapter and upload it with the plain Hub API.

    Not `trainer.push_to_hub()`: that goes through the callback handler and hits
    the Trackio/Parquet failure described in the config above. Uploading the
    folder directly touches no Trainer callbacks. The Jobs filesystem is deleted
    when the job exits, so a failure here would lose the adapter -- but
    `output_dir` is a mounted bucket, so the checkpoint survives regardless and
    the upload is reported rather than fatal.
    """
    from huggingface_hub import HfApi

    final = pathlib.Path(trainer.args.output_dir) / "final"
    trainer.save_model(str(final))
    logger.info("adapter saved to %s", final)
    # `save_model` is already rank-aware; this upload is not, and four ranks
    # pushing the same folder concurrently is four times the work and a race.
    if int(os.getenv("RANK", "0")) != 0:
        return
    try:
        api = HfApi()
        api.create_repo(HUB_MODEL_ID, exist_ok=True, repo_type="model")
        api.upload_folder(folder_path=str(final), repo_id=HUB_MODEL_ID)
        logger.info("pushed to https://huggingface.co/%s", HUB_MODEL_ID)
    except Exception as exc:  # noqa: BLE001 - the checkpoint is already safe
        logger.error(
            "upload to %s failed (%s). The adapter is in %s on the mounted "
            "bucket; retrieve it with `hf buckets sync`.",
            HUB_MODEL_ID,
            exc,
            final,
        )


def _relaunch_distributed() -> None:
    """Re-execute this script under `torchrun` when NPROC > 1.

    `hf jobs uv run` requires a `.py` entrypoint, so `accelerate launch` cannot
    be the job command -- and pointing the job at `accelerate` would mean uv no
    longer reads this file's PEP 723 header, moving every dependency onto
    `--with` flags. Re-executing from inside the built environment keeps the
    header authoritative: `torchrun` is already on PATH here because torch is a
    dependency, and the children inherit this interpreter.

    `RANK` is set by torchrun in the children, which is what stops this from
    recursing.
    """
    if NPROC <= 1 or "RANK" in os.environ:
        return
    torchrun = pathlib.Path(sys.executable).with_name("torchrun")
    argv = [
        str(torchrun),
        f"--nproc_per_node={NPROC}",
        "--nnodes=1",
        str(pathlib.Path(__file__).resolve()),
    ]
    logger.info("relaunching under torchrun on %d GPUs", NPROC)
    os.execv(str(torchrun), argv)


if __name__ == "__main__":
    _relaunch_distributed()
    main()
