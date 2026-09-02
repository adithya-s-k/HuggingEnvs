# SPDX-License-Identifier: BSD-3-Clause

"""Data models for the watercolour environment.

An episode is a single exchange: the environment names a subject, the model
replies with a sketch, and the environment paints it and judges it. There is no
multi-turn state to carry, so the observation is designed to be a complete
record of why a submission scored what it did.
"""

from __future__ import annotations

from typing import Any

from openenv.core.env_server import Action, Observation, State
from pydantic import Field


class WatercolourAction(Action):
    """A submitted sketch.

    Attributes:
        response (`str`):
            The model's raw reply. The environment extracts the JavaScript from
            it, so a fenced code block or surrounding prose is fine. Handing
            over the unedited reply rather than a pre-cleaned sketch keeps
            extraction failures visible in the score instead of hidden in the
            harness.
    """

    response: str


class WatercolourObservation(Observation):
    """The task, or the verdict on an attempt at it.

    Attributes:
        prompt (`str`):
            The painting instruction. Populated on reset.
        system_prompt (`str`):
            The p5.brush API reference to send as a system message. Without it
            no model tested up to 30B emitted a single real `brush.*` call, so
            the environment hands it over rather than leaving every harness to
            rediscover that.
        task_id (`str`):
            Identifier of the sampled task.
        subject (`str`):
            What was asked for.
        feedback (`str`):
            Short explanation of the score, safe to show to the model.
        gate_passed (`bool`):
            Whether the submission painted with the library.
        length_score (`float`):
            One if the sketch's length is in the accepted band, zero otherwise.
            Close to constant with a small model; see the note in
            [`~envs.watercolour_env.server.scoring`].
        judge_score (`float`):
            How the painting placed against the sampled references, in [0, 1].
            One means it beat every reference in both presentation orders.
        quality_score (`float`):
            The painting's absolute mark, judged on its own, in [0, 1]. Fills
            the slot HPSv3 holds in the write-up's rubric.
        render_unavailable (`bool`):
            The browser produced no canvas and reported no error, which is a
            failure of the renderer rather than of the sketch. A harness should
            treat it like an unanswered scorer, not like a rejection.
        judge_weight (`float`):
            What the pairwise term is worth in this run's reward. Zero means a
            missing judge verdict costs the reward nothing, so discarding the
            rollout over it would throw away a painting for free.
        quality_scored (`bool`):
            Whether an absolute mark was actually obtained. Same distinction
            `judged` makes, for the same reason.
        judged (`bool`):
            Whether a judge verdict was actually obtained. Distinguishes "the
            painting scored zero" from "nobody looked at it".
        paint_fraction (`float`):
            Share of the canvas the sketch painted.
        finished (`bool`):
            Whether the sketch stopped itself before the render deadline.
            `False` means it threw inside `draw()` and was scored on whatever
            it had painted by then.
        violations (`list[str]`):
            Gate violation codes, empty when the gate passed.
        js_errors (`list[str]`):
            JavaScript errors the sketch raised while painting.
        breakdown (`dict[str, Any]`):
            The full per-layer analysis, for debugging and for leaderboards.
        image_png_base64 (`str` or `None`):
            The painting, included only when the environment is configured to
            return it.
    """

    prompt: str = ""
    system_prompt: str = ""
    task_id: str = ""
    subject: str = ""
    feedback: str = ""
    gate_passed: bool = False
    length_score: float = 0.0
    judge_score: float = 0.0
    judged: bool = False
    quality_score: float = 0.0
    quality_scored: bool = False
    render_unavailable: bool = False
    judge_weight: float = 0.0
    paint_fraction: float = 0.0
    finished: bool = False
    violations: list[str] = Field(default_factory=list)
    js_errors: list[str] = Field(default_factory=list)
    breakdown: dict[str, Any] = Field(default_factory=dict)
    critique: str = ""
    revisions_left: int = 0
    image_png_base64: str | None = None


class WatercolourState(State):
    """Internal state of an episode.

    Attributes:
        task_id (`str`):
            The task sampled for this episode.
        submitted (`bool`):
            Whether the single allowed submission has been made.
    """

    task_id: str = ""
    submitted: bool = False
    revisions_used: int = 0
