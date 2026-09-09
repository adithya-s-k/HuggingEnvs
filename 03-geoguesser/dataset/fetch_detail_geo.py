# SPDX-License-Identifier: BSD-3-Clause

"""Fetch the optional detail layers the guess map draws when zoomed in.

Without these the agent's map shows country outlines and major cities only,
which is enough to place a country but not to choose a point within a city. The
human's map is street-level, so the two disagree about how precisely a pin can
be aimed — and precision is exactly what the distance reward measures.

The layers are Natural Earth 10m: roads, urban areas, river centrelines and
populated places. They total ~87 MB as raw GeoJSON, too large to commit, so
they are fetched once and compacted here into small arrays holding only the
geometry and the name, with coordinates rounded to 4 decimals (about 11 m,
finer than the panorama spacing).

Usage:
    python dataset/fetch_detail_geo.py
    python dataset/fetch_detail_geo.py --layers roads places
"""

from __future__ import annotations

import argparse
import json
import pathlib
import urllib.request

BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"

LAYERS: dict[str, tuple[str, str | None]] = {
    # name: (source file, property holding a label)
    "roads": ("ne_10m_roads", None),
    "urban": ("ne_10m_urban_areas", None),
    "rivers": ("ne_10m_rivers_lake_centerlines", None),
    "places": ("ne_10m_populated_places_simple", "name"),
}

PRECISION = 4


def _round(coordinates):
    """Round coordinates in place, at any nesting depth."""
    if isinstance(coordinates[0], (int, float)):
        return [
            round(float(coordinates[0]), PRECISION),
            round(float(coordinates[1]), PRECISION),
        ]
    return [_round(part) for part in coordinates]


def compact(features: list[dict], label: str | None) -> list[dict]:
    """Strip a Natural Earth layer to geometry plus one optional label."""
    out = []
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry or not geometry.get("coordinates"):
            continue
        row = {
            "t": geometry["type"],
            "c": _round(geometry["coordinates"]),
        }
        if label:
            row["n"] = feature.get("properties", {}).get(label) or ""
        out.append(row)
    return out


def fetch(names: list[str], out_dir: pathlib.Path) -> None:
    """Download and compact each requested layer."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        source, label = LAYERS[name]
        url = f"{BASE}/{source}.geojson"
        print(f"{name}: downloading {source}.geojson", flush=True)
        with urllib.request.urlopen(url, timeout=300) as response:
            payload = json.loads(response.read())
        rows = compact(payload["features"], label)
        target = out_dir / f"{name}.json"
        target.write_text(json.dumps(rows, separators=(",", ":")))
        print(
            f"{name}: {len(rows):,} features -> {target.name} "
            f"({target.stat().st_size / 1e6:.1f} MB)",
            flush=True,
        )


def main() -> None:
    """Command-line entry point."""
    root = pathlib.Path(__file__).resolve().parents[1] / "env"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--layers", nargs="+", choices=sorted(LAYERS), default=sorted(LAYERS)
    )
    parser.add_argument(
        "--out", type=pathlib.Path, default=root / "data" / "geo" / "detail"
    )
    args = parser.parse_args()
    fetch(args.layers, args.out)
    print(
        "\nThe guess map will now draw roads, towns and urban areas when zoomed in. "
        "Delete the directory to go back to outlines only."
    )


if __name__ == "__main__":
    main()
