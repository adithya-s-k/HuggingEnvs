# SPDX-License-Identifier: BSD-3-Clause

"""FastAPI application for the GeoGuesser environment.

Configuration comes from the process environment so one image can serve every
variant. `MAPILLARY_API_KEY` is needed only to fill cache misses; with a warm
cache the server runs with no network access at all.

Usage:
    uv run --project . server
    uvicorn server.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import inspect
import logging
import os
import pathlib

from openenv.core.env_server.http_server import create_app

try:
    from geoguesser_env.models import GeoGuesserAction, GeoGuesserObservation
    from geoguesser_env.server.geoguesser_environment import GeoGuesserEnvironment
except ImportError:  # running uvicorn from inside envs/geoguesser_env
    from models import GeoGuesserAction, GeoGuesserObservation

    from .geoguesser_environment import GeoGuesserEnvironment


logger = logging.getLogger(__name__)

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Fallback index, used only when no named split resolves. It is the eval split
# on purpose: the legacy `pano_v1.jsonl` predates the contamination rule and has
# a task 603 m from an eval start, so it is a demo index, never a train split.
INDEX_PATH = os.getenv("GEOGUESSER_INDEX", str(_ROOT / "tasks" / "eval_pano_v3.jsonl"))
CACHE_DIR = os.getenv("GEOGUESSER_CACHE", str(_ROOT / "data" / "panos"))
# Named splits, as (environment variable, repo-relative default). Each is
# optional and a split whose file is absent is simply not offered, so the same
# image serves a checkout with the indexes committed, a Space with a bucket
# mounted at /data, and a deployment carrying only the eval set.
SPLIT_SOURCES = {
    "train": ("GEOGUESSER_TASKS_TRAIN", "tasks/train_pano_v3.jsonl"),
    "eval": ("GEOGUESSER_TASKS_EVAL", "tasks/eval_pano_v3.jsonl"),
}
DEFAULT_SPLIT = os.getenv("GEOGUESSER_DEFAULT_SPLIT", "")
EPISODE_MODE = os.getenv("GEOGUESSER_EPISODE_MODE", "agentic")
REWARD_MODE = os.getenv("GEOGUESSER_REWARD_MODE", "coords")
MAX_STEPS = int(os.getenv("GEOGUESSER_MAX_STEPS", "24"))
VIEW_SIZE = int(os.getenv("GEOGUESSER_VIEW_SIZE", "640"))
HIERARCHICAL = os.getenv("GEOGUESSER_HIERARCHICAL", "0") in {"1", "true", "True"}
# Training defaults differ from play defaults on purpose; see the reward-shape
# note in the README. A hosted Space serves play traffic, so it keeps the game
# curve and shows the licence credit unless these are set explicitly.
REWARD_SHAPE = os.getenv("GEOGUESSER_REWARD_SHAPE", "geoguessr")
COST_MODE = os.getenv("GEOGUESSER_COST_MODE", "subtract")
HIDE_IDENTITY = os.getenv("GEOGUESSER_HIDE_IDENTITY", "0") in {"1", "true", "True"}
ALLOW_FETCH = os.getenv("GEOGUESSER_ALLOW_FETCH", "1") in {"1", "true", "True"}
HIRES_ZOOM = os.getenv("GEOGUESSER_HIRES_ZOOM", "1") in {"1", "true", "True"}
REVEAL_MAP = os.getenv("GEOGUESSER_REVEAL_MAP", "1") in {"1", "true", "True"}
# The browser game needs the raw panorama and the task's coordinates; a training
# deployment does not, and serving them unauthenticated next to the agent's own
# endpoint means any harness holding the env URL can read the answer without
# playing. On by default so the public Space stays playable, and REPRODUCE.md
# tells you to turn it off for a training Space.
PLAY_ROUTES = os.getenv("GEOGUESSER_PLAY_ROUTES", "1") in {"1", "true", "True"}
# Off by default, which is what the README says and what a training deployment
# wants: the overlay is fetched from Overpass per agent pin, so it cannot be
# pre-warmed and it puts a network call in the middle of a rollout. The image
# and the play Space turn it on explicitly.
STREET_DETAIL = os.getenv("GEOGUESSER_STREET_DETAIL", "0") in {"1", "true", "True"}
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_ENVS", "4"))


try:
    from .render.minimap import set_street_detail
except ImportError:  # running uvicorn from inside envs/geoguesser_env
    from render.minimap import set_street_detail

# Deliberately independent of ALLOW_FETCH. That flag governs Mapillary imagery,
# which a mirrored dataset must never reach for; street detail comes from
# Overpass and caches to the container's own writable disk, so a fully mirrored
# deployment can still draw labelled streets. Coupling the two silently gave a
# Space unlabelled agent maps while a local run had labelled ones.
set_street_detail(STREET_DETAIL)


def resolve_splits() -> tuple[dict[str, str], str]:
    """
    Work out which named splits this deployment actually serves.

    A split is offered only when its environment variable is set *and* the file
    exists, because a Space that mounts a bucket read-only should degrade to the
    splits it really has rather than failing to start. When none are configured
    the legacy single `GEOGUESSER_INDEX` becomes one `train` split, so existing
    containers behave exactly as before.

    Returns:
        `tuple` of:
            - `dict[str, str]`: Split name to index path.
            - `str`: Name of the default split.
    """
    splits: dict[str, str] = {}
    for name, (variable, relative) in SPLIT_SOURCES.items():
        override = os.getenv(variable)
        path = override or str(_ROOT / relative)
        if not pathlib.Path(path).exists():
            # Only complain when someone asked for it explicitly. A missing
            # default just means this checkout has not built that split yet.
            if override:
                logger.warning(
                    "%s points at %s, which does not exist; "
                    "the %r split will not be offered",
                    variable,
                    path,
                    name,
                )
            continue
        splits[name] = path

    if not splits:
        return {"train": INDEX_PATH}, "train"

    default = DEFAULT_SPLIT or ("train" if "train" in splits else next(iter(splits)))
    if default not in splits:
        logger.warning(
            "GEOGUESSER_DEFAULT_SPLIT=%r is not among %s; using %r",
            DEFAULT_SPLIT,
            sorted(splits),
            next(iter(splits)),
        )
        default = next(iter(splits))
    return splits, default


SPLITS, ACTIVE_DEFAULT_SPLIT = resolve_splits()


def create_geoguesser_environment() -> GeoGuesserEnvironment:
    """Factory: a fresh environment per WebSocket session."""
    return GeoGuesserEnvironment(
        splits=SPLITS,
        default_split=ACTIVE_DEFAULT_SPLIT,
        cache_dir=CACHE_DIR,
        episode_mode=EPISODE_MODE,
        max_steps=MAX_STEPS,
        reward_mode=REWARD_MODE,
        hierarchical_reward=HIERARCHICAL,
        reward_shape=REWARD_SHAPE,
        cost_mode=COST_MODE,
        hide_task_identity=HIDE_IDENTITY,
        view_size=VIEW_SIZE,
        allow_fetch=ALLOW_FETCH,
        hires_zoom=HIRES_ZOOM,
        reveal_map=REVEAL_MAP,
    )


def _build_app():
    """Create the app, attaching the Gradio tab when this openenv supports it."""
    kwargs = dict(
        env_name="geoguesser_env",
        max_concurrent_envs=MAX_CONCURRENT,
    )
    signature = inspect.signature(create_app)
    # Land people on the game, not the raw action form.
    if "custom_tab_primary" in signature.parameters:
        kwargs["custom_tab_primary"] = True
    if "custom_tab_name" in signature.parameters:
        kwargs["custom_tab_name"] = "Try Environment"
    if "default_tab_name" in signature.parameters:
        kwargs["default_tab_name"] = "MCP Playground"
    if "title_override" in signature.parameters:
        kwargs["title_override"] = "Geoguesser Environment"
    if "gradio_builder" in signature.parameters:
        try:
            from .gradio_ui import build_geoguesser_gradio_app

            kwargs["gradio_builder"] = build_geoguesser_gradio_app
        except Exception as exc:  # pragma: no cover - optional UI dependency
            logger.warning("Gradio UI unavailable: %r", exc)
    else:
        logger.warning(
            "Installed openenv does not support gradio_builder; "
            "the GeoGuessr-style play tab will not be available."
        )
    return create_app(
        create_geoguesser_environment,
        GeoGuesserAction,
        GeoGuesserObservation,
        **kwargs,
    )


def _attach_play_routes(application) -> None:
    """Serve panoramas and task metadata to the browser-side viewers.

    The Pannellum viewer needs the raw equirectangular JPEG, which the agent
    never receives — it only ever sees reprojected views. Ground truth is
    exposed here because these routes exist for a human playing a round in
    their own browser; the agent's observations still withhold it until it
    guesses.

    That also makes these routes an oracle for anything that can reach the URL,
    so they are gated on `GEOGUESSER_PLAY_ROUTES`. Leave them on for a Space
    people play, turn them off for one a trainer points at.
    """
    from fastapi import HTTPException, Query
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

    # One environment, reused for metadata only. Its per-split backends share
    # the process-wide parsed index cache, so this is cheap.
    catalog = create_geoguesser_environment()

    def _backend(split: str | None):
        """Resolve a split name to its backend, as a 404 rather than a 500."""
        try:
            return catalog._backend_for(split or ACTIVE_DEFAULT_SPLIT)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get(
        "/geoguesser/task/{task_index}",
        tags=["geoguesser"],
        response_class=JSONResponse,
    )
    async def geoguesser_task(task_index: int, split: str | None = Query(None)):
        """Metadata for one task, for the play UI."""
        try:
            task = _backend(split).task(task_index)
        except IndexError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        frame = task.frames[task.start_frame]
        return JSONResponse(
            {
                "task_index": task.task_index,
                "task_id": task.task_id,
                "lat": frame.lat,
                "lon": frame.lon,
                "country": task.country,
                "compass_angle": frame.compass_angle,
                "captured_at": frame.captured_at,
                "attribution": task.attribution,
                "n_frames": len(task.frames),
                "start_frame": task.start_frame,
                # Per-frame headings only. Coordinates are withheld for frames
                # other than the start, which is the one the guess is scored
                # against and therefore already revealed to a human player.
                "frames": [
                    {
                        "index": i,
                        "compass_angle": f.compass_angle,
                        "captured_at": f.captured_at,
                    }
                    for i, f in enumerate(task.frames)
                ],
            }
        )

    def _pano_response(task_index: int, frame_index: int | None, split: str | None):
        """Resolve one frame's panorama file, fetching it if necessary."""
        resolved = _backend(split)
        try:
            task = resolved.task(task_index)
        except IndexError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        position = task.start_frame if frame_index is None else frame_index
        if not 0 <= position < len(task.frames):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"frame {position} out of range for task {task_index} "
                    f"with {len(task.frames)} frames"
                ),
            )
        frame = task.frames[position]
        try:
            resolved.load_pano(frame.image_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return FileResponse(
            pathlib.Path(CACHE_DIR) / f"{frame.image_id}.jpg",
            media_type="image/jpeg",
        )

    @application.get(
        "/geoguesser/pano/{task_index}",
        tags=["geoguesser"],
        response_class=FileResponse,
    )
    async def geoguesser_pano(task_index: int, split: str | None = Query(None)):
        """The task's starting panorama, for the browser viewer."""
        return _pano_response(task_index, None, split)

    @application.get(
        "/geoguesser/pano/{task_index}/{frame_index}",
        tags=["geoguesser"],
        response_class=FileResponse,
    )
    async def geoguesser_pano_frame(
        task_index: int, frame_index: int, split: str | None = Query(None)
    ):
        """One specific frame's panorama, so the viewer can follow `move()`."""
        return _pano_response(task_index, frame_index, split)

    @application.get(
        "/geoguesser/play", tags=["geoguesser"], response_class=HTMLResponse
    )
    async def geoguesser_play(split: str | None = Query(None)):
        """The standalone play page, also embedded in the Gradio tab."""
        from .gradio_ui import play_page_html

        return HTMLResponse(play_page_html(catalog.list_splits(), split))

    @application.get(
        "/geoguesser/tasks", tags=["geoguesser"], response_class=JSONResponse
    )
    async def geoguesser_tasks():
        """Which splits exist and how many tasks each holds."""
        splits = catalog.list_splits()
        return JSONResponse(
            {
                "splits": splits,
                "default_split": ACTIVE_DEFAULT_SPLIT,
                # Kept so an older play page still finds a count.
                "n_tasks": next(
                    s["num_tasks"] for s in splits if s["name"] == ACTIVE_DEFAULT_SPLIT
                ),
            }
        )


app = _build_app()

if PLAY_ROUTES:
    try:
        _attach_play_routes(app)
    except Exception as exc:  # pragma: no cover - index may be absent in CI
        logger.warning("play routes unavailable: %r", exc)
else:
    logger.info(
        "play routes disabled (GEOGUESSER_PLAY_ROUTES=0): no raw panoramas, and "
        "no task coordinates over HTTP"
    )


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    Entry point for running the server without Docker.

    Args:
        host (`str`, *optional*, defaults to `"0.0.0.0"`):
            Address to bind.
        port (`int`, *optional*, defaults to `8000`):
            Port to listen on.
    """
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    main(host=args.host, port=args.port)
