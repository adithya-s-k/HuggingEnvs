"""Fetch openly licensed hibiscus photographs from iNaturalist, with attribution.

The reference photographs are what the pool's refinement loop iterates against, and
Narreddi's blog never says where theirs came from, so this picks a source that can be
published: research-grade observations of Hibiscus rosa-sinensis under cc0, cc-by or
cc-by-sa. 376 are available, which is plenty when one photograph can seed several
candidates.

The Hugging Face mirrors of iNaturalist are not usable here. The largest,
`philipp-zettl/inaturalist-s3-massive`, carries only `photo_id`, `observation_uuid` and
`image`: no species, no licence, no author. iNaturalist has no official account on the
Hub. The API gives all three in one call.

Attribution is collected at download time rather than reconstructed later, because
cc-by and cc-by-sa both require it and matching photographs back to observations after
the fact is the kind of job nobody does.
"""
from __future__ import annotations

import json
import pathlib
import urllib.parse
import urllib.request

TAXON = "Hibiscus rosa-sinensis"
LICENCES = "cc0,cc-by,cc-by-sa"
PER_PAGE = 100
OUT = pathlib.Path("/tmp/blog/fotos")
UA = "watercolour-repro/1.0 (open reproduction of an RL painting experiment)"


def get(url: str) -> dict:
    """One JSON GET with the user agent iNaturalist asks for."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=90).read())


def observations() -> list[dict]:
    """Every research-grade, openly licensed observation of the taxon."""
    out, page = [], 1
    while True:
        url = (
            "https://api.inaturalist.org/v1/observations"
            f"?taxon_name={urllib.parse.quote(TAXON)}"
            f"&quality_grade=research&photo_license={LICENCES}"
            f"&per_page={PER_PAGE}&page={page}&order_by=votes"
        )
        data = get(url)
        out.extend(data["results"])
        print(f"  pagina {page}: {len(data['results'])} de {data['total_results']}", flush=True)
        if len(out) >= data["total_results"] or not data["results"]:
            return out
        page += 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    obs = observations()
    manifest = []
    for o in obs:
        for photo in o.get("photos", [])[:1]:  # the first photo of each observation
            # `square` is the thumbnail the API returns; `large` is the useful size.
            url = photo["url"].replace("/square.", "/large.")
            name = f"{photo['id']}.jpg"
            path = OUT / name
            if not path.exists():
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    path.write_bytes(urllib.request.urlopen(req, timeout=90).read())
                except Exception as exc:
                    print(f"  falla {photo['id']}: {type(exc).__name__}", flush=True)
                    continue
            manifest.append({
                "file": name,
                "photo_id": photo["id"],
                "observation_id": o["id"],
                "observation_url": o.get("uri"),
                "licence": photo.get("license_code"),
                "attribution": photo.get("attribution"),
                "observed_on": o.get("observed_on"),
                "place": o.get("place_guess"),
            })
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    by_licence: dict[str, int] = {}
    for m in manifest:
        by_licence[m["licence"]] = by_licence.get(m["licence"], 0) + 1
    print(f"\n{len(manifest)} fotos en {OUT}")
    for k, v in sorted(by_licence.items()):
        print(f"   {k}: {v}")
    print(f"manifiesto con atribucion: {OUT / 'manifest.json'}")


if __name__ == "__main__":
    main()
