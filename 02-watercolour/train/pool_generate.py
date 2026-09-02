# /// script
# requires-python = ">=3.10"
# dependencies = ["huggingface_hub", "pillow", "playwright", "requests"]
# ///
"""Generate reference paintings by refining each candidate against a photograph.

This is the loop that produced the published pool. A text-only generator writes a
sketch, the render is shown to a vision judge next to a real photograph of the
subject, the judge says in plain words what the painting would need, and the
generator rewrites the whole sketch with that feedback. Three rounds per candidate.
The generators never see the photograph: the judge sees it and turns it into words,
which is why a photograph with a hand or a label in it is still usable.

**Every round of every candidate is kept.** HPSv3 put the peak at round 1 rather
than round 2 in five of seven cases measured, and one candidate fell from +6.92 to
+0.15 between rounds, so keeping only the last round would keep the worse painting
about half the time. Tiering happens afterwards, by hand, over everything:
`pool_rate.py` reads the output directory directly.

Four model families rather than one, because a pool from a single model is a pool
in a single style. The four below are the ones that produced a valid sketch every
time in a reliability check; two other candidates were dropped for spending their
whole budget on reasoning traces or not surviving concurrency.

Scoring along the way is HPSv3's, through the same Space the training reward uses
(`--hpsv3-url`). Vision judges were tried for this and rejected: two different ones
marked twenty-one visibly different paintings all 7 out of 10, while HPSv3 spread
the same paintings over eight points in an order that matches the eye. The score is
metadata for the later rating pass, not a filter: nothing is discarded here.

    python train/pool_photos.py --out pool_photos
    python train/pool_generate.py --photos pool_photos --out pool_candidates \\
        --hpsv3-url https://<you>-watercolour-hpsv3.hf.space
    python train/pool_rate.py serve --directory pool_candidates

The run writes `progress.html` in the output directory, a self-refreshing page with
every painting so far, best first. Stopping is safe: everything finished is already
on disk.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import io
import json
import pathlib
import random
import statistics
import sys
import time

import requests
from huggingface_hub import AsyncInferenceClient, get_token
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from envs.watercolour.core.domains import get_domain  # noqa: E402
from envs.watercolour.core.prompt import system_prompt  # noqa: E402
from envs.watercolour.core.render import close_shared_renderer, shared_renderer  # noqa: E402
from envs.watercolour.core.sketch_source import SourceError, extract_sketch  # noqa: E402

# `enable_thinking: False` where the model otherwise burns its budget on a
# reasoning trace and returns empty content. Measured on three subjects each:
# all four produce a sketch three times out of three under concurrency.
NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}
GENERATORS = [
    ("moonshotai/Kimi-K3", NO_THINK),
    ("Qwen/Qwen3.5-122B-A10B", NO_THINK),
    ("Qwen/Qwen3-Coder-Next", None),
    ("zai-org/GLM-5.2", None),
]
VISION = "Qwen/Qwen3-VL-30B-A3B-Instruct"

CRITIQUE = """You are looking at two images. The first is a photograph of a flower. The second
is a watercolour painting made by writing code, which is trying to capture the flower in the
photograph.

Judge only the bloom. Ignore the photograph's background, and any hands, labels, pots or other
objects in it: the painting is meant to show the flower alone on plain paper.

Say what the painting would need to change to read more like that flower as a loose watercolour.
Be concrete and visual: colours, how many petals and their shape, how the centre reads, the
leaves and stem, how much of the frame the flower fills. Do not mention code, methods, scores or
judges. At most five sentences. If the painting is already a good loose watercolour of that
flower, say so in one sentence and nothing else."""


def data_uri(data: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def photo_uri(path: pathlib.Path) -> str:
    """The photograph, downscaled so the request stays small."""
    im = Image.open(path).convert("RGB")
    im.thumbnail((640, 640))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return data_uri(buf.getvalue(), "image/jpeg")


def hpsv3_score(url: str | None, png: bytes) -> float:
    if not url:
        return float("nan")
    for _ in range(2):
        try:
            r = requests.post(f"{url.rstrip('/')}/score",
                              json={"png_base64": base64.b64encode(png).decode()}, timeout=60)
            r.raise_for_status()
            return float(r.json()["mu"])
        except Exception:
            time.sleep(2)
    return float("nan")


async def generate(client, model: str, extra, messages: list[dict]) -> str | None:
    """One sketch, or None if the reply had no code in it."""
    kw = {"extra_body": extra} if extra else {}
    try:
        reply = await client.chat_completion(
            model=model, max_tokens=4096, temperature=0.9, messages=messages, **kw
        )
    except Exception as exc:
        print(f"      {model.split('/')[-1]}: generation failed {type(exc).__name__}", flush=True)
        return None
    try:
        return extract_sketch(reply.choices[0].message.content or "")
    except SourceError:
        return None


async def critique(client, photo: str, png: bytes) -> str:
    """What the painting would need, in the judge's words."""
    content = [
        {"type": "text", "text": CRITIQUE},
        {"type": "image_url", "image_url": {"url": photo}},
        {"type": "image_url", "image_url": {"url": data_uri(png)}},
    ]
    reply = await client.chat_completion(
        model=VISION, messages=[{"role": "user", "content": content}],
        max_tokens=320, temperature=0.2,
    )
    return (reply.choices[0].message.content or "").strip()


async def candidate(client, renderer, index: int, model: str, extra,
                    photo: pathlib.Path, subject: str, rounds: int,
                    out: pathlib.Path, hpsv3_url: str | None,
                    done: list[dict], gate: asyncio.Semaphore) -> None:
    """Generate, render, critique and regenerate, `rounds` times."""
    async with gate:
        fu = photo_uri(photo)
        messages = [
            {"role": "system", "content": system_prompt(get_domain())},
            {"role": "user", "content": f"Paint {subject} in loose watercolour."},
        ]
        for r in range(rounds):
            sketch = await generate(client, model, extra, messages)
            if not sketch:
                return
            try:
                render = await renderer.render(sketch)
            except Exception:
                return
            name = f"c{index:04d}_r{r}"
            (out / f"{name}.png").write_bytes(render.png)
            (out / f"{name}.js").write_text(sketch)
            mu = await asyncio.to_thread(hpsv3_score, hpsv3_url, render.png)
            done.append({
                "png": f"{name}.png",
                "kept": True,
                "model": model.split("/")[-1],
                "subject": subject,
                "round": r,
                "hpsv3_mu": mu,
                "photo": photo.name,
                "paint_fraction": render.paint_fraction,
                "errors": [str(e)[:90] for e in render.errors][:3],
            })
            if r < rounds - 1:
                words = await critique(client, fu, render.png)
                if not words:
                    return
                messages = messages + [
                    {"role": "assistant", "content": f"```javascript\n{sketch}\n```"},
                    {"role": "user", "content":
                     f"Here is what your painting needs:\n\n{words}\n\n"
                     "Write the whole sketch again with those changes. "
                     "Same rules, same methods."},
                ]


def write_page(out: pathlib.Path, done: list[dict], planned: int) -> None:
    """Rewrite the progress page from everything finished so far, best first."""
    alive = sorted((d for d in done), key=lambda d: -(d["hpsv3_mu"] if d["hpsv3_mu"] == d["hpsv3_mu"] else -99))
    by_model: dict[str, list[float]] = {}
    for d in alive:
        if d["hpsv3_mu"] == d["hpsv3_mu"]:
            by_model.setdefault(d["model"], []).append(d["hpsv3_mu"])
    rows = "".join(
        f"<tr><td>{html.escape(m)}</td><td>{len(v)}</td>"
        f"<td>{statistics.mean(v):+.2f}</td><td>{max(v):+.2f}</td></tr>"
        for m, v in sorted(by_model.items(), key=lambda x: -statistics.mean(x[1])))
    cards = "".join(
        f'<figure><img loading="lazy" src="{d["png"]}" alt="{d["png"]}">'
        f'<figcaption><b>{d["hpsv3_mu"]:+.2f}</b> <span>{html.escape(d["model"][:14])} '
        f'r{d["round"]} · paint {d["paint_fraction"]:.2f}</span></figcaption></figure>'
        for d in alive[:400])
    (out / "progress.html").write_text(f"""<!doctype html><meta charset="utf-8">
<meta http-equiv="refresh" content="45"><title>Pool, generating</title>
<style>
body{{background:#faf7f2;color:#20201d;font:400 15px/1.5 system-ui,sans-serif;margin:0;padding:0 0 4rem;}}
header{{padding:1.2rem 1.4rem;border-bottom:1px solid #e3ddd2;}}
h1{{font:600 1.15rem/1.2 system-ui;margin:0 0 .5rem;}} p{{color:#6d6a62;font-size:.87rem;margin:.3rem 0;}}
table{{border-collapse:collapse;font-size:.85rem;margin:.8rem 0 0;font-variant-numeric:tabular-nums;}}
th,td{{text-align:left;padding:.25rem .9rem .25rem 0;border-bottom:1px solid #e3ddd2;}}
main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.7rem;padding:1.2rem 1.4rem;}}
figure{{margin:0;background:#fff;border:1px solid #e3ddd2;border-radius:6px;overflow:hidden;}}
img{{display:block;width:100%;height:150px;object-fit:contain;background:#fff;}}
figcaption{{padding:.3rem .45rem;font-size:.72rem;color:#6d6a62;display:flex;gap:.4rem;}}
</style>
<header><h1>Pool, generating</h1>
<p><b>{len(alive)}</b> paintings of <b>{planned}</b> planned, ordered by HPSv3, best first.
The page reloads itself every 45 seconds.</p>
<table><tr><th>model</th><th>n</th><th>mean</th><th>best</th></tr>{rows}</table>
</header><main>{cards}</main>""")


async def run(args) -> None:
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    photos_dir = pathlib.Path(args.photos)
    manifest = json.loads((photos_dir / "manifest.json").read_text())
    rnd = random.Random(args.seed)
    jobs = []
    domain = get_domain()
    for i in range(args.candidates):
        model, extra = GENERATORS[i % len(GENERATORS)]
        photo = photos_dir / manifest[rnd.randrange(len(manifest))]["file"]
        jobs.append((i, model, extra, photo, domain.subjects[i % len(domain.subjects)]))
    print(f"{args.candidates} candidates x {args.rounds} rounds over {len(manifest)} photographs, "
          f"{len(GENERATORS)} models, concurrency {args.concurrency}", flush=True)
    if not args.hpsv3_url:
        print("no --hpsv3-url: paintings will carry no score, which only affects the progress page")

    done: list[dict] = []
    renderer = shared_renderer()
    gate = asyncio.Semaphore(args.concurrency)
    async with AsyncInferenceClient(api_key=get_token(), timeout=400) as client:
        for start in range(0, len(jobs), args.batch):
            batch = jobs[start:start + args.batch]
            await asyncio.gather(*(
                candidate(client, renderer, i, m, e, p, s, args.rounds, out,
                          args.hpsv3_url, done, gate)
                for i, m, e, p, s in batch))
            write_page(out, done, args.candidates * args.rounds)
            (out / "candidates.json").write_text(json.dumps(done, indent=1))
            print(f"  candidates {min(start + len(batch), args.candidates)}/{args.candidates}   "
                  f"{len(done)} paintings", flush=True)
    await close_shared_renderer()
    (out / "candidates.json").write_text(json.dumps(done, indent=1))
    print(f"\ndone: {len(done)} paintings in {out}. Rate them with pool_rate.py.")


def main() -> None:
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--photos", required=True,
                    help="Directory from pool_photos.py: photographs plus manifest.json.")
    ap.add_argument("--out", required=True, help="Directory for paintings, sketches and metadata.")
    ap.add_argument("--candidates", type=int, default=500)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--hpsv3-url", help="The HPSv3 scorer Space. Optional but recommended.")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--batch", type=int, default=25,
                    help="Progress page and manifest are rewritten after each batch.")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
