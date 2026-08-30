"""End-to-end rollout: LLM driving the deployed ORS Jupyter agent.

Pattern (mirrors the OpenReward Python SDK quickstart):

    from openreward import EnvironmentsAPI

    api = EnvironmentsAPI(base_url="https://AdithyaSK-jupyter-agent-ors.hf.space", api_key="")
    env = api.get("jupyteragentors")
    tasks = env.list_tasks("train")
    tools = env.list_tools()

    with env.session(task=tasks[0]) as session:
        prompt = session.get_prompt()
        out = session.call_tool("add_and_execute_code_cell", {"code": "print(2+2)"})
        # ToolOutput(blocks=[...], reward=..., finished=...)

The rollout loop:
    1. Pick a task from `train` split (override with TASK_INDEX env var).
    2. Open a session, get the task prompt.
    3. Auto-discover the env's tools, convert to OpenAI tool schema.
    4. Drive a multi-turn loop with Qwen-Coder via HF Router (or any OpenAI model
       if ROLLOUT_MODEL has no ":" suffix).
    5. After each tool call, accumulate `ToolOutput.reward`. Stop when
       `finished=True`, the model produces no tool call, or MAX_TURNS is hit.
    6. Print every step + final cumulative reward.

Run:
    cd 00-environments-101/envs/jupyter/ors
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
from openreward import EnvironmentsAPI

# ── config ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

ENV_URL = os.environ.get("ORS_URL", "https://AdithyaSK-jupyter-agent-ors.hf.space")
ENV_NAME = os.environ.get("ORS_ENV_NAME", "jupyteragentors")
SPLIT = os.environ.get("ORS_SPLIT", "train")
TASK_INDEX = int(os.environ.get("TASK_INDEX", "0"))
MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-Coder-480B-A35B-Instruct:together")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "8"))

SYSTEM = (
    "You are a Python data-analysis agent running in a Jupyter notebook. "
    "Use the provided tools to execute code in the notebook. Variables persist "
    "between cells. When you have the answer, call the `final_answer` tool with "
    "a concise string and then stop calling tools."
)


def ors_tools_to_openai(tools) -> list[dict]:
    """ToolSpec(name, description, input_schema) -> OpenAI tool schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema or {"type": "object", "properties": {}},
            },
        }
        for t in tools
    ]


def blocks_to_text(blocks) -> str:
    """Flatten a list of TextBlock/ImageBlock to plain text."""
    return "\n".join(getattr(b, "text", str(b)) for b in (blocks or []))


def main() -> int:
    # provider auto-detect (HF Router if "<repo>:<provider>", else OpenAI native)
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
    print(f"ORS server: {ENV_URL}")
    print(f"Env name:   {ENV_NAME}")
    print(f"Split:      {SPLIT}  task_index={TASK_INDEX}")
    print(f"Provider:   {provider}")
    print(f"Model:      {MODEL}")
    print("=" * 80)

    api = EnvironmentsAPI(base_url=ENV_URL, api_key="")
    env = api.get(ENV_NAME)

    tasks = env.list_tasks(SPLIT)
    print(f"\n{len(tasks)} tasks in '{SPLIT}' split. Using task #{TASK_INDEX}.")
    task = tasks[TASK_INDEX]

    tools = ors_tools_to_openai(env.list_tools())
    print(f"Discovered {len(tools)} tools: {[t['function']['name'] for t in tools]}\n")

    with env.session(task=task) as session:
        prompt_blocks = session.get_prompt()
        user_msg = blocks_to_text(prompt_blocks)
        print(f"[task] {user_msg}\n")

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ]
        cumulative_reward = 0.0
        finished = False

        for turn in range(1, MAX_TURNS + 1):
            print(f"──── turn {turn} ────────────────────────────────────────")
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
                print("[done] no tool calls, stopping.")
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

                out = session.call_tool(name, args)  # ToolOutput
                text = blocks_to_text(out.blocks)
                cumulative_reward += float(out.reward or 0.0)
                print(f"[tool-result reward={out.reward} finished={out.finished}]\n{text}\n")

                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "name": name, "content": text}
                )
                if out.finished:
                    finished = True

            if finished:
                print("[done] env reported finished=True, stopping.")
                break
        else:
            print(f"[hit MAX_TURNS={MAX_TURNS}]")

    print("\n" + "=" * 80)
    print(f"FINAL  cumulative_reward={cumulative_reward}  finished={finished}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
