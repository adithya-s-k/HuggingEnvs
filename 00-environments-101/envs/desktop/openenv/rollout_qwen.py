"""End-to-end rollout: Qwen3-VL (via HF Router) driving the Desktop OpenEnv.

Unlike OpenAI's computer-use-preview, Qwen3-VL has no built-in computer-use
tool schema — it just function-calls whatever tools we expose. We hand it
the env's MCP tools converted to OpenAI's function-calling format and feed
the current screenshot as an image in each user turn.

Run:
    cd 00-environments-101/envs/desktop/openenv
    uv run uvicorn server.app:app --port 8771 --host 127.0.0.1 &
    uv run python rollout_qwen.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

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
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))
MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-VL-8B-Instruct:novita")
TASK = os.environ.get(
    "TASK",
    "You are looking at a Linux desktop with Firefox. Click the URL bar at the top "
    "of Firefox, type https://example.com and press enter. When you see the "
    "'Example Domain' page, call the `terminate` tool with status='success'.",
)

SYSTEM = (
    "You are a vision-capable computer-use agent. The user message includes a screenshot "
    "of a Linux desktop. Decide what to do next, then call exactly ONE tool. "
    "Coordinates are absolute pixel positions in the screen, given as a [x, y] array. "
    "After each tool call, you'll receive the next screenshot. When the task is "
    "complete, call terminate(status='success'). If stuck, call terminate(status='failure')."
)


def _call(env, name: str, **kwargs):
    out = env.step(CallToolAction(tool_name=name, arguments=kwargs))
    return out.observation.result or {}


def _b64_screenshot(env) -> str:
    res = _call(env, "screenshot")
    for c in res.get("content", []) or []:
        if c.get("type") == "image" and c.get("data"):
            return c["data"]
    raise RuntimeError(f"screenshot returned no image: {res}")


def _result_text(res: dict) -> str:
    parts = []
    for c in res.get("content", []) or []:
        if c.get("type") == "text" and c.get("text"):
            parts.append(c["text"])
        elif c.get("type") == "image":
            parts.append("(image returned)")
    return "\n".join(parts) or "(no output)"


def _list_tools_as_openai(env) -> list[dict]:
    """Return env's MCP tools in OpenAI function-calling format."""
    tools = env.list_tools()
    out = []
    for t in tools:
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": (t.description or "").strip()[:1024],
                "parameters": t.input_schema or {"type": "object", "properties": {}},
            },
        })
    return out


def _user_with_screenshot(text: str, b64: str) -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ],
    }


def main() -> int:
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN missing in repo-root .env")
    llm = OpenAI(api_key=token, base_url="https://router.huggingface.co/v1")

    print("=" * 80)
    print(f"OpenEnv server : {ENV_URL}")
    print(f"App / res      : {APP}  {RESOLUTION[0]}x{RESOLUTION[1]}")
    print(f"Model          : {MODEL}  (HF Router)")
    print(f"Task           : {TASK[:100]}...")
    print("=" * 80)

    with MCPToolClient(base_url=ENV_URL).sync() as env:
        env.reset(app=APP, resolution=list(RESOLUTION))
        print(f"[env] sandbox reset done ({APP})")
        tools = _list_tools_as_openai(env)
        print(f"[env] {len(tools)} tools exposed to model\n")

        b64 = _b64_screenshot(env)
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM},
            _user_with_screenshot(TASK, b64),
        ]
        terminate_status = None

        for turn in range(1, MAX_TURNS + 1):
            print(f"──── turn {turn} ────────────────────────────────────────")
            r = llm.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_completion_tokens=512,
            )
            msg = r.choices[0].message
            if msg.content:
                print(f"[assistant] {msg.content[:300]}")

            if not msg.tool_calls:
                print("[done] no tool calls.")
                break

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                } for tc in msg.tool_calls],
            })

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                print(f"[tool-call] {name}({args})")
                try:
                    result = _call(env, name, **args)
                    text = _result_text(result)
                except Exception as e:
                    text = f"ERROR: {e}"
                print(f"[tool-result] {text[:160]}")
                if name == "terminate":
                    terminate_status = args.get("status")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": text,
                })

            if terminate_status is not None:
                print(f"[done] terminate({terminate_status})")
                break

            # Append a fresh screenshot for the next turn
            b64 = _b64_screenshot(env)
            messages.append(_user_with_screenshot("Here is the latest screenshot.", b64))
        else:
            print(f"[hit MAX_TURNS={MAX_TURNS}]")

        print("\n" + "=" * 80)
        print(f"FINAL  terminate_status={terminate_status}")
        print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
