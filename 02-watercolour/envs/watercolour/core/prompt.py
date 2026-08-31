# SPDX-License-Identifier: BSD-3-Clause

"""The system prompt handed to the model, and why it is an allowlist.

The obvious thing to put here is a full API reference, and it is the wrong
thing. Narreddi's write-up reports that a 400-line p5.brush reference produced
"confident, well-formatted code that invented APIs that did not exist", and that
optimising the prompt with GEPA over 200 iterations converged on the opposite: a
strict allowlist, no API documentation, no examples. Their generalisation is that
long reference documentation makes models hallucinate APIs, while a short
opinionated allowlist constrains output better than the spec does.

The measurements taken here before adopting that are consistent with it. With a
full 25-method reference in context a 4B model emitted ten to thirteen real
`brush.*` calls and no bare p5 primitives, which looked like a success, and then
three of four sketches died at runtime on API misuse: an invented `brush.noLoop`,
a painting call before any `brush.set`, and the method name `wash` passed as a
brush name. A long list of plausible neighbours is an invitation to complete the
family.

The *contents* of the list went through two designs, and the second is the one in
force. The first derived nineteen methods from the union of the three sketches
Narreddi published, on the reasoning that their trained model demonstrably uses
nineteen while the write-up says eight. That was the right list for the wrong
question: it copied what their finished model reaches for, not what makes an
allowlist work.

Classifying twenty-one JavaScript errors from two training runs said what the
difference is. Ten of them are invented brush and field names: `"pencil"` three
times where the list says `cpencil`, `"CPencil"` twice, `"waves"` and `"hand"`
passed to `brush.set` although they are field names sitting in the list below it,
`" HB"` with a leading space, and a colour hex where a brush name goes. Four
attempts to fix that by editing the prompt all lost to the prompt they were
replacing, because they all made the documentation clearer instead of removing the
need for it.

So the list is now ten methods and **none of them takes a string**. `brush.set`,
`brush.field` and `brush.hatchStyle` are gone, and with them every way to write a
name that does not exist. Their eight works the same way: their allowlist has no
`brush.set` either, so their model never has to produce the string `cpencil`.
Restricting the API is not the same move as shortening its documentation.

Two things this costs, both measured and neither hidden.

Hatching is gone. `brush.hatchStyle` takes a brush name and `brush.hatch` alone
throws "No brush or color set", so the string-free list cannot hatch at all, and
frames from the video show dense hatching carrying half the visual language of
the finished paintings. Stroked lines go the same way: a stem is now a long
narrow filled shape rather than a `brush.line`.

What it buys, over 297 generations with the list only advised here and not
enforced by the gate: one sketch strayed off the list, and no generation produced
a name error of any kind.

And the skeleton was wrong in three ways at once. Their sketches call
`angleMode(DEGREES)`, they `translate(-width / 2, -height / 2)` so coordinates run
0 to 600 from the top left rather than -300 to 300 from the centre, and they call
`noLoop()` inside `setup` rather than at the end of `draw`. A model told a
different convention reasons about space in a different frame than the one its
reward was built on.

Adopting their translate needed a second sentence, and finding out cost five blank
canvases out of five. A 4B copies the `translate` from the skeleton and then paints
at negative coordinates anyway, because centred coordinates are what a p5 sketch
usually uses: it holds both conventions at once and everything lands off canvas.
Their trained model learned the convention; an untrained one has to be told where
the centre is and that negatives paint nothing.

The composition guidance describes the **reference pool**, not the trained model's
output, and conflating those two cost two wrong prompts in a row.

Frames from the video Narreddi posted show elaborate full-canvas compositions,
median coverage around 0.3 with several above 0.8, fourteen of thirty-eight on a
dark ground. Reasoning from those, the prompt asked for a full canvas and blessed
dark grounds, and candidates came back four dark out of five. But the video shows
what the *finished policy* paints. The reward points at the reference pool, and
the pool is a different thing entirely.

The pool image in the write-up, cropped and measured, settles it. The love tier is
117 tiles, which matches their stated count exactly, and every one is a single
hibiscus centred on pale cream paper in soft translucent warm washes, most with
green leaves and a stem. No dark grounds. No edge-to-edge compositions. Coverage
runs 0.043 to 0.656 with a median of 0.222, against a median of 0.052 for
candidates generated here, so the flower does need to be bigger and the pigment
heavier. As a bigger flower on paper, not as a filled canvas.

The opacity and reach numbers come from hand-iterating one reference through five
renders and watching each: coverage went 0.070, 0.149, 0.177, 0.196, 0.225,
landing on their median. Opacity and bleed did most of that. "Soft translucent
washes" gets a model to opacity 40 and an empty-looking canvas; "180 to 230" gets
paint.

The shape count came from reading the failures instead of the successes. Of 53
generated candidates only about five were usable, and the largest failing group
was not what it looked like: a dozen came out as green line drawings of a plant,
and they were **not** drawing outlines. They used `beginShape`/`vertex`/`fill` at
opacity 100 to 200, the same calls as the good ones. The difference was that they
drew about fourteen small filled shapes each while the usable ones drew about five
big ones. Many small shapes is a diagram; few large ones is a painting. That is
why the count is stated as a ceiling.

Five more craft findings came out of that iteration and are deliberately **not**
here: build each petal from eight vertices at alternating radii, run the second
glaze along the petal rather than pooling it centrally, put damp blooms on the
petals rather than one wide circle behind them, draw the stem as a filled taper
because a line has no body, and keep the staminal column short enough to stay
inside the flower. All five are real, and all five made a 4B worse. Added to the
prompt they raised coverage from 0.027 to 0.479 while the paintings became large
off-centre blobs and blank canvases, which is what happens when advice a model
cannot execute lengthens the prompt it has to follow. They belong in the notes for
authoring references by hand, where they were measured, not in the instruction a
small policy is trying to obey.

Without any prompt at all, no model tested up to 30B emitted a single real
`brush.*` call, falling back to bare p5 primitives that the gate rejects. The
point is that the constraint is what helps, not the documentation.
"""

from __future__ import annotations

# The nineteen methods that appear across the three sketches Narreddi published
# from the trained model. Every signature below is copied from their call sites
# rather than inferred, and every method is checked against the vendored p5.brush
# 2.2.1 export table, so all of them exist in the build that will run.
#
# Nineteen rather than the eight the write-up mentions, because their own model
# demonstrably uses nineteen and their tweet says the write-up is out of date. A
# closed list of nineteen one-line signatures is still the thing their finding was
# about: it says nothing else exists, which a 400-line reference with prose and
# examples does not.
_PREAMBLE = """You paint watercolours by writing a p5.js 2.x sketch that uses the p5.brush library, available as the global `brush`.

Use exactly this skeleton:

  async function setup() {
    createCanvas(600, 600, WEBGL);
    brush.scaleBrushes(3);
    angleMode(DEGREES);
    noLoop();
  }

  function draw() {
    translate(-width / 2, -height / 2);
    background(hex);
    // painting goes here
  }

So: angles are in degrees, and after the translate the canvas runs from 0 to 600 on both axes with the origin at the top LEFT, not the centre. The centre of the canvas is (300, 300). Every coordinate you paint at must be between 0 and 600: a negative coordinate is off the canvas and paints nothing at all. Colours are hex strings like "#e08a72".

%%COMPOSITION%%

These ten brush methods exist. Nothing else on `brush` exists, and there is no way to
name or select a brush: everything is painted as a filled shape. Do not call any other brush
method, and never use the bare p5 drawing functions such as ellipse, rect, vertex or beginShape:
  brush.scaleBrushes(factor)
  brush.noStroke()
  brush.fill(colorHex, opacity)
  brush.noFill()
  brush.fillBleed(amount)
  brush.fillTexture(amount, borderIntensity)
  brush.beginShape(curvature)
  brush.vertex(x, y)
  brush.endShape(true)
  brush.circle(x, y, radius, scribble)

colorHex is a string like "#e08a72". opacity runs 0 to 255. amount, curvature,
borderIntensity and scribble run 0 to 1.

Every mark is a filled shape. Build petals and leaves with brush.beginShape, a run of at least
three brush.vertex calls, then brush.endShape(true), and call brush.fill before each one. A stem
is a long narrow filled shape, not a line. brush.circle fills a disc.
"""

# What the pre-allowlist prompt listed, and what the published sketches use, for
# anyone who wants the numbers without re-deriving them.
FULL_REFERENCE_METHODS = 25
PUBLISHED_SKETCH_METHODS_ALL_THREE = 11
PUBLISHED_SKETCH_METHODS_UNION = 19
ALLOWLIST_METHODS = 12
# The v2 block names ten methods and none of them takes a string, so the family of
# invented brush and field names cannot be written. Measured over 297 generations with
# the list only advised in the prompt and not enforced by the gate: one sketch strayed.
RESTRICTED_METHODS = 10


def system_prompt(domain=None) -> str:
    """Return the system prompt for a painting episode.

    The allowlist and the structural rules are shared: they are about p5.brush
    and about this renderer, not about what is being painted. Only the
    composition guidance comes from the domain.

    Args:
        domain ([`~envs.watercolour_env.server.domains.Domain`], *optional*):
            Which subject to describe. Defaults to the hibiscus task, so a
            caller that asks for nothing gets exactly what it got before this
            was parameterised.

    Returns:
        `str`: The prompt, ready to be sent as a system message.

    Examples:

    ```python
    from .domains import get_domain

    messages = [{"role": "system", "content": system_prompt(get_domain())}]
    ```
    """
    if domain is None:
        from .domains import get_domain

        domain = get_domain()
    # `replace`, not `format`: the preamble contains the JS skeleton, and its
    # braces make `str.format` try to substitute `createCanvas(600, 600, WEBGL)`.
    return _PREAMBLE.replace("%%COMPOSITION%%", domain.composition)


def hibiscus_prompt() -> str:
    """Return the hibiscus prompt, which is what `system_prompt()` defaults to.

    Exists so callers that want the concrete text rather than the template have a
    name for it. An earlier version left `ALLOWLIST = None` behind after
    parameterising, which hands anything that imported it a silent `None`.
    """
    return system_prompt()
