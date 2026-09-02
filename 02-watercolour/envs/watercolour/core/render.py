# SPDX-License-Identifier: BSD-3-Clause

"""Run a sketch in a headless browser and bring back the painting.

The submission is arbitrary JavaScript, so it runs in Chromium rather than in
anything that shares a process with the server. p5.brush needs a real WEBGL
context, which in a container means software GL through SwiftShader.

Five things here are load-bearing, and most of them were arrived at by watching
a plausible-looking blank canvas come back:

- p5.brush 2.x requires p5.js 2.x. Against p5 1.x the canvas is created and
  `background()` paints, so the page looks healthy, and every `brush.*` call
  draws nothing at all with no error anywhere.
- A WEBGL canvas loses its back buffer before a page screenshot is taken. The
  pixels have to be read inside the page with `toDataURL()`.
- A sketch that throws inside `draw()` never reaches its own `noLoop()`, so it
  keeps requesting frames forever. Without the deadline below one bad
  submission stalls the episode, and bad submissions are most of them early in
  a run.
- Readiness is polled with explicit `evaluate` calls rather than Playwright's
  `wait_for_function`, whose default requestAnimationFrame polling is throttled
  to a standstill on a backgrounded page. That one reported every render as a
  timeout while the renders were in fact finishing in 250ms.
- The browser owns a private event loop on a background thread, because a
  Playwright browser is bound to the loop that launched it. See
  [`SketchRenderer`].

Render time tracks how much paint is laid down rather than how long the source
is, and then tracks how much CPU there is. A plain sketch from a small model
finishes in 250ms; the reference paintings in `reference_pool/` take 4.8s to 29s
on a laptop, and one of them took 64s on a free-tier Space with two shared
vCPUs. The browser is therefore started once and kept, and each submission gets
a fresh page. Reusing a page across submissions breaks p5's global-mode setup on
the second sketch.
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

CANVAS_SIZE = 600

# Chromium flags that get a WEBGL context out of software rendering. Without
# these p5.brush refuses to initialise and every sketch reports "p5.brush
# requires a WEBGL canvas".
CHROMIUM_ARGS = [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--disable-gpu-sandbox",
    "--no-sandbox",
]

# How long a single sketch gets to finish drawing. Render time scales with how
# much paint is laid down rather than with source length, and it scales again
# with how little CPU there is: the same reference sketch takes 8s on a laptop,
# 16s in a local container, and 64s on a free-tier Space with two shared vCPUs.
# The deadline has to clear that, because a policy learning to paint like the
# references would otherwise be cut off exactly as it starts succeeding.
#
# It is a soft bound, checked between polls. A single `evaluate` can itself block
# for tens of seconds while a heavy render monopolises the page's JavaScript
# thread, so a legitimately slow sketch can and does overshoot. That is the right
# behaviour: the case this deadline exists for is a sketch that loops forever
# without erroring, and those poll fast and get cut off on time. A sketch that
# throws is caught immediately by `_DEAD` instead.
RENDER_DEADLINE_S = 90.0

# How many sketches may paint at once, which is also how many browsers get
# launched, because those turn out to be the same number.
#
# Concurrency has to be spread across browsers rather than across pages inside
# one. Measured on eight rollouts of mixed cost, one browser with eight
# concurrent pages took exactly as long as painting them one after another: pages
# share the browser's GPU process and SwiftShader serialises inside it, so
# concurrent pages contend instead of overlapping.
#
# Across browsers it does help, and less than you would hope: 1 browser 33.1s,
# 2 browsers 32.3s, 4 browsers 18.4s (1.8x), 8 browsers 15.7s (2.1x) on a
# 14-core machine. Software rasterisation is CPU-bound and each instance already
# spreads over several threads, so the curve flattens fast. Four is the knee.
#
# The honest read is that this is not where the scaling comes from. Narreddi
# renders rollouts on Modal, which is horizontal across machines, and that is the
# answer when a rollout costs twenty to two hundred seconds. The pool here keeps a
# single container from serialising a whole GRPO group.
RENDER_POOL_SIZE = max(1, min(4, (os.cpu_count() or 4) - 2))

# Interval between readiness checks. Cheap enough not to matter next to the
# render itself, tight enough not to add much to the measured 250ms.
POLL_INTERVAL_S = 0.04

# Euclidean RGB distance from the modal (background) colour above which a pixel
# counts as paint.
PAINT_DISTANCE_THRESHOLD = 32.0

_VENDOR = Path(__file__).parent / "vendor"

# Readiness keys off `__setupDone`, a flag the page sets by wrapping the sketch's
# own `setup`, rather than off p5's `frameCount`. That is not a stylistic choice:
# p5 only increments `frameCount` from inside `draw`, so a sketch that paints
# everything in `setup` and defines no `draw` sits at `frameCount === 0` forever
# while its finished painting waits on the canvas. Keying off frames meant those
# burned the entire render deadline and then reported themselves unfinished.
#
# Past setup there are two cases. Without a `draw`, setup returning is the whole
# render. With one, wait for a frame *and* for the loop to stop, and the frame
# half is what closes a race: sketches in the shape Narreddi's model writes call
# `noLoop()` inside `setup`, so `isLooping()` is already false the instant setup
# returns and before `draw` has painted anything. Checking only the loop state
# would occasionally capture a blank canvas, which during training reads as a
# random zero reward rather than as a bug.
_DONE = (
    "!!window.__setupDone"
    " && (typeof draw !== 'function'"
    "     || (typeof frameCount !== 'undefined' && frameCount >= 1"
    "         && (typeof isLooping !== 'function' || !isLooping())))"
)

# A sketch that threw after getting through setup is not coming back: whatever it
# painted before dying is what there is to score. A sketch that threw *inside*
# setup is not caught here, because it may still be about to fail to make a
# canvas at all, which `RenderError` covers.
_DEAD = "window.__errors.length > 0 && !!window.__setupDone"

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<script>
// Before p5 and p5.brush load, not after. p5.brush captures its PRNG seeds at
// evaluation time (`let d=m(Math.random()), g=m(Math.random()+":2")`), so an
// override installed in the body runs too late and the same sketch keeps painting
// a different picture. Measured that way on four sketches rendered four times
// each: HPSv3 moved by up to 0.195 of score on identical code, 37% of the
// within-group reward spread for a mid-range painting, which GRPO reads as coming
// from the action.
(function () {{
  let s = ({seed} >>> 0) || 1;
  Math.random = function () {{
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  }};
}})();
</script>
<script>{p5}</script>
<script>{brush}</script>
<style>html,body{{margin:0;background:#fff}}</style>
</head><body><script>
window.__errors = [];
window.__setupDone = false;
window.onerror = (message) => {{ window.__errors.push(String(message)); return true }};
window.addEventListener("unhandledrejection", (e) => window.__errors.push(String(e.reason)));
{sketch}
</script><script>
// Wrapping `setup` needs its own script block, running after the sketch has
// defined it and before p5 calls it. p5's global mode waits for the load event,
// and inline scripts all run before that, so this window is reliable.
if (typeof window.setup === "function") {{
  const original = window.setup;
  window.setup = function () {{
    try {{ original.apply(this, arguments) }}
    finally {{ window.__setupDone = true }}
  }};
}} else {{
  window.__setupDone = true;
}}
</script></body></html>"""


class RenderError(Exception):
    """Raised when a sketch produced no canvas at all."""


@dataclass(frozen=True)
class Render:
    """The outcome of running one sketch.

    Attributes:
        png (`bytes`):
            The painting as PNG data.
        paint_fraction (`float`):
            Share of pixels differing from the background colour.
        finished (`bool`):
            Whether the sketch stopped looping before the deadline. `False`
            means it threw inside `draw()`, and the painting is whatever had
            been laid down by then.
        errors (`list[str]`):
            JavaScript errors the page reported, in order.
        elapsed_ms (`int`):
            Wall-clock time the render took.
    """

    png: bytes
    paint_fraction: float
    finished: bool
    errors: list[str]
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable view, without the image bytes."""
        data = asdict(self)
        data.pop("png")
        return data


def paint_fraction(png_bytes: bytes) -> float:
    """Measure how much of a painting differs from its own background.

    The background is taken as the most common colour after coarse
    quantisation, so a sketch that washes the whole canvas is measured the same
    way as one that leaves it bare.

    Args:
        png_bytes (`bytes`):
            PNG data as produced by [`SketchRenderer.render`].

    Returns:
        `float`: Fraction of painted pixels, in [0, 1].

    Examples:

    ```python
    coverage = paint_fraction(render.png)
    ```
    """
    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
    canvas.alpha_composite(image)
    # float32, not an integer dtype: squared channel differences reach 65025,
    # which overflows int16 and turns dark-on-light pixels into NaN distances
    # that then fail every comparison.
    rgb = np.asarray(canvas.convert("RGB"), dtype=np.float32)
    bins = (rgb.astype(np.uint16) >> 4).astype(np.uint32)
    packed = (bins[..., 0] << 16) | (bins[..., 1] << 8) | bins[..., 2]
    values, counts = np.unique(packed, return_counts=True)
    modal = rgb[packed == values[int(np.argmax(counts))]].mean(axis=0)
    distance = np.sqrt(((rgb - modal) ** 2).sum(axis=-1))
    return float((distance > PAINT_DISTANCE_THRESHOLD).sum() / distance.size)


class SketchRenderer:
    """A pool of headless browsers that turns sketch source into paintings.

    The browser lives on a private event loop in a background thread, and every
    render is dispatched onto it. That indirection is not decoration: a
    Playwright browser is bound to the loop that launched it, and the
    environment's synchronous `step()` wraps `step_async` in its own
    `asyncio.run`, so a second `step()` on the same environment reaches the
    browser from a loop that did not create it and hangs there forever. Owning
    the loop means both the async server path and repeated synchronous calls get
    the same warm browser.

    A pool of browsers is launched on first use and kept for the life of the
    process. Each render takes one from the pool, paints in a fresh page, and
    hands the browser back. Concurrency lives across browsers rather than across
    pages: see [`RENDER_POOL_SIZE`] for the measurements behind that.

    Examples:

    ```python
    renderer = SketchRenderer()
    render = await renderer.render(sketch_source)
    print(render.paint_fraction, render.finished)
    await renderer.close()
    ```
    """

    def __init__(self, pool_size: int = RENDER_POOL_SIZE):
        self._playwright = None
        self._browsers: list = []
        self._pool: asyncio.Queue | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._pool_size = pool_size
        self._p5 = (_VENDOR / "p5.min.js").read_text()
        self._brush = (_VENDOR / "p5.brush.js").read_text()

    def _own_loop(self) -> asyncio.AbstractEventLoop:
        """Return the renderer's private loop, starting its thread on first call."""
        with self._start_lock:
            if self._loop is None:
                ready = threading.Event()

                def run():
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
                    ready.set()
                    self._loop.run_forever()

                self._thread = threading.Thread(
                    target=run, name="sketch-renderer", daemon=True
                )
                self._thread.start()
                ready.wait()
            return self._loop

    def _submit(self, coro):
        """Run a coroutine on the renderer's loop and return its result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._own_loop())
        return asyncio.wrap_future(future)

    async def _pool_ready(self) -> asyncio.Queue:
        """Return the browser pool, launching it on first call.

        Runs on the renderer's own loop, so no cross-loop lock is needed. The
        queue is created here rather than in `__init__` because an asyncio queue
        binds to the loop that first awaits it, and that has to be this one.
        """
        if self._pool is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._pool = asyncio.Queue()
            for _ in range(self._pool_size):
                browser = await self._playwright.chromium.launch(args=CHROMIUM_ARGS)
                self._browsers.append(browser)
                self._pool.put_nowait(browser)
        return self._pool

    async def render(self, sketch: str, seed: int = 0) -> Render:
        """Run a sketch and return its painting.

        `seed` fixes `Math.random` for the run, so the same sketch paints the same
        picture. Left at zero it still fixes it, which is what makes a group of
        rollouts comparable: the difference between two of them is then the code
        and not the dice.

        Args:
            sketch (`str`):
                JavaScript defining `setup` and `draw`.

        Returns:
            [`Render`]: The painting and what happened while making it.

        Raises:
            RenderError: If the sketch never created a canvas, which means it
                failed before or inside `createCanvas`.
        """
        return await self._submit(self._render(sketch, seed))

    async def _render(self, sketch: str, seed: int = 0) -> Render:
        """Do the render. Only ever runs on the renderer's own loop."""
        pool = await self._pool_ready()
        browser = await pool.get()
        try:
            return await self._render_in_browser(browser, sketch, seed)
        finally:
            pool.put_nowait(browser)

    async def _render_in_browser(self, browser, sketch: str, seed: int = 0) -> Render:
        """Paint one sketch in a browser taken from the pool."""
        loop = asyncio.get_running_loop()
        started = loop.time()
        page = await browser.new_page(
            viewport={"width": CANVAS_SIZE + 100, "height": CANVAS_SIZE + 100}
        )
        try:
            # `wait_until="commit"` rather than the default `"load"`. A heavy
            # sketch blocks the page's main thread while it paints, so `load`
            # does not fire until the render is finished, and Playwright's own
            # 30s default fires first: sketches from Narreddi's trained model,
            # which run over a hundred brush calls, made `set_content` itself
            # throw before this function's own deadline had any say. Nothing here
            # needs `load`, because readiness is polled below and every asset is
            # inline.
            await page.set_content(
                _PAGE.format(p5=self._p5, brush=self._brush, sketch=sketch, seed=seed),
                wait_until="commit",
            )
            finished = False
            while loop.time() - started < RENDER_DEADLINE_S:
                if await page.evaluate(_DONE):
                    finished = True
                    break
                # A sketch that has thrown after painting at least one frame
                # never reached its own `noLoop()` and never will, so waiting
                # out the deadline only costs time. Bailing here is what keeps
                # a deadline long enough for the references from making every
                # broken submission expensive.
                if await page.evaluate(_DEAD):
                    break
                await asyncio.sleep(POLL_INTERVAL_S)
            data_url = await page.evaluate(
                "document.querySelector('canvas')"
                " ? document.querySelector('canvas').toDataURL('image/png')"
                " : null"
            )
            errors = await page.evaluate("window.__errors")
        finally:
            await page.close()

        if data_url is None:
            raise RenderError("sketch created no canvas")
        png = base64.b64decode(data_url.split(",", 1)[1])
        return Render(
            png=png,
            paint_fraction=paint_fraction(png),
            finished=finished,
            errors=[str(e) for e in errors],
            elapsed_ms=int((loop.time() - started) * 1000),
        )

    async def close(self) -> None:
        """Shut the browser down and stop the renderer's thread."""
        if self._loop is None:
            return
        await self._submit(self._close())
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=10)
        self._loop = None
        self._thread = None

    async def _close(self) -> None:
        """Tear the pool down. Only ever runs on the renderer's own loop."""
        for browser in self._browsers:
            await browser.close()
        self._browsers = []
        self._pool = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


# One pool for the whole process, shared by every session. Each session gets
# its own `Environment`, so a renderer per instance meant a Chromium per session:
# four concurrent rollouts launched four browsers, each with its own software GL
# stack, on a machine that has one CPU to share between them. Sharing means the
# pool is sized once, against the machine, instead of multiplying by whatever
# number of sessions happens to connect.
_SHARED: SketchRenderer | None = None
_SHARED_LOCK = threading.Lock()


def shared_renderer() -> SketchRenderer:
    """Return the process-wide renderer, creating it on first call.

    Returns:
        [`SketchRenderer`]: The shared instance.

    Examples:

    ```python
    render = await shared_renderer().render(sketch)
    ```
    """
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None:
            _SHARED = SketchRenderer()
        return _SHARED


async def close_shared_renderer() -> None:
    """Shut the shared renderer down, if one was ever created."""
    global _SHARED
    with _SHARED_LOCK:
        renderer, _SHARED = _SHARED, None
    if renderer is not None:
        await renderer.close()
