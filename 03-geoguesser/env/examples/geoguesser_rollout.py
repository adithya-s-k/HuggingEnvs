# SPDX-License-Identifier: BSD-3-Clause

"""A scripted rollout, end to end, with no model in the loop.

Runs in process against the committed fixtures, so it needs no server and no
network:

    PYTHONPATH=src:envs uv run python \\
        env/examples/geoguesser_rollout.py
"""

from __future__ import annotations

import pathlib

from geoguesser_env.models import (
    GuessAction,
    LookAction,
    MeasureAction,
    MoveAction,
    PinAction,
    to_wire,
)
from geoguesser_env.server.geoguesser_environment import GeoGuesserEnvironment


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def main() -> None:
    """Play one episode with a fixed script and print the trace."""
    env = GeoGuesserEnvironment(
        index_path=str(FIXTURES / "pano_v1.jsonl"),
        cache_dir=str(FIXTURES / "panos"),
        allow_fetch=False,
    )

    observation = env.reset(index=0)
    print(
        f"task {observation.metadata['task_index']} "
        f"({observation.metadata['task_id']}), "
        f"captured {observation.captured_at}"
    )
    print(f"tools: {', '.join(observation.available_tools)}\n")

    script = [
        LookAction(heading_deg=0),
        LookAction(heading_deg=90),
        LookAction(heading_deg=180, fov_deg=30),
        MoveAction(direction="forward", meters=20),
        PinAction(lat=39.7, lon=-104.9, label="Colorado?"),
        MeasureAction(lat_a=39.7, lon_a=-104.9, lat_b=38.9, lon_b=-104.8),
        PinAction(lat=38.87, lon=-104.79, label="Colorado Springs?"),
    ]
    for action in script:
        observation = env.step(to_wire(action))
        image = len(observation.image_base64 or "")
        print(
            f"{type(action).__name__:14s} [{observation.image_kind:4s} "
            f"{image:>7d}B] {observation.feedback[:96]}"
        )

    result = env.step(
        to_wire(
            GuessAction(
                response=(
                    "Wide roads, US plates, front range foothills.\n"
                    "<guess>38.87, -104.79</guess>"
                ),
                confidence=0.6,
            )
        )
    )
    print(f"\n{result.feedback}")
    print(
        f"reward {result.reward:.3f}  "
        f"score {result.score:.3f}  "
        f"cost {result.action_cost:.2f}  "
        f"distance {result.distance_km:.1f} km"
    )


if __name__ == "__main__":
    main()
