"""End-to-end rollout: LLM driving the in-process Verifiers Jupyter agent.

Verifiers is in-process — there's no server. Tools are plain Python functions
imported from `env.py`. We drive the multi-turn loop manually with the openai
client (Qwen via HF Router by default).

Two ways to consume Verifiers envs:

    A) Native verifiers (`vf.ToolEnv` + `env.evaluate(client, model)`) — verifiers
       owns the loop. Good for verifiers-native users.

    B) Manual rollout (this file) — import the tool functions directly, build
       OpenAI tool schemas from their signatures + docstrings, drive the loop
       yourself. Same code transitions cleanly to TRL training as
       `environment_factory=JupyterToolkit`.

Run:
    cd 00-environments-101/envs/jupyter/verifiers
    uv sync
    uv run python rollout.py
"""
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

# Import the 4 tool functions from the env module.
from env import (  # noqa: E402
    TOOL_FUNCTIONS,
    add_and_execute_code_cell,
    edit_and_execute_current_cell,
    execute_shell_command,
    get_notebook_state,
)

MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-Coder-480B-A35B-Instruct:together")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))

TASK = (
    "Compute the mean and standard deviation of the list "
    "[12, 19, 23, 31, 7, 14, 28, 5, 22, 18] using NumPy. "
    "Print both values, then end your reply with the line: "
    "FINAL: mean=<m>, std=<s>"
)
SYSTEM = (
    "You are a Python data-analysis agent in a Jupyter notebook. Use the tools "
    "to execute code. Variables persist between cells. When done, end your "
    "final assistant message with a line starting `FINAL:` and stop calling tools."
)


def func_to_openai_tool(fn) -> dict:
    """Build an OpenAI tool schema from a plain Python function's signature + docstring."""
    sig = inspect.signature(fn)
    doc = (fn.__doc__ or "").strip()
    description = doc.split("\n\n")[0].strip()  # first paragraph as description

    properties: dict = {}
    required: list[str] = []
    for name, p in sig.parameters.items():
        ann = p.annotation
        json_type = "string"
        if ann is int:
            json_type = "integer"
        elif ann is float:
            json_type = "number"
        elif ann is bool:
            json_type = "boolean"
        properties[name] = {"type": json_type, "description": f"{name}"}
        if p.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOL_TABLE = {fn.__name__: fn for fn in TOOL_FUNCTIONS}


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

    if not os.environ.get("E2B_API_KEY"):
        sys.exit("E2B_API_KEY missing in .env (Verifiers runs the sandbox in-process)")

    print("=" * 80)
    print(f"Verifiers env: in-process (sandbox = E2B)")
    print(f"Provider:      {provider}")
    print(f"Model:         {MODEL}")
    print(f"Tools:         {list(TOOL_TABLE.keys())}")
    print(f"Task:          {TASK}")
    print("=" * 80)

    tools = [func_to_openai_tool(fn) for fn in TOOL_FUNCTIONS]
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": TASK},
    ]

    for turn in range(1, MAX_TURNS + 1):
        print(f"\n──── turn {turn} ────────────────────────────────────────")
        r = llm.chat.completions.create(
            model=MODEL, messages=messages, tools=tools, max_completion_tokens=512
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
            try:
                result = TOOL_TABLE[name](**args)
            except Exception as e:
                result = f"Tool error: {type(e).__name__}: {e}"
            text = result if isinstance(result, str) else json.dumps(result)
            print(f"[tool-result]\n{text}\n")
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "name": name, "content": text}
            )
    else:
        print(f"[hit MAX_TURNS={MAX_TURNS}]")

    # cleanup: close the sandbox if it was created
    try:
        from env import _shared_sandbox  # noqa: F401
        if _shared_sandbox is not None:
            _shared_sandbox.close()
            print("\n[cleanup] E2B sandbox closed.")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
