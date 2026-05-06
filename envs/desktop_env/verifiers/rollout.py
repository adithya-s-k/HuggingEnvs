"""End-to-end rollout: Qwen3-VL via HF Router driving the in-process Verifiers Desktop env.

In-process means the rollout itself owns the E2B Desktop sandbox — `E2B_API_KEY`
is required. Tools are plain Python functions; OpenAI schemas are auto-built
from signatures + docstrings.

Run:
    cd envs/desktop_env/verifiers
    uv sync
    uv run python rollout.py
"""
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path
from typing import get_type_hints, get_args, get_origin

from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

from env import DesktopToolkit, TOOL_FUNCTIONS  # noqa: E402

MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-VL-8B-Instruct:novita")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "5"))
APP = os.environ.get("APP", "firefox")

SYSTEM = (
    "You are a vision-capable computer-use agent on a Linux desktop. The user "
    "message includes the latest screenshot. Decide what to do next, then call "
    "exactly ONE tool. Coordinates are absolute pixels [x, y]. End the episode "
    "with terminate(status='success' or 'failure')."
)
TASK = (
    "Use Firefox to navigate to https://example.com. When the page shows "
    "'Example Domain', call terminate(status='success')."
)


def func_to_openai_tool(fn) -> dict:
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    doc = (fn.__doc__ or "").strip().split("\n\n")[0].strip()
    properties, required = {}, []
    for name, p in sig.parameters.items():
        ann = hints.get(name, str)
        origin = get_origin(ann)
        if origin in (list, "list"):
            inner = get_args(ann)
            sub = inner[0] if inner else int
            properties[name] = {
                "type": "array",
                "items": {"type": "integer" if sub is int else "string"},
            }
        elif ann is int:
            properties[name] = {"type": "integer"}
        elif ann is float:
            properties[name] = {"type": "number"}
        elif ann is bool:
            properties[name] = {"type": "boolean"}
        else:
            properties[name] = {"type": "string"}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": doc,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def main() -> int:
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN missing")
    if not os.environ.get("E2B_API_KEY"):
        sys.exit("E2B_API_KEY missing — Verifiers runs the sandbox in-process")
    llm = OpenAI(api_key=token, base_url="https://router.huggingface.co/v1")

    print("=" * 80)
    print(f"Verifiers env: in-process (E2B Desktop)")
    print(f"Model:         {MODEL}")
    print(f"App:           {APP}")
    print("=" * 80)

    # Use the DesktopToolkit directly so we can grab the screenshot bytes
    kit = DesktopToolkit(app=APP)
    kit.initialize()

    # Convert the kit's bound methods to OpenAI tool schemas
    tool_methods = {
        "screenshot": kit.screenshot, "left_click": kit.left_click,
        "double_click": kit.double_click, "type": kit.type, "key": kit.key,
        "scroll": kit.scroll, "wait": kit.wait, "terminate": kit.terminate,
    }
    tools = [func_to_openai_tool(fn) for fn in tool_methods.values()]

    # Initial screenshot for the model
    text, b64 = kit._ctrl.screenshot()
    messages: list = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": TASK},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]

    finished = False
    try:
        for turn in range(1, MAX_TURNS + 1):
            print(f"──── turn {turn} ────────────────────────────")
            r = llm.chat.completions.create(model=MODEL, messages=messages, tools=tools,
                                            tool_choice="auto", max_completion_tokens=512)
            msg = r.choices[0].message
            if msg.content:
                print(f"[assistant] {msg.content[:200]}")
            if not msg.tool_calls:
                break
            messages.append({"role": "assistant", "content": msg.content or "",
                "tool_calls": [{"id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                print(f"[tool-call] {name}({args})")
                fn = tool_methods.get(name)
                if fn is None:
                    text = f"unknown tool {name}"
                else:
                    try:
                        text = fn(**args)
                    except Exception as e:
                        text = f"ERROR: {e}"
                print(f"[tool-result] {str(text)[:160]}")
                messages.append({"role": "tool", "tool_call_id": tc.id, "name": name,
                                 "content": str(text)})
                if name == "terminate":
                    finished = True
            if finished:
                break
            # Refresh screenshot for the next turn
            _, new_b64 = kit._ctrl.screenshot()
            messages.append({"role": "user", "content": [
                {"type": "text", "text": "Latest screenshot:"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{new_b64}"}},
            ]})
        print(f"\nFINAL  finished={finished}  terminate_status={kit.terminate_status}")
    finally:
        kit.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
