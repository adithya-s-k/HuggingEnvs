"""Desktop Verifiers Environment — in-process, plain Python tools.

Two ways to use:
  1. `DesktopToolkit` — stateful wrapper used by the TRL adapter; introspect
     public methods to discover tools.
  2. `create_verifiers_env()` — builds a `vf.ToolEnv` for native verifiers.

The 19 desktop actions live as bound methods on `DesktopToolkit`. The
underlying E2B Desktop sandbox is owned by the toolkit and reset between
episodes.

Note: this is a vision-heavy env. Verifiers' tool returns are text-only,
so the `screenshot` tool returns the screenshot as a base64 PNG embedded
in markdown — vision models that accept images-in-tool-results will see
it; text-only models will just see the base64 string.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

_parent = str(Path(__file__).resolve().parents[1])
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from core.desktop import DesktopController  # noqa: E402
from core.tasks import TASKS  # noqa: E402

load_dotenv()


# ──────────────────────────────────────────────────────────────────────────────
# DesktopToolkit — stateful wrapper for the TRL adapter
# ──────────────────────────────────────────────────────────────────────────────

class DesktopToolkit:
    """One E2B Desktop sandbox per episode. Methods are introspected as tools."""

    def __init__(
        self,
        api_key: str = "",
        app: str = "firefox",
        resolution: tuple = (1024, 768),
        max_turns: int = 10,
    ):
        self.max_turns = max_turns
        self._app = app
        self._resolution = resolution
        self._api_key = api_key or os.environ.get("E2B_API_KEY", "")
        self._ctrl: Optional[DesktopController] = None
        self.last_output = ""
        self.step_count = 0

    def initialize(self):
        if self._ctrl is None:
            self._ctrl = DesktopController(
                api_key=self._api_key, app=self._app, resolution=self._resolution,
            )
            self._ctrl.start()

    def cleanup(self):
        if self._ctrl is not None:
            self._ctrl.close()
            self._ctrl = None

    def reset(self):
        self.cleanup()
        self.last_output = ""
        self.step_count = 0

    @property
    def terminated(self) -> bool:
        return self._ctrl.terminated if self._ctrl else False

    @property
    def terminate_status(self) -> Optional[str]:
        return self._ctrl.terminate_status if self._ctrl else None

    # -- tool methods (introspected as tools) ---------------------------

    def screenshot(self) -> str:
        """Capture the current screen. Returns the screenshot embedded as a base64 PNG markdown image."""
        self.initialize(); self.step_count += 1
        text, b64 = self._ctrl.screenshot()
        self.last_output = text
        return f"![screenshot](data:image/png;base64,{b64})\n{text}"

    def left_click(self, coordinate: List[int], text: Optional[str] = None) -> str:
        """Left click at coordinate=[x, y]. Optional `text` modifier (e.g. "shift", "ctrl+shift")."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.left_click(coordinate, text); self.last_output = msg; return msg

    def right_click(self, coordinate: List[int], text: Optional[str] = None) -> str:
        """Right click at coordinate=[x, y]."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.right_click(coordinate, text); self.last_output = msg; return msg

    def double_click(self, coordinate: List[int], text: Optional[str] = None) -> str:
        """Double click at coordinate=[x, y]."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.double_click(coordinate, text); self.last_output = msg; return msg

    def mouse_move(self, coordinate: List[int]) -> str:
        """Move cursor to coordinate=[x, y] without clicking."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.mouse_move(coordinate); self.last_output = msg; return msg

    def left_click_drag(self, start_coordinate: List[int], coordinate: List[int],
                        text: Optional[str] = None) -> str:
        """Press at start_coordinate, drag to coordinate, release."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.left_click_drag(start_coordinate, coordinate, text)
        self.last_output = msg; return msg

    def scroll(self, coordinate: List[int], scroll_direction: str,
               scroll_amount: int, text: Optional[str] = None) -> str:
        """Scroll at coordinate in scroll_direction (up/down/left/right) by scroll_amount clicks."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.scroll(coordinate, scroll_direction, scroll_amount, text)
        self.last_output = msg; return msg

    def type(self, text: str) -> str:
        """Type `text` at the current cursor position."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.type(text); self.last_output = msg; return msg

    def key(self, keys: str) -> str:
        """Press a key or combo, e.g. "enter" or "ctrl+s"."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.key(keys); self.last_output = msg; return msg

    def wait(self, duration: float) -> str:
        """Pause for `duration` seconds while UI animations settle."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.wait(duration); self.last_output = msg; return msg

    def terminate(self, status: str) -> str:
        """End the episode. status='success' or 'failure'."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.terminate(status); self.last_output = msg; return msg

    def run_command(self, command: str) -> str:
        """Run a shell command in the sandbox (escape hatch for setup/grading)."""
        self.initialize(); self.step_count += 1
        msg, _ = self._ctrl.run_command(command); self.last_output = msg; return msg


# ──────────────────────────────────────────────────────────────────────────────
# Standalone tool functions (shared toolkit for native verifiers)
# ──────────────────────────────────────────────────────────────────────────────

_shared: Optional[DesktopToolkit] = None


def _kit() -> DesktopToolkit:
    global _shared
    if _shared is None:
        _shared = DesktopToolkit()
    return _shared


def screenshot() -> str:
    """Capture the screen as a base64 PNG."""
    return _kit().screenshot()


def left_click(coordinate: List[int], text: Optional[str] = None) -> str:
    """Left click at coordinate=[x, y]."""
    return _kit().left_click(coordinate, text)


def double_click(coordinate: List[int], text: Optional[str] = None) -> str:
    """Double click at coordinate=[x, y]."""
    return _kit().double_click(coordinate, text)


def type_text(text: str) -> str:
    """Type text at the cursor."""
    return _kit().type(text)


def key(keys: str) -> str:
    """Press a key or combo."""
    return _kit().key(keys)


def scroll(coordinate: List[int], scroll_direction: str, scroll_amount: int) -> str:
    """Scroll wheel."""
    return _kit().scroll(coordinate, scroll_direction, scroll_amount)


def wait(duration: float) -> str:
    """Pause for `duration` seconds."""
    return _kit().wait(duration)


def terminate(status: str) -> str:
    """End the episode."""
    return _kit().terminate(status)


TOOL_FUNCTIONS = [screenshot, left_click, double_click, type_text, key, scroll, wait, terminate]


def create_verifiers_env():
    """Create a `vf.ToolEnv` for native verifiers usage."""
    import verifiers as vf
    from datasets import Dataset

    dataset = Dataset.from_list([
        {"question": t["task"], "answer": t["expected_output"]} for t in TASKS
    ])

    async def correctness(completion, answer, **kwargs) -> float:
        # Reward 1.0 if the agent called terminate(status='success') and
        # the expected_output appeared somewhere in the trajectory.
        seen_success = False
        seen_expected = False
        for msg in completion or []:
            content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            if "Episode terminated: success" in content:
                seen_success = True
            if answer and answer.strip() in content:
                seen_expected = True
        return 1.0 if (seen_success and seen_expected) else (0.5 if seen_success else 0.0)

    rubric = vf.Rubric(funcs=[correctness])

    return vf.ToolEnv(
        tools=TOOL_FUNCTIONS,
        max_turns=8,
        dataset=dataset,
        rubric=rubric,
        system_prompt=(
            "You are a computer-use agent operating a Linux desktop. Use the "
            "provided tools to drive the mouse and keyboard. Take a screenshot "
            "first, then act based on what you see. Coordinates are pixel "
            "[x, y] arrays. Call terminate(status='success') when done."
        ),
    )
