# SPDX-License-Identifier: BSD-3-Clause

"""Score one painting on its own, with nothing to compare it against.

This fills the slot HPSv3 holds in Narreddi's rubric at weight 0.30, and the slot
is about the *shape* of the signal rather than the model. A pairwise judge is
relative: it needs a reference, its score lands on a 1/2N grid, and it bottoms out
at zero the moment the painting is worse than everything it was shown. Measured on
a run of this environment, twenty-four rollouts in a row scored exactly zero on the
judge while the reward sat on 0.300, so seventy per cent of the weight carried no
gradient at all. A reference-free score keeps grading after the comparison has
given up, which is the whole point of the term.

HPSv3 itself is the faithful choice (https://huggingface.co/MizzenAI/HPSv3): a 7B
preference model trained on 1.17M human pairwise annotations, so it knows what
people prefer rather than being asked at inference time. It is not used here for
one practical reason: it pins `transformers==4.45.2`. That conflicts with the
trainer, though not fatally, since the environment is a separate container; what
rules it out is that this container has no GPU, and a 7B on eight vCPUs cannot keep
up with a rollout group.

So the judge model is asked for an absolute mark instead. Validated before being
wired in, five paintings per group, temperature zero:

    pool love   9.0    pool okay   8.4    pool meh   7.4
    a VLM's own untrained output   3.4     a small model's    6.2

Monotonic across the tiers, and the part that matters is the bottom: our own
paintings came back 1, 1, 3, 6, 6 where the pairwise judge had given all of them
zero. It is compressed at the top and distinguishes `love` from `okay` poorly, but
the pairwise judge is what does the fine discrimination. This one exists to give a
policy something to climb before it can beat anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# The anchors matter more than the range. An unanchored "score from 1 to 10" drifts
# between calls and compresses everything into 7-9, which is the same dead signal in
# a different disguise. Naming what a 1, a 4, a 7 and a 10 look like is what pinned
# the tiers apart in the numbers above.
_RUBRIC = (
    "Score this single painting from 1 to 10 on those criteria. 1 is a blank or "
    "formless canvas. 4 is a coloured mass that does not read as a flower. 7 is a "
    "recognisable flower with petals around a centre. 10 is an accomplished "
    "watercolour flower with a stem, layered washes and varied edges. Answer as "
    "JSON with an integer `score` and a short `reason`."
)

SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["score", "reason"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class QualityReport:
    """One absolute mark.

    Attributes:
        score (`float`):
            The mark rescaled to [0, 1], zero when nothing was scored.
        mark (`int`):
            The raw 1 to 10 mark, zero when nothing was scored.
        reason (`str`):
            What the model said about the painting.
        available (`bool`):
            Whether a mark was actually obtained. Distinguishes "this painting
            is bad" from "nobody looked at it", which is the distinction that
            cost three steps of a run to notice was missing.
    """

    score: float = 0.0
    mark: int = 0
    reason: str = ""
    available: bool = False


class QualityScorer:
    """Ask a vision model for an absolute mark out of ten.

    Args:
        client:
            Vision client exposing `describe(prompt, png)`.
        criteria (`str`):
            The domain's judging criteria, so the mark and the pairwise verdict
            are answering the same question.

    Examples:

    ```python
    scorer = QualityScorer(HFVisionClient(), criteria=domain.judge_criteria)
    report = await scorer.score(png)
    print(report.mark, report.reason)
    ```
    """

    def __init__(self, client, criteria: str):
        self._client = client
        self._prompt = criteria.strip() + "\n\n" + _RUBRIC

    async def score(self, png: bytes) -> QualityReport:
        """Mark one painting.

        Args:
            png (`bytes`):
                The painting to mark.

        Returns:
            [`QualityReport`]: The mark, or an unavailable report when the model
                could not answer.
        """
        try:
            reply = await self._client.describe(self._prompt, png, SCHEMA)
            verdict = json.loads(reply)
            mark = int(verdict["score"])
        except Exception:
            # A model that cannot answer leaves the term unscored rather than
            # failing the episode, and `available` carries that out so a zero is
            # never mistaken for a verdict.
            return QualityReport()
        mark = max(1, min(10, mark))
        return QualityReport(
            score=(mark - 1) / 9.0,
            mark=mark,
            reason=str(verdict.get("reason", "")),
            available=True,
        )

class HPSv3Scorer:
    """The real preference model, over HTTP, in the same slot as the stand-in.

    HPSv3 is what Narreddi's rubric puts at 0.30, and the stand-in above is a chat
    model asked for a mark out of ten. Measured on our own reference pool at
    448x448, the difference is not subtle:

        stand-in   love 9.0   okay 8.4   meh 7.4   (they overlap, and one `meh`
                                                    outscored one `love`)
        HPSv3      love +3.5  okay +3.6  meh -7.5  (no overlap at all)

    It sits behind a Space rather than in this container for two reasons. It pins
    `transformers==4.45.2`, which is fine here (the environment depends on neither
    torch nor transformers) but not in the trainer; and it needs about 27GB, so it
    wants a card this environment does not have and should not pay for. Keeping it
    separate also means the GPU can be turned off on its own between runs.

    Args:
        url (`str`):
            Base URL of the scoring Space.
        timeout (`float`, *optional*, defaults to `120.0`):
            Per-request timeout in seconds.

    Examples:

    ```python
    scorer = HPSv3Scorer("https://user-watercolour-hpsv3.hf.space")
    report = await scorer.score(png)
    ```
    """

    # One attempt at 120s was the whole policy, and the failure it produced was
    # silent: `available=False`, the term counted as zero, and a painting HPSv3
    # scores at +7.59 by hand collected 0.259 of reward instead of the 0.589 the
    # dense term alone owed it. Three of five rollouts picked out by eye as
    # suspicious turned out to be this.
    #
    # Two attempts rather than three, and 90s rather than 120s each, because the
    # cost of retrying is wall clock on a run that is already slow: the worst case
    # goes from 120s to 185s per rollout instead of to six minutes. 90s clears the
    # 56s a cold start took when it was measured, so a legitimate slow answer is
    # not cut off. The failure this actually protects against is queueing, not an
    # outage: four runs put 32 near-simultaneous requests on one a100.
    ATTEMPTS = 3
    BACKOFF_S = 5.0

    def __init__(self, url: str, timeout: float = 90.0):
        self._url = url.rstrip("/") + "/score"
        self._timeout = timeout

    async def score(self, png: bytes) -> QualityReport:
        """Mark one painting.

        Args:
            png (`bytes`):
                The painting to mark.

        Returns:
            [`QualityReport`]: The mark, or an unavailable report when the service
                could not answer. `mark` carries HPSv3's raw `mu` rounded, which is
                unbounded and often negative, so it is for reading and not for
                arithmetic.
        """
        import base64

        import aiohttp

        payload = {
            "png_base64": base64.b64encode(png).decode(),
            # Measured over thirty images per rung. Naming the flower costs half the metric:
            # "a hibiscus painted in loose watercolour" spans +4.76 from a blank canvas to a
            # painting and inverts the first step, scoring a few marks (-10.11) below an empty
            # canvas (-9.98). It asks for a likeness no painting of the policy reaches yet, so
            # it flattens the range the policy has to climb. This one spans +9.04 and keeps the
            # rungs in order, and it is the string every measurement in the project was taken
            # with, so the pool scores and these stay comparable.
            "prompt": "a loose watercolour flower",
        }
        import asyncio

        body = None
        for intento in range(self.ATTEMPTS):
            try:
                timeout = aiohttp.ClientTimeout(total=self._timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self._url, json=payload) as response:
                        body = await response.json()
                if body.get("available"):
                    break
            except Exception as exc:
                print(
                    f"HPSv3 attempt {intento + 1}/{self.ATTEMPTS} failed: "
                    f"{type(exc).__name__}",
                    flush=True,
                )
                body = None
            if intento < self.ATTEMPTS - 1:
                await asyncio.sleep(self.BACKOFF_S)
        # Same contract as the pairwise judge: a scorer that cannot answer leaves
        # the term unscored rather than failing the episode, and `available`
        # carries that out so a zero is never read as a verdict. Said out loud,
        # because deducing this rate from the rewards took an afternoon.
        if body is None or not body.get("available"):
            print("HPSv3 unavailable after all attempts, term left unscored", flush=True)
            return QualityReport()
        return QualityReport(
            score=float(body["score"]),
            mark=int(round(body.get("mu") or 0.0)),
            reason=f"HPSv3 mu {body.get('mu'):+.2f} sigma {body.get('sigma')}",
            available=True,
        )
