"""End-to-end rollout: LLM driving the deployed NeMo Gym Jupyter agent.

NeMo Gym exposes the env as plain FastAPI endpoints + cookie-based sessions.
There's no SDK client to import; we just talk to the server with `requests`.

Server endpoints used:
    POST /seed_session                   -> sets a session cookie
    POST /add_and_execute_code_cell      -> {"code": "..."}    -> {"output": "..."}
    POST /edit_and_execute_current_cell  -> {"code": "..."}
    POST /execute_shell_command          -> {"command": "..."}
    POST /get_notebook_state             -> {"include_images": false}
    POST /final_answer                   -> {"answer": "..."}

Run:
    cd envs/jupyter_agent/nemo_gym
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

ENV_URL = os.environ.get("NEMO_GYM_URL", "https://AdithyaSK-jupyter-agent-nemo-gym.hf.space")
MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-Coder-480B-A35B-Instruct:together")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))

# Tool spec is hardcoded here (mirrors the server's request schemas).
# A more generic version could discover them from /openapi.json — see README.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_and_execute_code_cell",
            "description": "Run Python in the persistent notebook. Variables persist between cells.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Python source"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_and_execute_current_cell",
            "description": "Replace the last cell with new code and re-run.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_shell_command",
            "description": "Run a shell command inside the sandbox (e.g. 'pip install x').",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_notebook_state",
            "description": "Compact summary of executed cells.",
            "parameters": {
                "type": "object",
                "properties": {"include_images": {"type": "boolean", "default": False}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "final_answer",
            "description": "Submit the final answer for the task. Call when done.",
            "parameters": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        },
    },
]

TASK = (
    "Compute the mean and standard deviation of the list "
    "[12, 19, 23, 31, 7, 14, 28, 5, 22, 18] using NumPy. "
    "Print both values, then call `final_answer` with a concise summary."
)
SYSTEM = (
    "You are a Python data-analysis agent in a Jupyter notebook. Use the tools "
    "to execute code. Variables persist between cells. When done, call "
    "`final_answer` with a concise string."
)


def main() -> int:
    if ":" in MODEL:
        token = os.environ.get("HF_TOKEN")
        if not token:
            sys.exit("HF_TOKEN missing")
        llm = OpenAI(api_key=token, base_url="https://router.huggingface.co/v1")
        provider = "hf-router"
    else:
        token = os.environ.get("OPENAI_API_KEY")
        if not token:
            sys.exit("OPENAI_API_KEY missing")
        llm = OpenAI(api_key=token)
        provider = "openai"

    print("=" * 80)
    print(f"NeMo Gym server: {ENV_URL}")
    print(f"Provider:        {provider}")
    print(f"Model:           {MODEL}")
    print(f"Task:            {TASK}")
    print("=" * 80)

    # session: NeMo Gym uses cookies via /seed_session
    s = requests.Session()
    r = s.post(f"{ENV_URL}/seed_session", json={}, timeout=60)
    r.raise_for_status()
    print(f"\n[seed_session] {r.status_code}; cookies={dict(s.cookies)}\n")

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": TASK},
    ]

    for turn in range(1, MAX_TURNS + 1):
        print(f"──── turn {turn} ────────────────────────────────────────")
        r = llm.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, max_completion_tokens=512
        )
        msg = r.choices[0].message
        if msg.content:
            print(f"[assistant] {msg.content}")

        if not msg.tool_calls:
            print("[done] no tool calls.")
            break

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"[tool-call] {name}({args})")
            resp = s.post(f"{ENV_URL}/{name}", json=args, timeout=120)
            if not resp.ok:
                text = f"[HTTP {resp.status_code}] {resp.text[:300]}"
            else:
                payload = resp.json()
                text = payload.get("output", json.dumps(payload))
            print(f"[tool-result]\n{text}\n")
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "name": name, "content": text}
            )
    else:
        print(f"[hit MAX_TURNS={MAX_TURNS}]")

    print("\n" + "=" * 80)
    print("FINAL TRAJECTORY")
    print("=" * 80)
    for m in messages:
        role = m["role"]
        if role == "tool":
            print(f"[{role}:{m.get('name')}]\n{m['content']}\n")
        elif role == "assistant" and m.get("tool_calls"):
            calls = ", ".join(tc["function"]["name"] for tc in m["tool_calls"])
            print(f"[{role}] {(m.get('content') or '').strip()}  -> {calls}\n")
        else:
            print(f"[{role}] {m.get('content', '')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
