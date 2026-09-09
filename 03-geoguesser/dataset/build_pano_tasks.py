# SPDX-License-Identifier: BSD-3-Clause

"""Build a frozen task index of Mapillary 360-degree panoramas.

Discovery is panorama-first. Sampling coordinates and hoping for coverage does
not work: probing 45 Street-View locations found any Mapillary imagery at 21
and a 360-degree panorama at only 7. So this script probes many candidate
points, keeps whatever panoramas exist, and defines tasks there.

Two API constraints shape the implementation. The `/images` search is not a
bulk endpoint — `limit` does not cap the scan and dense bounding boxes fail
with "reduce the amount of data" — so probes use very small boxes. And
`camera_type` returns `spherical`, not the `equirectangular` the documentation
claims, so filtering on the documented value silently matches nothing.

Usage:
    python dataset/build_pano_tasks.py --tasks 100 --frames 24
    python dataset/build_pano_tasks.py --tasks 8 --frames 6 --out tests/fixtures
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import logging
import os
import pathlib
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "env"))

from server.render.minimap import _cities, locate  # noqa: E402


GRAPH_API = "https://graph.mapillary.com"
PROBE_HALF_DEG = 0.0004
TIMEOUT_S = 30.0

SEARCH_FIELDS = "id,is_pano,camera_type,sequence,quality_score"
FRAME_FIELDS = (
    "id,geometry,computed_geometry,compass_angle,computed_compass_angle,"
    "captured_at,is_pano,camera_type,quality_score,creator,make,model,width,height"
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("build_pano_tasks")


# Rate limits are per application, so harvesting on its own key means a bulk
# harvest cannot starve a training run that is filling its panorama cache.
DATA_KEY_NAMES = ("MAPILLARY_API_KEY_TRAIN", "MAPILLARY_API_KEY")
RUNTIME_KEY_NAMES = ("MAPILLARY_API_KEY",)


def _read_env_file(names: tuple[str, ...]) -> str | None:
    env_file = next(
        (c for c in (
            pathlib.Path(__file__).resolve().parents[1] / ".env",
            pathlib.Path(__file__).resolve().parents[2] / ".env",
            pathlib.Path(__file__).resolve().parents[3] / ".env",
        ) if c.is_file()),
        pathlib.Path(__file__).resolve().parents[1] / ".env",
    )
    if not env_file.exists():
        return None
    values = {}
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    for name in names:
        if values.get(name):
            return values[name]
    return None


def _token(names: tuple[str, ...] = DATA_KEY_NAMES) -> str:
    """
    Return a Mapillary token, preferring the harvesting key.

    Args:
        names (`tuple[str, ...]`, *optional*):
            Environment variable names to try, in order. Defaults to the
            harvesting key first, then the runtime key.

    Returns:
        `str`: The token.
    """
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    token = _read_env_file(names)
    if not token:
        raise SystemExit(
            "No Mapillary token found. Set one of "
            + ", ".join(names)
            + ". Register an application at "
            "https://www.mapillary.com/dashboard/developers (READ scope only)."
        )
    return token


def _get(token: str, path: str, **params) -> dict:
    params["access_token"] = token
    url = f"{GRAPH_API}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return {"__error": exc.code, "__body": exc.read().decode()[:160]}
    except Exception as exc:  # network flake, DNS, timeout
        return {"__error": -1, "__body": repr(exc)[:160]}


def _month(captured_at_ms: int | None) -> str:
    if not captured_at_ms:
        return ""
    return time.strftime("%Y-%m", time.gmtime(captured_at_ms / 1000))


def seed_points(count: int, seed: int = 0) -> list[tuple[str, float, float]]:
    """
    Candidate probe points, drawn from the bundled populated-places file.

    Using committed data keeps the builder reproducible and avoids a hardcoded
    list of favourite cities. Each point is jittered so repeated runs explore
    slightly different streets.

    Args:
        count (`int`):
            How many probe points to return.
        seed (`int`, *optional*, defaults to `0`):
            Seed for the jitter and the shuffle.

    Returns:
        `list[tuple[str, float, float]]`: `(name, lat, lon)` triples.
    """
    rng = random.Random(seed)
    cities = list(_cities())
    rng.shuffle(cities)
    points = []
    while len(points) < count:
        for name, lat, lon in cities:
            if len(points) >= count:
                break
            # Later passes over the same city jitter further out, so a dense
            # metro contributes several distinct streets rather than one point.
            spread = 0.01 + 0.02 * (len(points) // max(1, len(cities)))
            points.append(
                (
                    name,
                    lat + rng.uniform(-spread, spread),
                    lon + rng.uniform(-spread, spread),
                )
            )
    return points


def probe(token: str, point: tuple[str, float, float]) -> dict | None:
    """Return the best spherical panorama near one probe point, if any."""
    name, lat, lon = point
    d = PROBE_HALF_DEG
    bbox = f"{lon - d},{lat - d},{lon + d},{lat + d}"
    result = _get(token, "images", bbox=bbox, fields=SEARCH_FIELDS)
    if "__error" in result:
        return None
    panos = [
        image
        for image in result.get("data", [])
        if image.get("is_pano") and image.get("camera_type") == "spherical"
    ]
    if not panos:
        return None
    best = max(panos, key=lambda image: image.get("quality_score") or 0.0)
    best["__seed_name"] = name
    return best


def sequence_frames(token: str, sequence_id: str) -> list[str]:
    """Ordered image ids making up a sequence."""
    result = _get(token, "image_ids", sequence_id=sequence_id)
    if "__error" in result:
        return []
    return [str(row["id"]) for row in result.get("data", [])]


def frame_detail(token: str, image_id: str) -> dict | None:
    """Full entity for one frame, or `None` when the request fails."""
    result = _get(token, str(image_id), fields=FRAME_FIELDS)
    return None if "__error" in result else result


def build(
    n_tasks: int,
    n_frames: int,
    out_dir: pathlib.Path,
    cache_dir: pathlib.Path,
    max_per_country: int,
    n_seeds: int,
    workers: int,
    prefetch_frames: int,
    seed: int,
    require_country: bool = True,
) -> None:
    """Discover panoramas, assemble tasks and write the index."""
    token = _token()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    points = seed_points(n_seeds, seed=seed)
    logger.info("probing %d candidate points with %d workers", len(points), workers)

    found: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for i, hit in enumerate(pool.map(lambda p: probe(token, p), points), 1):
            if hit:
                found.append(hit)
            if i % 25 == 0:
                logger.info("  %d/%d probed, %d panoramas", i, len(points), len(found))
    logger.info("found %d panoramas from %d probes", len(found), len(points))

    seen_sequences: set[str] = set()
    per_country: dict[str, int] = {}
    tasks: list[dict] = []

    for hit in found:
        if len(tasks) >= n_tasks:
            break
        sequence_id = hit.get("sequence")
        if not sequence_id or sequence_id in seen_sequences:
            continue
        seen_sequences.add(sequence_id)

        ids = sequence_frames(token, sequence_id)
        if len(ids) < 2:
            continue
        anchor = ids.index(str(hit["id"])) if str(hit["id"]) in ids else 0
        lo = max(0, anchor - n_frames // 2)
        window = ids[lo : lo + n_frames]

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            details = list(pool.map(lambda i: frame_detail(token, i), window))

        frames = []
        for detail in details:
            if not detail:
                continue
            geometry = detail.get("computed_geometry") or detail.get("geometry")
            if not geometry:
                continue
            lon, lat = geometry["coordinates"]
            frames.append(
                {
                    "image_id": str(detail["id"]),
                    "lat": lat,
                    "lon": lon,
                    "compass_angle": detail.get("computed_compass_angle")
                    or detail.get("compass_angle")
                    or 0.0,
                    "captured_at": _month(detail.get("captured_at")),
                    "is_pano": bool(detail.get("is_pano")),
                }
            )
        frames = [f for f in frames if f["is_pano"]]
        if len(frames) < 2:
            continue

        start = min(len(frames) // 2, len(frames) - 1)
        start_frame = frames[start]
        place = locate(start_frame["lat"], start_frame["lon"])
        country = place.country or "unknown"
        if require_country and country == "unknown":
            # The coordinate fell outside the coarse 110m polygons, usually a
            # coastline or small island. Country partial credit would be
            # meaningless there, so leave it out of the index.
            continue
        if per_country.get(country, 0) >= max_per_country:
            continue

        anchor_detail = next(
            (d for d in details if d and str(d["id"]) == start_frame["image_id"]), {}
        )
        creator = anchor_detail.get("creator", {}) or {}

        checksums: dict[str, str] = {}
        to_cache = [start_frame["image_id"]]
        if prefetch_frames:
            to_cache = [f["image_id"] for f in frames[:prefetch_frames]]
        for image_id in to_cache:
            path = cache_dir / f"{image_id}.jpg"
            if not path.exists():
                detail = _get(token, image_id, fields="thumb_2048_url")
                thumb_url = detail.get("thumb_2048_url")
                if "__error" in detail or not thumb_url:
                    # A successful response can still omit the thumbnail, for
                    # images whose derivatives have not been generated.
                    logger.warning("  no thumbnail available for %s", image_id)
                    continue
                try:
                    with urllib.request.urlopen(
                        thumb_url, timeout=TIMEOUT_S
                    ) as response:
                        path.write_bytes(response.read())
                except Exception as exc:
                    logger.warning("  fetch failed for %s: %r", image_id, exc)
                    continue
            checksums[image_id] = hashlib.sha256(path.read_bytes()).hexdigest()

        if start_frame["image_id"] not in checksums:
            continue

        per_country[country] = per_country.get(country, 0) + 1
        tasks.append(
            {
                "task_index": len(tasks),
                "task_id": f"mly-{len(tasks):04d}",
                "country": country,
                "sequence_id": sequence_id,
                "provider": "mapillary",
                "start_frame": start,
                "frames": frames,
                "attribution": {
                    "creator_username": creator.get("username", ""),
                    "creator_id": creator.get("id", ""),
                    "licence": "CC-BY-SA-4.0",
                    "source": "Mapillary",
                },
                "meta": {
                    "seed_name": hit.get("__seed_name", ""),
                    "camera_make": anchor_detail.get("make", ""),
                    "camera_model": anchor_detail.get("model", ""),
                    "quality_score": anchor_detail.get("quality_score"),
                    "continent": place.continent,
                    "subregion": place.subregion,
                    "nearest_city": place.nearest_city,
                    "sha256": checksums,
                },
            }
        )
        logger.info(
            "  task %3d  %-22s %-16s %2d frames  %s",
            len(tasks) - 1,
            country[:22],
            start_frame["captured_at"],
            len(frames),
            anchor_detail.get("model", "")[:18],
        )

    index_path = out_dir / "pano_v1.jsonl"
    with index_path.open("w") as handle:
        for task in tasks:
            handle.write(json.dumps(task) + "\n")

    countries = sorted(per_country.items(), key=lambda kv: -kv[1])
    logger.info(
        "\nwrote %d tasks to %s (%.0f KB)",
        len(tasks),
        index_path,
        index_path.stat().st_size / 1024,
    )
    logger.info("countries: %s", ", ".join(f"{c}:{n}" for c, n in countries))
    cached = list(cache_dir.glob("*.jpg"))
    logger.info(
        "cache: %d images, %.0f MB",
        len(cached),
        sum(p.stat().st_size for p in cached) / 1e6,
    )


def main() -> None:
    """Command-line entry point."""
    root = pathlib.Path(__file__).resolve().parents[1] / "env"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=100)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--seeds", type=int, default=900)
    parser.add_argument("--max-per-country", type=int, default=4)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prefetch-frames", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--allow-unknown-country",
        action="store_true",
        help="Keep tasks whose coordinate falls outside the country polygons.",
    )
    parser.add_argument("--out", type=pathlib.Path, default=root / "tasks")
    parser.add_argument("--cache", type=pathlib.Path, default=root / "data" / "panos")
    args = parser.parse_args()
    build(
        n_tasks=args.tasks,
        n_frames=args.frames,
        out_dir=args.out,
        cache_dir=args.cache,
        max_per_country=args.max_per_country,
        n_seeds=args.seeds,
        workers=args.workers,
        prefetch_frames=args.prefetch_frames,
        seed=args.seed,
        require_country=not args.allow_unknown_country,
    )


if __name__ == "__main__":
    main()
