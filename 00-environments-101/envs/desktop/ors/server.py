"""
Desktop Computer-Use ORS Environment.

Same action surface as `00-environments-101/envs/desktop/openenv/` but exposed via the Open
Reward Standard (`openreward.environments`). Each session creates a fresh
E2B Desktop sandbox, the model interacts via tools that mirror Anthropic's
`computer_20251124` schema, and rewards arrive per-tool-call (per-step) plus
a terminal reward when the agent calls `terminate(status)`.

Deploy:
    docker build -t desktop-ors .
    docker run -p 8080:8080 -e E2B_API_KEY=e2b_... desktop-ors
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4

from dotenv import load_dotenv
from e2b_desktop import Sandbox
from openreward.environments import (
    Environment,
    ImageBlock,
    Server,
    Split,
    TextBlock,
    ToolOutput,
    tool,
)
from pydantic import BaseModel, Field

_parent = str(Path(__file__).resolve().parents[0])
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from tasks import TASKS  # noqa: E402

load_dotenv()


# ──────────────────────────────────────────────────────────────────────────────
# App presets (install + launch + wait_ms after launch)
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


def _coerce_coord(coord) -> Tuple[int, int]:
    if isinstance(coord, str):
        coord = [int(p.strip()) for p in coord.replace("[", "").replace("]", "").replace("(", "").replace(")", "").split(",")]
    x, y = coord
    return int(x), int(y)


def _split_modifiers(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [_MODIFIER_ALIAS.get(p.strip().lower(), p.strip().lower()) for p in text.split("+")]


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic input models for @tool methods
# ──────────────────────────────────────────────────────────────────────────────

class _Empty(BaseModel):
    pass


class _Coord(BaseModel):
    coordinate: List[int] = Field(..., description="[x, y] in pixel space")
    text: Optional[str] = Field(None, description='Modifier keys held during the action (e.g. "shift", "ctrl+shift")')


class _MoveOnly(BaseModel):
    coordinate: List[int]


class _OptCoord(BaseModel):
    coordinate: Optional[List[int]] = None


class _Drag(BaseModel):
    start_coordinate: List[int]
    coordinate: List[int]
    text: Optional[str] = None


class _Scroll(BaseModel):
    coordinate: List[int]
    scroll_direction: str = Field(..., description='"up" | "down" | "left" | "right"')
    scroll_amount: int
    text: Optional[str] = None


class _Type(BaseModel):
    text: str


class _Key(BaseModel):
    keys: str = Field(..., description='Key or combo, xdotool syntax. e.g. "enter", "ctrl+s"')


class _HoldKey(BaseModel):
    keys: str
    duration: float


class _Wait(BaseModel):
    duration: float


class _Terminate(BaseModel):
    status: str = Field(..., description='"success" or "failure"')


class _Cmd(BaseModel):
    command: str


# ──────────────────────────────────────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────────────────────────────────────

class DesktopORS(Environment):
    """Cloud desktop env over ORS, backed by an E2B Desktop sandbox."""

    def __init__(self, task_spec=None, secrets=None, **kwargs):
        if task_spec is None:
            task_spec = {}
        if secrets is None:
            secrets = {}
        super().__init__(task_spec=task_spec, secrets=secrets)

        # API key: prefer the per-session secret; fall back to env var.
        self._api_key = secrets.get("E2B_API_KEY") or os.environ.get("E2B_API_KEY")
        if not self._api_key:
            raise RuntimeError("E2B_API_KEY not provided in secrets or env")

        self._sandbox: Optional[Sandbox] = None
        self._step_count = 0
        self._terminated = False
        self._terminate_status: Optional[str] = None

    # -- ORS lifecycle ----------------------------------------------------

    def setup(self):
        """Spin up an E2B Desktop sandbox according to the task_spec."""
        app = self.task_spec.get("app", "desktop")
        resolution = tuple(self.task_spec.get("resolution", [1024, 768]))
        timeout = int(self.task_spec.get("timeout", 600))

        if app in APP_PRESETS:
            install_cmds, launch_cmd, wait_ms = APP_PRESETS[app]
        else:
            install_cmds = self.task_spec.get("install_commands", [])
            launch_cmd = app
            wait_ms = 3000

        self._resolution = resolution
        self._sandbox = Sandbox.create(
            resolution=resolution,
            dpi=96,
            timeout=timeout,
            api_key=self._api_key,
        )

        for cmd in install_cmds:
            self._sandbox.commands.run(cmd, timeout=300)

        if launch_cmd:
            self._sandbox.commands.run(launch_cmd, background=True)
            self._sandbox.wait(wait_ms)

        self._sandbox.stream.start()

    def teardown(self):
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

    # -- ORS metadata -----------------------------------------------------

    @classmethod
    def list_splits(cls):
        return [Split(name="train", type="train")]

    @classmethod
    def list_tasks(cls, split: str):
        return TASKS

    def get_prompt(self):
        app = self.task_spec.get("app", "desktop")
        res = self.task_spec.get("resolution", [1024, 768])
        instruction = self.task_spec.get(
            "instruction",
            "Use the desktop tools to complete the task. When finished, call "
            "terminate(status='success'); on giving up, terminate(status='failure').",
        )
        return [TextBlock(text=(
            f"You are operating a Linux desktop ({app}, {res[0]}x{res[1]}). "
            f"Coordinates are absolute pixels in [x, y] arrays.\n\n"
            f"Task: {instruction}\n\n"
            "Call screenshot first to see the screen, then drive with the click/"
            "type/key tools. Only one tool call per turn. End with terminate."
        ))]

    # -- helpers ----------------------------------------------------------

    def _require(self):
        if not self._sandbox:
            raise RuntimeError("Sandbox not initialized — setup() not yet run.")

    def _step_reward(self) -> float:
        return 0.0  # per-step reward is 0; all reward comes at terminate

    def _bump(self):
        self._step_count += 1

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

    def _shot_block(self) -> ImageBlock:
        data = self._sandbox.screenshot()
        return ImageBlock(data=base64.b64encode(data).decode("utf-8"), mimeType="image/png")

    # -- Observation tools -----------------------------------------------

    @tool
    def screenshot(self, params: _Empty) -> ToolOutput:
        """Capture the current screen as a PNG image block."""
        self._require()
        self._bump()
        return ToolOutput(blocks=[self._shot_block()], reward=self._step_reward(), finished=False)

    @tool
    def cursor_position(self, params: _Empty) -> ToolOutput:
        """Return current mouse cursor position as 'x,y'."""
        self._require()
        self._bump()
        x, y = self._sandbox.get_cursor_position()
        return ToolOutput(blocks=[TextBlock(text=f"{x},{y}")], reward=self._step_reward(), finished=False)

    @tool
    def get_screen_size(self, params: _Empty) -> ToolOutput:
        """Return screen dimensions as 'WxH'."""
        self._require()
        self._bump()
        w, h = self._sandbox.get_screen_size()
        return ToolOutput(blocks=[TextBlock(text=f"{w}x{h}")], reward=self._step_reward(), finished=False)

    # -- Mouse: clicks ---------------------------------------------------

    def _click_at(self, button: str, params: _Coord) -> ToolOutput:
        self._require()
        self._bump()
        x, y = _coerce_coord(params.coordinate)
        click = {
            "left": self._sandbox.left_click,
            "right": self._sandbox.right_click,
            "middle": getattr(self._sandbox, "middle_click", self._sandbox.left_click),
        }[button]
        with self._held(_split_modifiers(params.text)):
            click(x, y)
        return ToolOutput(
            blocks=[TextBlock(text=f"{button.title()}-clicked at ({x},{y})")],
            reward=self._step_reward(), finished=False,
        )

    @tool
    def left_click(self, params: _Coord) -> ToolOutput:
        """Left-click at coordinate=[x, y]. Optional modifier `text` (e.g. 'shift')."""
        return self._click_at("left", params)

    @tool
    def right_click(self, params: _Coord) -> ToolOutput:
        """Right-click at coordinate=[x, y]. Optional modifier `text`."""
        return self._click_at("right", params)

    @tool
    def middle_click(self, params: _Coord) -> ToolOutput:
        """Middle-click at coordinate=[x, y]. Optional modifier `text`."""
        return self._click_at("middle", params)

    @tool
    def double_click(self, params: _Coord) -> ToolOutput:
        """Double-click at coordinate=[x, y]. Optional modifier `text`."""
        self._require(); self._bump()
        x, y = _coerce_coord(params.coordinate)
        with self._held(_split_modifiers(params.text)):
            self._sandbox.double_click(x, y)
        return ToolOutput(blocks=[TextBlock(text=f"Double-clicked at ({x},{y})")],
                          reward=self._step_reward(), finished=False)

    @tool
    def triple_click(self, params: _Coord) -> ToolOutput:
        """Triple-click at coordinate=[x, y]. Selects the line/word in most apps."""
        self._require(); self._bump()
        x, y = _coerce_coord(params.coordinate)
        with self._held(_split_modifiers(params.text)):
            self._sandbox.left_click(x, y)
            self._sandbox.left_click(x, y)
            self._sandbox.left_click(x, y)
        return ToolOutput(blocks=[TextBlock(text=f"Triple-clicked at ({x},{y})")],
                          reward=self._step_reward(), finished=False)

    # -- Mouse: motion ---------------------------------------------------

    @tool
    def mouse_move(self, params: _MoveOnly) -> ToolOutput:
        """Move cursor to coordinate=[x, y] without clicking."""
        self._require(); self._bump()
        x, y = _coerce_coord(params.coordinate)
        self._sandbox.move_mouse(x, y)
        return ToolOutput(blocks=[TextBlock(text=f"Moved cursor to ({x},{y})")],
                          reward=self._step_reward(), finished=False)

    @tool
    def left_click_drag(self, params: _Drag) -> ToolOutput:
        """Press at start_coordinate, drag to coordinate, release."""
        self._require(); self._bump()
        sx, sy = _coerce_coord(params.start_coordinate)
        ex, ey = _coerce_coord(params.coordinate)
        with self._held(_split_modifiers(params.text)):
            self._sandbox.drag((sx, sy), (ex, ey))
        return ToolOutput(blocks=[TextBlock(text=f"Dragged ({sx},{sy})→({ex},{ey})")],
                          reward=self._step_reward(), finished=False)

    @tool
    def left_mouse_down(self, params: _OptCoord) -> ToolOutput:
        """Press the left mouse button (without releasing). Optionally move first."""
        self._require(); self._bump()
        if params.coordinate is not None:
            x, y = _coerce_coord(params.coordinate)
            self._sandbox.move_mouse(x, y)
        try:
            self._sandbox.mouse_press("left")
        except AttributeError:
            pass
        return ToolOutput(blocks=[TextBlock(text="Left mouse pressed")],
                          reward=self._step_reward(), finished=False)

    @tool
    def left_mouse_up(self, params: _OptCoord) -> ToolOutput:
        """Release the left mouse button. Optionally move first."""
        self._require(); self._bump()
        if params.coordinate is not None:
            x, y = _coerce_coord(params.coordinate)
            self._sandbox.move_mouse(x, y)
        try:
            self._sandbox.mouse_release("left")
        except AttributeError:
            pass
        return ToolOutput(blocks=[TextBlock(text="Left mouse released")],
                          reward=self._step_reward(), finished=False)

    @tool
    def scroll(self, params: _Scroll) -> ToolOutput:
        """Scroll at coordinate in scroll_direction by scroll_amount clicks."""
        self._require(); self._bump()
        x, y = _coerce_coord(params.coordinate)
        self._sandbox.move_mouse(x, y)
        with self._held(_split_modifiers(params.text)):
            self._sandbox.scroll(direction=params.scroll_direction, amount=int(params.scroll_amount))
        return ToolOutput(
            blocks=[TextBlock(text=f"Scrolled {params.scroll_direction} {params.scroll_amount} at ({x},{y})")],
            reward=self._step_reward(), finished=False,
        )

    # -- Keyboard --------------------------------------------------------

    @tool
    def type(self, params: _Type) -> ToolOutput:
        """Type `text` at the current cursor position."""
        self._require(); self._bump()
        self._sandbox.write(params.text)
        return ToolOutput(blocks=[TextBlock(text=f"Typed {len(params.text)} chars")],
                          reward=self._step_reward(), finished=False)

    @tool
    def key(self, params: _Key) -> ToolOutput:
        """Press a key or combo using xdotool syntax (e.g. 'enter', 'ctrl+s')."""
        self._require(); self._bump()
        if "+" in params.keys:
            self._sandbox.press([k.strip() for k in params.keys.split("+")])
        else:
            self._sandbox.press(params.keys)
        return ToolOutput(blocks=[TextBlock(text=f"Pressed {params.keys}")],
                          reward=self._step_reward(), finished=False)

    @tool
    def hold_key(self, params: _HoldKey) -> ToolOutput:
        """Hold `keys` (e.g. 'shift') for `duration` seconds."""
        self._require(); self._bump()
        parts = [k.strip() for k in params.keys.split("+")]
        try:
            for p in parts:
                self._sandbox.key_press(p)
            time.sleep(float(params.duration))
        finally:
            for p in reversed(parts):
                try:
                    self._sandbox.key_release(p)
                except Exception:
                    pass
        return ToolOutput(blocks=[TextBlock(text=f"Held {params.keys} for {params.duration}s")],
                          reward=self._step_reward(), finished=False)

    # -- Control ---------------------------------------------------------

    @tool
    def wait(self, params: _Wait) -> ToolOutput:
        """Pause for `duration` seconds."""
        self._bump()
        time.sleep(float(params.duration))
        return ToolOutput(blocks=[TextBlock(text=f"Waited {params.duration}s")],
                          reward=self._step_reward(), finished=False)

    @tool
    def terminate(self, params: _Terminate) -> ToolOutput:
        """End the episode with `status` ('success' or 'failure'). Reward is 1.0 on success, else 0.0."""
        self._terminated = True
        self._terminate_status = params.status
        reward = 1.0 if params.status == "success" else 0.0
        return ToolOutput(
            blocks=[TextBlock(text=f"Episode terminated: {params.status}")],
            metadata={"terminate_status": params.status},
            reward=reward,
            finished=True,
        )

    @tool
    def run_command(self, params: _Cmd) -> ToolOutput:
        """Run a shell command in the sandbox (out-of-band of the model spec)."""
        self._require(); self._bump()
        result = self._sandbox.commands.run(params.command, timeout=60)
        out = result.stdout or ""
        if result.exit_code != 0 and result.stderr:
            out += f"\nSTDERR: {result.stderr}"
        return ToolOutput(blocks=[TextBlock(text=out or "(no output)")],
                          reward=self._step_reward(), finished=False)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Desktop ORS Server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    print(f"Starting Desktop ORS server on {args.host}:{args.port}")
    print(f"  Tasks: {len(TASKS)}")
    print("  Tools: screenshot, cursor_position, get_screen_size, "
          "left/right/middle/double/triple_click, mouse_move, left_click_drag, "
          "left_mouse_down/up, scroll, type, key, hold_key, wait, terminate, run_command")
    Server([DesktopORS]).run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
