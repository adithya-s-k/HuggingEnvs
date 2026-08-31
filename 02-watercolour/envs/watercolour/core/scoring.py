# SPDX-License-Identifier: BSD-3-Clause

"""Run the layers over one submission and assemble the verdict.

The weights follow the rubric Narreddi's write-up converged on after the first
one, which had nine signals, plateaued: a binary compile-and-uses-brush gate at
0.05, a binary length check at 0.05, HPSv3 at 0.30, and the pairwise judge at
0.60.

Two deliberate differences from that, both of which change what the numbers mean.

**HPSv3's slot is filled by an absolute mark from the judge model.** HPSv3 is a
7B preference model trained on 1.17M human comparisons, and it carries 0.30 of
their reward. Its *role* is what matters: it scores a painting on its own rather
than against a reference, so a policy has something to climb before it can beat
anything in the pool. Leaving that slot empty cost the first four runs, and
filling it with a coverage term cost the next few: coverage knows how much paint
landed and nothing about whether the painting is any good, so once the policy
painted a plausible amount the term went flat while the pairwise judge sat at
exactly zero for twenty-four rollouts in a row. See
[`~envs.watercolour_env.server.quality`] for the replacement and for the measured
proof that it grades where the comparison had given up.

**The gate stays absolute for the dishonest cases.** Awarding 0.05 for compiling
is their structure and it is worth keeping, because it is the only term a policy
can earn on day one and so the only source of reward variance before the judge
engages. But a sketch that loaded somebody else's painting or wrote the answer as
text scores zero outright rather than collecting the compile credit.

The gate runs first and is free. Only what clears it reaches the judge, and the
render is carried across so the painting is produced exactly once per episode.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from .gate import GateResult, run_gate
from .pairwise_judge import JudgeReport, PairwiseJudge
from .quality import QualityReport, QualityScorer
from .render import SketchRenderer
from .tasks import Task


# Defaults are the write-up's final rubric, kept exactly. They are read from the
# environment because the split between the pairwise judge and the preference model
# is the one thing worth varying: three runs of this environment differ only in
# these four numbers, and hard-coding them meant a forked copy of the whole server
# per combination.
GATE_WEIGHT = float(os.environ.get("WATERCOLOUR_GATE_WEIGHT", 0.05))
LENGTH_WEIGHT = float(os.environ.get("WATERCOLOUR_LENGTH_WEIGHT", 0.05))
JUDGE_WEIGHT = float(os.environ.get("WATERCOLOUR_JUDGE_WEIGHT", 0.60))
# The slot HPSv3 holds in their rubric, at their weight. See
# [`~envs.watercolour_env.server.quality`] for why an absolute mark from the judge
# model stands in for the preference model itself, and for the numbers that say the
# stand-in discriminates where the pairwise term had stopped.
QUALITY_WEIGHT = float(os.environ.get("WATERCOLOUR_QUALITY_WEIGHT", 0.30))

# A ramp, not a band, and the change is deliberate. Their write-up describes "a
# code length ramp targeting around 3,000 tokens" and sketches that "compressed
# from 13,500 tokens to under 2,000", so elaboration is something their reward
# pulls towards. The band this replaces returned one for anything between 150 and
# 1200 tokens, and measured output sits inside it: a 4B writes 570 to 1256 tokens
# and a VLM 700 to 1300. A term that is one for every rollout contributes nothing
# to a GRPO group, so the only signal about elaboration in the whole rubric was
# doing no work.
#
# Below the floor a sketch is degenerate and scores zero. From there it climbs to
# full credit at the target, so writing more elaborate code always pays a little.
# Past the runaway cap it scores zero again: their 13,500-token sketches were a
# problem to be compressed, not a goal.
MIN_LENGTH_TOKENS = 150
TARGET_LENGTH_TOKENS = 3000
RUNAWAY_LENGTH_TOKENS = 6000


def length_score(source: str) -> float:
    """Return how close a sketch's length is to the target elaboration.

    Args:
        source (`str`):
            The extracted sketch source.

    Returns:
        `float`: Zero below the floor and above the runaway cap, climbing
            linearly to one at the target in between.

    Examples:

    ```python
    >>> length_score("x" * 4 * 600)  # what a 4B writes today
    0.16
    >>> length_score("x" * 4 * 3000)  # the target
    1.0
    ```
    """
    tokens = len(source) / 4
    if tokens < MIN_LENGTH_TOKENS or tokens > RUNAWAY_LENGTH_TOKENS:
        return 0.0
    if tokens >= TARGET_LENGTH_TOKENS:
        return 1.0
    return (tokens - MIN_LENGTH_TOKENS) / (TARGET_LENGTH_TOKENS - MIN_LENGTH_TOKENS)


@dataclass(frozen=True)
class Evaluation:
    """Everything known about one submission.

    Attributes:
        task ([`Task`]):
            The request the submission was answering.
        gate ([`GateResult`]):
            Verdict of the admission check.
        judge ([`JudgeReport`] or `None`):
            The comparative verdict, `None` when the gate rejected the
            submission or no judge was configured.
        judge_enabled (`bool`):
            Whether a judge was configured for this run, regardless of whether
            it managed to answer.
        quality ([`QualityReport`], *optional*):
            The absolute mark, `None` when the gate rejected the submission or
            no scorer was configured.
    """

    task: Task
    gate: GateResult
    judge: JudgeReport | None = None
    judge_enabled: bool = False
    quality: QualityReport | None = None

    @property
    def gate_passed(self) -> bool:
        """`bool`: Whether the submission cleared the admission check."""
        return self.gate.passed

    @property
    def judge_score(self) -> float:
        """`float`: The comparative score, zero when nothing was judged."""
        return self.judge.score if self.judge is not None else 0.0

    @property
    def render_unavailable(self) -> bool:
        """`bool`: Whether the browser failed rather than the sketch."""
        return self.gate.render_unavailable

    @property
    def judged(self) -> bool:
        """`bool`: Whether a judge verdict was actually obtained."""
        return self.judge is not None and self.judge.available

    @property
    def quality_score(self) -> float:
        """`float`: The absolute mark in [0, 1], zero when nothing was marked."""
        return self.quality.score if self.quality is not None else 0.0

    @property
    def quality_scored(self) -> bool:
        """`bool`: Whether an absolute mark was actually obtained."""
        return self.quality is not None and self.quality.available

    @property
    def length_score(self) -> float:
        """`float`: One if the sketch's length is in the accepted band."""
        if self.gate.source is None:
            return 0.0
        return length_score(self.gate.source.source)

    @property
    def reward(self) -> float:
        """`float`: The episode reward.

        A weighted sum of the components that survive, and the components are
        what matter more than the total. Clearing the gate is worth 0.05 on its
        own, which is the only thing a policy can earn before it paints well
        enough to beat anything, and therefore the only reward variance a GRPO
        group has on day one.

        Failing the gate scores zero outright. A submission that loaded someone
        else's painting or wrote the answer in words does not collect the
        compile credit, and one that did not render has no painting to judge.

        Without a judge configured only the free components count, which is a
        thin signal useful for shaking out a run without spending on vision
        calls and not something to train against.
        """
        if not self.gate.passed:
            return 0.0
        total = GATE_WEIGHT + LENGTH_WEIGHT * self.length_score
        total += QUALITY_WEIGHT * self.quality_score
        if self.judge_enabled:
            total += JUDGE_WEIGHT * self.judge_score
        return total

    @property
    def critique(self) -> str:
        """`str`: What may be shown to the policy between revisions.

        Deliberately narrower than [`feedback`], which exists for a person reading
        a log and says how many references the painting beat and what it scored.
        Handing that to the policy would teach it to optimise against the specific
        references it was drawn, not to paint: with a shared seed the whole group
        faces the same eight, so naming the outcome names the opponents. The
        reference paintings and the score are the answer key.

        What is left is the submission's own properties, which it could have
        measured itself if it had eyes: whether it was admitted, why not, and how
        much of the canvas it covered.
        """
        if not self.gate.passed:
            return "rejected: " + ", ".join(self.gate.violations)
        render = self.gate.render
        painted = render.paint_fraction if render else 0.0
        return (
            f"admitted. {painted:.1%} of the canvas carries pigment; the reference "
            f"paintings run from 12% to 25%."
        )

    @property
    def feedback(self) -> str:
        """`str`: A short explanation of the score, safe to show the model."""
        if not self.gate.passed:
            return "rejected: " + ", ".join(self.gate.violations)
        if not self.judge_enabled:
            return "painted, no judge configured"
        if not self.judged:
            return "painted, judge unavailable"
        # Counts only comparisons the judge actually resolved. Reporting a
        # loss for a reference nobody managed to look at reads as a verdict
        # when it is a failed call.
        resolved = [
            c
            for c in self.judge.comparisons
            if c.score is not None
            and (c.submission_first is not None or c.reference_first is not None)
        ]
        won = sum(1 for c in resolved if c.score == 1.0)
        return (
            f"painted, beat {won} of {len(resolved)} references"
            f" (judge {self.judge_score:.2f}, quality {self.quality_score:.2f},"
            f" reward {self.reward:.2f})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the full per-layer analysis."""
        return {
            "task_id": self.task.task_id,
            "reward": self.reward,
            "components": {
                "gate": GATE_WEIGHT if self.gate.passed else 0.0,
                "length": LENGTH_WEIGHT * self.length_score,
                "quality": QUALITY_WEIGHT * self.quality_score,
                "judge": JUDGE_WEIGHT * self.judge_score if self.judge_enabled else 0.0,
            },
            "gate": self.gate.to_dict(),
            "judge": self.judge.to_dict() if self.judge else None,
            "judge_enabled": self.judge_enabled,
            "judge_weight": JUDGE_WEIGHT if self.judge_enabled else 0.0,
        }


async def evaluate_submission(
    response: str,
    task: Task,
    renderer: SketchRenderer,
    judge: PairwiseJudge | None,
    seed: int | None = None,
    references: int | None = None,
    scorer: QualityScorer | None = None,
) -> Evaluation:
    """Score one submission.

    Args:
        response (`str`):
            The model's raw reply.
        task ([`Task`]):
            The request it was answering.
        renderer ([`SketchRenderer`]):
            The browser to render with.
        judge ([`PairwiseJudge`], *optional*):
            The comparative scorer. `None` scores on gate admission alone.
        seed (`int`, *optional*):
            Makes the sampled references reproducible.
        references (`int`, *optional*):
            Override how many references to judge against. Defaults to the
            judge's own setting.
        scorer ([`QualityScorer`], *optional*):
            The absolute scorer. `None` leaves that term of the reward at zero.

    Returns:
        [`Evaluation`]: The assembled verdict.

    Examples:

    ```python
    evaluation = await evaluate_submission(reply, task, renderer, judge)
    print(evaluation.reward, evaluation.feedback)
    ```
    """
    gate = await run_gate(response, renderer)
    if not gate.passed:
        return Evaluation(task=task, gate=gate, judge_enabled=judge is not None)
    # Both vision terms look at the same painting, so they go out together rather
    # than one after the other. The absolute mark is one call against the pairwise
    # judge's two per reference, so it adds nothing to the wall clock.
    coroutines = []
    if judge is not None:
        coroutines.append(judge.score(gate.png, seed=seed, references=references))
    if scorer is not None:
        coroutines.append(scorer.score(gate.png))
    results = list(await asyncio.gather(*coroutines)) if coroutines else []
    report = results.pop(0) if judge is not None else None
    mark = results.pop(0) if scorer is not None else None
    return Evaluation(
        task=task,
        gate=gate,
        judge=report,
        judge_enabled=judge is not None,
        quality=mark,
    )
