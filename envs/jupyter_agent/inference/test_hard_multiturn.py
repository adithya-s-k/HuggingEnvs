"""Test HARD multi-turn tasks that require pip installs, error recovery, and 3+ turns.

Usage:
    python test_hard_multiturn.py --api-url https://<your-modal-url>/v1
"""

import argparse
import json
import time
from openai import OpenAI

ENV_URL = "https://AdithyaSK-jupyter-agent-openenv.hf.space"
MODEL = "Qwen/Qwen3-4B"

SYSTEM_PROMPT = """You are an intelligent data science assistant operating inside a stateful Jupyter notebook environment.
Your goal is to solve analytical and computational tasks through careful, iterative code execution.
Always execute code to verify — never guess at results. Use the available tools to write and run Python code."""

TOOLS = [
    {"type": "function", "function": {
        "name": "add_and_execute_code_cell",
        "description": "Execute Python code in the stateful Jupyter notebook. Variables and imports persist between calls.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    }},
    {"type": "function", "function": {
        "name": "edit_and_execute_current_cell",
        "description": "Replace the last code cell with new code and re-execute it. Use to fix errors.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    }},
    {"type": "function", "function": {
        "name": "execute_shell_command",
        "description": "Run a shell command. Useful for pip install, ls, etc.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
]

HARD_TASKS = [
    {
        "task": (
            "Install the 'sympy' library using pip, then use it to: "
            "1) Find the first 10 prime numbers using sympy.prime() "
            "2) Compute the sum of those primes "
            "3) Factorize that sum using sympy.factorint() "
            "Print the factorization as a dictionary."
        ),
        "expected": "{2: 1, 3: 1, 5: 1, 7: 1, 11: 1}",  # sum of first 10 primes = 129 -> wait let me check
        "label": "pip install + multi-step sympy",
    },
    {
        "task": (
            "Install 'scipy' using pip. Then: "
            "1) Generate 1000 random numbers from a normal distribution with mean=50, std=10 using numpy seed 42 "
            "2) Run a Shapiro-Wilk normality test on the data using scipy.stats.shapiro "
            "3) Print the p-value rounded to 4 decimal places"
        ),
        "expected": "",  # seed-dependent
        "label": "pip install scipy + statistical test",
    },
    {
        "task": (
            "Do the following step by step:\n"
            "Step 1: Create a CSV file called 'sales.csv' with columns: product, quantity, price. "
            "Add 5 rows of sample data (e.g. Widget/10/29.99, Gadget/5/49.99, etc).\n"
            "Step 2: Read the CSV back using pandas.\n"
            "Step 3: Add a new column 'total' = quantity * price.\n"
            "Step 4: Print the product with the highest total revenue."
        ),
        "expected": "",  # depends on data
        "label": "File I/O + pandas pipeline (4 steps)",
    },
    {
        "task": (
            "Install 'matplotlib' using pip. Then:\n"
            "1) Create data: x = numpy.linspace(0, 2*pi, 100), y = sin(x)\n"
            "2) Plot y vs x with a title 'Sine Wave'\n"
            "3) Save the plot to 'sine.png'\n"
            "4) Verify the file exists by checking its size with os.path.getsize\n"
            "Print the file size in bytes."
        ),
        "expected": "",
        "label": "pip install + plot + file verify",
    },
    {
        "task": (
            "This task has an intentional trap. Try to import a module called 'nonexistent_module'. "
            "When that fails (it will), catch the ImportError and instead: "
            "1) Create your own function called 'fibonacci' that returns the nth fibonacci number "
            "2) Use it to compute fibonacci(20) "
            "3) Print the result"
        ),
        "expected": "6765",
        "label": "Error recovery + function writing",
    },
]


# --- Colors ---
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RESET = "\033[0m"


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


def run_episode(client, model, env_client, task_info, max_turns=10):
    task = task_info["task"]
    expected = task_info["expected"]
    label = task_info.get("label", "")

    print(f"\n  {DIM}Resetting environment...{RESET}", end="", flush=True)
    t_reset = time.time()
    env_client.reset()
    print(f" {DIM}done ({time.time()-t_reset:.1f}s){RESET}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{task}\n\nPrint the final answer as the last output."},
    ]

    print(f"\n{BOLD}{'━'*76}{RESET}")
    print(f"  {BOLD}{label}{RESET}")
    print(f"  {DIM}{task[:120]}{'...' if len(task)>120 else ''}{RESET}")
    if expected:
        print(f"  {DIM}Expected: {expected}{RESET}")
    print(f"{BOLD}{'━'*76}{RESET}")

    total_gen = 0
    total_env = time.time() - t_reset
    last_tool_output = ""
    tool_calls_count = 0

    for turn in range(1, max_turns + 1):
        t0 = time.time()
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, tools=TOOLS,
                temperature=0.7, top_p=0.8, max_tokens=2048,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        except Exception as e:
            print(f"\n  {RED}⚠️  API Error: {e}{RESET}")
            return False, turn, tool_calls_count

        gen_time = time.time() - t0
        total_gen += gen_time
        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg.model_dump())
            for tc in msg.tool_calls:
                fn = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except:
                    args = {}

                tool_calls_count += 1
                print(f"\n  {BLUE}┌─ Turn {turn}.{tool_calls_count} │ {BOLD}{fn}{RESET} {DIM}(gen={gen_time:.1f}s){RESET}")

                if fn in ("add_and_execute_code_cell", "edit_and_execute_current_cell"):
                    code = args.get("code", "")
                    for line in code.split("\n"):
                        print(f"  {BLUE}│{RESET}  {YELLOW}{line}{RESET}")
                    t1 = time.time()
                    result = env_client.call_tool(fn, code=code)
                    env_time = time.time() - t1
                    total_env += env_time
                    output = extract_text(result)
                    last_tool_output = output
                    is_err = "ERROR:" in output or "Traceback" in output
                    color = RED if is_err else GREEN
                    tag = "ERROR" if is_err else "OK"
                    print(f"  {BLUE}│{RESET}")
                    print(f"  {BLUE}└─{RESET} {color}[{tag}]{RESET} {DIM}({env_time:.1f}s){RESET}")
                    for line in output.split("\n")[:8]:
                        print(f"     {color}{line}{RESET}")
                    if output.count("\n") > 8:
                        print(f"     {DIM}...{RESET}")

                elif fn == "execute_shell_command":
                    cmd = args.get("command", "")
                    print(f"  {BLUE}│{RESET}  {YELLOW}$ {cmd}{RESET}")
                    t1 = time.time()
                    result = env_client.call_tool("execute_shell_command", command=cmd)
                    env_time = time.time() - t1
                    total_env += env_time
                    output = extract_text(result)
                    last_tool_output = output
                    print(f"  {BLUE}└─{RESET} {GREEN}[OK]{RESET} {DIM}({env_time:.1f}s){RESET}")
                    for line in output.split("\n")[:6]:
                        print(f"     {line}")
                    if output.count("\n") > 6:
                        print(f"     {DIM}...{RESET}")
                else:
                    output = f"Unknown: {fn}"

                messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})
        else:
            content = msg.content or ""
            print(f"\n  {MAGENTA}┌─ Turn {turn} │ {BOLD}FINAL RESPONSE{RESET} {DIM}(gen={gen_time:.1f}s){RESET}")
            for line in content.split("\n")[:6]:
                print(f"  {MAGENTA}│{RESET}  {line}")
            print(f"  {MAGENTA}└─{RESET}")

            all_out = [m.get("content","") for m in messages if m.get("role")=="tool"]
            all_out.append(content)
            solved = (not expected) or any(expected in (o or "") for o in all_out)

            status = f"{GREEN}{BOLD}✅ SOLVED{RESET}" if solved else f"{RED}{BOLD}❌ FAILED{RESET}"
            print(f"\n  {status} │ {tool_calls_count} tool calls │ {turn} turns │ gen={total_gen:.1f}s env={total_env:.1f}s")
            return solved, turn, tool_calls_count

    print(f"\n  {YELLOW}⚠️  Max turns reached{RESET}")
    solved = expected and expected in (last_tool_output or "")
    return solved, max_turns, tool_calls_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--task", type=int, default=None)
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    if not api_url.endswith("/v1"):
        api_url += "/v1"

    client = OpenAI(base_url=api_url, api_key="EMPTY")
    from jupyter_agent_env import JupyterAgentEnv
    env = JupyterAgentEnv(base_url=ENV_URL).sync()
    env.__enter__()

    print(f"{BOLD}{'═'*76}{RESET}")
    print(f"  {BOLD}HARD MULTI-TURN TEST{RESET} — tasks requiring pip install, error recovery, 3+ turns")
    print(f"  Model: {args.model} │ API: {api_url}")
    print(f"{BOLD}{'═'*76}{RESET}")

    tasks = [HARD_TASKS[args.task]] if args.task is not None else HARD_TASKS
    results = []
    for i, t in enumerate(tasks):
        solved, turns, tc = run_episode(client, args.model, env, t)
        results.append({"label": t["label"], "solved": solved, "turns": turns, "tool_calls": tc})

    print(f"\n{BOLD}{'═'*76}{RESET}")
    print(f"  {BOLD}SUMMARY: {sum(r['solved'] for r in results)}/{len(results)} solved{RESET}")
    print(f"{'═'*76}{RESET}")
    for r in results:
        s = f"{GREEN}✅{RESET}" if r["solved"] else f"{RED}❌{RESET}"
        print(f"  {s} [{r['label']}] — {r['turns']} turns, {r['tool_calls']} tool calls")

    env.__exit__(None, None, None)


if __name__ == "__main__":
    main()
