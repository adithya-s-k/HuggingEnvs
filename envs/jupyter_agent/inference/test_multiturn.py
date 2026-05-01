"""Test multi-turn tool calling with Qwen3-4B + Jupyter Agent OpenEnv.

Deploys a vLLM server on Modal, connects to it, and runs multi-turn
episodes against the HF Space environment. Prints full conversation traces.

Usage:
    python test_multiturn.py

This will:
1. Deploy vLLM on Modal (1x A100-80GB)
2. Run 3 tasks with multi-turn tool calling
3. Print full conversation traces
4. Shut down the server
"""

import json
import time
import subprocess
import sys
import os
from pathlib import Path

# --- Config ---
MODEL = "Qwen/Qwen3-4B"
ENV_URL = "https://AdithyaSK-jupyter-agent-openenv.hf.space"

SYSTEM_PROMPT = """You are an intelligent data science assistant operating inside a stateful Jupyter notebook environment.
Your goal is to solve analytical and computational tasks through careful, iterative code execution.
Always execute code to verify — never guess at results. Use the available tools to write and run Python code."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_and_execute_code_cell",
            "description": "Execute Python code in the stateful Jupyter notebook. Variables and imports persist between calls.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Python code to execute. Can span multiple lines."}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_and_execute_current_cell",
            "description": "Replace the last code cell with new code and re-execute it. Use to fix errors.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Replacement Python code."}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_shell_command",
            "description": "Run a shell command inside the sandbox. Useful for pip install, ls, etc.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Shell command to execute."}},
                "required": ["command"],
            },
        },
    },
]

# Tasks designed to require multi-turn reasoning
TASKS = [
    {
        "task": "Calculate the sum of all prime numbers less than 50 and print the result.",
        "expected": "328",
        "difficulty": "easy (1 turn)",
    },
    {
        "task": "Create a pandas DataFrame with columns 'name' = ['Alice', 'Bob', 'Carol'] and 'score' = [95, 82, 91]. Print the mean of the 'score' column rounded to 1 decimal place.",
        "expected": "89.3",
        "difficulty": "medium (1-2 turns)",
    },
    {
        "task": "Create a list of numbers from 1 to 20, filter out the odd numbers, square the remaining even numbers, and print the sum.",
        "expected": "1540",
        "difficulty": "medium (multi-step)",
    },
    {
        "task": "Install the 'sympy' library, then use it to compute the 100th prime number and print it.",
        "expected": "541",
        "difficulty": "hard (requires shell + code, 2+ turns)",
    },
    {
        "task": "Write a function that checks if a string is a palindrome. Test it with 'racecar' and 'hello', printing True/False for each on separate lines.",
        "expected": "True",
        "difficulty": "medium (multi-step code)",
    },
]


def extract_text(result):
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list) and content:
            return content[0].get("text", str(result))
        res = result.get("result", "")
        if isinstance(res, dict):
            content = res.get("content", [])
            if isinstance(content, list) and content:
                return content[0].get("text", str(res))
            return res.get("data", str(res))
        return str(res)
    return str(result)


def run_episode(client, model, env_client, task_info, max_turns=8):
    """Run a single multi-turn episode with full trace output."""
    from openai import OpenAI

    task = task_info["task"]
    expected = task_info["expected"]

    env_client.reset()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{task}\n\nPrint the final answer as the last output."},
    ]

    print(f"\n{'━'*70}")
    print(f"  TASK: {task}")
    print(f"  EXPECTED: {expected}")
    print(f"  DIFFICULTY: {task_info.get('difficulty', '?')}")
    print(f"{'━'*70}")

    total_gen_time = 0
    total_env_time = 0
    last_tool_output = ""

    for turn in range(max_turns):
        t0 = time.time()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                temperature=0.7,
                top_p=0.8,
                max_tokens=2048,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        except Exception as e:
            print(f"\n  ⚠️  API Error: {e}")
            return False, turn + 1, total_gen_time, total_env_time

        gen_time = time.time() - t0
        total_gen_time += gen_time
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            messages.append(msg.model_dump())

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                print(f"\n  ┌─ Turn {turn+1} │ {fn_name} │ gen={gen_time:.1f}s")

                if fn_name == "add_and_execute_code_cell":
                    code = fn_args.get("code", "")
                    for line in code.split("\n"):
                        print(f"  │  {line}")

                    t1 = time.time()
                    result = env_client.call_tool("add_and_execute_code_cell", code=code)
                    env_time = time.time() - t1
                    total_env_time += env_time
                    output = extract_text(result)
                    last_tool_output = output

                    is_error = "ERROR:" in output or "Traceback" in output
                    status = "❌ ERROR" if is_error else "✅"
                    print(f"  │")
                    print(f"  └─ Output ({env_time:.1f}s) {status}: {output[:150]}")

                elif fn_name == "edit_and_execute_current_cell":
                    code = fn_args.get("code", "")
                    for line in code.split("\n"):
                        print(f"  │  {line}")

                    t1 = time.time()
                    result = env_client.call_tool("edit_and_execute_current_cell", code=code)
                    env_time = time.time() - t1
                    total_env_time += env_time
                    output = extract_text(result)
                    last_tool_output = output

                    is_error = "ERROR:" in output or "Traceback" in output
                    status = "❌ ERROR" if is_error else "✅"
                    print(f"  │")
                    print(f"  └─ Output ({env_time:.1f}s) {status}: {output[:150]}")

                elif fn_name == "execute_shell_command":
                    cmd = fn_args.get("command", "")
                    print(f"  │  $ {cmd}")

                    t1 = time.time()
                    result = env_client.call_tool("execute_shell_command", command=cmd)
                    env_time = time.time() - t1
                    total_env_time += env_time
                    output = extract_text(result)
                    last_tool_output = output
                    print(f"  │")
                    print(f"  └─ Output ({env_time:.1f}s): {output[:150]}")

                else:
                    output = f"Unknown tool: {fn_name}"
                    last_tool_output = output

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": output,
                })
        else:
            content = msg.content or ""
            print(f"\n  ┌─ Turn {turn+1} │ FINAL RESPONSE │ gen={gen_time:.1f}s")
            for line in content.split("\n")[:5]:
                print(f"  │  {line}")
            print(f"  └─")

            all_outputs = [m.get("content", "") for m in messages if m.get("role") == "tool"]
            all_outputs.append(content)
            solved = any(expected in (o or "") for o in all_outputs)

            print(f"\n  {'✅ SOLVED' if solved else '❌ FAILED'} in {turn+1} turn(s) │ gen={total_gen_time:.1f}s env={total_env_time:.1f}s")
            return solved, turn + 1, total_gen_time, total_env_time

    # Check if last tool output had the answer
    solved = expected in (last_tool_output or "")
    print(f"\n  {'✅ SOLVED (from tool output)' if solved else '❌ MAX TURNS'} │ gen={total_gen_time:.1f}s env={total_env_time:.1f}s")
    return solved, max_turns, total_gen_time, total_env_time


def test_with_api(api_url, model=MODEL):
    """Run multi-turn tests against an OpenAI-compatible API."""
    from openai import OpenAI
    from jupyter_agent_env import JupyterAgentEnv

    client = OpenAI(base_url=api_url, api_key="EMPTY")
    env_client = JupyterAgentEnv(base_url=ENV_URL).sync()
    env_client.__enter__()

    print(f"Model: {model}")
    print(f"API: {api_url}")
    print(f"Env: {ENV_URL}")
    print(f"Tasks: {len(TASKS)}")

    results = []
    for task_info in TASKS:
        solved, turns, gen_t, env_t = run_episode(client, model, env_client, task_info)
        results.append({
            "task": task_info["task"][:60],
            "difficulty": task_info.get("difficulty", "?"),
            "solved": solved,
            "turns": turns,
            "gen_time": gen_t,
            "env_time": env_t,
        })

    print(f"\n{'━'*70}")
    print(f"  SUMMARY: {sum(r['solved'] for r in results)}/{len(results)} solved")
    print(f"{'━'*70}")
    for r in results:
        status = "✅" if r["solved"] else "❌"
        print(f"  {status} [{r['difficulty']}] {r['task']}...")
        print(f"     {r['turns']} turns │ gen={r['gen_time']:.1f}s env={r['env_time']:.1f}s")
    print()

    total_gen = sum(r["gen_time"] for r in results)
    total_env = sum(r["env_time"] for r in results)
    print(f"  Total: gen={total_gen:.1f}s env={total_env:.1f}s")

    env_client.__exit__(None, None, None)
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test multi-turn tool calling")
    parser.add_argument("--api-url", default=None,
                        help="OpenAI-compatible API URL. If not set, deploys vLLM on Modal.")
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()

    if args.api_url:
        test_with_api(args.api_url, args.model)
    else:
        print("No --api-url provided. To test, run a vLLM server:")
        print(f"  vllm serve {MODEL} --max-model-len 8192")
        print(f"Then:")
        print(f"  python test_multiturn.py --api-url http://localhost:8000/v1")
