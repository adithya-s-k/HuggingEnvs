# SPDX-License-Identifier: BSD-3-Clause

"""Read a model's reply as sketch source and take inventory of it.

Everything here is textual and cheap. It runs before the browser does, so a
submission that was never going to paint anything is rejected without paying
for a render, and the shortcuts a model reaches for are visible in the source
long before they are visible in the picture.

The two API lists come from the export table of the vendored p5.brush bundle
rather than from the docs, so they describe the build that will actually run.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

# Calls that put paint on the canvas. A sketch that never makes one of these
# cannot have painted anything, whatever else it did.
PAINTING_CALLS = frozenset(
    {
        "arc",
        "box",
        "circle",
        "endShape",
        "endStroke",
        "flowLine",
        "hatch",
        "hatchArray",
        "line",
        "polygon",
        "rect",
        "spline",
        "wash",
    }
)

# The rest of the public surface: state, configuration and geometry helpers.
SUPPORTING_CALLS = frozenset(
    {
        "add",
        "addField",
        "beginShape",
        "beginStroke",
        "clip",
        "field",
        "fill",
        "fillBleed",
        "fillTexture",
        "hatchStyle",
        "instance",
        "listFields",
        "load",
        "mass",
        "massArray",
        "move",
        "noClip",
        "noField",
        "noFill",
        "noHatch",
        "noMass",
        "noStroke",
        "noWash",
        "noiseSeed",
        "pick",
        "refreshField",
        "scaleBrushes",
        "seed",
        "set",
        "stroke",
        "strokeWeight",
        "vertex",
        "wRand",
        "wiggle",
    }
)

KNOWN_CALLS = PAINTING_CALLS | SUPPORTING_CALLS

# Bare p5 drawing primitives. Using these is how a model paints without
# p5.brush, which produces a picture that scores on composition while dodging
# the medium entirely. Matched only when not preceded by a dot, so
# `brush.rect(...)` does not trip the check on `rect`.
def _strip_comments(source: str) -> str:
    """Return `source` with JavaScript comments blanked out.

    Crude on purpose: a `//` inside a string literal would be removed too. The
    sketches use no URLs and their only strings are hex colours, so the cost is
    nil against the alternative of parsing JavaScript to read a source inventory.
    """
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"//[^\n]*", " ", source)


BARE_PRIMITIVES = (
    "arc",
    "beginShape",
    "bezier",
    "circle",
    "curve",
    "ellipse",
    "line",
    "point",
    "quad",
    "rect",
    "square",
    "triangle",
    "vertex",
)

# Ways a sketch could put someone else's picture on the canvas, or reach off
# the machine at all. The submission is untrusted code with a network stack
# behind it, so this is a security boundary as much as an anti-cheat one.
EXTERNAL_ACCESS = (
    "loadImage",
    "loadBytes",
    "loadJSON",
    "loadStrings",
    "loadTable",
    "loadXML",
    "loadModel",
    "loadFont",
    "loadShader",
    "createImg",
    "createVideo",
    "createCapture",
    "fetch",
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
    "importScripts",
    "createElement",
    "innerHTML",
    "document.write",
    "eval",
    "Function(",
)

_FENCE = re.compile(r"```(?:js|javascript)?\s*(.*?)```", re.DOTALL)
# A definition of `setup` or `draw`, not a mention of one. Testing for the bare
# words matches a refusal like "Sorry, I cannot draw images", which then gets
# rejected for the wrong reason two checks later.
_ENTRY_POINT = re.compile(
    r"\b(?:function\s+(?:setup|draw)\s*\(|(?:setup|draw)\s*=\s*(?:function|\())"
)
_CALL = re.compile(r"\bbrush\s*\.\s*([A-Za-z_$][\w$]*)")
_CREATE_CANVAS = re.compile(r"\bcreateCanvas\s*\(([^)]*)\)")
_TEXT_CALL = re.compile(r"(^|[^.\w])text\s*\(")
_DATA_URI = re.compile(r"data\s*:\s*image/", re.IGNORECASE)


class SourceError(Exception):
    """Raised when the reply holds nothing that could be a sketch."""


@dataclass(frozen=True)
class SourceReport:
    """What the source says about itself.

    Attributes:
        source (`str`):
            The extracted JavaScript.
        painting_calls (`list[str]`):
            Distinct `brush.*` calls used that put paint down.
        supporting_calls (`list[str]`):
            Distinct `brush.*` calls used that configure rather than paint.
        unknown_calls (`list[str]`):
            `brush.*` calls that do not exist in the vendored build. These are
            the sketch's own invention and each one throws at runtime.
        bare_primitives (`list[str]`):
            Bare p5 drawing primitives used, which is drawing without the
            library.
        external_access (`list[str]`):
            Names suggesting the sketch tried to load or reach something.
        has_setup (`bool`):
            Whether a `setup` function is defined.
        has_draw (`bool`):
            Whether a `draw` function is defined.
        webgl (`bool`):
            Whether `createCanvas` asked for a WEBGL context, which p5.brush
            requires.
        calls_no_loop (`bool`):
            Whether the sketch stops itself. Sketches that do not are scored on
            whatever they painted before the render deadline.
        writes_text (`bool`):
            Whether the sketch calls `text`, which is how a drawing task gets
            answered in words instead of paint.
        balanced (`bool`):
            Whether braces balance. Unbalanced means the reply was cut off.
    """

    source: str
    painting_calls: list[str] = field(default_factory=list)
    supporting_calls: list[str] = field(default_factory=list)
    unknown_calls: list[str] = field(default_factory=list)
    bare_primitives: list[str] = field(default_factory=list)
    external_access: list[str] = field(default_factory=list)
    has_setup: bool = False
    has_draw: bool = False
    webgl: bool = False
    calls_no_loop: bool = False
    writes_text: bool = False
    balanced: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable view, without the source itself."""
        data = asdict(self)
        data.pop("source")
        return data


def extract_sketch(response: str) -> str:
    """Pull JavaScript out of a model reply.

    Args:
        response (`str`):
            The raw reply, with or without a fenced code block.

    Returns:
        `str`: The sketch source.

    Raises:
        SourceError: If nothing in the reply defines `setup` or `draw`. A reply
            that only mentions them, such as a refusal to draw, counts as
            nothing.

    Examples:

    ```python
    source = extract_sketch("```js\\nfunction setup(){}\\n```")
    ```
    """
    match = _FENCE.search(response)
    source = (match.group(1) if match else response).strip()
    if not _ENTRY_POINT.search(source):
        raise SourceError("no sketch in response")
    return source


def inspect_source(source: str) -> SourceReport:
    """Take inventory of a sketch without running it.

    Args:
        source (`str`):
            The sketch source.

    Returns:
        [`SourceReport`]: The inventory.

    Examples:

    ```python
    report = inspect_source(extract_sketch(reply))
    print(report.painting_calls, report.bare_primitives)
    ```
    """
    # Every check below reads code, so comments come out first. They were not
    # stripped, and the primitive check allows whitespace before the paren, so
    # ordinary English prose in a comment counted as a call: `// the center point
    # (300, 300)` matched `point (`, and `// Outer curve (bulging out)` matched
    # `curve (`. Measured on the twelve-sample probe of a 35B, that rejected four
    # rollouts out of twelve, a third of them, purely for being commented. The
    # bigger the model the more it comments, so the penalty grew with capability.
    # All four pass once comments are gone, and none of the eight that passed
    # starts failing.
    code = _strip_comments(source)
    used = set(_CALL.findall(code))
    canvas = _CREATE_CANVAS.search(code)
    bare = [
        name
        for name in BARE_PRIMITIVES
        if re.search(rf"(^|[^.\w]){name}\s*\(", code, re.MULTILINE)
    ]
    external = [name for name in EXTERNAL_ACCESS if name in code]
    if _DATA_URI.search(code):
        external.append("data_uri_image")
    return SourceReport(
        source=source,
        painting_calls=sorted(used & PAINTING_CALLS),
        supporting_calls=sorted(used & SUPPORTING_CALLS),
        unknown_calls=sorted(used - KNOWN_CALLS),
        bare_primitives=bare,
        external_access=external,
        has_setup=bool(
            re.search(r"function\s+setup\s*\(|setup\s*=\s*(?:function|\()", source)
        ),
        has_draw=bool(
            re.search(r"function\s+draw\s*\(|draw\s*=\s*(?:function|\()", source)
        ),
        webgl=bool(canvas and "WEBGL" in canvas.group(1)),
        calls_no_loop="noLoop" in source,
        writes_text=bool(_TEXT_CALL.search(source)),
        balanced=source.count("{") == source.count("}"),
    )
