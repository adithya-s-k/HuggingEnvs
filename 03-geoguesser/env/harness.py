# SPDX-License-Identifier: BSD-3-Clause

"""Harness-oriented GeoGuesser session adapters.

Follows the pattern in `reasoning_gym_env.harness`: expose a `GeoGuesserEnv`
client as a `ResourceSession` driven through MCP-style tools, so it plugs into
`openenv.core.harness` unchanged.

That single adapter is what makes the rest work without extra code:

- `CollectRunner(tasks=...)` walks a task list into a JSONL rollout dataset,
  with resume, recording which task produced each episode.
- `build_harness_rollout_func(...)` yields a TRL-compatible rollout function
  where each prompt *is* a task — the GRPO path.
- `EvalConfig` / `EvalResult` carry the provenance an eval score needs.

A task is a plain dict, so it survives serialisation into an `EpisodeRecord`:

```python
{"task_index": 7, "task_id": "mly-0007"}
```
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Callable, Iterator

from openenv.core.env_server.mcp_types import Tool
from openenv.core.harness import (
    ResourceSessionFactory,
    StepEnvSessionAdapter,
    ToolResult,
    VerifyResult,
)

from .client import GeoGuesserEnv
from .models import (
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


def _number(description: str) -> dict[str, Any]:
    return {"type": "number", "description": description}


GEOGUESSER_TOOLS: list[Tool] = [
    Tool(
        name="look",
        description=(
            "Look in a direction from where you stand. heading_deg is "
            "absolute, 0 being true north. Smaller fov_deg zooms in."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "heading_deg": _number("Compass heading in degrees."),
                "pitch_deg": _number("Vertical angle; positive looks up."),
                "fov_deg": _number("Field of view in degrees, 10 to 120."),
            },
            "required": ["heading_deg"],
        },
    ),
    Tool(
        name="pan",
        description="Turn relative to your current heading; positive turns right.",
        input_schema={
            "type": "object",
            "properties": {"delta_deg": _number("Degrees to turn.")},
            "required": ["delta_deg"],
        },
    ),
    Tool(
        name="zoom",
        description="Change field of view without turning. Around 30 reads distant signs.",
        input_schema={
            "type": "object",
            "properties": {"fov_deg": _number("New field of view in degrees.")},
            "required": ["fov_deg"],
        },
    ),
    Tool(
        name="move",
        description=(
            "Walk along the captured road. Reports how far you actually "
            "travelled, since frame spacing is irregular."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["forward", "backward"],
                    "description": "Which way to walk.",
                },
                "meters": _number("Requested distance in metres."),
            },
            "required": ["direction"],
        },
    ),
    Tool(
        name="place_pin",
        description=(
            "Pin a candidate coordinate and see where it falls on the map. "
            "Tells you what is at that coordinate. It says nothing about "
            "whether you are right."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "lat": _number("Latitude of the candidate."),
                "lon": _number("Longitude of the candidate."),
                "label": {"type": "string", "description": "Optional note."},
                "span_deg": _number(
                    "Half-width of the returned map in degrees. Below about 4 "
                    "the map adds roads, urban areas and town names."
                ),
            },
            "required": ["lat", "lon"],
        },
    ),
    Tool(
        name="view_map",
        description="Pan and zoom the map without placing a pin.",
        input_schema={
            "type": "object",
            "properties": {
                "lat": _number("Latitude at the centre of the view."),
                "lon": _number("Longitude at the centre of the view."),
                "span_deg": _number("Half-width of the window in degrees."),
            },
            "required": ["lat", "lon"],
        },
    ),
    Tool(
        name="measure",
        description="Distance in km between two coordinates of your own choosing. Free.",
        input_schema={
            "type": "object",
            "properties": {
                "lat_a": _number("Latitude of the first point."),
                "lon_a": _number("Longitude of the first point."),
                "lat_b": _number("Latitude of the second point."),
                "lon_b": _number("Longitude of the second point."),
            },
            "required": ["lat_a", "lon_a", "lat_b", "lon_b"],
        },
    ),
    Tool(
        name="submit_guess",
        description="Commit your final answer. This ends the episode.",
        input_schema={
            "type": "object",
            "properties": {
                "lat": _number("Latitude of your guess."),
                "lon": _number("Longitude of your guess."),
                "country": {
                    "type": "string",
                    "description": "Optional ISO-3166 alpha-2 code or country name.",
                },
                "confidence": _number("Optional confidence in [0, 1]."),
                "reasoning": {
                    "type": "string",
                    "description": "Optional rationale, recorded but not scored.",
                },
            },
            "required": ["lat", "lon"],
        },
    ),
]

_ACTION_BY_TOOL: dict[str, Callable[[dict[str, Any]], Any]] = {
    "look": lambda a: LookAction(
        heading_deg=float(a["heading_deg"]),
        pitch_deg=float(a.get("pitch_deg", 0.0)),
        fov_deg=float(a.get("fov_deg", 90.0)),
    ),
    "pan": lambda a: PanAction(delta_deg=float(a["delta_deg"])),
    "zoom": lambda a: ZoomAction(fov_deg=float(a["fov_deg"])),
    "move": lambda a: MoveAction(
        direction=str(a["direction"]), meters=float(a.get("meters", 10.0))
    ),
    "place_pin": lambda a: PinAction(
        lat=float(a["lat"]),
        lon=float(a["lon"]),
        label=a.get("label") or None,
        span_deg=float(a.get("span_deg", 7.0)),
    ),
    "view_map": lambda a: ViewMapAction(
        lat=float(a["lat"]),
        lon=float(a["lon"]),
        span_deg=float(a.get("span_deg", 7.0)),
    ),
    "measure": lambda a: MeasureAction(
        lat_a=float(a["lat_a"]),
        lon_a=float(a["lon_a"]),
        lat_b=float(a["lat_b"]),
        lon_b=float(a["lon_b"]),
    ),
    "submit_guess": lambda a: GuessAction(
        lat=float(a["lat"]),
        lon=float(a["lon"]),
        country=a.get("country") or None,
        confidence=(
            float(a["confidence"]) if a.get("confidence") is not None else None
        ),
        reasoning=a.get("reasoning") or None,
    ),
}


def load_tasks(
    index_path: str | pathlib.Path,
    repeat: int = 1,
    split: str | None = None,
) -> list[dict[str, Any]]:
    """
    Read a frozen task index into harness task dicts.

    Args:
        index_path (`str` or `pathlib.Path`):
            The JSONL index written by `dataset/build_tasks.py`.
        repeat (`int`, *optional*, defaults to `1`):
            Emit each task this many times consecutively. `repeat=16` gives a
            GRPO group of 16 rollouts per location.
        split (`str`, *optional*):
            Split name to record on every task, so the session factory selects
            from the right index server-side. Required whenever the server
            serves more than one split, because an index alone does not say
            which one it is.

    Returns:
        `list[dict]`: One dict per episode, each with `task_index`, `task_id`,
        `country` and, when given, `split`.

    Examples:

    ```python
    tasks = load_tasks("tasks/eval_pano_v3.jsonl", split="eval")
    tasks = load_tasks("tasks/train_pano_v3.jsonl", repeat=16, split="train")
    ```
    """
    rows = []
    for line in pathlib.Path(index_path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        task = {
            "task_index": int(row["task_index"]),
            "task_id": str(row["task_id"]),
            "country": str(row.get("country", "")),
        }
        if split is not None:
            task["split"] = split
        rows.extend([dict(task) for _ in range(repeat)])
    return rows


def cycle_tasks(tasks: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield tasks forever, so `num_episodes` may exceed the index size."""
    while True:
        for task in tasks:
            yield dict(task)


def _initial_messages(result: Any, task: Any) -> list[dict[str, Any]]:
    """Opening message: the prompt plus the first view, as an image part."""
    observation = result.observation
    content: list[dict[str, Any]] = [{"type": "text", "text": observation.prompt}]
    if observation.image_base64:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{observation.image_base64}"
                },
            }
        )
    return [{"role": "user", "content": content}]


def _tool_result(
    tool_name: str, arguments: dict[str, Any], result: Any, state: Any
) -> ToolResult:
    """Feed the observation back as text plus, when present, an image."""
    observation = result.observation
    data: dict[str, Any] = {
        "feedback": observation.feedback,
        "heading_deg": observation.heading_deg,
        "fov_deg": observation.fov_deg,
        "steps_remaining": observation.steps_remaining,
        "pins": [p.model_dump() for p in observation.pins],
    }
    if observation.image_base64:
        data["image_base64"] = observation.image_base64
        data["image_kind"] = observation.image_kind
    if observation.distance_km is not None:
        data["distance_km"] = observation.distance_km
    return ToolResult(
        data=data,
        done=bool(result.done),
        metadata={
            "reward": result.reward,
            "tool": tool_name,
            "state": state.model_dump() if hasattr(state, "model_dump") else state,
        },
    )


def _verify(
    transcript: list[dict[str, Any]],
    final_state: Any,
    last_result: Any,
    task: Any,
) -> VerifyResult:
    """
    Summarise a finished episode for the collector.

    `env_reward` forwards the reward the environment itself computed. Domain
    knowledge belongs inside the environment, so nothing here recomputes or
    adjusts it; the extra fields are derived statistics only.
    """
    observation = getattr(last_result, "observation", None)
    distance = getattr(observation, "distance_km", None)
    env_reward = getattr(last_result, "reward", None)
    metrics: dict[str, Any] = {
        "distance_km": float(distance) if distance is not None else -1.0,
        "parsed_ok": float(bool(getattr(observation, "parsed_ok", False))),
        "guessed": float(distance is not None),
        "within_200km": float(distance is not None and distance < 200.0),
        "within_25km": float(distance is not None and distance < 25.0),
    }
    if isinstance(task, dict) and task.get("task_index") is not None:
        metrics["task_index"] = float(task["task_index"])
    return VerifyResult(
        env_reward=float(env_reward) if env_reward is not None else None,
        done=bool(getattr(last_result, "done", False)),
        metrics=metrics,
    )


class GeoGuesserSessionFactory(ResourceSessionFactory):
    """Create GeoGuesser-backed resource sessions for harness rollouts.

    Args:
        client_factory (`Callable[[], GeoGuesserEnv]`):
            Builds a client per session, so concurrent sessions stay isolated.
        include_navigation (`bool`, *optional*, defaults to `True`):
            Advertise `move` in the tool list. Set `False` for a task index
            whose backend cannot walk, so the model never sees a dead tool.

    Examples:

    ```python
    factory = GeoGuesserSessionFactory(
        lambda: GeoGuesserEnv(base_url="http://localhost:8000")
    )
    session = factory.create(task={"task_index": 7})
    ```
    """

    def __init__(
        self,
        client_factory: Callable[[], GeoGuesserEnv],
        *,
        include_navigation: bool = True,
    ):
        self._client_factory = client_factory
        self._tools = [
            tool
            for tool in GEOGUESSER_TOOLS
            if include_navigation or tool.name != "move"
        ]

    def create(
        self,
        task: Any = None,
        seed: int | None = None,
        episode_id: str | None = None,
    ) -> StepEnvSessionAdapter:
        """
        Open a session on one task.

        The task's `split` and `task_index` are passed through `reset_kwargs`,
        which is what makes a rollout reproducible: the same task always starts
        from the same panorama at the same heading. Without the split, an index
        is ambiguous once the server serves more than one.

        Args:
            task (`dict`, *optional*):
                Task dict with a `task_index` and optionally a `split`. `None`
                selects randomly from the server's default split.
            seed (`int`, *optional*):
                Fallback selector when no task is given.
            episode_id (`str`, *optional*):
                Episode identifier recorded by the collector.

        Returns:
            `StepEnvSessionAdapter`: The session, ready to be driven.
        """
        reset_kwargs: dict[str, Any] = {}
        if isinstance(task, dict):
            if task.get("split"):
                reset_kwargs["split"] = str(task["split"])
            if task.get("task_index") is not None:
                reset_kwargs["index"] = int(task["task_index"])
        elif isinstance(task, int):
            reset_kwargs["index"] = task

        return StepEnvSessionAdapter(
            client=self._client_factory(),
            task=task,
            seed=seed,
            episode_id=episode_id,
            tool_specs=list(self._tools),
            action_builder=lambda name, arguments: to_wire(
                _ACTION_BY_TOOL[name](arguments)
            ),
            initial_messages_builder=_initial_messages,
            tool_result_builder=_tool_result,
            verify_builder=_verify,
            reset_kwargs=reset_kwargs,
        )


__all__ = [
    "GEOGUESSER_TOOLS",
    "GeoGuesserSessionFactory",
    "cycle_tasks",
    "load_tasks",
]
