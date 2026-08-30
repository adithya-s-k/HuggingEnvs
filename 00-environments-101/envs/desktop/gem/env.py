"""Desktop GEM Environment — `gem.Env` with the same tag-parsed action set
as the SkyRL variant, but `step()` returns the Gymnasium 5-tuple
`(observation, reward, terminated, truncated, info)`.

Tags: same as `desktop_env/skyrl_gym/env.py`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, SupportsFloat, Tuple

from dotenv import load_dotenv

try:
    from gem import Env
except ImportError:
    import abc
    class Env(abc.ABC):
        @abc.abstractmethod
        def step(self, action): ...
        @abc.abstractmethod
        def reset(self, seed=None): ...
        def close(self): pass

_parent = str(Path(__file__).resolve().parents[1])
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from core.desktop import DesktopController  # noqa: E402
from core.tasks import TASKS  # noqa: E402

load_dotenv()


_TAG_RE = re.compile(
    r"<(?P<name>[a-z_]+)"
    r"(?P<attrs>(?:\s+[a-z_]+=\"[^\"]*\")*)\s*"
    r"(?:/>|>(?P<body>.*?)</(?P=name)>)",
    re.DOTALL,
)
_ATTR_RE = re.compile(r"([a-z_]+)=\"([^\"]*)\"")


def _parse_tags(s: str):
    out = []
    for m in _TAG_RE.finditer(s):
        attrs = dict(_ATTR_RE.findall(m.group("attrs") or ""))
        out.append((m.group("name"), attrs, m.group("body")))
    return out


class DesktopGemEnv(Env):
    """GEM Env wrapping an E2B Desktop sandbox with tag-parsed text actions."""

    def __init__(
        self,
        task: str = "",
        expected_output: str = "",
        app: str = "firefox",
        resolution: tuple = (1024, 768),
        max_turns: int = 8,
        api_key: str = "",
        task_index: int = -1,
        **kwargs,
    ):
        super().__init__()
        self._api_key = api_key or os.environ.get("E2B_API_KEY", "")
        self._task = task
        self._expected_output = expected_output
        self._app = app
        self._resolution = resolution
        self._max_turns = max_turns
        self._task_index = task_index
        self._ctrl: Optional[DesktopController] = None
        self.last_output = ""
        self.step_count = 0
        self.error_count = 0

    def reset(self, seed: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
        super().reset(seed) if hasattr(super(), "reset") else None
        if self._ctrl:
            self._ctrl.close()
            self._ctrl = None

        if not self._task:
            t = TASKS[(self._task_index if self._task_index >= 0 else 0) % len(TASKS)]
            self._task = t["task"]
            self._expected_output = t["expected_output"]
            self._app = t.get("app", self._app)
            self._resolution = tuple(t.get("resolution", self._resolution))

        self._ctrl = DesktopController(api_key=self._api_key, app=self._app, resolution=self._resolution)
        self._ctrl.start()
        self.last_output = ""
        self.step_count = 0
        self.error_count = 0
        return (
            f"{self._task}\n\nUse <click>, <type>, <key>, <screenshot/>, "
            "<scroll>, <wait>, <terminate status=\"success\"/> tags.",
            {"task": self._task, "expected_output": self._expected_output},
        )

    def step(self, action: str) -> Tuple[str, SupportsFloat, bool, bool, Dict[str, Any]]:
        if self._ctrl is None:
            self.reset()
        self.step_count += 1
        results = []
        for name, attrs, body in _parse_tags(action):
            try:
                text, image = self._dispatch(name, attrs, body)
            except Exception as e:
                self.error_count += 1
                results.append(f"[{name} error] {e}")
                continue
            if image:
                results.append(f"[{name}]\n![screenshot](data:image/png;base64,{image})")
            else:
                results.append(f"[{name}] {text}")
            self.last_output = text

        if not results:
            results.append("(no recognizable action tag in your reply)")

        terminated = bool(self._ctrl and self._ctrl.terminated)
        truncated = self.step_count >= self._max_turns
        reward = 1.0 if (terminated and self._ctrl.terminate_status == "success") else 0.0

        return "\n".join(results), reward, terminated, truncated, {
            "step_count": self.step_count,
            "errors": self.error_count,
            "terminate_status": getattr(self._ctrl, "terminate_status", None),
        }

    def _coord(self, attrs):
        return [int(attrs.get("x", "0")), int(attrs.get("y", "0"))]

    def _dispatch(self, name, attrs, body):
        c = self._ctrl
        if name == "screenshot":
            return c.screenshot()
        if name == "click":
            button = attrs.get("button", "left")
            fn = {"left": c.left_click, "right": c.right_click, "middle": c.middle_click}.get(button, c.left_click)
            return fn(self._coord(attrs), attrs.get("modifier"))
        if name == "double_click":
            return c.double_click(self._coord(attrs), attrs.get("modifier"))
        if name == "triple_click":
            return c.triple_click(self._coord(attrs), attrs.get("modifier"))
        if name == "move":
            return c.mouse_move(self._coord(attrs))
        if name == "drag":
            sx, sy = int(attrs.get("sx", "0")), int(attrs.get("sy", "0"))
            return c.left_click_drag([sx, sy], self._coord(attrs))
        if name == "scroll":
            return c.scroll(self._coord(attrs), attrs.get("direction", "down"),
                            int(attrs.get("amount", "3")), attrs.get("modifier"))
        if name == "type":
            return c.type(body or "")
        if name == "key":
            return c.key(body or attrs.get("keys", ""))
        if name == "wait":
            return c.wait(float(attrs.get("seconds", "1")))
        if name == "run":
            return c.run_command(body or "")
        if name == "terminate":
            return c.terminate(attrs.get("status", "failure"))
        raise ValueError(f"unknown action tag: {name}")

    def close(self):
        if self._ctrl:
            self._ctrl.close()
            self._ctrl = None

    def spawn(self, same_state: bool = False, **kwargs):
        return DesktopGemEnv(
            task=self._task if same_state else "",
            expected_output=self._expected_output if same_state else "",
            app=self._app, resolution=self._resolution,
            max_turns=self._max_turns, api_key=self._api_key,
            task_index=self._task_index, **kwargs,
        )
