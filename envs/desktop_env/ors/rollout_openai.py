"""ORS rollout: OpenAI `computer-use-preview` driving the Desktop ORS env.

Same loop as `envs/desktop_env/openenv/rollout_openai.py` but using the
official `openreward` client.

Run:
    cd envs/desktop_env/ors
    uv run python server.py --port 8772 --host 127.0.0.1 &
    uv run python rollout_openai.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from openreward import EnvironmentsAPI

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

ENV_URL = os.environ.get("ORS_URL", "http://127.0.0.1:8772")
ENV_NAME = os.environ.get("ORS_ENV_NAME", "desktopors")
SPLIT = os.environ.get("ORS_SPLIT", "train")
TASK_INDEX = int(os.environ.get("TASK_INDEX", "0"))
MAX_TURNS = int(os.environ.get("MAX_TURNS", "8"))


def _shot_b64(session) -> str:
    out = session.call_tool("screenshot", {})
    for b in out.blocks or []:
        if getattr(b, "type", "") == "image":
            return b.data
    raise RuntimeError(f"screenshot returned no image: {out}")


def _map_action(session, action) -> None:
    a = action.type
    if a == "screenshot":
        session.call_tool("screenshot", {})
    elif a == "click":
        button = getattr(action, "button", "left")
        modifier = "+".join(getattr(action, "keys", []) or []) or None
        tool = {"left": "left_click", "middle": "middle_click", "right": "right_click"}.get(button, "left_click")
        session.call_tool(tool, {"coordinate": [int(action.x), int(action.y)], "text": modifier})
    elif a == "double_click":
        modifier = "+".join(getattr(action, "keys", []) or []) or None
        session.call_tool("double_click", {"coordinate": [int(action.x), int(action.y)], "text": modifier})
    elif a == "move":
        session.call_tool("mouse_move", {"coordinate": [int(action.x), int(action.y)]})
    elif a == "drag":
        path = list(action.path or [])
        if len(path) >= 2:
            sx, sy = path[0]["x"], path[0]["y"]
            ex, ey = path[-1]["x"], path[-1]["y"]
            session.call_tool("left_click_drag", {
                "start_coordinate": [int(sx), int(sy)],
                "coordinate": [int(ex), int(ey)],
            })
    elif a == "scroll":
        sx = getattr(action, "scrollX", 0) or 0
        sy = getattr(action, "scrollY", 0) or 0
        if abs(sy) >= abs(sx):
            direction = "down" if sy > 0 else "up"
            amount = max(1, abs(int(sy)) // 100)
        else:
            direction = "right" if sx > 0 else "left"
            amount = max(1, abs(int(sx)) // 100)
        modifier = "+".join(getattr(action, "keys", []) or []) or None
        session.call_tool("scroll", {
            "coordinate": [int(action.x), int(action.y)],
            "scroll_direction": direction,
            "scroll_amount": amount,
            "text": modifier,
        })
    elif a == "keypress":
        keys = list(action.keys or [])
        session.call_tool("key", {"keys": "+".join(keys)})
    elif a == "type":
        session.call_tool("type", {"text": action.text})
    elif a == "wait":
        session.call_tool("wait", {"duration": 1.0})
    else:
        print(f"[warn] unhandled action type: {a}")


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY missing in repo-root .env")
    client = OpenAI(api_key=api_key)

    print("=" * 80)
    print(f"ORS server : {ENV_URL}")
    print(f"Env / split: {ENV_NAME}/{SPLIT} task_index={TASK_INDEX}")
    print(f"Model      : computer-use-preview (OpenAI Responses API)")
    print("=" * 80)

    api = EnvironmentsAPI(base_url=ENV_URL, api_key="")
    env = api.get(ENV_NAME)
    tasks = env.list_tasks(SPLIT)
    task = tasks[TASK_INDEX]
    print(f"\nTask spec: {task.task_spec}\n")

    width, height = task.task_spec.get("resolution", [1024, 768])
    instruction = task.task_spec.get("instruction", "Use the desktop tools to complete the task.")

    with env.session(task=task) as session:
        prompt_blocks = session.get_prompt()
        prompt_text = "\n".join(getattr(b, "text", "") for b in (prompt_blocks or []) if getattr(b, "type", "") == "text")
        print(f"[prompt] {prompt_text[:240]}...\n")

        b64 = _shot_b64(session)
        input_items: list[dict[str, Any]] = [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": instruction},
                {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"},
            ],
        }]
        tools = [{
            "type": "computer_use_preview",
            "display_width": width,
            "display_height": height,
            "environment": "linux",
        }]

        previous_id = None
        cumulative_reward = 0.0
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
            for m in r.output:
                if getattr(m, "type", "") == "message":
                    for c in getattr(m, "content", []) or []:
                        if getattr(c, "type", "") == "output_text":
                            print(f"[assistant] {c.text}")

            if not calls:
                print("[done] no computer_call returned.")
                finished = True
                break

            input_items = []
            for call in calls:
                action = call.action
                print(f"[action] {action.type}({getattr(action, '__dict__', {})})")
                try:
                    _map_action(session, action)
                except Exception as e:
                    print(f"[error] {e}")
                b64 = _shot_b64(session)
                input_items.append({
                    "type": "computer_call_output",
                    "call_id": call.call_id,
                    "output": {
                        "type": "computer_screenshot",
                        "image_url": f"data:image/png;base64,{b64}",
                    },
                })
        else:
            print(f"[hit MAX_TURNS={MAX_TURNS}]")

        print("\n" + "=" * 80)
        print(f"FINAL  finished={finished}  cumulative_reward={cumulative_reward}")
        print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
