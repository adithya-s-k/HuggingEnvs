"""End-to-end rollout: LLM driving the in-process SkyRL Gym Jupyter agent.

SkyRL Gym is in-process. The env subclasses `BaseTextEnv` and dispatches tools
by parsing tags out of the model's raw text:

    <code>print(2 ** 10)</code>          -> add_and_execute_code_cell
    <shell>pip install sympy</shell>      -> execute_shell_command
    <edit>print(2 ** 10)</edit>           -> edit_and_execute_current_cell

The env's `step(action)` parses these tags, runs the snippets in the E2B
sandbox, and returns `BaseTextEnvStepOutput(observations, reward, done, ...)`.

This is the **native SkyRL pattern** — no OpenAI tool-calling, just text in /
text out. A simple regex parser on the env side is the whole tool dispatch.

Run:
    cd envs/jupyter_env/skyrl_gym
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

from env import JupyterSkyRLEnv  # noqa: E402

MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-Coder-480B-A35B-Instruct:together")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))

TASK = (
    "Compute the mean and standard deviation of the list "
    "[12, 19, 23, 31, 7, 14, 28, 5, 22, 18] using NumPy. "
    "Print both values."
)
EXPECTED = "8.080222769206305"   # the env scores reward=1 if this substring appears

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
        sys.exit("E2B_API_KEY missing in .env (SkyRL Gym runs the sandbox in-process)")

    print("=" * 80)
    print(f"SkyRL Gym env: in-process JupyterSkyRLEnv (sandbox = E2B)")
    print(f"Provider:      {provider}")
    print(f"Model:         {MODEL}")
    print(f"Task:          {TASK}")
    print("=" * 80)

    env = JupyterSkyRLEnv(expected_output=EXPECTED, max_turns=MAX_TURNS)
    prompt = [{"role": "user", "content": TASK}]
    _, info = env.init(prompt)
    print(f"\n[init] info={info}\n")

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": TASK},
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

            out = env.step(action)
            # SkyRL Gym sometimes returns a dict, sometimes a dataclass. Handle both.
            if isinstance(out, dict):
                observations = out.get("observations") or []
                reward = out.get("reward", 0.0)
                done = bool(out.get("done"))
            else:
                observations = out.observations or []
                reward = out.reward
                done = bool(out.done)
            obs_text = "\n".join(o["content"] for o in observations)
            cumulative_reward += float(reward or 0.0)
            print(f"[env-result reward={reward} done={done}]\n{obs_text}\n")

            if done:
                print("[done] env reported done=True, stopping.")
                break
            messages.append({"role": "user", "content": obs_text})
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
