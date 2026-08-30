"""End-to-end rollout: OpenAI `computer-use-preview` driving the Desktop OpenEnv.

Uses the OpenAI Responses API. The model emits `computer_call` items whose
`action.type` is one of: click, double_click, drag, keypress, move, screenshot,
scroll, type, wait. Each is translated to an MCP tool call against the local
desktop env, and the resulting screenshot is returned as a `computer_call_output`.

Run:
    cd 00-environments-101/envs/desktop/openenv
    uv run uvicorn server.app:app --port 8771 --host 127.0.0.1 &   # if not already
    uv run python rollout_openai.py
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from openenv.core.env_server.mcp_types import CallToolAction
from openenv.core.mcp_client import MCPToolClient

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

ENV_URL = os.environ.get("OPENENV_URL", "http://127.0.0.1:8771")
APP = os.environ.get("APP", "firefox")
RESOLUTION = (
    int(os.environ.get("WIDTH", "1024")),
    int(os.environ.get("HEIGHT", "768")),
)
MAX_TURNS = int(os.environ.get("MAX_TURNS", "8"))
TASK = os.environ.get(
    "TASK",
    "Open the Firefox browser if it isn't focused, then navigate to https://example.com. "
    "When the page is fully loaded and you can see 'Example Domain', take one final "
    "screenshot and stop emitting actions.",
)


def _call(env, name: str, **kwargs):
    """Call MCP tool, return the raw FastMCP result dict (content + data)."""
    out = env.step(CallToolAction(tool_name=name, arguments=kwargs))
    return out.observation.result or {}


def _b64_screenshot(env) -> str:
    """Take a screenshot via the env and return base64 PNG bytes."""
    res = _call(env, "screenshot")
    for c in res.get("content", []) or []:
        if c.get("type") == "image" and c.get("data"):
            return c["data"]
    raise RuntimeError(f"screenshot tool returned no image content: {res}")


def _map_action_to_tool_call(env, action) -> None:
    """Translate OpenAI computer_use action -> MCP tool call against our env."""
    a = action.type
    if a == "screenshot":
        _call(env,"screenshot")
    elif a == "click":
        button = getattr(action, "button", "left")
        modifier = "+".join(getattr(action, "keys", []) or []) or None
        tool = {"left": "left_click", "middle": "middle_click", "right": "right_click"}.get(button, "left_click")
        _call(env,tool, coordinate=[int(action.x), int(action.y)], text=modifier)
    elif a == "double_click":
        modifier = "+".join(getattr(action, "keys", []) or []) or None
        _call(env,"double_click", coordinate=[int(action.x), int(action.y)], text=modifier)
    elif a == "move":
        _call(env,"mouse_move", coordinate=[int(action.x), int(action.y)])
    elif a == "drag":
        path = list(action.path or [])
        if len(path) >= 2:
            sx, sy = path[0]["x"], path[0]["y"]
            ex, ey = path[-1]["x"], path[-1]["y"]
            _call(env,"left_click_drag",
                          start_coordinate=[int(sx), int(sy)],
                          coordinate=[int(ex), int(ey)])
    elif a == "scroll":
        sx = getattr(action, "scrollX", 0) or 0
        sy = getattr(action, "scrollY", 0) or 0
        # OpenAI scroll uses pixel delta; map sign+magnitude to direction+amount
        if abs(sy) >= abs(sx):
            direction = "down" if sy > 0 else "up"
            amount = max(1, abs(int(sy)) // 100)
        else:
            direction = "right" if sx > 0 else "left"
            amount = max(1, abs(int(sx)) // 100)
        modifier = "+".join(getattr(action, "keys", []) or []) or None
        _call(env,"scroll",
                      coordinate=[int(action.x), int(action.y)],
                      scroll_direction=direction,
                      scroll_amount=amount,
                      text=modifier)
    elif a == "keypress":
        keys = list(action.keys or [])
        _call(env,"key", keys="+".join(keys))
    elif a == "type":
        _call(env,"type", text=action.text)
    elif a == "wait":
        _call(env,"wait", duration=1.0)
    else:
        print(f"[warn] unhandled action type: {a}")


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY missing in repo-root .env")
    client = OpenAI(api_key=api_key)

    print("=" * 80)
    print(f"OpenEnv server : {ENV_URL}")
    print(f"App / res      : {APP}  {RESOLUTION[0]}x{RESOLUTION[1]}")
    print(f"Model          : computer-use-preview (OpenAI Responses API)")
    print(f"Task           : {TASK[:100]}...")
    print("=" * 80)

    with MCPToolClient(base_url=ENV_URL).sync() as env:
        env.reset(app=APP, resolution=list(RESOLUTION))
        print(f"[env] sandbox reset done ({APP})\n")

        # Prime with the user task and an initial screenshot.
        b64 = _b64_screenshot(env)
        input_items: list[dict[str, Any]] = [
            {"role": "user", "content": [
                {"type": "input_text", "text": TASK},
                {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"},
            ]},
        ]

        tools = [{
            "type": "computer_use_preview",
            "display_width": RESOLUTION[0],
            "display_height": RESOLUTION[1],
            "environment": "linux",
        }]

        previous_id = None
        finished = False
        for turn in range(1, MAX_TURNS + 1):
            print(f"──── turn {turn} ────────────────────────────────────────")
            r = client.responses.create(
                model="computer-use-preview",
                input=input_items,
                tools=tools,
                truncation="auto",
                previous_response_id=previous_id,
            )
            previous_id = r.id

            calls = [item for item in r.output if getattr(item, "type", "") == "computer_call"]
            messages = [item for item in r.output if getattr(item, "type", "") == "message"]
            for m in messages:
                for c in getattr(m, "content", []) or []:
                    if getattr(c, "type", "") == "output_text":
                        print(f"[assistant] {c.text}")

            if not calls:
                print("[done] no computer_call returned — model finished.")
                finished = True
                break

            input_items = []  # subsequent turns: only feed new outputs
            for call in calls:
                action = call.action
                print(f"[action] {action.type}({getattr(action, '__dict__', {})})")
                try:
                    _map_action_to_tool_call(env, action)
                except Exception as e:
                    print(f"[error] {e}")
                # Always send a fresh screenshot back
                b64 = _b64_screenshot(env)
                input_items.append({
                    "type": "computer_call_output",
                    "call_id": call.call_id,
                    "output": {"type": "computer_screenshot",
                               "image_url": f"data:image/png;base64,{b64}"},
                })
        else:
            print(f"[hit MAX_TURNS={MAX_TURNS}]")

        print("\n" + "=" * 80)
        print(f"FINAL  finished={finished}")
        print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
