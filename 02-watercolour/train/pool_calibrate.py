# SPDX-License-Identifier: BSD-3-Clause

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "huggingface-hub",
#     "pillow",
#     "numpy",
# ]
# ///

"""Sort candidate references by how often the policy already beats them.

The tiers were assigned by eye, and by eye is how this project keeps going wrong:
the same ten GLM candidates read as "two are good" in a contact sheet and "none
are good" at full size. Eye is also the wrong instrument for the question the pool
actually answers, which is not *is this painting good* but *is this painting a
useful opponent for the policy as it stands right now*.

A pairwise comparison carries the most information when the policy wins about half
the time. A reference it always loses to and a reference it always beats teach the
same amount, which is nothing: both give every rollout in the group the same score,
and GRPO normalises a constant to zero advantage. The current pool is the first
failure and it is measured, not suspected: over the run's first fourteen rollouts,
four references each, the policy won 0 of 56 comparisons.

So this takes the paintings the policy actually produced and the candidates on
offer, runs the real judge between them in both orders, and reports the win rate
per candidate. What comes out is a difficulty ladder measured against this policy
rather than a ranking of taste.

    python examples/watercolour_pool_calibrate.py \\
        --candidates envs/watercolour_env/server/reference_pool/candidates \\
        --paintings watch/repo/film/v3-coverage \\
        --samples 6

Cost is `candidates x samples x 2` judge calls, so the defaults are small on
purpose. Nothing here writes to the pool: it prints the ladder and saves the
numbers, and packing the pool stays a separate, deliberate step.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from envs.watercolour_env.server.domains import get_domain  # noqa: E402
from envs.watercolour_env.server.gate import MIN_PAINT_FRACTION  # noqa: E402
from envs.watercolour_env.server.pairwise_judge import (  # noqa: E402
    DEFAULT_JUDGE_MODEL,
    HFVisionClient,
    PairwiseJudge,
)

# Win rates in this band make a candidate worth having: the policy beats it often
# enough to learn that it can, and loses often enough for there to be somewhere to
# go. Outside it the comparison is decided before it runs.
RUNG_LOW, RUNG_HIGH = 0.25, 0.75


def coverage(path: pathlib.Path) -> float:
    """Return the fraction of the canvas carrying pigment."""
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    bg = np.median(a.reshape(-1, 3), axis=0)
    return float((np.abs(a - bg).sum(2) > 30).mean())


def spread(paths: list[pathlib.Path], n: int) -> list[pathlib.Path]:
    """Pick `n` paintings evenly across the coverage range.

    Sampling at random would be a fair picture of the policy but a noisy one at
    this many calls, and sampling its best would flatter it. An even spread across
    what it produced is stable enough to compare candidates against each other,
    which is all the ladder needs.

    Paintings that would not clear the gate's paint floor are dropped first. They
    are real output, but the gate zeroes them before the judge ever runs, so
    including them measures comparisons that never happen in training and drags
    every candidate toward looking like a ceiling. The first dry run sampled a
    blank canvas at coverage 0.000 and did exactly that.
    """
    ranked = sorted(
        (p for p in paths if coverage(p) >= MIN_PAINT_FRACTION), key=coverage
    )
    if not ranked:
        raise SystemExit("every painting would fail the gate; nothing to calibrate")
    if len(ranked) <= n:
        return ranked
    step = (len(ranked) - 1) / (n - 1)
    return [ranked[round(i * step)] for i in range(n)]


async def win_rate(judge, paintings, name, reference) -> tuple[float, int]:
    """Return the policy's win rate against one candidate, and comparisons run.

    Uses the judge's own `_compare`, which runs both presentation orders and
    resolves a disagreement to a tie. Reimplementing that here would let the
    calibration drift away from the reward it is supposed to be calibrating.
    """
    results = await asyncio.gather(
        *(judge._compare(png, name, reference) for png in paintings)
    )
    resolved = [c for c in results if c.score is not None]
    if not resolved:
        return float("nan"), 0
    return sum(c.score for c in resolved) / len(resolved), len(resolved)


async def run(args) -> None:
    candidates = sorted(pathlib.Path(args.candidates).glob("*.png"))
    films = sorted(pathlib.Path(args.paintings).glob("*.png"))
    if not candidates or not films:
        raise SystemExit(f"candidates {len(candidates)}, paintings {len(films)}")
    if args.limit:
        candidates = random.Random(args.seed).sample(
            candidates, min(args.limit, len(candidates))
        )
    sample = spread(films, args.samples)

    judge = PairwiseJudge(
        HFVisionClient(model=args.model),
        pool=[],
        criteria=get_domain(args.domain).judge_criteria,
    )
    pngs = [p.read_bytes() for p in sample]
    print(
        f"{len(candidates)} candidates against {len(sample)} paintings "
        f"(coverage {coverage(sample[0]):.3f} to {coverage(sample[-1]):.3f}), "
        f"{len(candidates) * len(sample) * 2} judge calls\n"
    )

    rows = []
    for path in candidates:
        rate, n = await win_rate(judge, pngs, path.name, path.read_bytes())
        rows.append(
            {
                "file": path.name,
                "win_rate": rate,
                "comparisons": n,
                "coverage": coverage(path),
            }
        )
        print(
            f"  {path.name:24s} cov {rows[-1]['coverage']:.3f}  "
            f"policy wins {rate:.2f}  ({n} resolved)",
            flush=True,
        )

    rows.sort(key=lambda r: r["win_rate"])
    rungs = [r for r in rows if RUNG_LOW <= r["win_rate"] <= RUNG_HIGH]
    above = [r for r in rows if r["win_rate"] < RUNG_LOW]
    below = [r for r in rows if r["win_rate"] > RUNG_HIGH]

    print(f"\n{'-' * 58}")
    print(f"above the policy, a ceiling      {len(above):>3}  (win rate < {RUNG_LOW})")
    print(
        f"the rung worth sampling          {len(rungs):>3}  ({RUNG_LOW} to {RUNG_HIGH})"
    )
    print(f"below the policy, a free win     {len(below):>3}  (win rate > {RUNG_HIGH})")
    if rungs:
        print("\nthe rung:")
        for r in rungs:
            print(f"  {r['file']:24s} {r['win_rate']:.2f}")
    else:
        print(
            "\nNo rung. Every candidate is decided before the comparison runs, so"
            "\nthe judge term contributes the same number to every rollout and"
            "\nGRPO has nothing to separate them with. Generate weaker candidates"
            "\nif they are all a ceiling, stronger ones if they are all free wins."
        )

    out = pathlib.Path(args.out)
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nsaved {out}")


def main() -> None:
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument(
        "--candidates",
        default=str(ROOT / "envs/watercolour_env/server/reference_pool/candidates"),
    )
    ap.add_argument(
        "--paintings",
        required=True,
        help="A run's film: what the policy actually painted. The ladder is "
        "measured against this policy, so it goes stale as the policy improves.",
    )
    ap.add_argument("--samples", type=int, default=6, help="Paintings per candidate.")
    ap.add_argument("--limit", type=int, default=0, help="Cap the candidates tried.")
    ap.add_argument("--model", default=DEFAULT_JUDGE_MODEL)
    ap.add_argument("--domain", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="calibration.json")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
