# SPDX-License-Identifier: BSD-3-Clause

"""The semantic layer: is this a better watercolour than the reference?

Judging is comparative rather than absolute. "Rate this watercolour 0 to 10"
drifts between runs and between models, and calibrating it against a moving
policy is a project of its own. "Which of these two is the better watercolour"
is a question a vision model answers stably, and it is also the shape of signal
GRPO already normalises within a group.

Every comparison runs in both orders, and that is not a refinement. Measured
across two judges on pairs with a real quality difference, the verdict was
correct and order-invariant eight times out of eight. On a pair of two equally
poor paintings both judges picked whichever image came first, every time. The
position bias appears exactly when the judge has no real preference, so running
both orders converts that failure into a visible tie instead of an invented
winner. A tie scores half, because the submission genuinely matched the
reference rather than beating or losing to it.

References are drawn mostly from the weak tier rather than uniformly; see
[`DEFAULT_MIX`] for the measurement behind that.

Cost is two vision calls per reference.
The 30B judge matched the 72B on every pair measured, so the small one is the
default.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .pool import pool_dir

DEFAULT_JUDGE_MODEL = "Qwen/Qwen3-VL-30B-A3B-Instruct"

# How many references each submission is compared against. Two is enough to
# place a painting against a hand-rated pool without the cost growing linearly
# in pool size.
DEFAULT_REFERENCES = 4

# How each rollout's references are split across the tiers. Uniform sampling over
# a tiered pool throws the ladder away, which took a measurement to see: against
# uniformly drawn references, a weak policy faces at least one reference it cannot
# beat in almost every draw, and losing to it drowns whatever it wins lower down.
# Drawing half from `okay` keeps some comparisons winnable from step 0, which is
# where the judge's gradient comes from. Drawing half from `love` keeps the ceiling
# honest: sampling only what the policy can already beat is how a reward climbs
# while the paintings stay bad. The write-up compares against its top tier alone;
# the 50/50 split is this environment's one deliberate change, so an early policy
# still gets signal.
#
# The pool that ships is the published hand-rated one: 178 references in `love`
# and `okay`, pinned by revision in `pool.py`. `rung` stays in `TIERS` at zero
# weight so a pool that carries files under that tier still samples cleanly.
DEFAULT_MIX = {
    "love": float(os.environ.get("WATERCOLOUR_MIX_LOVE", 0.50)),
    "okay": float(os.environ.get("WATERCOLOUR_MIX_OKAY", 0.50)),
    "rung": float(os.environ.get("WATERCOLOUR_MIX_RUNG", 0.0)),
}

# Filename prefixes are the tier. The pool is built that way by
# `examples/watercolour_pool_author.py`, and a pool without them falls back to
# uniform sampling rather than failing.
TIERS = ("love", "okay", "rung")


# The criteria sentence is the domain's, not this module's. Telling a judge to
# weigh "layered translucent washes" is the right question for a jellyfish and a
# strange one for dense hatching, so a subject swap that leaves this alone scores
# a painting against a standard it cannot satisfy.
_PROMPT_TEMPLATE = (
    "You are judging two generative watercolour paintings, image A first and "
    "image B second.\n"
    "Which one is the better watercolour painting? {criteria}\n"
    "Ignore what the paintings depict. Judge only how they are painted.\n"
    "State the winner first, then a reason of at most twenty words."
)


def build_prompt(criteria: str) -> str:
    """Return the judge prompt for one domain's criteria."""
    return _PROMPT_TEMPLATE.format(criteria=criteria)


# `winner` is declared first and `reason` is capped, and both of those are load
# bearing. Asked the other way round the judge writes four hundred characters of
# appreciation and only then names a winner, which lands within a token or two
# of any sane limit: the verdict is what gets truncated, the JSON no longer
# parses, and the comparison silently drops out of the reward. Emitting the
# verdict first makes a cut-off reply harmless.
_SCHEMA = {
    "type": "object",
    "properties": {
        "winner": {"type": "string", "enum": ["A", "B"]},
        "reason": {"type": "string", "maxLength": 160},
    },
    "required": ["winner", "reason"],
    "additionalProperties": False,
}

# Room for the capped reason with margin, so a verbose judge still parses.
MAX_JUDGE_TOKENS = 220

# Two attempts, not three: the cost of retrying is wall clock on a run that is
# already slow, and the failure this protects against is queueing rather than an
# outage.
ATTEMPTS = 3
BACKOFF_S = 5.0

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class VisionClient(Protocol):
    """Minimal protocol for a multimodal chat endpoint."""

    model: str

    async def compare(self, prompt: str, first: bytes, second: bytes) -> str:
        """Send a prompt plus two images and return the reply text."""
        ...

    async def describe(self, prompt: str, png: bytes, schema: dict) -> str:
        """Send a prompt plus one image and return the reply text."""
        ...


class HFVisionClient:
    """Vision client backed by Hugging Face Inference Providers.

    Args:
        model (`str`, *optional*, defaults to `"Qwen/Qwen3-VL-30B-A3B-Instruct"`):
            Repository id of the judge model.
        api_key (`str`, *optional*):
            Token to authenticate with. Falls back to the ambient Hugging Face
            token when omitted.
        timeout (`float`, *optional*, defaults to `120.0`):
            Per-request timeout in seconds.

    Examples:

    ```python
    client = HFVisionClient()
    reply = await client.compare(prompt, submission_png, reference_png)
    ```
    """

    def __init__(
        self,
        model: str = DEFAULT_JUDGE_MODEL,
        api_key: str | None = None,
        timeout: float = 120.0,
    ):
        from huggingface_hub import get_token

        self.model = model
        self._api_key = api_key or get_token()
        self._timeout = timeout

    async def compare(self, prompt: str, first: bytes, second: bytes) -> str:
        """Send a prompt plus two images and return the reply text."""
        from huggingface_hub import AsyncInferenceClient

        content = [{"type": "text", "text": prompt}]
        for png in (first, second):
            uri = "data:image/png;base64," + base64.b64encode(png).decode()
            content.append({"type": "image_url", "image_url": {"url": uri}})
        # The client is built per call rather than held on the instance. Its
        # underlying session binds to whichever event loop created it, and the
        # synchronous `step()` path runs each call under its own short-lived
        # loop, so a cached client fails with "Event loop is closed" on every
        # request after the first.
        # Retried for the reason given on `HPSv3Scorer`: one attempt and no retry
        # was the whole policy, and a comparison that does not come back is read
        # downstream as a loss rather than as a missing answer. The router
        # returned 504 twice while this was being written, with four runs on the
        # same endpoint.
        import asyncio

        for intento in range(ATTEMPTS):
            try:
                async with AsyncInferenceClient(
                    api_key=self._api_key, timeout=self._timeout
                ) as client:
                    response = await client.chat_completion(
                        model=self.model,
                        messages=[{"role": "user", "content": content}],
                        max_tokens=MAX_JUDGE_TOKENS,
                        temperature=0.0,
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "verdict",
                                "schema": _SCHEMA,
                                "strict": True,
                            },
                        },
                    )
                return response.choices[0].message.content or ""
            except Exception as exc:
                print(
                    f"judge attempt {intento + 1}/{ATTEMPTS} failed: "
                    f"{type(exc).__name__}",
                    flush=True,
                )
                if intento == ATTEMPTS - 1:
                    raise
                await asyncio.sleep(BACKOFF_S)
        return ""

    async def describe(self, prompt: str, png: bytes, schema: dict) -> str:
        """Send a prompt plus one image and return the reply text.

        Same transport as [`compare`], with one image instead of two and the
        caller's schema, because an absolute mark and a pairwise verdict do not
        share a shape. A client per call for the reason given in [`compare`].

        Args:
            prompt (`str`):
                The question to ask.
            png (`bytes`):
                The painting to look at.
            schema (`dict`):
                JSON schema the reply must satisfy.
        """
        from huggingface_hub import AsyncInferenceClient

        uri = "data:image/png;base64," + base64.b64encode(png).decode()
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": uri}},
        ]
        async with AsyncInferenceClient(
            api_key=self._api_key, timeout=self._timeout
        ) as client:
            response = await client.chat_completion(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                max_tokens=MAX_JUDGE_TOKENS,
                temperature=0.0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "mark", "schema": schema, "strict": True},
                },
            )
        return response.choices[0].message.content or ""


@dataclass(frozen=True)
class Comparison:
    """One submission weighed against one reference, in both orders.

    Attributes:
        reference (`str`):
            Filename of the reference from the pool.
        submission_first (`str` or `None`):
            Which image won when the submission was shown first, `"A"` for the
            submission and `"B"` for the reference. `None` if the call failed.
        reference_first (`str` or `None`):
            Which image won when the reference was shown first, so `"A"` is now
            the reference and `"B"` the submission.
        score (`float`):
            One if the submission won both orders, zero if it lost both, half
            if the two orders disagreed.
        reasons (`list[str]`):
            What the judge said, in order.
    """

    reference: str
    submission_first: str | None
    reference_first: str | None
    score: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable view of the comparison."""
        return asdict(self)


@dataclass(frozen=True)
class JudgeReport:
    """The judge's verdict on a submission.

    Attributes:
        score (`float`):
            Mean of the per-reference scores, in [0, 1].
        comparisons (`list[Comparison]`):
            One entry per reference the submission was weighed against.
        available (`bool`):
            Whether any comparison completed. `False` means nobody looked at
            the painting, which a harness should tell apart from a bad score.
    """

    score: float
    comparisons: list[Comparison] = field(default_factory=list)
    available: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable view of the verdict."""
        return {
            "score": self.score,
            "available": self.available,
            "comparisons": [c.to_dict() for c in self.comparisons],
        }


def load_pool(directory: Path | None = None) -> list[tuple[str, bytes]]:
    """Load the reference paintings.

    Args:
        directory (`Path`, *optional*):
            Where to read PNGs from. Defaults to [`~envs.watercolour_env.server.pool.pool_dir`].

    Returns:
        `list[tuple[str, bytes]]`: Filename and PNG data for each reference,
            sorted by name so a seed picks the same references every run.

    Raises:
        FileNotFoundError: If the directory holds no PNGs. A judge with no
            references cannot judge, and it used to return zero for every
            comparison instead of saying so: the jellyfish domain pointed at a
            directory that did not exist, so selecting it would have trained
            against a reward with 0.60 of its weight permanently dead and nothing
            in the output to show it.

    Examples:

    ```python
    pool = load_pool()
    print(len(pool))
    ```
    """
    directory = pool_dir() if directory is None else directory
    references = [(p.name, p.read_bytes()) for p in sorted(directory.glob("*.png"))]
    if not references:
        raise FileNotFoundError(f"no reference paintings in {directory}")
    return references


class PairwiseJudge:
    """Scores a painting by comparing it against a pool of references.

    Args:
        client ([`VisionClient`]):
            The multimodal endpoint to ask.
        pool (`list[tuple[str, bytes]]`, *optional*):
            References to compare against. Defaults to the shipped pool.
        references (`int`, *optional*, defaults to `2`):
            How many references to sample per submission.

    Examples:

    ```python
    judge = PairwiseJudge(HFVisionClient())
    report = await judge.score(render.png, seed=0)
    print(report.score)
    ```
    """

    def __init__(
        self,
        client: VisionClient,
        pool: list[tuple[str, bytes]] | None = None,
        references: int = DEFAULT_REFERENCES,
        mix: dict[str, float] | None = None,
        criteria: str | None = None,
    ):
        self._client = client
        self._pool = pool if pool is not None else load_pool()
        self._references = references
        self._mix = mix or DEFAULT_MIX
        if criteria is None:
            from .domains import get_domain

            criteria = get_domain().judge_criteria
        self._prompt = build_prompt(criteria)

    def _sample(self, rng, wanted: int) -> list[tuple[str, bytes]]:
        """Draw references, keeping most of them reachable.

        Split by the tier in the filename, at the weights in [`DEFAULT_MIX`],
        renormalised over the tiers actually present so a pool missing one still
        gets a sensible draw. A pool with no tier prefixes at all degrades to a
        uniform draw rather than raising: it still works, it just loses the ladder.
        """
        present = {
            t: refs
            for t in TIERS
            if (refs := [r for r in self._pool if r[0].startswith(f"{t}_")])
        }
        if not present:
            return rng.sample(self._pool, min(wanted, len(self._pool)))
        total = sum(self._mix[t] for t in present)
        # Whole slots first, then hand out the remainder largest-fraction first.
        # Rounding each tier independently loses references whenever the shares do
        # not land on integers: at four references the mix gives 1, 1, 2 exactly,
        # but at two it rounded 0.5 down three times and drew a single reference
        # instead of two.
        exact = {t: wanted * self._mix[t] / total for t in present}
        counts = {t: min(len(present[t]), int(exact[t])) for t in present}
        while sum(counts.values()) < wanted:
            room = [t for t in present if counts[t] < len(present[t])]
            if not room:
                break
            counts[max(room, key=lambda t: exact[t] - counts[t])] += 1
        return [r for t in present for r in rng.sample(present[t], counts[t])]

    async def _verdict(self, first: bytes, second: bytes) -> tuple[str | None, str]:
        """Ask once and return the winning slot and the stated reason."""
        try:
            reply = await self._client.compare(self._prompt, first, second)
        except Exception:
            # A judge that cannot answer leaves the comparison unresolved
            # rather than failing the episode. `available` carries that fact
            # out to the harness.
            return None, "judge unavailable"
        match = _JSON_BLOCK.search(reply)
        if not match:
            return None, reply[:80]
        try:
            verdict = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None, reply[:80]
        winner = verdict.get("winner")
        return (winner if winner in {"A", "B"} else None), str(
            verdict.get("reason", "")
        )

    async def _compare(self, submission: bytes, name: str, reference: bytes):
        """Weigh the submission against one reference in both orders."""
        (a_winner, a_reason), (b_winner, b_reason) = await asyncio.gather(
            self._verdict(submission, reference),
            self._verdict(reference, submission),
        )
        # The submission is slot A in the first call and slot B in the second.
        wins = [a_winner == "A", b_winner == "B"]
        # Both orders or none. A single surviving call is exactly the one the
        # two-order design exists to distrust: with one verdict the score can only
        # be 0 or 1, the tie disappears, and the position bias decides. Measured
        # over 366 rollout scores, 79 of them (22%) landed on an odd eighth, which
        # is only reachable through a tie, so the mechanism carries real weight.
        # Judging against three trustworthy references beats four with one flipped
        # by coin toss.
        resolved = wins if a_winner is not None and b_winner is not None else []
        score = sum(resolved) / len(resolved) if resolved else 0.0
        return Comparison(
            reference=name,
            submission_first=a_winner,
            reference_first=b_winner,
            score=score,
            reasons=[a_reason, b_reason],
        )

    async def score(
        self, png: bytes, seed: int | None = None, references: int | None = None
    ) -> JudgeReport:
        """Judge a painting against a sample of the pool.

        Args:
            png (`bytes`):
                The painting to judge.
            seed (`int`, *optional*):
                Makes the sampled references reproducible.
            references (`int`, *optional*):
                How many references to sample. Defaults to the value the judge
                was built with.

        Returns:
            [`JudgeReport`]: The verdict.
        """
        if not self._pool:
            return JudgeReport(score=0.0, available=False)
        rng = random.Random(seed)
        wanted = references if references is not None else self._references
        chosen = self._sample(rng, wanted)
        comparisons = await asyncio.gather(
            *(self._compare(png, name, ref) for name, ref in chosen)
        )
        resolved = [
            c
            for c in comparisons
            if c.submission_first is not None and c.reference_first is not None
        ]
        if not resolved:
            return JudgeReport(
                score=0.0, comparisons=list(comparisons), available=False
            )
        return JudgeReport(
            score=sum(c.score for c in resolved) / len(resolved),
            comparisons=list(comparisons),
            available=True,
        )
