# SPDX-License-Identifier: BSD-3-Clause

"""The admission check a submission has to clear before anyone judges it.

Nothing here is a matter of taste. The gate answers one narrow question: is
this a sketch that used the watercolour library to put paint on a canvas? A
submission that fails scores zero and is never sent to the judge, which is what
keeps a run affordable while a model is still producing garbage.

Two of the checks are about honesty rather than competence. `bare_primitives`
catches painting with plain p5 shapes, which yields a picture that can score on
composition while dodging the medium the task is about. `external_access`
catches loading somebody else's painting, which is the only way to score well
without painting at all.

The paint floor is calibrated against measured renders: real sketches from small models
model covered 2.6% to 5.0% of the canvas, a sketch that errored before painting
covered 0.07%, and an empty canvas covers 0%. The floor sits between them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .render import Render, RenderError, SketchRenderer
from .sketch_source import extract_sketch, inspect_source, SourceError, SourceReport

MIN_PAINT_FRACTION = 0.005

# Painting calls a sketch must make to count as having used the library. One is
# enough: a single wash is a legitimate, if minimal, watercolour.
MIN_PAINTING_CALLS = 1

# Two attempts at the render. See `GateResult.render_unavailable` for the measurement
# that says a failure here is the browser rather than the sketch.
RENDER_ATTEMPTS = 2


@dataclass(frozen=True)
class GateResult:
    """Outcome of the admission check.

    Attributes:
        passed (`bool`):
            Whether the submission cleared every check.
        violations (`list[str]`):
            Reasons for rejection, empty when `passed` is `True`.
        source (`SourceReport` or `None`):
            The source inventory, `None` if no sketch could be extracted.
        render ([`Render`] or `None`):
            The render, `None` if the source was rejected before rendering or
            the sketch produced no canvas.
        render_unavailable (`bool`):
            The browser never produced a canvas and never reported an error.
            That is not the same as a bad sketch, and scoring it zero trains the
            policy away from code that was probably fine: of every `render_failed`
            recorded across eight runs, not one carried a JavaScript error, and all
            of them had already cleared the static checks for entry points and
            WEBGL. 37 of 2432 rollouts (1.5%) took a phantom zero this way, and in
            one run it reached 5.2% of rollouts and 35% of steps.
    """

    passed: bool
    violations: list[str] = field(default_factory=list)
    source: SourceReport | None = None
    render: Render | None = None
    render_unavailable: bool = False

    @property
    def png(self) -> bytes | None:
        """`bytes` or `None`: The painting, when one was produced."""
        return self.render.png if self.render is not None else None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable view of the verdict."""
        return {
            "passed": self.passed,
            "violations": list(self.violations),
            "source": self.source.to_dict() if self.source else None,
            "render": self.render.to_dict() if self.render else None,
            "render_unavailable": self.render_unavailable,
        }


def _source_violations(report: SourceReport) -> list[str]:
    """Return the reasons a source is not worth rendering."""
    violations = []
    if not report.balanced:
        violations.append("truncated")
    # Only `setup` is required. Requiring `draw` too was rejecting paintings
    # that paint perfectly well: a sketch that does all its work in `setup`
    # renders the same picture as the equivalent one split across both, measured
    # at the same paint coverage. Demanding the split flattened the reward for no
    # reason a picture could show.
    if not report.has_setup:
        violations.append("missing_entry_points")
    if not report.webgl:
        violations.append("not_webgl")
    if report.external_access:
        violations.append("external_access")
    if report.writes_text:
        violations.append("text_label")
    if report.bare_primitives:
        violations.append("bare_primitives")
    # A method that is not on `brush` at all throws inside `draw`, the render
    # stops, and what comes back is whatever had been painted first: usually
    # nothing, reported as `blank_canvas`. That misnames the cause, and it cost a
    # day of blaming off-canvas coordinates. Measured on a twelve-sample probe of
    # a 35B, the four lowest-coverage submissions were exactly the four that threw
    # (`brush.lineWidth`, `brush.rotate`, and two undefined variables), and two of
    # them still cleared the gate at 0.7% coverage and were paid for a crash.
    #
    # `unknown_calls` was already computed and never read. It only matches names
    # called on `brush`, so helper functions, `Math.*` and p5 globals are
    # untouched: measured over the 56 reference sources, none is flagged. The
    # twenty-eight real p5.brush methods the prompt does not list are in
    # `KNOWN_CALLS` and still pass, so this rejects only what cannot exist.
    if report.unknown_calls:
        violations.append("unknown_brush_method")
    if len(report.painting_calls) < MIN_PAINTING_CALLS:
        violations.append("no_painting_calls")
    return violations


async def run_gate(response: str, renderer: SketchRenderer) -> GateResult:
    """Check a submission and, if it is worth it, render it.

    Args:
        response (`str`):
            The model's raw reply.
        renderer ([`SketchRenderer`]):
            The browser to render with.

    Returns:
        [`GateResult`]: The verdict, carrying the render so the judge does not
            pay to produce it again.

    Examples:

    ```python
    result = await run_gate(reply, renderer)
    if result.passed:
        print(result.render.paint_fraction)
    ```
    """
    try:
        source = extract_sketch(response)
    except SourceError:
        return GateResult(passed=False, violations=["no_sketch_in_response"])

    report = inspect_source(source)
    violations = _source_violations(report)
    if violations:
        return GateResult(passed=False, violations=violations, source=report)

    # Retried for the reason given on `render_unavailable`, and the retry is what
    # separates the two cases: a sketch that genuinely draws nothing fails every
    # time, while a browser that dropped the page usually succeeds on the next one.
    for intento in range(RENDER_ATTEMPTS):
        try:
            render = await renderer.render(source)
            break
        except RenderError:
            print(
                f"render attempt {intento + 1}/{RENDER_ATTEMPTS} produced no canvas",
                flush=True,
            )
            if intento == RENDER_ATTEMPTS - 1:
                return GateResult(
                    passed=False,
                    violations=["render_failed"],
                    source=report,
                    render_unavailable=True,
                )

    if render.paint_fraction < MIN_PAINT_FRACTION:
        return GateResult(
            passed=False,
            violations=["blank_canvas"],
            source=report,
            render=render,
        )
    return GateResult(passed=True, source=report, render=render)
