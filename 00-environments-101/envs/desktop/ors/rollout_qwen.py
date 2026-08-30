"""ORS rollout: Qwen3-VL via HF Router driving the Desktop ORS env.

Run:
    cd 00-environments-101/envs/desktop/ors
    uv run python server.py --port 8772 --host 127.0.0.1 &
    uv run python rollout_qwen.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from openreward import EnvironmentsAPI

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

ENV_URL = os.environ.get("ORS_URL", "http://127.0.0.1:8772")
ENV_NAME = os.environ.get("ORS_ENV_NAME", "desktopors")
SPLIT = os.environ.get("ORS_SPLIT", "train")
TASK_INDEX = int(os.environ.get("TASK_INDEX", "0"))
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))
MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-VL-8B-Instruct:novita")

SYSTEM = (
    "You are a vision-capable computer-use agent. Each user message includes a screenshot "
    "of a Linux desktop. Decide what to do next, then call exactly ONE tool. "
    "Coordinates are absolute pixel positions in the screen, given as a [x, y] array. "
    "After each tool call, you'll receive the next screenshot. When the task is "
    "complete, call terminate(status='success'). If stuck, call terminate(status='failure')."
)


def _shot_b64(session) -> str:
    out = session.call_tool("screenshot", {})
    for b in out.blocks or []:
        if getattr(b, "type", "") == "image":
            return b.data
    raise RuntimeError(f"screenshot returned no image: {out}")


def _result_text(out) -> str:
    parts = []
    for b in out.blocks or []:
        if getattr(b, "type", "") == "text":
            parts.append(b.text)
        elif getattr(b, "type", "") == "image":
            parts.append("(image returned)")
    return "\n".join(parts) or "(no output)"


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
    print(f"ORS server : {ENV_URL}")
    print(f"Env / split: {ENV_NAME}/{SPLIT} task_index={TASK_INDEX}")
    print(f"Model      : {MODEL}  (HF Router)")
    print("=" * 80)

    api = EnvironmentsAPI(base_url=ENV_URL, api_key="")
    env = api.get(ENV_NAME)
    tasks = env.list_tasks(SPLIT)
    task = tasks[TASK_INDEX]
    instruction = task.task_spec.get("instruction", "Use the desktop tools to complete the task.")
    print(f"\nTask spec: {task.task_spec}\n")

    # Use the openai-format tool list returned by the env
    tools = env.list_tools(format="openai")

    with env.session(task=task) as session:
        prompt_blocks = session.get_prompt()
        prompt_text = "\n".join(getattr(b, "text", "") for b in (prompt_blocks or []) if getattr(b, "type", "") == "text")
        print(f"[prompt] {prompt_text[:240]}...\n")

        b64 = _shot_b64(session)
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM},
            _user_with_screenshot(instruction, b64),
        ]
        cumulative_reward = 0.0
        terminate_status = None
        finished = False

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
                    out = session.call_tool(name, args)
                    text = _result_text(out)
                    cumulative_reward += float(out.reward or 0.0)
                    if out.finished:
                        finished = True
                except Exception as e:
                    text = f"ERROR: {e}"
                    out = None
                print(f"[tool-result reward={getattr(out,'reward',None)} finished={getattr(out,'finished',None)}] {text[:160]}")
                if name == "terminate":
                    terminate_status = args.get("status")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": text,
                })

            if finished:
                print(f"[done] env reported finished=True (terminate={terminate_status})")
                break

            b64 = _shot_b64(session)
            messages.append(_user_with_screenshot("Here is the latest screenshot.", b64))
        else:
            print(f"[hit MAX_TURNS={MAX_TURNS}]")

        print("\n" + "=" * 80)
        print(f"FINAL  cumulative_reward={cumulative_reward}  finished={finished}  terminate={terminate_status}")
        print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
