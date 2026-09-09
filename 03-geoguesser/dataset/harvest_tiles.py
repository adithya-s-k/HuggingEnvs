# SPDX-License-Identifier: BSD-3-Clause

"""Enumerate panorama sequences worldwide from Mapillary coverage tiles.

This replaces point probing. Probing a coordinate and searching a small box
finds a panorama about 5% of the time at 45 m boxes and 26% at city centres,
and each request answers for one spot. A single z6 tile from the `mly1_public`
**sequence** layer instead returns every sequence crossing roughly 600 km of
ground, each feature already carrying `is_pano`, an anchor `image_id`,
`creator_id` and `quality_score`. Measured, one request each:

    Denver   z6   71,752 sequences   18,587 panoramic   7.3 MB   3.5 s
    Paris    z6   85,920 sequences   11,617 panoramic   8.6 MB   4.2 s
    Nairobi  z6    8,491 sequences    1,670 panoramic   0.8 MB   1.3 s

The world is 4,096 tiles at z6 and 1,059 of them intersect land, so a complete
pass is about 4 GB and uses 2% of the 50,000/day tile budget — with full recall
rather than a lottery.

Output is a pool of candidate sequences, not tasks. Assembling frames is a
separate, slower step, and keeping them apart means you can harvest once and
sample from the pool as often as you like.

Usage:
    export MAPILLARY_API_KEY="MLY|..."
    python dataset/harvest_tiles.py                    # whole world, z6
    python dataset/harvest_tiles.py --zoom 6 --workers 6
    python dataset/harvest_tiles.py --bbox -10 35 30 60    # Europe only
"""

from __future__ import annotations

import argparse
import concurrent.futures
import functools
import json
import logging
import math
import pathlib
import sys
import threading
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_pano_tasks import _token  # noqa: E402


TILE_URL = "https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}"
SEQUENCE_LAYER = "sequence"
USER_AGENT = "openenv-geoguesser-env/0.1 (research environment)"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("harvest_tiles")


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Return `(west, south, east, north)` in degrees for one tile."""
    n = 2**z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


@functools.lru_cache(maxsize=1)
def _land_paths():
    """Country outlines from the bundled Natural Earth file."""
    from matplotlib.path import Path as MplPath

    root = pathlib.Path(__file__).resolve().parents[1] / "env"
    features = json.loads(
        (root / "data" / "geo" / "ne_110m_admin_0_countries.geojson").read_text()
    )["features"]
    paths = []
    for feature in features:
        geometry = feature["geometry"]
        rings = (
            [geometry["coordinates"][0]]
            if geometry["type"] == "Polygon"
            else [poly[0] for poly in geometry["coordinates"]]
        )
        paths.extend(MplPath(ring) for ring in rings)
    return paths


def land_tiles(
    zoom: int, bbox: tuple[float, float, float, float] | None
) -> list[tuple[int, int]]:
    """Tiles that intersect land, optionally restricted to a bounding box.

    A tile counts as land if its centre or any corner falls inside a country
    polygon. Antarctica and the high Arctic are skipped — no imagery, and they
    would be a fifth of the work.
    """
    paths = _land_paths()
    n = 2**zoom
    keep = []
    for x in range(n):
        for y in range(n):
            west, south, east, north = tile_bounds(zoom, x, y)
            if north < -58 or south > 78:
                continue
            if bbox:
                if (
                    east < bbox[0]
                    or west > bbox[2]
                    or north < bbox[1]
                    or south > bbox[3]
                ):
                    continue
            probes = [
                ((west + east) / 2, (south + north) / 2),
                (west, south),
                (east, south),
                (west, north),
                (east, north),
            ]
            if any(path.contains_point(p) for p in probes for path in paths):
                keep.append((x, y))
    return keep


def fetch_tile(token: str, zoom: int, x: int, y: int, retries: int = 2) -> bytes | None:
    """Fetch one coverage tile, or `None` when it cannot be had."""
    url = TILE_URL.format(z=zoom, x=x, y=y) + f"?access_token={token}"
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - a lost tile is not fatal
            if attempt == retries:
                logger.warning("tile %d/%d/%d failed: %r", zoom, x, y, exc)
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def sequences_in_tile(raw: bytes, zoom: int, x: int, y: int) -> list[dict]:
    """Decode a tile and return its panoramic sequence features.

    Tile geometry is in local integer coordinates, so the first vertex of each
    LineString is converted back to longitude and latitude. That position is
    approximate — low-zoom geometry is simplified — and is used only for
    sampling and country capping; exact coordinates come from the Graph API when
    frames are assembled.
    """
    import mapbox_vector_tile

    try:
        decoded = mapbox_vector_tile.decode(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("tile %d/%d/%d did not decode: %r", zoom, x, y, exc)
        return []

    layer = decoded.get(SEQUENCE_LAYER)
    if not layer:
        return []
    extent = layer.get("extent", 4096)
    west, south, east, north = tile_bounds(zoom, x, y)

    out = []
    for feature in layer.get("features", []):
        properties = feature.get("properties", {})
        if properties.get("is_pano") not in (True, 1, "true"):
            continue
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates") or []
        while coords and isinstance(coords[0], (list, tuple)):
            coords = coords[0]
        if len(coords) < 2:
            continue
        local_x, local_y = float(coords[0]), float(coords[1])
        lon = west + (local_x / extent) * (east - west)
        lat = south + (local_y / extent) * (north - south)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        out.append(
            {
                "sequence_id": properties.get("id"),
                "image_id": properties.get("image_id"),
                "creator_id": properties.get("creator_id"),
                "quality_score": properties.get("quality_score"),
                "captured_at": properties.get("captured_at"),
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "tile": f"{zoom}/{x}/{y}",
            }
        )
    return out


def harvest(args: argparse.Namespace) -> None:
    """Walk the tiles and write the sequence pool."""
    token = _token()
    tiles = land_tiles(args.zoom, tuple(args.bbox) if args.bbox else None)
    if args.limit:
        tiles = tiles[: args.limit]
    logger.info(
        "z%d: %d tiles to fetch, %d workers, budget is 50,000 tiles/day (%.1f%% of it)",
        args.zoom,
        len(tiles),
        args.workers,
        100 * len(tiles) / 50_000,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    lock = threading.Lock()
    stats = {"tiles": 0, "bytes": 0, "features": 0, "kept": 0, "failed": 0}
    handle = args.out.open("w")

    def work(tile):
        x, y = tile
        raw = fetch_tile(token, args.zoom, x, y)
        if raw is None:
            with lock:
                stats["failed"] += 1
            return
        rows = sequences_in_tile(raw, args.zoom, x, y)
        with lock:
            stats["tiles"] += 1
            stats["bytes"] += len(raw)
            stats["features"] += len(rows)
            for row in rows:
                sequence_id = row["sequence_id"]
                # Sequences cross tile boundaries and appear in every tile they
                # touch, so the pool is deduplicated as it is written.
                if not sequence_id or sequence_id in seen:
                    continue
                seen.add(sequence_id)
                handle.write(json.dumps(row) + "\n")
                stats["kept"] += 1

    try:
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            TextColumn,
            TimeElapsedColumn,
            TimeRemainingColumn,
        )

        progress = Progress(
            TextColumn("[cyan]harvesting tiles"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn(
                "sequences={task.fields[kept]} · {task.fields[mb]:.0f} MB · "
                "failed={task.fields[failed]}"
            ),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )
        with progress:
            task_id = progress.add_task(
                "tiles", total=len(tiles), kept=0, mb=0.0, failed=0
            )
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=args.workers
            ) as pool:
                for _ in pool.map(work, tiles):
                    progress.update(
                        task_id,
                        advance=1,
                        kept=stats["kept"],
                        mb=stats["bytes"] / 1e6,
                        failed=stats["failed"],
                    )
    except ImportError:  # pragma: no cover - rich ships with openenv
        logger.info("rich not installed, falling back to plain logging")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for index, _ in enumerate(pool.map(work, tiles), 1):
                if index % 25 == 0:
                    logger.info(
                        "  %d/%d tiles, %d sequences, %.0f MB",
                        index,
                        len(tiles),
                        stats["kept"],
                        stats["bytes"] / 1e6,
                    )
    finally:
        handle.close()

    logger.info(
        "\n%d unique panorama sequences -> %s (%.1f MB)",
        stats["kept"],
        args.out,
        args.out.stat().st_size / 1e6,
    )
    logger.info(
        "read %d tiles (%d failed), %.1f GB of tiles, %d raw features before dedupe",
        stats["tiles"],
        stats["failed"],
        stats["bytes"] / 1e9,
        stats["features"],
    )
    logger.info("next: python dataset/build_tasks.py --tasks 2500")


def main() -> None:
    """Command-line entry point."""
    root = pathlib.Path(__file__).resolve().parents[1] / "env"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zoom", type=int, default=6, help="Sequence layer is served from z6."
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument(
        "--limit", type=int, default=0, help="Stop after this many tiles."
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Restrict to a bounding box, for a quick trial run.",
    )
    parser.add_argument(
        "--out", type=pathlib.Path, default=root / "data" / "pool" / "sequences.jsonl"
    )
    harvest(parser.parse_args())


if __name__ == "__main__":
    main()
