"""Interactive multi-turn tool-calling test — mirrors what happens during training rollouts.

Connects to a vLLM server + Jupyter Agent OpenEnv and runs multi-turn
episodes with rich visual output showing exactly what the model does.

Usage:
    python test_multiturn_app.py --api-url https://<your-modal-vllm-url>

Or with a local server:
    python test_multiturn_app.py --api-url http://localhost:8000/v1
"""

import argparse
import json
import time
import sys

from openai import OpenAI

ENV_URL = "https://AdithyaSK-jupyter-agent-openenv.hf.space"
MODEL = "Qwen/Qwen3-4B"

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
            "description": "Replace the last code cell with new code and re-execute it. Use to fix errors without cluttering the notebook.",
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
            "description": "Run a shell command. Useful for pip install, ls, etc.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Shell command."}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_notebook_state",
            "description": "Return a compact summary of all executed cells and their outputs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# --- Tasks designed to test different multi-turn patterns ---
TASKS = [
    {
        "task": "Calculate the sum of all prime numbers less than 50 and print the result.",
        "expected": "328",
        "label": "Simple (1 turn)",
    },
    {
        "task": "Create a pandas DataFrame with columns 'name' = ['Alice', 'Bob', 'Carol'] and 'score' = [95, 82, 91]. Print the mean of the 'score' column rounded to 1 decimal place.",
        "expected": "89.3",
        "label": "Pandas (1-2 turns)",
    },
    {
        "task": "Create a list of numbers from 1 to 20, filter out the odd numbers, square the remaining even numbers, and print the sum.",
        "expected": "1540",
        "label": "Multi-step logic",
    },
    {
        "task": "Write a function that checks if a number is prime. Use it to find all twin primes (pairs of primes that differ by 2) less than 100. Print how many twin prime pairs there are.",
        "expected": "8",
        "label": "Complex (multi-turn likely)",
    },
    {
        "task": "Create a 5x5 numpy matrix of random integers between 1-100 using seed 42. Print the sum of the diagonal elements.",
        "expected": "",  # Seed-dependent
        "label": "NumPy with seed",
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


# --- Pretty printing ---

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RESET = "\033[0m"


def print_header(text, char="━"):
    w = 76
    print(f"\n{BOLD}{char * w}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{BOLD}{char * w}{RESET}")


def print_section(label, content, color=CYAN):
    print(f"  {color}{BOLD}{label}{RESET}")
    for line in content.split("\n"):
        print(f"  {DIM}│{RESET} {line}")


def print_tool_call(turn, tool_name, gen_time):
    print(f"\n  {BLUE}┌─ Turn {turn} │ {BOLD}{tool_name}{RESET}{BLUE} │ gen={gen_time:.1f}s{RESET}")


def print_code(code):
    for line in code.split("\n"):
        print(f"  {BLUE}│{RESET}  {YELLOW}{line}{RESET}")


def print_output(output, env_time, is_error=False):
    color = RED if is_error else GREEN
    status = "ERROR" if is_error else "OK"
    print(f"  {BLUE}│{RESET}")
    print(f"  {BLUE}└─ Output{RESET} {DIM}({env_time:.1f}s){RESET} {color}[{status}]{RESET}")
    for line in output.split("\n")[:10]:
        print(f"     {color}{line}{RESET}")
    if output.count("\n") > 10:
        print(f"     {DIM}... ({output.count(chr(10)) - 10} more lines){RESET}")


def print_final_response(turn, content, gen_time):
    print(f"\n  {MAGENTA}┌─ Turn {turn} │ {BOLD}FINAL RESPONSE{RESET}{MAGENTA} │ gen={gen_time:.1f}s{RESET}")
    for line in content.split("\n")[:8]:
        print(f"  {MAGENTA}│{RESET}  {line}")
    print(f"  {MAGENTA}└─{RESET}")


def print_result(solved, turns, gen_time, env_time):
    status = f"{GREEN}{BOLD}✅ SOLVED{RESET}" if solved else f"{RED}{BOLD}❌ FAILED{RESET}"
    print(f"\n  {status} in {turns} turn(s) │ gen={gen_time:.1f}s env={env_time:.1f}s total={gen_time+env_time:.1f}s")


# --- Episode runner ---

def run_episode(client, model, env_client, task_info, max_turns=8):
    task = task_info["task"]
    expected = task_info["expected"]
    label = task_info.get("label", "")

    # Reset environment (just like training rollout does)
    print(f"\n  {DIM}Resetting environment...{RESET}", end="", flush=True)
    t_reset = time.time()
    env_client.reset()
    reset_time = time.time() - t_reset
    print(f" {DIM}done ({reset_time:.1f}s){RESET}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Solve this task using the Jupyter notebook tools:\n\n{task}\n\nPrint the final answer as the last output."},
    ]

    print_header(f"{label}: {task}")
    if expected:
        print(f"  {DIM}Expected output: {expected}{RESET}")

    total_gen_time = 0
    total_env_time = reset_time
    last_tool_output = ""
    conversation = []

    for turn in range(1, max_turns + 1):
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
            print(f"\n  {RED}⚠️  API Error: {e}{RESET}")
            return False, turn, total_gen_time, total_env_time, conversation

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

                print_tool_call(turn, fn_name, gen_time)

                if fn_name in ("add_and_execute_code_cell", "edit_and_execute_current_cell"):
                    code = fn_args.get("code", "")
                    print_code(code)

                    t1 = time.time()
                    result = env_client.call_tool(fn_name, code=code)
                    env_time = time.time() - t1
                    total_env_time += env_time
                    output = extract_text(result)
                    last_tool_output = output
                    is_error = "ERROR:" in output or "Traceback" in output

                    print_output(output, env_time, is_error)
                    conversation.append({
                        "turn": turn, "tool": fn_name, "code": code,
                        "output": output, "error": is_error, "time_s": round(env_time, 2),
                    })

                elif fn_name == "execute_shell_command":
                    cmd = fn_args.get("command", "")
                    print(f"  {BLUE}│{RESET}  {YELLOW}$ {cmd}{RESET}")

                    t1 = time.time()
                    result = env_client.call_tool("execute_shell_command", command=cmd)
                    env_time = time.time() - t1
                    total_env_time += env_time
                    output = extract_text(result)
                    last_tool_output = output

                    print_output(output, env_time)
                    conversation.append({
                        "turn": turn, "tool": fn_name, "command": cmd,
                        "output": output, "time_s": round(env_time, 2),
                    })

                elif fn_name == "get_notebook_state":
                    t1 = time.time()
                    result = env_client.call_tool("get_notebook_state")
                    env_time = time.time() - t1
                    total_env_time += env_time
                    output = extract_text(result)
                    print_output(output, env_time)

                else:
                    output = f"Unknown tool: {fn_name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": output,
                })
        else:
            content = msg.content or ""
            print_final_response(turn, content, gen_time)

            all_outputs = [m.get("content", "") for m in messages if m.get("role") == "tool"]
            all_outputs.append(content)
            solved = expected and any(expected in (o or "") for o in all_outputs)
            if not expected:
                solved = True  # No expected = auto-pass

            print_result(solved, turn, total_gen_time, total_env_time)
            return solved, turn, total_gen_time, total_env_time, conversation

    # Check last tool output
    solved = expected and expected in (last_tool_output or "")
    print(f"\n  {YELLOW}⚠️  Max turns ({max_turns}) reached{RESET}")
    print_result(solved, max_turns, total_gen_time, total_env_time)
    return solved, max_turns, total_gen_time, total_env_time, conversation


def main():
    parser = argparse.ArgumentParser(description="Interactive multi-turn tool-calling test")
    parser.add_argument("--api-url", required=True, help="vLLM OpenAI-compatible API URL (e.g. https://xxx.modal.run/v1)")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--env-url", default=ENV_URL)
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--task", type=int, default=None, help="Run a single task by index (0-based)")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    if not api_url.endswith("/v1"):
        api_url += "/v1"

    client = OpenAI(base_url=api_url, api_key="EMPTY")

    from jupyter_agent_env import JupyterAgentEnv
    env_client = JupyterAgentEnv(base_url=args.env_url).sync()
    env_client.__enter__()

    print_header("MULTI-TURN TOOL-CALLING TEST", "═")
    print(f"  Model:     {args.model}")
    print(f"  API:       {api_url}")
    print(f"  Env:       {args.env_url}")
    print(f"  Max turns: {args.max_turns}")
    print(f"  Tasks:     {len(TASKS)}")

    tasks = [TASKS[args.task]] if args.task is not None else TASKS
    results = []

    for i, task_info in enumerate(tasks):
        solved, turns, gen_t, env_t, conv = run_episode(
            client, args.model, env_client, task_info, args.max_turns
        )
        results.append({
            "idx": args.task if args.task is not None else i,
            "task": task_info["task"][:60],
            "label": task_info.get("label", ""),
            "solved": solved,
            "turns": turns,
            "gen_time": gen_t,
            "env_time": env_t,
            "conversation": conv,
        })

    # --- Summary ---
    print_header("SUMMARY", "═")
    total_solved = sum(r["solved"] for r in results)
    print(f"  {BOLD}{total_solved}/{len(results)} solved{RESET}\n")

    for r in results:
        status = f"{GREEN}✅{RESET}" if r["solved"] else f"{RED}❌{RESET}"
        print(f"  {status} [{r['label']}] {r['task']}...")
        print(f"     {r['turns']} turns │ gen={r['gen_time']:.1f}s env={r['env_time']:.1f}s │ {len(r['conversation'])} tool calls")

    total_gen = sum(r["gen_time"] for r in results)
    total_env = sum(r["env_time"] for r in results)
    print(f"\n  {BOLD}Total: gen={total_gen:.1f}s env={total_env:.1f}s combined={total_gen+total_env:.1f}s{RESET}")

    env_client.__exit__(None, None, None)


if __name__ == "__main__":
    main()
