"""End-to-end rollout: Qwen-Coder via HF Router talking to the OpenEnv Jupyter agent.

Pattern:
    1. Connect to the OpenEnv server (deployed on HF Spaces by default).
    2. Auto-discover the MCP tools the server exposes.
    3. Convert MCP tool schemas to OpenAI tool schemas.
    4. Drive a multi-turn loop with Qwen3-Coder via the openai client pointed
       at the HF Router (https://router.huggingface.co/v1).
    5. Print every step of the trajectory.

Reads HF_TOKEN from the repo-root .env. No E2B key needed on the client side
because the deployed Space owns the sandbox.

Run:
    cd envs/jupyter_agent/openenv
    uv sync
    uv run python rollout.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from openenv.core.mcp_client import MCPToolClient

# ── config ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

ENV_URL = os.environ.get("OPENENV_URL", "https://AdithyaSK-jupyter-agent-openenv.hf.space")
MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-Coder-480B-A35B-Instruct:together")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))

TASK = (
    "Compute the mean and standard deviation of the list "
    "[12, 19, 23, 31, 7, 14, 28, 5, 22, 18] using NumPy. "
    "Print both values, then stop."
)

SYSTEM = (
    "You are a Python data-analysis agent running in a Jupyter notebook. "
    "Use the provided tools to execute code in the notebook. Variables persist "
    "between cells. When you have the final answer, call the `final_answer` "
    "tool with a concise string. Do not stop without calling `final_answer`."
)


def mcp_tools_to_openai(mcp_tools) -> list[dict]:
    """Convert MCP tool list (with .name, .description, .input_schema) to OpenAI tool schema."""
    out = []
    for t in mcp_tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.input_schema or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def main() -> int:
    # Pick provider by model name: "<repo>:<provider>" -> HF Router; otherwise -> OpenAI native.
    if ":" in MODEL:
        token = os.environ.get("HF_TOKEN")
        if not token:
            sys.exit("HF_TOKEN missing in .env at repo root")
        llm = OpenAI(api_key=token, base_url="https://router.huggingface.co/v1")
        provider = "hf-router"
    else:
        token = os.environ.get("OPENAI_API_KEY")
        if not token:
            sys.exit("OPENAI_API_KEY missing in .env at repo root")
        llm = OpenAI(api_key=token)
        provider = "openai"

    print("=" * 80)
    print(f"OpenEnv server: {ENV_URL}")
    print(f"Provider:       {provider}")
    print(f"Model:          {MODEL}")
    print(f"Task:           {TASK}")
    print("=" * 80)

    with MCPToolClient(base_url=ENV_URL).sync() as env:
        env.reset()
        tools = mcp_tools_to_openai(env.list_tools())
        print(f"\nDiscovered {len(tools)} tools: {[t['function']['name'] for t in tools]}\n")

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": TASK},
        ]

        for turn in range(1, MAX_TURNS + 1):
            print(f"\n──── turn {turn} ────────────────────────────────────────")
            r = llm.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                max_completion_tokens=512,
            )
            msg = r.choices[0].message

            if msg.content:
                print(f"[assistant] {msg.content}")

            if not msg.tool_calls:
                print("\n[done] no tool calls, stopping.")
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
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

                result = env.call_tool(name, **args)
                # MCPToolClient.call_tool flattens content blocks to a plain string.
                text = result if isinstance(result, str) else str(result)
                print(f"[tool-result]\n{text}\n")

                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "name": name, "content": text}
                )
        else:
            print(f"\n[hit max_turns={MAX_TURNS}]")

    print("\n" + "=" * 80)
    print("FINAL TRAJECTORY")
    print("=" * 80)
    for m in messages:
        role = m["role"]
        if role == "tool":
            print(f"[{role}:{m.get('name')}]\n{m['content']}\n")
        elif role == "assistant" and m.get("tool_calls"):
            calls = ", ".join(tc["function"]["name"] for tc in m["tool_calls"])
            print(f"[{role}] {(m.get('content') or '').strip()}  -> tool_calls: {calls}\n")
        else:
            print(f"[{role}] {m.get('content', '')}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
