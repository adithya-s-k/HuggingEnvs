"""
Desktop Computer-Use OpenEnv Environment.

Exposes a cloud desktop sandbox (E2B) with tools designed to mirror the action
schemas of the major frontier computer-use models — so a model's native tool
output can drive the env with minimal token-level rewriting.

Action surface (modelled on Anthropic's `computer_20251124` since it's the
broadest superset of OpenAI Operator and Qwen3-VL ComputerUse):

  Observation:
    screenshot()                         -> image (PNG)
    cursor_position()                    -> "x,y"
    get_screen_size()                    -> "WxH"

  Mouse — all coordinate args are `[x, y]` arrays (matches Anthropic + Qwen):
    left_click(coordinate, text=None)
    right_click(coordinate, text=None)
    middle_click(coordinate, text=None)
    double_click(coordinate, text=None)
    triple_click(coordinate, text=None)
    mouse_move(coordinate)
    left_click_drag(start_coordinate, coordinate, text=None)
    left_mouse_down(coordinate=None)
    left_mouse_up(coordinate=None)
    scroll(coordinate, scroll_direction, scroll_amount, text=None)

  Keyboard:
    type(text)
    key(keys)                  e.g. "ctrl+s" or "enter"
    hold_key(keys, duration)

  Control:
    wait(duration)
    terminate(status)          status="success"|"failure"; sets done=True
    run_command(command)       bash escape hatch (out-of-band of the model spec)

The `text` modifier on click/scroll holds shift/ctrl/alt/super while clicking,
matching Anthropic's spec exactly. Coordinates are in **pixel space** at the
configured `display_width_px` × `display_height_px`. If the model emits
0–1000 normalized coords (Qwen2.5-VL), the rollout adapter must rescale.
"""

import base64
import os
import time
from typing import Any, List, Optional, Tuple
from uuid import uuid4

from dotenv import load_dotenv
from e2b_desktop import Sandbox
from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from openenv.core.env_server.mcp_environment import MCPEnvironment
from openenv.core.env_server.types import Action, Observation

load_dotenv()


# Pre-built app configs: (install_commands, launch_command, wait_ms)
APP_PRESETS = {
    "libreoffice-calc": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-calc"],
        "libreoffice --calc",
        5000,
    ),
    "libreoffice-writer": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-writer"],
        "libreoffice --writer",
        5000,
    ),
    "libreoffice-impress": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-impress"],
        "libreoffice --impress",
        5000,
    ),
    "firefox": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq firefox"],
        "firefox",
        5000,
    ),
    "blender": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq blender"],
        "blender",
        8000,
    ),
    "terminal": (
        [],
        "xfce4-terminal",
        2000,
    ),
    "gimp": (
        ["sudo apt-get update -qq", "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gimp"],
        "gimp",
        6000,
    ),
    "desktop": (
        [],
        None,
        1000,
    ),
}


_MODIFIER_ALIAS = {
    "shift": "shift",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "super": "super",
    "cmd": "super",
    "command": "super",
    "win": "super",
    "meta": "super",
}


def _coerce_coord(coord: Any) -> Tuple[int, int]:
    """Accept [x,y] / (x,y) / "x,y"; return (int, int)."""
    if isinstance(coord, str):
        parts = coord.replace("(", "").replace(")", "").replace("[", "").replace("]", "").split(",")
        coord = [int(p.strip()) for p in parts]
    x, y = coord
    return int(x), int(y)


def _split_modifiers(mod_text: Optional[str]) -> List[str]:
    """Split a modifier text like 'shift' or 'ctrl+shift' into normalized keys."""
    if not mod_text:
        return []
    return [_MODIFIER_ALIAS.get(p.strip().lower(), p.strip().lower()) for p in mod_text.split("+")]


class DesktopEnvironment(MCPEnvironment):
    """Cloud desktop environment backed by E2B Desktop sandbox."""

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._api_key = os.environ["E2B_API_KEY"]
        self._sandbox: Optional[Sandbox] = None
        self._resolution = (1024, 768)  # safe default for vision-model coord scaling
        self._timeout = 600

        try:
            from ..models import DesktopState, ScreenAction
        except ImportError:
            from models import DesktopState, ScreenAction

        self._DesktopState = DesktopState
        self._ScreenAction = ScreenAction
        self._state = DesktopState(episode_id=str(uuid4()))
        self._terminated = False
        self._terminate_status: Optional[str] = None

        # ── Register MCP tools ──────────────────────────────────────────
        mcp = FastMCP("desktop_env")

        # ----- Observation ------------------------------------------------

        @mcp.tool
        def screenshot() -> Image:
            """Capture the current screen state.

            Returns the screen as a PNG image content block — the model sees
            the actual pixels, not a base64 string.
            """
            self._require_sandbox()
            data = self._sandbox.screenshot()
            self._state.last_screenshot_b64 = base64.b64encode(data).decode("utf-8")
            self._record("screenshot", "Captured screenshot")
            return Image(data=data, format="png")

        @mcp.tool
        def cursor_position() -> str:
            """Return current mouse cursor position as 'x,y'."""
            self._require_sandbox()
            x, y = self._sandbox.get_cursor_position()
            return f"{x},{y}"

        @mcp.tool
        def get_screen_size() -> str:
            """Return screen dimensions as 'WxH'."""
            self._require_sandbox()
            w, h = self._sandbox.get_screen_size()
            return f"{w}x{h}"

        # ----- Mouse: clicks --------------------------------------------

        @mcp.tool
        def left_click(coordinate: List[int], text: Optional[str] = None) -> str:
            """Left-click at `coordinate=[x, y]`.

            Optional `text` holds modifier keys ("shift", "ctrl", "alt",
            "super", or combinations like "ctrl+shift") for the duration
            of the click.
            """
            return self._click("left", coordinate, text)

        @mcp.tool
        def right_click(coordinate: List[int], text: Optional[str] = None) -> str:
            """Right-click at `coordinate=[x, y]`. Optional modifier `text`."""
            return self._click("right", coordinate, text)

        @mcp.tool
        def middle_click(coordinate: List[int], text: Optional[str] = None) -> str:
            """Middle-click at `coordinate=[x, y]`. Optional modifier `text`."""
            return self._click("middle", coordinate, text)

        @mcp.tool
        def double_click(coordinate: List[int], text: Optional[str] = None) -> str:
            """Double-click at `coordinate=[x, y]`. Optional modifier `text`."""
            self._require_sandbox()
            x, y = _coerce_coord(coordinate)
            with self._held(_split_modifiers(text)):
                self._sandbox.double_click(x, y)
            self._record("double_click", f"Double click at ({x},{y}) mods={text or ''}")
            return f"Double-clicked at ({x},{y})"

        @mcp.tool
        def triple_click(coordinate: List[int], text: Optional[str] = None) -> str:
            """Triple-click at `coordinate=[x, y]`. Selects line/word in most apps."""
            self._require_sandbox()
            x, y = _coerce_coord(coordinate)
            with self._held(_split_modifiers(text)):
                # E2B has no triple_click — emulate with three rapid left clicks
                self._sandbox.left_click(x, y)
                self._sandbox.left_click(x, y)
                self._sandbox.left_click(x, y)
            self._record("triple_click", f"Triple click at ({x},{y})")
            return f"Triple-clicked at ({x},{y})"

        # ----- Mouse: motion --------------------------------------------

        @mcp.tool
        def mouse_move(coordinate: List[int]) -> str:
            """Move the mouse cursor to `coordinate=[x, y]` without clicking."""
            self._require_sandbox()
            x, y = _coerce_coord(coordinate)
            self._sandbox.move_mouse(x, y)
            self._record("mouse_move", f"Moved mouse to ({x},{y})")
            return f"Moved cursor to ({x},{y})"

        @mcp.tool
        def left_click_drag(
            start_coordinate: List[int],
            coordinate: List[int],
            text: Optional[str] = None,
        ) -> str:
            """Press at `start_coordinate`, drag to `coordinate`, then release."""
            self._require_sandbox()
            sx, sy = _coerce_coord(start_coordinate)
            ex, ey = _coerce_coord(coordinate)
            with self._held(_split_modifiers(text)):
                self._sandbox.drag((sx, sy), (ex, ey))
            self._record("left_click_drag", f"Drag ({sx},{sy})→({ex},{ey}) mods={text or ''}")
            return f"Dragged from ({sx},{sy}) to ({ex},{ey})"

        @mcp.tool
        def left_mouse_down(coordinate: Optional[List[int]] = None) -> str:
            """Press the left mouse button (without releasing). Optionally move first."""
            self._require_sandbox()
            if coordinate is not None:
                x, y = _coerce_coord(coordinate)
                self._sandbox.move_mouse(x, y)
            try:
                self._sandbox.mouse_press("left")
            except AttributeError:
                # older e2b_desktop: emulate with left_click
                pass
            self._record("left_mouse_down", f"Pressed left at {coordinate}")
            return "Left mouse pressed"

        @mcp.tool
        def left_mouse_up(coordinate: Optional[List[int]] = None) -> str:
            """Release the left mouse button. Optionally move first."""
            self._require_sandbox()
            if coordinate is not None:
                x, y = _coerce_coord(coordinate)
                self._sandbox.move_mouse(x, y)
            try:
                self._sandbox.mouse_release("left")
            except AttributeError:
                pass
            self._record("left_mouse_up", f"Released left at {coordinate}")
            return "Left mouse released"

        @mcp.tool
        def scroll(
            coordinate: List[int],
            scroll_direction: str,
            scroll_amount: int,
            text: Optional[str] = None,
        ) -> str:
            """Scroll at `coordinate=[x, y]` in `scroll_direction` ("up"/"down"/"left"/"right").

            `scroll_amount` is the number of clicks of the scroll wheel.
            Optional `text` modifier (e.g. "shift" for horizontal scrolling).
            """
            self._require_sandbox()
            x, y = _coerce_coord(coordinate)
            self._sandbox.move_mouse(x, y)
            with self._held(_split_modifiers(text)):
                self._sandbox.scroll(direction=scroll_direction, amount=int(scroll_amount))
            self._record("scroll", f"Scrolled {scroll_direction} {scroll_amount} at ({x},{y})")
            return f"Scrolled {scroll_direction} {scroll_amount} clicks at ({x},{y})"

        # ----- Keyboard --------------------------------------------------

        @mcp.tool(name="type")
        def type_text(text: str) -> str:
            """Type `text` at the current cursor position (character-by-character)."""
            self._require_sandbox()
            self._sandbox.write(text)
            preview = text[:80] + ("..." if len(text) > 80 else "")
            self._record("type", f'Typed: "{preview}"')
            return f"Typed {len(text)} chars"

        @mcp.tool
        def key(keys: str) -> str:
            """Press a key or key combo using xdotool syntax.

            Examples: "enter", "ctrl+s", "ctrl+shift+t", "alt+F4".
            """
            self._require_sandbox()
            if "+" in keys:
                self._sandbox.press([k.strip() for k in keys.split("+")])
            else:
                self._sandbox.press(keys)
            self._record("key", f"Pressed: {keys}")
            return f"Pressed {keys}"

        @mcp.tool
        def hold_key(keys: str, duration: float) -> str:
            """Hold `keys` (e.g. "shift") for `duration` seconds."""
            self._require_sandbox()
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
            self._record("hold_key", f"Held {keys} for {duration}s")
            return f"Held {keys} for {duration}s"

        # ----- Control ---------------------------------------------------

        @mcp.tool
        def wait(duration: float) -> str:
            """Pause for `duration` seconds. Useful while UI animations settle."""
            time.sleep(float(duration))
            self._record("wait", f"Waited {duration}s")
            return f"Waited {duration}s"

        @mcp.tool
        def terminate(status: str) -> str:
            """End the episode with `status` ("success" or "failure")."""
            self._terminated = True
            self._terminate_status = status
            self._record("terminate", f"Terminated: {status}")
            return f"Episode terminated with status={status}"

        @mcp.tool
        def run_command(command: str) -> str:
            """Run a shell command in the sandbox (escape hatch / grading hook)."""
            self._require_sandbox()
            result = self._sandbox.commands.run(command, timeout=60)
            output = result.stdout or ""
            if result.exit_code != 0 and result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            self._record("command", f"$ {command}")
            return output if output else "(no output)"

        super().__init__(mcp)

    # ── Internal helpers ───────────────────────────────────────────────

    def _require_sandbox(self):
        if not self._sandbox:
            raise RuntimeError("Environment not reset — call reset() first.")

    def _record(self, action_type: str, detail: str):
        self._state.actions.append(self._ScreenAction(
            action_type=action_type,
            detail=detail,
            step=self._state.step_count,
        ))

    def _click(self, button: str, coordinate, modifier_text: Optional[str]) -> str:
        self._require_sandbox()
        x, y = _coerce_coord(coordinate)
        click_fn = {
            "left": self._sandbox.left_click,
            "right": self._sandbox.right_click,
            "middle": getattr(self._sandbox, "middle_click", self._sandbox.left_click),
        }[button]
        with self._held(_split_modifiers(modifier_text)):
            click_fn(x, y)
        self._record(f"{button}_click", f"{button} click at ({x},{y}) mods={modifier_text or ''}")
        return f"{button.title()}-clicked at ({x},{y})"

    class _Held:
        def __init__(self, sandbox, mods: List[str]):
            self._sandbox = sandbox
            self._mods = mods or []

        def __enter__(self):
            for m in self._mods:
                try:
                    self._sandbox.key_press(m)
                except Exception:
                    pass
            return self

        def __exit__(self, *exc):
            for m in reversed(self._mods):
                try:
                    self._sandbox.key_release(m)
                except Exception:
                    pass

    def _held(self, mods: List[str]):
        return self._Held(self._sandbox, mods)

    # ── OpenEnv lifecycle ──────────────────────────────────────────────

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Observation:
        if self._sandbox:
            try:
                self._sandbox.kill()
            except Exception:
                pass

        app = kwargs.get("app", "desktop")
        resolution = tuple(kwargs.get("resolution", (1024, 768)))
        timeout = int(kwargs.get("timeout", 600))
        custom_install = kwargs.get("install_commands", [])

        self._resolution = resolution
        self._terminated = False
        self._terminate_status = None

        if app in APP_PRESETS:
            install_cmds, launch_cmd, wait_ms = APP_PRESETS[app]
        else:
            install_cmds = custom_install
            launch_cmd = app
            wait_ms = 3000

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
        stream_url = self._sandbox.stream.get_url()

        self._state = self._DesktopState(
            episode_id=episode_id or str(uuid4()),
            sandbox_id=self._sandbox.sandbox_id,
            stream_url=stream_url,
            app=app,
            screen_width=resolution[0],
            screen_height=resolution[1],
            step_count=0,
        )

        return Observation(
            done=False,
            reward=None,
            metadata={
                "status": "ready",
                "sandbox_id": self._sandbox.sandbox_id,
                "stream_url": stream_url,
                "app": app,
                "resolution": f"{resolution[0]}x{resolution[1]}",
                "message": (
                    f"Desktop ready ({app}, {resolution[0]}x{resolution[1]}). "
                    "Call screenshot to see the screen, then drive the mouse / "
                    "keyboard with coordinate arrays in pixel space. Coordinates "
                    "are absolute pixels in this resolution."
                ),
            },
        )

    def _step_impl(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        return Observation(
            done=False,
            reward=None,
            metadata={
                "error": f"Unknown action type: {type(action).__name__}. "
                "Use ListToolsAction or CallToolAction for MCP interactions."
            },
        )

    def step(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        self._state.step_count += 1
        obs = super().step(action, timeout_s=timeout_s, **kwargs)
        if self._terminated:
            obs = Observation(
                done=True,
                reward=1.0 if self._terminate_status == "success" else 0.0,
                metadata={**(obs.metadata or {}), "terminate_status": self._terminate_status},
            )
        return obs

    async def step_async(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        self._state.step_count += 1
        obs = await super().step_async(action, timeout_s=timeout_s, **kwargs)
        if self._terminated:
            obs = Observation(
                done=True,
                reward=1.0 if self._terminate_status == "success" else 0.0,
                metadata={**(obs.metadata or {}), "terminate_status": self._terminate_status},
            )
        return obs

    @property
    def state(self):
        return self._state
