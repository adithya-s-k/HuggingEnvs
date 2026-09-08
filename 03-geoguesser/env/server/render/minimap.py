# SPDX-License-Identifier: BSD-3-Clause

"""The guess map, rendered offline.

Everything here runs against bundled Natural Earth vectors, so a pin costs no
network call and always renders the same bytes. Map detail is a function of
zoom alone and never of proximity to the target: prefetching finer data around
task locations would turn the map into a ground-truth oracle.

The renderer answers only "where did the agent point?". It never draws, names
or hints at the true location.
"""

from __future__ import annotations

import functools
import hashlib
import io
import json
import logging
import math
import os
import pathlib
import urllib.parse
import urllib.request
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as path_effects  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from PIL import Image  # noqa: E402

from ..scoring import haversine_km as _haversine_km  # noqa: E402

logger = logging.getLogger(__name__)


GEO_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "geo"
COUNTRIES_FILE = GEO_DIR / "ne_110m_admin_0_countries.geojson"
CITIES_FILE = GEO_DIR / "ne_50m_populated_places.geojson"

# Optional detail layers, fetched by dataset/fetch_detail_geo.py. Without them
# the map shows outlines and major cities only, which is enough to place a
# country but not to aim within a city — while the human's map is street-level.
# The reward measures precision, so the two views have to agree about how
# precisely a pin can be aimed.
DETAIL_DIR = GEO_DIR / "detail"

# Detail appears as a function of zoom alone, never of proximity to the answer.
# Loading finer data near task locations would turn the cache into an oracle.
# Below this the map fetches real OSM ways, because Natural Earth 10m tops out
# at highway level: it will show the motorways around a city but not the street
# grid inside it, and the player's tiles show both. Responses are cached to
# disk, so the first render of a neighbourhood is slow and every later one is
# instant and byte-identical.
STREET_MAX_SPAN_DEG = 0.35
STREET_LABEL_MAX_SPAN_DEG = 0.08
"""Street names only below this span. Wider, and the names collide."""
MAX_STREET_LABELS = 14
"""A cap, because a dense grid has hundreds of named ways."""
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT_S = 40.0
OSM_CACHE_DIR = pathlib.Path(
    os.environ.get("GEOGUESSER_OSM_CACHE", str(GEO_DIR / "osm_cache"))
)
"""Where fetched street windows are cached.

Configurable so a deployment that cannot reach Overpass -- a Space, whose
datacenter egress gets 504s from the public instance -- can mount a pre-warmed
cache instead of silently rendering maps without streets.
"""

OVERPASS_ATTEMPTS = 2
"""Overpass 504s under load; one cheap retry recovers a useful fraction."""

_STREET_FETCH_FAILED = [False]
"""Whether the most recent street fetch failed, for observation metadata.

A map quietly missing its streets looks like a styling choice rather than a
degraded environment, so the failure is reported rather than inferred.
"""


def street_fetch_failed() -> bool:
    """Whether the last street fetch in this process failed."""
    return _STREET_FETCH_FAILED[0]


_OSM_SCHEMA = 2
"""Bumped whenever the per-way record changes, to retire stale caches."""

# Ways worth drawing, heaviest first, with the line width to draw them at.
STREET_WEIGHTS = {
    "motorway": 2.2,
    "trunk": 2.0,
    "primary": 1.7,
    "secondary": 1.4,
    "tertiary": 1.1,
    "residential": 0.8,
    "unclassified": 0.8,
    "living_street": 0.7,
    "service": 0.5,
    "pedestrian": 0.5,
    "motorway_link": 1.2,
    "trunk_link": 1.1,
    "primary_link": 1.0,
    "secondary_link": 0.9,
    "tertiary_link": 0.8,
}

URBAN_MAX_SPAN_DEG = 4.0
ROADS_MAX_SPAN_DEG = 4.0
RIVERS_MAX_SPAN_DEG = 6.0
TOWNS_MAX_SPAN_DEG = 4.0

# Version of the bundled geodata. Any change alters reverse-geocode text and
# therefore the observations, so eval scores must cite it.
GEODATA_VERSION = "natural-earth-110m+50m/2024.1"

_LAND = "#e9e5dd"
_ROAD = "#8a6a52"
_RIVER = "#6f9fba"
_URBAN = "#e4ded6"
_TOWN = "#3d3833"
_WATER = "#cfe0ea"
_BORDER = "#5f5a54"
_PIN = "#c4332a"
_TRUTH = "#3f7a55"
_INK = "#2b2a28"

_COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

# Mutable so the server can turn street fetching off for a run that must never
# touch the network, without threading a flag through every render call.
_STREETS_ENABLED = [True]


def set_street_detail(enabled: bool) -> None:
    """Turn OSM street fetching on or off for this process."""
    _STREETS_ENABLED[0] = bool(enabled)


def street_detail_enabled() -> bool:
    """Whether OSM street fetching is currently on."""
    return _STREETS_ENABLED[0]


@dataclass(frozen=True)
class Place:
    """Where a coordinate falls, in words.

    Attributes:
        country (`str` or `None`):
            Country name, or `None` over open water.
        continent (`str` or `None`):
            Continent name, or `None` over open water.
        subregion (`str` or `None`):
            UN subregion, or `None` over open water.
        nearest_city (`str`):
            Name of the closest populated place in the bundled dataset.
        city_distance_km (`float`):
            Distance to that city in kilometres.
        city_bearing (`str`):
            Compass direction from the city to the coordinate.
    """

    country: str | None
    continent: str | None
    subregion: str | None
    nearest_city: str
    city_distance_km: float
    city_bearing: str


@functools.lru_cache(maxsize=1)
def _countries() -> list[dict]:
    return json.loads(COUNTRIES_FILE.read_text())["features"]


@functools.lru_cache(maxsize=1)
def _cities() -> list[tuple[str, float, float]]:
    feats = json.loads(CITIES_FILE.read_text())["features"]
    out = []
    for f in feats:
        lon, lat = f["geometry"]["coordinates"]
        out.append((f["properties"]["name"], lat, lon))
    return out


@functools.lru_cache(maxsize=8)
def _detail(layer: str) -> list[dict]:
    """Load one optional detail layer, or an empty list when absent."""
    path = DETAIL_DIR / f"{layer}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _osm_cache_path(lat: float, lon: float, span: float) -> pathlib.Path:
    """Cache file for one street window, keyed by a quantised bounding box.

    The key carries `_OSM_SCHEMA`, so widening what is stored per way retires
    the old files instead of serving geometry with no labels.
    """
    key = f"v{_OSM_SCHEMA}_{round(lat, 3):.3f}_{round(lon, 3):.3f}_{round(span, 4):.4f}"
    digest = hashlib.sha1(key.encode()).hexdigest()[:16]
    return OSM_CACHE_DIR / f"{digest}.json"


def _fetch_streets(lat: float, lon: float, span: float) -> list[dict]:
    """Ask Overpass for the ways in one window, or return an empty list.

    Any failure — offline, rate limited, malformed — degrades to no streets
    rather than failing the step that asked for the map.
    """
    box = f"{lat - span},{lon - span},{lat + span},{lon + span}"
    # Street names and road numbers are what make the agent's map comparable to
    # the human's, and they cost nothing extra: Overpass returns tags with the
    # geometry either way.
    query = f'[out:json][timeout:30];way["highway"]({box});out tags geom;'
    payload = None
    for attempt in range(1, OVERPASS_ATTEMPTS + 1):
        request = urllib.request.Request(
            OVERPASS_URL,
            data=urllib.parse.urlencode({"data": query}).encode(),
            headers={"User-Agent": "openenv-geoguesser-env/0.1 (research environment)"},
        )
        try:
            with urllib.request.urlopen(
                request, timeout=OVERPASS_TIMEOUT_S
            ) as response:
                payload = json.loads(response.read())
            break
        except Exception as exc:  # noqa: BLE001 - a missing map must not end a step
            logger.warning(
                "street detail unavailable for %.3f,%.3f (attempt %d/%d): %r",
                lat,
                lon,
                attempt,
                OVERPASS_ATTEMPTS,
                exc,
            )
    if payload is None:
        _STREET_FETCH_FAILED[0] = True
        return []
    _STREET_FETCH_FAILED[0] = False
    ways = []
    for element in payload.get("elements", []):
        geometry = element.get("geometry") or []
        if len(geometry) < 2:
            continue
        tags = element.get("tags") or {}
        kind = tags.get("highway", "residential")
        way = {
            "w": STREET_WEIGHTS.get(kind, 0.6),
            "c": [[point["lon"], point["lat"]] for point in geometry],
        }
        # A road number is often the only label a rural road has, and it is
        # exactly the clue a player reads off a sign.
        label = tags.get("name") or tags.get("ref")
        if label:
            way["n"] = label[:34]
        ways.append(way)
    return ways


def street_ways(lat: float, lon: float, span: float) -> list[dict]:
    """
    Street geometry for one window, cached on disk.

    Args:
        lat (`float`):
            Latitude at the centre of the window.
        lon (`float`):
            Longitude at the centre of the window.
        span (`float`):
            Half-width of the window in degrees.

    Returns:
        `list[dict]`: One entry per way, with a line width `w` and a coordinate
        list `c`. Empty when the window is too wide, streets are disabled, or
        the fetch failed.
    """
    path = _osm_cache_path(lat, lon, span)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            path.unlink(missing_ok=True)
    ways = _fetch_streets(lat, lon, span)
    OSM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ways, separators=(",", ":")))
    logger.info(
        "cached %d street ways for %.3f,%.3f span %.3f", len(ways), lat, lon, span
    )
    return ways


def has_detail() -> bool:
    """Whether the optional detail layers are installed."""
    return any(
        (DETAIL_DIR / f"{name}.json").exists()
        for name in ("roads", "urban", "places", "rivers")
    )


def _parts(row: dict) -> list[list]:
    """Coordinate lists for one compacted feature, whatever its geometry."""
    kind, coordinates = row["t"], row["c"]
    if kind in ("LineString", "Point"):
        return [coordinates] if kind == "LineString" else [[coordinates]]
    if kind == "MultiLineString":
        return coordinates
    if kind == "Polygon":
        return [coordinates[0]]
    if kind == "MultiPolygon":
        return [polygon[0] for polygon in coordinates]
    return []


def _near(points: list, lat: float, lon: float, span: float) -> bool:
    return any(
        abs(point[0] - lon) < span and abs(point[1] - lat) < span for point in points
    )


def _rings(geometry: dict) -> list[list]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [poly[0] for poly in geometry["coordinates"]]
    return []


def _bearing(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> str:
    d_lon = math.radians(to_lon - from_lon)
    lat_a, lat_b = math.radians(from_lat), math.radians(to_lat)
    y = math.sin(d_lon) * math.cos(lat_b)
    x = math.cos(lat_a) * math.sin(lat_b) - math.sin(lat_a) * math.cos(
        lat_b
    ) * math.cos(d_lon)
    deg = (math.degrees(math.atan2(y, x)) + 360) % 360
    return _COMPASS[int(deg / 45 + 0.5) % 8]


def locate(lat: float, lon: float) -> Place:
    """
    Describe a coordinate using only the bundled vectors.

    Args:
        lat (`float`):
            Latitude in degrees.
        lon (`float`):
            Longitude in degrees.

    Returns:
        [`Place`]: Administrative names for the point, plus the nearest
        populated place with distance and bearing.
    """
    country = continent = subregion = None
    for feature in _countries():
        for ring in _rings(feature["geometry"]):
            if MplPath(ring).contains_point((lon, lat)):
                props = feature["properties"]
                country = props.get("ADMIN")
                continent = props.get("CONTINENT")
                subregion = props.get("SUBREGION")
                break
        if country:
            break

    best_name, best_km, best_bearing = "", float("inf"), "N"
    for name, city_lat, city_lon in _cities():
        km = _haversine_km(lat, lon, city_lat, city_lon)
        if km < best_km:
            best_name, best_km = name, km
            best_bearing = _bearing(city_lat, city_lon, lat, lon)
    return Place(country, continent, subregion, best_name, best_km, best_bearing)


def describe_pin(
    index: int, lat: float, lon: float, previous: tuple[float, float] | None = None
) -> str:
    """
    One line of feedback for a pin, containing nothing about the target.

    Args:
        index (`int`):
            1-based pin number.
        lat (`float`):
            Latitude of the pin.
        lon (`float`):
            Longitude of the pin.
        previous (`tuple[float, float]`, *optional*):
            The preceding pin, so the agent can compare its own candidates.

    Returns:
        `str`: Feedback describing the pinned location.
    """
    place = locate(lat, lon)
    where = (
        f"{place.country} ({place.subregion})"
        if place.country
        else "open water - no landmass at this coordinate"
    )
    line = (
        f"Pin {index} placed at {lat:.4f}, {lon:.4f} - {where}. "
        f"Nearest major city: {place.nearest_city}, "
        f"~{place.city_distance_km:.0f} km {place.city_bearing}."
    )
    if previous is not None:
        km = _haversine_km(lat, lon, previous[0], previous[1])
        line += f" Distance from pin {index - 1}: {km:.0f} km."
    return line


def _draw_land(ax, linewidth: float) -> None:
    for feature in _countries():
        for ring in _rings(feature["geometry"]):
            ax.add_patch(
                MplPolygon(
                    ring,
                    closed=True,
                    facecolor=_LAND,
                    edgecolor=_BORDER,
                    linewidth=linewidth,
                )
            )


def _label_countries(ax, lat: float, lon: float, span: float) -> None:
    """Label countries visible in the window, clipped to the viewport."""
    for feature in _countries():
        for ring in _rings(feature["geometry"]):
            visible = [
                p for p in ring if abs(p[0] - lon) < span and abs(p[1] - lat) < span
            ]
            if len(visible) > 3:
                cx = sum(p[0] for p in visible) / len(visible)
                cy = sum(p[1] for p in visible) / len(visible)
                ax.text(
                    cx,
                    cy,
                    feature["properties"]["NAME"],
                    fontsize=7.4,
                    ha="center",
                    color="#55504a",
                    zorder=7,
                )
                break


def _draw_detail(ax, lat: float, lon: float, span: float) -> None:
    """Draw urban areas, rivers, roads and town names, by zoom level.

    Each layer switches on below its own span so a wide view stays legible and a
    tight view shows enough road structure to aim a pin within a town.
    """
    if span <= URBAN_MAX_SPAN_DEG:
        for row in _detail("urban"):
            for part in _parts(row):
                if _near(part, lat, lon, span):
                    ax.add_patch(
                        MplPolygon(
                            part,
                            closed=True,
                            facecolor=_URBAN,
                            edgecolor="none",
                            zorder=2,
                        )
                    )
    if span <= RIVERS_MAX_SPAN_DEG:
        segments = [
            part
            for row in _detail("rivers")
            for part in _parts(row)
            if _near(part, lat, lon, span)
        ]
        if segments:
            ax.add_collection(
                LineCollection(segments, colors=_RIVER, linewidths=0.9, zorder=3)
            )
    if span <= ROADS_MAX_SPAN_DEG:
        segments = [
            part
            for row in _detail("roads")
            for part in _parts(row)
            if _near(part, lat, lon, span)
        ]
        if segments:
            ax.add_collection(
                LineCollection(segments, colors=_ROAD, linewidths=1.4, zorder=4)
            )
    if span <= STREET_MAX_SPAN_DEG and _STREETS_ENABLED[0]:
        ways = street_ways(lat, lon, span)
        # Generalise by zoom the way a real style does: drawing every service
        # road and footpath at city scale turns the grid into a smear, so the
        # minor classes only appear once the window is tight enough to hold
        # them, and widths grow as the window shrinks.
        floor = 0.75 if span > 0.15 else (0.55 if span > 0.05 else 0.0)
        scale = 1.0 if span > 0.15 else (1.4 if span > 0.05 else 1.9)
        drawn = [way for way in ways if way["w"] >= floor]
        for weight in sorted({way["w"] for way in drawn}):
            segments = [way["c"] for way in drawn if way["w"] == weight]
            width = weight * scale
            # A casing under a white fill is what makes a dense grid legible; a
            # single flat colour reads as noise.
            ax.add_collection(
                LineCollection(
                    segments, colors="#c9bfb3", linewidths=width + 0.5, zorder=4
                )
            )
            ax.add_collection(
                LineCollection(segments, colors="#ffffff", linewidths=width, zorder=5)
            )
        _label_streets(ax, drawn, lat, lon, span)
    if span <= TOWNS_MAX_SPAN_DEG:
        shown = 0
        for row in _detail("places"):
            point = row["c"]
            if abs(point[0] - lon) < span * 0.95 and abs(point[1] - lat) < span * 0.95:
                ax.plot(
                    point[0],
                    point[1],
                    "o",
                    markersize=2.6,
                    markerfacecolor=_TOWN,
                    markeredgecolor="none",
                    zorder=6,
                )
                if row.get("n"):
                    label = ax.text(
                        point[0],
                        point[1] + span * 0.03,
                        row["n"],
                        fontsize=6.2,
                        ha="center",
                        color=_TOWN,
                        zorder=9,
                    )
                    label.set_path_effects(
                        [
                            path_effects.Stroke(linewidth=1.8, foreground="#ffffff"),
                            path_effects.Normal(),
                        ]
                    )
                shown += 1
                if shown >= (8 if span <= STREET_MAX_SPAN_DEG else 28):
                    break


def _label_streets(ax, ways: list[dict], lat: float, lon: float, span: float) -> None:
    """
    Write street names along the ways, the way a real map style does.

    One label per name, on that name's longest visible run, rotated to follow
    the road and haloed so it stays readable over the casing. Longest-run
    selection matters: labelling an arbitrary segment puts "Main Street" on a
    50 m stub while the avenue itself goes unnamed.

    Args:
        ax:
            Matplotlib axes to draw on.
        ways (`list[dict]`):
            Way records from [`street_ways`], some carrying a name in `n`.
        lat (`float`):
            Latitude at the centre of the window.
        lon (`float`):
            Longitude at the centre of the window.
        span (`float`):
            Half-width of the window in degrees.
    """
    if span > STREET_LABEL_MAX_SPAN_DEG:
        return
    # Pick, per name, the longest run of points that actually falls inside the
    # window, so the label lands where the reader can see it.
    best: dict[str, tuple[float, list]] = {}
    for way in ways:
        name = way.get("n")
        if not name:
            continue
        inside = [
            point
            for point in way["c"]
            if abs(point[0] - lon) < span * 0.92 and abs(point[1] - lat) < span * 0.92
        ]
        if len(inside) < 2:
            continue
        length = sum(
            math.dist(inside[i], inside[i + 1]) for i in range(len(inside) - 1)
        )
        if name not in best or length > best[name][0]:
            best[name] = (length, inside)

    ordered = sorted(best.items(), key=lambda item: -item[1][0])
    aspect = max(0.05, math.cos(math.radians(lat)))
    # Parallel streets in a grid all have their midpoint in the same place, so
    # placing every label at its midpoint stacks them into an unreadable pile.
    # Claim one coarse cell per label, walking along each road to find a free
    # one, and drop the label rather than overprint. Longest roads go first, so
    # the ones worth naming win the space.
    occupied: set[tuple[int, int]] = set()
    # The cell has to be taller than the crowding you want to break up, not
    # just taller than the glyphs: parallel streets one block apart land in
    # different fine cells and still read as a stack. A tall cell forces
    # neighbours to slide along their own road instead, which is what a real
    # map style does.
    cell_x = span * 0.22
    cell_y = span * 0.13
    placed = 0
    for name, (_, points) in ordered:
        if placed >= MAX_STREET_LABELS:
            break
        middle = len(points) // 2
        # Try the midpoint first, then positions either side of it.
        order = sorted(range(len(points)), key=lambda i: abs(i - middle))
        chosen = None
        for i in order:
            cell = (
                int((points[i][0] - lon) / cell_x),
                int((points[i][1] - lat) / cell_y),
            )
            if cell not in occupied:
                occupied.add(cell)
                chosen = i
                break
        if chosen is None:
            continue
        placed += 1
        middle = chosen
        start = points[max(0, middle - 1)]
        end = points[min(len(points) - 1, middle + 1)]
        # Longitude degrees are shorter than latitude ones away from the
        # equator, so the on-screen angle needs the cos(lat) correction or
        # labels sit visibly off their road.
        angle = math.degrees(
            math.atan2(end[1] - start[1], (end[0] - start[0]) * aspect)
        )
        if angle > 90:
            angle -= 180
        elif angle < -90:
            angle += 180
        text = ax.text(
            points[middle][0],
            points[middle][1],
            name,
            fontsize=4.6,
            ha="center",
            va="center",
            rotation=angle,
            rotation_mode="anchor",
            color="#4a453f",
            zorder=8,
        )
        text.set_path_effects(
            [
                path_effects.Stroke(linewidth=1.4, foreground="#ffffff"),
                path_effects.Normal(),
            ]
        )


def _scale_bar(ax, lat: float, lon: float, span: float) -> None:
    km_per_degree = 111.32 * max(0.05, math.cos(math.radians(lat)))
    # A bar reading "100 km" across a hemisphere is worse than no bar.
    if span > 20:
        unit = 2000
    elif span > 5:
        unit = 500
    elif span > 2:
        unit = 100
    elif span > 0.5:
        unit = 20
    else:
        unit = 5
    bar = unit / km_per_degree
    x0, y0 = lon - span * 0.9, lat - span * 0.9
    ax.plot([x0, x0 + bar], [y0, y0], color=_INK, linewidth=2.2, zorder=9)
    ax.text(
        x0 + bar / 2,
        y0 + span * 0.04,
        f"{unit} km",
        fontsize=6.6,
        ha="center",
        color=_INK,
        zorder=9,
    )


def _plot_pins(ax, pins: list[tuple[float, float]], size: float) -> None:
    for i, (lat, lon) in enumerate(pins, 1):
        ax.plot(
            lon,
            lat,
            marker="o",
            markersize=size,
            markerfacecolor=_PIN,
            markeredgecolor="white",
            markeredgewidth=1.5,
            zorder=8,
        )
        ax.annotate(
            str(i),
            (lon, lat),
            color="white",
            fontsize=size * 0.62,
            weight="bold",
            ha="center",
            va="center",
            zorder=9,
        )


def _plot_truth(ax, pins, truth: tuple[float, float], size: float) -> None:
    """Draw the true location and the line to the guess it is being compared to."""
    truth_lat, truth_lon = truth
    if pins:
        guess_lat, guess_lon = pins[-1]
        ax.plot(
            [guess_lon, truth_lon],
            [guess_lat, truth_lat],
            linestyle="--",
            color=_PIN,
            linewidth=1.6,
            zorder=7,
        )
    ax.plot(
        truth_lon,
        truth_lat,
        marker="o",
        markersize=size,
        markerfacecolor=_TRUTH,
        markeredgecolor="white",
        markeredgewidth=1.5,
        zorder=10,
    )


def render_map(
    pins: list[tuple[float, float]],
    focus: tuple[float, float] | None = None,
    span_deg: float = 7.0,
    dpi: int = 100,
    truth: tuple[float, float] | None = None,
) -> Image.Image:
    """
    Render the guess map: a world panel plus a zoomed panel.

    Args:
        pins (`list[tuple[float, float]]`):
            Pins as `(lat, lon)`, drawn and numbered in order.
        focus (`tuple[float, float]`, *optional*):
            Centre of the zoomed panel. Defaults to the last pin.
        span_deg (`float`, *optional*, defaults to `7.0`):
            Half-width of the zoomed panel in degrees. Below roughly 4 degrees
            the panel adds urban areas, roads, rivers and town names, when the
            optional detail layers are installed.
        dpi (`int`, *optional*, defaults to `100`):
            Figure resolution.
        truth (`tuple[float, float]`, *optional*):
            Ground truth, drawn in green with a dashed line to the last pin.
            Only ever passed after a guess has been scored, so it cannot leak
            into an observation the agent sees before committing.

    Returns:
        `PIL.Image.Image`: The two-panel map.
    """
    fig, (world, zoom) = plt.subplots(
        1, 2, figsize=(10.2, 3.9), dpi=dpi, gridspec_kw={"width_ratios": [1.55, 1]}
    )

    _draw_land(world, 0.35)
    world.set_xlim(-180, 180)
    world.set_ylim(-90, 90)
    world.set_facecolor(_WATER)
    for x in range(-180, 181, 60):
        world.axvline(x, color="white", linewidth=0.5, alpha=0.7)
    for y in range(-60, 61, 30):
        world.axhline(y, color="white", linewidth=0.5, alpha=0.7)
    _plot_pins(world, pins, 8.0)
    if truth is not None:
        _plot_truth(world, pins, truth, 8.0)
    title = "guess and true location" if truth is not None else "your pins - world"
    world.set_title(title, fontsize=9, loc="left", color="#333")
    world.set_xticks([])
    world.set_yticks([])

    focus_lat, focus_lon = focus if focus else (pins[-1] if pins else (20.0, 0.0))
    _draw_land(zoom, 0.9)
    zoom.set_xlim(focus_lon - span_deg, focus_lon + span_deg)
    zoom.set_ylim(focus_lat - span_deg, focus_lat + span_deg)
    zoom.set_facecolor(_WATER)
    _draw_detail(zoom, focus_lat, focus_lon, span_deg)
    # Above about 20 degrees every country in a hemisphere wants a label and the
    # panel turns into a stack of overlapping text.
    if TOWNS_MAX_SPAN_DEG < span_deg <= 20.0:
        _label_countries(zoom, focus_lat, focus_lon, span_deg)
    _plot_pins(zoom, pins, 10.0)
    if truth is not None:
        _plot_truth(zoom, pins, truth, 10.0)
    _scale_bar(zoom, focus_lat, focus_lon, span_deg)
    # Below a degree, degrees round to "0"; kilometres are the useful unit there.
    width_deg = span_deg * 2
    label = (
        f"{width_deg:.0f} deg view"
        if width_deg >= 1
        else f"{width_deg * 111:.0f} km view"
    )
    zoom.set_title(label, fontsize=9, loc="left", color="#333")
    zoom.set_xticks([])
    zoom.set_yticks([])

    fig.tight_layout(pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")
