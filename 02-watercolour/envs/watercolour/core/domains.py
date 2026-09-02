# SPDX-License-Identifier: BSD-3-Clause

"""What changes between one painting subject and another.

The medium is the constant here and the subject is not, and it took building a
second one to see where the line actually falls. Everything about running
untrusted p5.brush in a browser, admitting or rejecting a sketch, and asking a
judge which of two paintings is better, is the same whether the subject is a
flower or a jellyfish. Four things are not:

1. What to paint.
2. How to compose it, including the numbers that make paint land.
3. **What the judge is told to value.** This is the one that hides. The judge is
   told to ignore what a painting depicts, which makes it look subject-agnostic,
   and it is. What it is not is *medium*-agnostic, and within watercolour it is
   not even subject-agnostic in practice: "layered translucent washes" is the
   right question for a jellyfish and a strange one for dense hatching.
4. The reference pool.

Two implementations is when collecting these stops being speculative. With one it
would have been an abstraction with a single user, which is why the earlier note
in the README said to wait for a second subject before writing this file.

`HIBISCUS` reproduces Narreddi's task and is the default, so nothing changes for
anything that does not ask for another domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pool import pool_dir


@dataclass(frozen=True)
class Domain:
    """One painting subject, and everything that changes with it.

    Attributes:
        name (`str`):
            Identifier, used to select the domain and to name its pool.
        subjects (`tuple[str, ...]`):
            What can be asked for. The first is the default.
        composition (`str`):
            The part of the system prompt describing what to paint and how,
            including the numeric paint-handling guidance. Everything generic
            about p5.brush lives in the allowlist and is shared.
        judge_criteria (`str`):
            What the judge is asked to weigh, in place of the watercolour
            criteria. Getting this wrong scores a painting against a standard it
            cannot satisfy.
        pool (`Path`):
            Directory of reference paintings.
    """

    name: str
    subjects: tuple[str, ...]
    composition: str
    judge_criteria: str
    pool: Path


HIBISCUS = Domain(
    name="hibiscus",
    subjects=(
        "a peach hibiscus",
        "a white hibiscus with a red eye",
        "a magenta hibiscus",
        "a yellow hibiscus",
        "a coral hibiscus",
    ),
    composition="""Paint one flower, centred, filling most of the frame, on a pale cream or off-white paper ground, in warm pinks, corals, yellows and magentas, with green leaves and a stem. Do not fill the canvas edge to edge, and do not paint on a dark ground.

Three numbers matter more than any adjective:
- Five petals. Paint each petal two or three times over, not once: a first pass at full size, then a smaller and more opaque pass inside it, and a small dark one near the centre. That layering is where a watercolour gets its depth, and it puts the whole painting at fifteen to thirty filled shapes. Keep the petals as five broad lobes, not fifteen separate little marks.
- Petals reaching 200 to 240 units from the centre, so the flower occupies the frame.
- Opacity never below 150, and 180 to 230 on the petals, with brush.fillBleed between 0.2 and 0.3. A dilute wash with a wide bleed disperses until no pigment reaches density and the flower comes out invisible.""",
    # Structure first, medium second, and the order is the whole point. Asked
    # about painterly quality alone the judge prefers a flat washed disc to a
    # small flower with a stem, and it is right to: the disc has more soft bleeds
    # and layered washes. Measured on those two exact paintings, same judge, both
    # presentation orders: medium-only picks the disc, this criteria picks the
    # flower, and both verdicts are order-invariant. Their write-up uses
    # medium-only criteria, which works for a 35B because almost everything it
    # emits already reads as the subject, so the structure gate is passed by
    # default. For a small policy it is not, and omitting it hands the judge a well-painted
    # non-flower with nothing to hold against it.
    # Style only, and the flowerness clause that used to open this is gone on
    # purpose. The template's next line says "Ignore what the paintings depict",
    # which contradicted it and, being last, won. Worse, the duplication was
    # wasteful: HPSv3 already answers the semantic question, and hard. Swapping
    # its prompt from "a loose watercolour flower" to "an abstract green
    # watercolour wash" moved every one of six non-flowers up (+0.62 to +5.67 of
    # mu) and every one of six flowers down (-1.98 to -3.23), twelve out of twelve
    # in the predicted direction. So HPSv3 owns "is it a flower" and this owns
    # "is it well painted", which is the only thing the pairwise judge does better.
    judge_criteria=(
        "Prefer soft pigment bleeds, layered translucent washes that show through "
        "each other, varied edge softness where edges dissolve rather than stop, "
        "and deliberate composition. Muddy opaque blobs, uniform scribbles, hard "
        "flat edges and near-empty canvases are worse."
    ),
    pool=pool_dir(),
)


JELLYFISH = Domain(
    name="jellyfish",
    subjects=(
        "a drifting jellyfish",
        "three jellyfish at different depths",
        "a pale moon jellyfish",
        "a deep violet jellyfish",
    ),
    # Written from five hand-iterated renders. The two structural findings are
    # here as instructions because both cost an iteration to learn: the flow
    # field warps filled shapes, so a symmetric bell comes out lopsided unless
    # the fills are drawn with brush.noField, and flowLine's angle runs
    # 0 right, 90 up, 180 left, 270 down, so tentacles at 90 leave the canvas
    # through the top.
    composition="""Paint a jellyfish drifting in water, on a pale cream or off-white ground, in translucent violets, roses and sea greens. The bell sits in the upper half and the tentacles hang below it.

What makes this read as a jellyfish rather than a mushroom:
- Build the bell from three or four nested domes at decreasing size, each a separate filled shape, so the washes layer and the edges dissolve into each other. A dome is the half of an ellipse above its centre: sweep the angle from 180 to 360.
- Draw the fills with brush.noField. A flow field warps a filled shape, so a bell that is symmetric in coordinates comes out lopsided.
- Tentacles hang with brush.flowLine at angle 270, which is downward: 0 is right, 90 is up, 180 is left. Turn a flow field on for these, because the drift is what makes them read as suspended in water rather than drawn. Vary their length and spacing, or they read as a comb.
- Add three or four frilled oral arms from the bell rim downward, shorter than the tentacles.
- Opacity 120 to 160 on the bell with brush.fillBleed around 0.28. Lower than a flower wants, because a jellyfish is translucent and the layers have to show through each other.
- If you paint more than one, make the far ones paler rather than only smaller, and leave the radial canals off them. In water, distance is paleness.""",
    judge_criteria=(
        "Judge painterly quality only: translucency and layered washes that show "
        "through each other, edges that dissolve rather than stop, tentacles that "
        "drift instead of hanging straight, and a sense of the creature being "
        "suspended in water. Opaque flat bells, stiff parallel tentacles and "
        "near-empty canvases are worse."
    ),
    pool=pool_dir() / "jellyfish",
)


# JELLYFISH is deliberately absent: its plumbing is done and verified, but it has
# no reference pool, and a domain without one cannot be trained on. It is left out
# rather than shipped broken, and rather than given a hand-authored pool, because a
# hand-authored pool is the prime suspect for why the hibiscus runs cannot earn
# judge credit: references written by tuning parameters are not drawn from any
# model's distribution, so they may be an unreachable target by construction. Add
# it back here in one line once it has a pool built the way theirs was.
DOMAINS = {d.name: d for d in (HIBISCUS,)}
DEFAULT_DOMAIN = HIBISCUS.name


def get_domain(name: str | None = None) -> Domain:
    """Return a domain by name, defaulting to the hibiscus task.

    Args:
        name (`str`, *optional*):
            One of the keys of [`DOMAINS`]. Defaults to [`DEFAULT_DOMAIN`].

    Returns:
        [`Domain`]: The selected domain.

    Raises:
        KeyError: If the name is not a known domain.

    Examples:

    ```python
    domain = get_domain("jellyfish")
    print(domain.subjects[0])
    ```
    """
    return DOMAINS[name or DEFAULT_DOMAIN]
