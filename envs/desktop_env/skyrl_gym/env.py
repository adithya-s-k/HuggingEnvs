"""Desktop SkyRL Gym Environment — `BaseTextEnv` with tag-parsed actions.

The model emits free text containing one or more action tags; the env parses
each tag, dispatches it to the `DesktopController`, and returns the combined
output as the next observation.

Supported tags (one action per tag):
  <screenshot/>
  <click x="100" y="200"/>             (left click; use button="right" for right click)
  <double_click x="100" y="200"/>
  <move x="100" y="200"/>
  <type>hello</type>
  <key>ctrl+s</key>
  <scroll x="500" y="400" direction="down" amount="3"/>
  <wait seconds="1"/>
  <run>echo hello</run>
  <terminate status="success"/>

Vision note: SkyRL's `BaseTextEnv` is text-only — screenshots come back as a
base64 PNG embedded in markdown so a multimodal-friendly trainer can parse
them. For pure text models, prefer terminal-app tasks where typed I/O is
sufficient.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

try:
    from skyrl_gym.envs.base_text_env import BaseTextEnv, BaseTextEnvStepOutput
except ImportError:
    from dataclasses import dataclass

    class BaseTextEnv:
        def init(self, prompt): return prompt, {}
        def step(self, action): raise NotImplementedError
        def close(self): pass

    @dataclass
    class BaseTextEnvStepOutput:
        observations: list
        reward: float
        done: bool
        metadata: dict
        postprocessed_action: str = None

_parent = str(Path(__file__).resolve().parents[1])
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from desktop import DesktopController  # noqa: E402
from tasks import TASKS  # noqa: E402

load_dotenv()


_TAG_RE = re.compile(
    r"<(?P<name>[a-z_]+)"
    r"(?P<attrs>(?:\s+[a-z_]+=\"[^\"]*\")*)\s*"
    r"(?:/>|>(?P<body>.*?)</(?P=name)>)",
    re.DOTALL,
)
_ATTR_RE = re.compile(r"([a-z_]+)=\"([^\"]*)\"")


def _parse_tags(s: str) -> List[Tuple[str, Dict[str, str], Optional[str]]]:
    """Return [(tag, attrs_dict, body_or_None), ...] in document order."""
    out = []
    for m in _TAG_RE.finditer(s):
        attrs = dict(_ATTR_RE.findall(m.group("attrs") or ""))
        out.append((m.group("name"), attrs, m.group("body")))
    return out


class DesktopSkyRLEnv(BaseTextEnv):
    """SkyRL BaseTextEnv driving an E2B Desktop sandbox via tag-parsed actions."""

    def __init__(
        self,
        task: str = "",
        expected_output: str = "",
        app: str = "firefox",
        resolution: tuple = (1024, 768),
        max_turns: int = 8,
        api_key: str = "",
        **kwargs,
    ):
        super().__init__()
        self._api_key = api_key or os.environ.get("E2B_API_KEY", "")
        self._app = app
        self._resolution = resolution
        self._task = task
        self._expected_output = expected_output
        self.max_turns = max_turns
        self._ctrl: Optional[DesktopController] = None
        self.last_output = ""
        self.error_count = 0

    def init(self, prompt) -> Tuple[Any, Dict]:
        if self._ctrl:
            self._ctrl.close()
        self._ctrl = DesktopController(api_key=self._api_key, app=self._app, resolution=self._resolution)
        self._ctrl.start()
        self.last_output = ""
        self.turns = 0
        self.error_count = 0
        return prompt, {"max_turns": self.max_turns}

    def step(self, action: str) -> BaseTextEnvStepOutput:
        self.turns += 1
        results: List[str] = []

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
            results.append("(no recognizable action tag found in your reply)")

        terminated = bool(self._ctrl and self._ctrl.terminated)
        reward = self._compute_reward(terminated)
        done = terminated or self.turns >= self.max_turns

        return BaseTextEnvStepOutput(
            observations=[{"role": "user", "content": "\n".join(results)}],
            reward=reward,
            done=done,
            metadata={"turns": self.turns, "errors": self.error_count,
                      "terminate_status": getattr(self._ctrl, "terminate_status", None)},
        )

    def close(self):
        if self._ctrl:
            self._ctrl.close()
            self._ctrl = None

    def _coord(self, attrs: Dict[str, str]) -> List[int]:
        return [int(attrs.get("x", "0")), int(attrs.get("y", "0"))]

    def _dispatch(self, name: str, attrs: Dict[str, str], body: Optional[str]):
        c = self._ctrl
        if name == "screenshot":
            return c.screenshot()
        if name == "click":
            button = attrs.get("button", "left")
            if button == "right":
                return c.right_click(self._coord(attrs), attrs.get("modifier"))
            if button == "middle":
                return c.middle_click(self._coord(attrs), attrs.get("modifier"))
            return c.left_click(self._coord(attrs), attrs.get("modifier"))
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
            return c.scroll(self._coord(attrs),
                            attrs.get("direction", "down"),
                            int(attrs.get("amount", "3")),
                            attrs.get("modifier"))
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

    def _compute_reward(self, terminated: bool) -> float:
        if not terminated:
            return 0.0
        if self._ctrl and self._ctrl.terminate_status == "success":
            return 1.0
        return 0.0


# Register
try:
    import skyrl_gym
    skyrl_gym.register("desktop:Desktop-v0", DesktopSkyRLEnv)
except (ImportError, Exception):
    pass
