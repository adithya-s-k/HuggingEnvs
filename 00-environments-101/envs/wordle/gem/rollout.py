"""End-to-end rollout: LLM playing Wordle via the in-process GEM env.

GEM uses the classic Gymnasium API: `step()` returns the 5-tuple
    (observation, reward, terminated, truncated, info).

Run:
    cd 00-environments-101/envs/wordle/gem
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

from env import WordleGemEnv  # noqa: E402

MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-Coder-480B-A35B-Instruct:together")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))

SYSTEM = """You are playing Wordle.

To guess a word, wrap it in <guess>...</guess> tags, e.g.:
    <guess>crane</guess>

Feedback symbols:
    🟩  letter is in the correct position
    🟨  letter is in the word but wrong position
    ⬛  letter is not in the word

You have 6 attempts."""


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
    print(f"GEM env:    in-process WordleGemEnv (pure Python)")
    print(f"Provider:   {provider}    Model: {MODEL}")
    print("=" * 80)

    env = WordleGemEnv(max_turns=MAX_TURNS)
    obs, info = env.reset()
    print(f"\n[reset] info={info}\n[obs] {obs[:200]}{'...' if len(obs) > 200 else ''}\n")

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
                model=MODEL, messages=messages, max_completion_tokens=256
            )
            action = r.choices[0].message.content or ""
            print(f"[assistant] {action}")
            messages.append({"role": "assistant", "content": action})

            obs, reward, terminated, truncated, info = env.step(action)
            cumulative_reward += float(reward or 0.0)
            done = bool(terminated or truncated)
            print(
                f"[env-result reward={reward} terminated={terminated} "
                f"truncated={truncated}] {obs}"
            )
            if done:
                print(f"\n[done] terminated={terminated} truncated={truncated}.")
                break
            messages.append({"role": "user", "content": obs})
        else:
            print(f"[hit MAX_TURNS={MAX_TURNS}]")
    finally:
        env.close()

    print("\n" + "=" * 80)
    print(f"FINAL  cumulative_reward={cumulative_reward}  done={done}  answer={info.get('answer')}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
