"""End-to-end rollout: Qwen3-VL via HF Router driving the NeMo Gym Desktop env.

NeMo Gym exposes the env as plain FastAPI endpoints + cookie-based sessions.
There's no SDK client; we just talk to the server with `requests`.

Run:
    cd envs/desktop_env/nemo_gym
    uv sync
    uv run python rollout.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

ENV_URL = os.environ.get("NEMO_GYM_URL", "http://127.0.0.1:11000")
MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-VL-8B-Instruct:novita")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))
APP = os.environ.get("APP", "firefox")
RESOLUTION = [int(os.environ.get("WIDTH", "1024")), int(os.environ.get("HEIGHT", "768"))]

# Tool definitions for the chat-completions API.
TOOLS = [
    {"type": "function", "function": {"name": "screenshot",
        "description": "Capture the current screen (returns image).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "left_click",
        "description": "Left click at coordinate=[x,y].",
        "parameters": {"type": "object", "properties": {
            "coordinate": {"type": "array", "items": {"type": "integer"}},
            "text": {"type": "string", "description": "modifier (shift/ctrl/etc)"}},
            "required": ["coordinate"]}}},
    {"type": "function", "function": {"name": "double_click",
        "description": "Double click at coordinate=[x,y].",
        "parameters": {"type": "object", "properties": {
            "coordinate": {"type": "array", "items": {"type": "integer"}}},
            "required": ["coordinate"]}}},
    {"type": "function", "function": {"name": "type",
        "description": "Type text at the current cursor position.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
            "required": ["text"]}}},
    {"type": "function", "function": {"name": "key",
        "description": "Press a key or combo, e.g. 'enter' or 'ctrl+s'.",
        "parameters": {"type": "object", "properties": {"keys": {"type": "string"}},
            "required": ["keys"]}}},
    {"type": "function", "function": {"name": "scroll",
        "description": "Scroll at coordinate in scroll_direction by scroll_amount clicks.",
        "parameters": {"type": "object", "properties": {
            "coordinate": {"type": "array", "items": {"type": "integer"}},
            "scroll_direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
            "scroll_amount": {"type": "integer"}},
            "required": ["coordinate", "scroll_direction", "scroll_amount"]}}},
    {"type": "function", "function": {"name": "wait",
        "description": "Pause for `duration` seconds.",
        "parameters": {"type": "object", "properties": {"duration": {"type": "number"}},
            "required": ["duration"]}}},
    {"type": "function", "function": {"name": "terminate",
        "description": "End the episode. status=success|failure.",
        "parameters": {"type": "object", "properties": {"status": {"type": "string"}},
            "required": ["status"]}}},
]

SYSTEM = (
    "You are a vision-capable computer-use agent on a Linux desktop. The user "
    "message includes a screenshot. Decide what to do, call exactly ONE tool. "
    "Coordinates are absolute pixels [x, y]. End with terminate(status='success')."
)


def main() -> int:
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN missing in repo-root .env")
    llm = OpenAI(api_key=token, base_url="https://router.huggingface.co/v1")

    session = requests.Session()
    print("=" * 80)
    print(f"NeMo Gym server: {ENV_URL}")
    print(f"Model:           {MODEL}")
    print("=" * 80)

    r = session.post(f"{ENV_URL}/seed_session", json={})
    r.raise_for_status()
    print(f"[seed] {r.status_code}")

    r = session.post(f"{ENV_URL}/reset", json={"app": APP, "resolution": RESOLUTION})
    r.raise_for_status()
    print(f"[reset] {r.json().get('output')}")

    def call(name, **kwargs):
        r = session.post(f"{ENV_URL}/{name}", json=kwargs)
        r.raise_for_status()
        return r.json()

    initial = call("screenshot")
    b64 = initial.get("image_b64") or ""

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": (
                f"You are looking at {APP} on a Linux desktop "
                f"({RESOLUTION[0]}x{RESOLUTION[1]}). Open the URL bar, navigate to "
                "https://example.com, and confirm 'Example Domain' is visible — "
                "then call terminate(status='success')."
            )},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]

    finished = False
    for turn in range(1, MAX_TURNS + 1):
        print(f"──── turn {turn} ────────────────────────────")
        r = llm.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS,
                                        tool_choice="auto", max_completion_tokens=512)
        msg = r.choices[0].message
        if msg.content:
            print(f"[assistant] {msg.content[:200]}")
        if not msg.tool_calls:
            break
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name,
                                         "arguments": tc.function.arguments}}
                            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"[tool-call] {name}({args})")
            res = call(name, **args)
            text = res.get("output", "")
            print(f"[tool-result] {text[:160]}")
            if name == "terminate":
                finished = True
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": name, "content": text})
        if finished:
            break
        # Refresh screenshot for next turn
        shot = call("screenshot")
        new_b64 = shot.get("image_b64") or ""
        messages.append({"role": "user", "content": [
            {"type": "text", "text": "Latest screenshot:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{new_b64}"}},
        ]})
    print(f"\nFINAL  finished={finished}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
