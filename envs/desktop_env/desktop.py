"""Shared E2B Desktop controller — used by every desktop_env framework variant.

The action surface mirrors Anthropic's `computer_20251124` schema. All
coordinate args are `[x, y]` arrays in pixel space (matches Anthropic +
Qwen native output). Modifier `text` (e.g. "shift", "ctrl+shift") is
held for the duration of click/scroll actions.

Methods return `(text, image_b64_or_none)` tuples. Image data is None for
non-screenshot calls; text is a short human-readable confirmation.
"""

from __future__ import annotations

import base64
import os
import time
from typing import Any, List, Optional, Tuple

from e2b_desktop import Sandbox

# ──────────────────────────────────────────────────────────────────────────────
# App presets
# ──────────────────────────────────────────────────────────────────────────────

APP_PRESETS: dict[str, Tuple[List[str], Optional[str], int]] = {
    "libreoffice-calc": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-calc"],
        "libreoffice --calc", 5000,
    ),
    "libreoffice-writer": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-writer"],
        "libreoffice --writer", 5000,
    ),
    "libreoffice-impress": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-impress"],
        "libreoffice --impress", 5000,
    ),
    "firefox": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq firefox"],
        "firefox", 5000,
    ),
    "blender": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq blender"],
        "blender", 8000,
    ),
    "terminal": ([], "xfce4-terminal", 2000),
    "gimp": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gimp"],
        "gimp", 6000,
    ),
    "desktop": ([], None, 1000),
}

_MODIFIER_ALIAS = {
    "shift": "shift", "ctrl": "ctrl", "control": "ctrl",
    "alt": "alt", "option": "alt",
    "super": "super", "cmd": "super", "command": "super", "win": "super", "meta": "super",
}


def _coerce(coord) -> Tuple[int, int]:
    if isinstance(coord, str):
        coord = [int(p.strip()) for p in coord.replace("[", "").replace("]", "").replace("(", "").replace(")", "").split(",")]
    x, y = coord
    return int(x), int(y)


def _split_mods(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [_MODIFIER_ALIAS.get(p.strip().lower(), p.strip().lower()) for p in text.split("+")]


# ──────────────────────────────────────────────────────────────────────────────
# Controller
# ──────────────────────────────────────────────────────────────────────────────

ActionResult = Tuple[str, Optional[str]]  # (text, image_b64 or None)


class DesktopController:
    """Stateful E2B Desktop wrapper with all 19 computer-use actions.

    Lazy sandbox init: nothing is created until `start()` is called. Every
    method returns `(text, image_b64_or_none)` so the caller can feed the
    image straight into a vision model.
    """

    def __init__(
        self,
        api_key: str = "",
        app: str = "desktop",
        resolution: Tuple[int, int] = (1024, 768),
        timeout: int = 600,
        install_commands: Optional[List[str]] = None,
    ):
        self._api_key = api_key or os.environ.get("E2B_API_KEY", "")
        self._app = app
        self._resolution = tuple(resolution)
        self._timeout = timeout
        self._extra_install = install_commands or []
        self._sandbox: Optional[Sandbox] = None
        self.terminated = False
        self.terminate_status: Optional[str] = None

    # -- lifecycle -------------------------------------------------------

    def start(self) -> str:
        if not self._api_key:
            raise RuntimeError("E2B_API_KEY required")
        if self._sandbox is not None:
            return "(already running)"
        if self._app in APP_PRESETS:
            install_cmds, launch_cmd, wait_ms = APP_PRESETS[self._app]
        else:
            install_cmds = self._extra_install
            launch_cmd = self._app
            wait_ms = 3000
        self._sandbox = Sandbox.create(
            resolution=self._resolution, dpi=96, timeout=self._timeout, api_key=self._api_key,
        )
        for cmd in install_cmds:
            self._sandbox.commands.run(cmd, timeout=300)
        if launch_cmd:
            self._sandbox.commands.run(launch_cmd, background=True)
            self._sandbox.wait(wait_ms)
        try:
            self._sandbox.stream.start()
        except Exception:
            pass
        return f"Started {self._app} at {self._resolution[0]}x{self._resolution[1]}"

    def close(self):
        if self._sandbox:
            try:
                self._sandbox.stream.stop()
            except Exception:
                pass
            try:
                self._sandbox.kill()
            except Exception:
                pass
            self._sandbox = None

    @property
    def stream_url(self) -> Optional[str]:
        if self._sandbox:
            try:
                return self._sandbox.stream.get_url()
            except Exception:
                return None
        return None

    @property
    def sandbox_id(self) -> Optional[str]:
        return self._sandbox.sandbox_id if self._sandbox else None

    def _require(self):
        if self._sandbox is None:
            self.start()

    # -- holding modifier keys around an action --------------------------

    class _Held:
        def __init__(self, sandbox, mods):
            self._s = sandbox
            self._mods = mods or []

        def __enter__(self):
            for m in self._mods:
                try:
                    self._s.key_press(m)
                except Exception:
                    pass

        def __exit__(self, *exc):
            for m in reversed(self._mods):
                try:
                    self._s.key_release(m)
                except Exception:
                    pass

    def _held(self, mods):
        return self._Held(self._sandbox, mods)

    # -- observation -----------------------------------------------------

    def screenshot(self) -> ActionResult:
        self._require()
        data = self._sandbox.screenshot()
        return (f"screenshot {self._resolution[0]}x{self._resolution[1]}",
                base64.b64encode(data).decode("utf-8"))

    def cursor_position(self) -> ActionResult:
        self._require()
        x, y = self._sandbox.get_cursor_position()
        return (f"{x},{y}", None)

    def get_screen_size(self) -> ActionResult:
        self._require()
        w, h = self._sandbox.get_screen_size()
        return (f"{w}x{h}", None)

    # -- mouse: clicks ---------------------------------------------------

    def _click(self, button: str, coordinate, text: Optional[str]) -> ActionResult:
        self._require()
        x, y = _coerce(coordinate)
        click = {
            "left": self._sandbox.left_click,
            "right": self._sandbox.right_click,
            "middle": getattr(self._sandbox, "middle_click", self._sandbox.left_click),
        }[button]
        with self._held(_split_mods(text)):
            click(x, y)
        return (f"{button.title()}-clicked at ({x},{y})", None)

    def left_click(self, coordinate, text=None) -> ActionResult:
        return self._click("left", coordinate, text)

    def right_click(self, coordinate, text=None) -> ActionResult:
        return self._click("right", coordinate, text)

    def middle_click(self, coordinate, text=None) -> ActionResult:
        return self._click("middle", coordinate, text)

    def double_click(self, coordinate, text=None) -> ActionResult:
        self._require()
        x, y = _coerce(coordinate)
        with self._held(_split_mods(text)):
            self._sandbox.double_click(x, y)
        return (f"Double-clicked at ({x},{y})", None)

    def triple_click(self, coordinate, text=None) -> ActionResult:
        self._require()
        x, y = _coerce(coordinate)
        with self._held(_split_mods(text)):
            self._sandbox.left_click(x, y)
            self._sandbox.left_click(x, y)
            self._sandbox.left_click(x, y)
        return (f"Triple-clicked at ({x},{y})", None)

    # -- mouse: motion ---------------------------------------------------

    def mouse_move(self, coordinate) -> ActionResult:
        self._require()
        x, y = _coerce(coordinate)
        self._sandbox.move_mouse(x, y)
        return (f"Moved cursor to ({x},{y})", None)

    def left_click_drag(self, start_coordinate, coordinate, text=None) -> ActionResult:
        self._require()
        sx, sy = _coerce(start_coordinate)
        ex, ey = _coerce(coordinate)
        with self._held(_split_mods(text)):
            self._sandbox.drag((sx, sy), (ex, ey))
        return (f"Dragged ({sx},{sy})→({ex},{ey})", None)

    def left_mouse_down(self, coordinate=None) -> ActionResult:
        self._require()
        if coordinate is not None:
            x, y = _coerce(coordinate)
            self._sandbox.move_mouse(x, y)
        try:
            self._sandbox.mouse_press("left")
        except AttributeError:
            pass
        return ("Left mouse pressed", None)

    def left_mouse_up(self, coordinate=None) -> ActionResult:
        self._require()
        if coordinate is not None:
            x, y = _coerce(coordinate)
            self._sandbox.move_mouse(x, y)
        try:
            self._sandbox.mouse_release("left")
        except AttributeError:
            pass
        return ("Left mouse released", None)

    def scroll(self, coordinate, scroll_direction, scroll_amount, text=None) -> ActionResult:
        self._require()
        x, y = _coerce(coordinate)
        self._sandbox.move_mouse(x, y)
        with self._held(_split_mods(text)):
            self._sandbox.scroll(direction=scroll_direction, amount=int(scroll_amount))
        return (f"Scrolled {scroll_direction} {scroll_amount} at ({x},{y})", None)

    # -- keyboard --------------------------------------------------------

    def type(self, text: str) -> ActionResult:
        self._require()
        self._sandbox.write(text)
        return (f"Typed {len(text)} chars", None)

    def key(self, keys: str) -> ActionResult:
        self._require()
        if "+" in keys:
            self._sandbox.press([k.strip() for k in keys.split("+")])
        else:
            self._sandbox.press(keys)
        return (f"Pressed {keys}", None)

    def hold_key(self, keys: str, duration: float) -> ActionResult:
        self._require()
        parts = [k.strip() for k in keys.split("+")]
        try:
            for p in parts:
                self._sandbox.key_press(p)
            time.sleep(float(duration))
        finally:
            for p in reversed(parts):
                try:
                    self._sandbox.key_release(p)
                except Exception:
                    pass
        return (f"Held {keys} for {duration}s", None)

    # -- control ---------------------------------------------------------

    def wait(self, duration: float) -> ActionResult:
        time.sleep(float(duration))
        return (f"Waited {duration}s", None)

    def terminate(self, status: str) -> ActionResult:
        self.terminated = True
        self.terminate_status = status
        return (f"Episode terminated: {status}", None)

    def run_command(self, command: str) -> ActionResult:
        self._require()
        result = self._sandbox.commands.run(command, timeout=60)
        out = result.stdout or ""
        if result.exit_code != 0 and result.stderr:
            out += f"\nSTDERR: {result.stderr}"
        return (out or "(no output)", None)


# Action registry — name → (method, [param_names]) — used by some frameworks
# for generic dispatch.
ACTION_SIGS: dict[str, Tuple[List[str], List[str]]] = {
    # name -> (required_params, optional_params)
    "screenshot":      ([], []),
    "cursor_position": ([], []),
    "get_screen_size": ([], []),
    "left_click":      (["coordinate"], ["text"]),
    "right_click":     (["coordinate"], ["text"]),
    "middle_click":    (["coordinate"], ["text"]),
    "double_click":    (["coordinate"], ["text"]),
    "triple_click":    (["coordinate"], ["text"]),
    "mouse_move":      (["coordinate"], []),
    "left_click_drag": (["start_coordinate", "coordinate"], ["text"]),
    "left_mouse_down": ([], ["coordinate"]),
    "left_mouse_up":   ([], ["coordinate"]),
    "scroll":          (["coordinate", "scroll_direction", "scroll_amount"], ["text"]),
    "type":            (["text"], []),
    "key":             (["keys"], []),
    "hold_key":        (["keys", "duration"], []),
    "wait":            (["duration"], []),
    "terminate":       (["status"], []),
    "run_command":     (["command"], []),
}
