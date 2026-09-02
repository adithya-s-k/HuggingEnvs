# SPDX-License-Identifier: BSD-3-Clause

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "huggingface-hub",
#     "playwright",
#     "pillow",
#     "numpy",
# ]
# ///

"""Generate candidate paintings for the reference pool.

**Known shape issue.** This generates every candidate and only then renders them
all, so the first painting lands on disk after the last API call rather than after
the first. The rating page is built to pick paintings up as they appear, and this
script defeats that: with fifty candidates the wait before there is anything to
rate is the whole generation phase.

Interleaving the two would fix it, since the browser pool sits idle through
generation and the network sits idle through rendering. The fix is a straight
swap of the two phases for a producer feeding a consumer queue.

The pool is the reward function, so what goes in it decides what the policy
learns. Narreddi's write-up is explicit that theirs is **all model output**:
"we could not source enough human made examples since the library is a niche
tool artists use". Theirs came from frontier models iterating against reference
photographs under a VLM judge, then hand-rated one at a time into love, okay and
nope, ending at 581 references from 1,664 generations.

This script does the generating. The rating is the part that needs a person, and
[`watercolour_pool_rate.py`](watercolour_pool_rate.py) does that.

**The pool has to span a quality range, not just be good.** That is the whole
reason this exists. Six uniformly decent references measured here produced a
reward of exactly zero on every rollout: a small model loses every comparison, a
constant term carries no gradient, and GRPO sees nothing to learn from. Their
pool works because it holds 117 love-tier alongside 266 merely okay, so a
mediocre painting can beat the weak end and lose to the strong one. So this
generates deliberately across a spread of models and temperatures rather than
trying to make every candidate good.

    python examples/watercolour_pool_generate.py --per-model 20
    python examples/watercolour_pool_rate.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from envs.watercolour_env.server.gate import MIN_PAINT_FRACTION  # noqa: E402
from envs.watercolour_env.server.prompt import system_prompt  # noqa: E402
from envs.watercolour_env.server.render import (  # noqa: E402
    close_shared_renderer,
    RenderError,
    shared_renderer,
)
from envs.watercolour_env.server.sketch_source import (  # noqa: E402
    extract_sketch,
    inspect_source,
    SourceError,
)
from envs.watercolour_env.server.tasks import SUBJECTS  # noqa: E402

# The four families that generated the published reference pool. Different
# families paint in different styles, and a pool from a single model is a pool
# in a single style. All four passed a reliability check before making the cut
# (a valid sketch three times out of three under concurrency); two other
# candidates were dropped for failing it.
DEFAULT_MODELS = (
    "zai-org/GLM-5.2",
    "moonshotai/Kimi-K3",
    "Qwen/Qwen3-Coder-Next",
    "Qwen/Qwen3.5-122B-A10B",
)

# Sampled per candidate. High temperatures widen the spread, which is the point.
TEMPERATURES = (0.6, 0.9, 1.1)

# Per-call ceiling. `InferenceClient` does not time out by default, and a single
# stalled request then hangs the whole run: one call that never comes back can
# hold an established socket for half an hour with nothing written. A generation
# pass is a few hundred sequential calls, so any one of them has to be allowed to
# fail rather than to block the rest.
CALL_TIMEOUT_S = 180.0


def generate_one(client, model: str, subject: str, temperature: float, max_tokens: int):
    """Ask one model for one sketch.

    Returns `(reply, why)`: the text and `None` when it worked, or `None` and a
    short reason when it did not. The two failure modes are worth telling apart,
    which an earlier version did not: a raised exception looks nothing like a
    reasoning model that spends its whole budget thinking and returns empty
    content, and only one of those is worth retrying.

    Every failure is swallowed on purpose. One model being unavailable, rate
    limited, slow or silent should cost its own candidate and nothing else.
    """
    try:
        response = client.chat_completion(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": f"Paint {subject} in loose watercolour."},
            ],
        )
        choice = response.choices[0]
        text = choice.message.content or ""
        if not text.strip():
            # A reasoning model with thinking on: GLM-5.2 burned all 2400 tokens
            # on `reasoning_content`, came back with `finish_reason: length` and
            # empty content, and never wrote a sketch. Ten calls, ten silences,
            # a minute each.
            thinking = getattr(choice.message, "reasoning_content", "") or ""
            return None, (
                f"empty content, finish={choice.finish_reason}"
                + (f", {len(thinking)} chars of thinking" if thinking else "")
            )
        return text, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:70]}"


async def render_all(candidates, out_dir: pathlib.Path, start_index: int = 0):
    """Paint every candidate and keep the ones that put paint on the canvas.

    Rendering is concurrent across the browser pool, which is worth roughly 2x
    and no more: software rasterisation is CPU-bound. At twenty to two hundred
    seconds for a rich sketch, generating a few hundred candidates is an
    overnight job rather than a coffee break, and that is a fact about the medium
    rather than about this script.
    """
    renderer = shared_renderer()
    out_dir.mkdir(parents=True, exist_ok=True)

    finished = [0]

    async def one(offset, candidate):
        index = start_index + offset
        # The source is written before the verdict, for both outcomes. Diagnosing
        # why five sketches in a row came back blank was impossible with only the
        # kept ones on disk, and the answer was in the discarded source: the model
        # emitted the translate and then painted at negative coordinates.
        (out_dir / f"cand_{index:04d}.js").write_text(candidate["source"])
        try:
            render = await renderer.render(candidate["source"])
        except RenderError as exc:
            return {**candidate, "kept": False, "why": f"render failed: {exc}"}
        if render.paint_fraction < MIN_PAINT_FRACTION:
            return {
                **candidate,
                "kept": False,
                "why": "blank canvas",
                "js_errors": render.errors[:2],
            }
        finished[0] += 1
        print(
            f"    painted {finished[0]}/{len(candidates)} "
            f"({render.elapsed_ms / 1000:.0f}s, coverage {render.paint_fraction:.3f})",
            flush=True,
        )
        name = f"cand_{index:04d}.png"
        (out_dir / name).write_bytes(render.png)
        return {
            **candidate,
            "kept": True,
            "png": name,
            "paint_fraction": round(render.paint_fraction, 4),
            "finished": render.finished,
            "elapsed_ms": render.elapsed_ms,
            "js_errors": render.errors[:2],
        }

    results = await asyncio.gather(
        *(one(i, c) for i, c in enumerate(candidates)), return_exceptions=True
    )
    await close_shared_renderer()
    return [r for r in results if isinstance(r, dict)]


def main() -> None:
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help="Generate from each of these. A spread of sizes on purpose: the "
        "small ones fill the weak end of the pool, which is the end a policy "
        "can beat while it is still learning.",
    )
    ap.add_argument("--per-model", type=int, default=15, help="Candidates per model.")
    ap.add_argument(
        "--subject",
        default="a peach hibiscus",
        help="Pin the subject rather than sampling. Pinned by default, and it "
        "matters more than it looks: the policy is trained on one subject, so a "
        "pool spread over twelve of them makes almost every comparison "
        "cross-subject and asks the judge to absorb variance that is not about "
        "painting at all. Narreddi's pool is one subject varying by colour, which "
        "is what 'grouped by colour' in their write-up means. Pass 'sample' to "
        "draw from the catalogue instead.",
    )
    ap.add_argument("--max-tokens", type=int, default=2400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="First candidate number. Offsetting lets a second batch write into "
        "the same directory as a run already in flight without overwriting it, "
        "which is how you get something rateable while the slow models are still "
        "being waited on.",
    )
    ap.add_argument(
        "--out",
        default=str(ROOT / "envs/watercolour_env/server/reference_pool/candidates"),
        help="Where the rendered candidates land, for the rating pass to read.",
    )
    args = ap.parse_args()

    from huggingface_hub import InferenceClient

    client = InferenceClient(timeout=CALL_TIMEOUT_S)
    rng = random.Random(args.seed)
    out_dir = pathlib.Path(args.out)

    # Flushed on every line. Generation is a few hundred sequential API calls
    # followed by renders that take seconds to minutes each, so a run is tens of
    # minutes long: without flushing, a pipe swallows every progress line and
    # there is no way to tell a slow run from a hung one.
    def log(message: str) -> None:
        print(message, flush=True)

    total = len(args.models) * args.per_model
    done = 0
    candidates = []
    started_generating = time.perf_counter()
    for model in args.models:
        log(f"  {model}")
        for _ in range(args.per_model):
            done += 1
            subject = rng.choice(SUBJECTS) if args.subject == "sample" else args.subject
            temperature = rng.choice(TEMPERATURES)
            reply, why = generate_one(
                client, model, subject, temperature, args.max_tokens
            )
            elapsed = time.perf_counter() - started_generating
            eta = elapsed / done * (total - done)
            log(
                f"    {done}/{total} {subject[:24]:24s} temp {temperature} "
                f"{'ok' if reply else 'FAIL: ' + (why or '?')} "
                f"[{elapsed / 60:.0f}m, ~{eta / 60:.0f}m left]"
            )
            if reply is None:
                continue
            try:
                source = extract_sketch(reply)
            except SourceError:
                continue
            report = inspect_source(source)
            # Rejected before rendering for the same reasons the environment's
            # gate would reject them, so the pool cannot contain a painting the
            # policy would be punished for producing.
            if report.bare_primitives or report.external_access or not report.webgl:
                continue
            candidates.append(
                {
                    "model": model,
                    "subject": subject,
                    "temperature": temperature,
                    "source": source,
                    "brush_calls": len(report.painting_calls)
                    + len(report.supporting_calls),
                    "unknown_calls": report.unknown_calls,
                }
            )
    log(
        f"\n{len(candidates)} candidates survived source inspection. Rendering now,"
        " which is the slow half: a plain sketch paints in under a second and a"
        " rich one takes minutes, four at a time."
    )

    started = time.perf_counter()
    rendered = asyncio.run(render_all(candidates, out_dir, args.start_index))
    kept = [r for r in rendered if r["kept"]]
    for r in rendered:
        r.pop("source", None)
    # Merged rather than overwritten. A second batch writes into the same
    # directory with an index offset, and clobbering the manifest would strip the
    # first batch's paintings of their model, subject and coverage while leaving
    # the images themselves in place.
    manifest = out_dir / "candidates.json"
    existing = json.loads(manifest.read_text()) if manifest.exists() else []
    by_png = {c.get("png"): c for c in existing if c.get("png")}
    for r in rendered:
        if r.get("png"):
            by_png[r["png"]] = r
    unnamed = [c for c in existing if not c.get("png")] + [
        r for r in rendered if not r.get("png")
    ]
    manifest.write_text(
        json.dumps(sorted(by_png.values(), key=lambda c: c["png"]) + unnamed, indent=2)
    )

    log(
        f"{len(kept)} painted, {len(rendered) - len(kept)} discarded, "
        f"{time.perf_counter() - started:.0f}s"
    )
    if kept:
        coverage = sorted(r["paint_fraction"] for r in kept)
        log(
            f"coverage {coverage[0]:.3f} to {coverage[-1]:.3f}, "
            f"median {coverage[len(coverage) // 2]:.3f}"
        )
        by_model = {}
        for r in kept:
            by_model.setdefault(r["model"], 0)
            by_model[r["model"]] += 1
        for model, n in by_model.items():
            log(f"  {model}: {n}")
    log(f"\nnow rate them:\n  python examples/watercolour_pool_rate.py --dir {out_dir}")


if __name__ == "__main__":
    main()
