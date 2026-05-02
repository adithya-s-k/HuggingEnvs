"""End-to-end rollout: LLM driving the in-process GEM Jupyter agent.

GEM is in-process and follows the classic Gymnasium API. The env subclasses
`gem.Env` and dispatches tools by parsing tags out of the model's raw text:

    <code>print(2 ** 10)</code>          -> add_and_execute_code_cell
    <shell>pip install sympy</shell>      -> execute_shell_command
    <edit>print(2 ** 10)</edit>           -> edit_and_execute_current_cell
    <state/>                              -> get_notebook_state

`step(action)` returns the Gymnasium 5-tuple:
    (observation, reward, terminated, truncated, info)

Run:
    cd envs/jupyter_agent/gem
    uv sync
    uv run python rollout.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

from env import JupyterGemEnv  # noqa: E402

MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-Coder-480B-A35B-Instruct:together")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))

TASK = (
    "Compute the mean and standard deviation of the list "
    "[12, 19, 23, 31, 7, 14, 28, 5, 22, 18] using NumPy. "
    "Print both values."
)
EXPECTED = "8.080222769206305"

SYSTEM = """You are a Python data-analysis agent in a Jupyter notebook.

Wrap every Python snippet you want executed in <code>...</code> tags.
For shell commands use <shell>...</shell>. To replace the last cell use <edit>...</edit>.
Variables persist between snippets in the same session.
After you have the final answer, print it as the last output and stop emitting tags.

Example:
<code>
import numpy as np
print(np.array([1,2,3]).mean())
</code>
"""


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
        sys.exit("E2B_API_KEY missing in .env (GEM runs the sandbox in-process)")

    print("=" * 80)
    print(f"GEM env:    in-process JupyterGemEnv (sandbox = E2B)")
    print(f"Provider:   {provider}")
    print(f"Model:      {MODEL}")
    print(f"Task:       {TASK}")
    print("=" * 80)

    env = JupyterGemEnv(task=TASK, expected_output=EXPECTED, max_turns=MAX_TURNS)
    obs, info = env.reset()
    print(f"\n[reset]\n  instruction: {obs[:200]}{'...' if len(obs) > 200 else ''}")
    print(f"  info: {info}\n")

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": obs},
    ]
    cumulative_reward = 0.0
    done = False

    try:
        for turn in range(1, MAX_TURNS + 1):
            print(f"──── turn {turn} ────────────────────────────────────────")
            r = llm.chat.completions.create(
                model=MODEL, messages=messages, max_completion_tokens=512
            )
            action = r.choices[0].message.content or ""
            print(f"[assistant]\n{action}\n")
            messages.append({"role": "assistant", "content": action})

            obs, reward, terminated, truncated, info = env.step(action)
            cumulative_reward += float(reward or 0.0)
            done = bool(terminated or truncated)
            print(
                f"[env-result reward={reward} terminated={terminated} "
                f"truncated={truncated}]\n{obs}\n"
            )

            if done:
                print(f"[done] terminated={terminated} truncated={truncated}, stopping.")
                break
            messages.append({"role": "user", "content": obs})
        else:
            print(f"[hit MAX_TURNS={MAX_TURNS}]")
    finally:
        env.close()
        print("\n[cleanup] E2B sandbox closed.")

    print("\n" + "=" * 80)
    print(f"FINAL  cumulative_reward={cumulative_reward}  done={done}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
