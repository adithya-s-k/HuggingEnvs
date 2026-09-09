# SPDX-License-Identifier: BSD-3-Clause

"""HTTP client for the GeoGuesser environment."""

from __future__ import annotations

from typing import Any, Dict

from openenv.core.client_types import StepResult
from openenv.core.env_client import EnvClient

from .models import (
    GeoGuesserAction,
    GeoGuesserObservation,
    GeoGuesserState,
    to_wire,
    TypedAction,
)


ENV_NAME = "geoguesser_env"
"""Task API routes are namespaced by the `env_name` the server registers."""


class GeoGuesserEnv(
    EnvClient[GeoGuesserAction, GeoGuesserObservation, GeoGuesserState]
):
    """
    Client for a running GeoGuesser environment server.

    Examples:

    ```python
    env = GeoGuesserEnv(base_url="http://localhost:8000")
    result = env.reset(task_index=0)
    result = env.step(LookAction(heading_deg=90))
    result = env.step(GuessAction(response("<guess>55.67, 12.57</guess>")))
    print(result.reward, result.observation.distance_km)
    ```
    """

    def _step_payload(self, action: GeoGuesserAction | TypedAction) -> Dict[str, Any]:
        """
        Serialise an action for the `/step` endpoint.

        Typed actions are flattened to the single wire schema the server
        declares; a wire action passes through unchanged.
        """
        wire = action if isinstance(action, GeoGuesserAction) else to_wire(action)
        return wire.model_dump(exclude_none=True)

    def _parse_result(self, response: Dict[str, Any]) -> StepResult:
        """Build a [`StepResult`] from a `/step` or `/reset` response."""
        observation = GeoGuesserObservation(**response["observation"])
        return StepResult(
            observation=observation,
            reward=response.get("reward"),
            done=response.get("done", False),
        )

    def _parse_state(self, response: Dict[str, Any]) -> GeoGuesserState:
        """Build a [`GeoGuesserState`] from a `/state` response."""
        return GeoGuesserState(**response)

    def reset(
        self,
        task_index: int | None = None,
        split: str | None = None,
        index: int | None = None,
        **kwargs: Any,
    ) -> StepResult:
        """
        Start an episode.

        Args:
            task_index (`int`, *optional*):
                Deprecated alias for `index`, kept so existing callers and
                recorded trajectories keep working.
            split (`str`, *optional*):
                Which split to draw from, as named by [`list_splits`]. Defaults
                to the server's default split.
            index (`int`, *optional*):
                Exact task to play within `split`. Repeated calls with the same
                split and index yield byte-identical observations, which is what
                a GRPO group needs. Omit it, and `seed`, for a random task.

        Returns:
            [`StepResult`]: The opening observation.
        """
        if index is None:
            index = task_index
        if split is not None:
            kwargs["split"] = split
        if index is not None:
            kwargs["index"] = index
        return super().reset(**kwargs)

    def list_splits(self) -> list[dict[str, Any]]:
        """
        Which splits the server offers, and how many tasks each holds.

        Core exposes the Task API over HTTP but ships no client for it, so this
        posts to the routes directly.

        Returns:
            `list[dict]`: Split descriptors with `name`, `type`, `num_tasks` and
                `default`.
        """
        return self._task_api("splits", method="GET")

    def num_tasks(self, split: str) -> int:
        """How many tasks a split holds."""
        return int(self._task_api("num_tasks", {"split": split})["num_tasks"])

    def get_task(self, split: str, index: int) -> dict[str, Any]:
        """
        Describe one task without starting an episode.

        The spec carries no coordinates and no country: it is metadata for
        whatever orchestrates a run, not a label source.
        """
        return self._task_api("task", {"split": split, "index": index})["task"]

    def _server_url(self) -> str:
        """
        The server URL, however the installed `core` exposes it.

        `base_url` is a property in openenv 0.4.2 and absent in 0.4.1 -- which
        is the current release, and therefore what a `pip install` of this
        package resolves to. Depending on the public name made every Task API
        call raise `AttributeError` on a released core while working fine
        against a development checkout. `_base_url` is set by `_set_base_url`
        in both, so it is read first and the public property is the fallback.

        Returns:
            `str`: The base URL with no trailing slash.
        """
        url = getattr(self, "_base_url", None) or getattr(self, "base_url", None)
        if not url:
            raise RuntimeError(
                "The Task API needs a server URL, and this client does not have "
                "one yet. A provider-backed client is assigned its URL on "
                "connect(), so call the Task API after entering the session."
            )
        return str(url).rstrip("/")

    def _task_api(
        self,
        route: str,
        payload: dict[str, Any] | None = None,
        method: str = "POST",
    ) -> Any:
        """Call one core Task API route on this environment."""
        import json
        import urllib.request

        url = f"{self._server_url()}/{ENV_NAME}/{route}"
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
