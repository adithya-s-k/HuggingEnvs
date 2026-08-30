"""End-to-end rollout: Qwen3-VL via HF Router driving the in-process GEM Desktop env.

GEM's `step()` returns the Gymnasium 5-tuple. Action grammar matches SkyRL.

Run:
    cd 00-environments-101/envs/desktop/gem
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

from env import DesktopGemEnv  # noqa: E402

MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-VL-8B-Instruct:novita")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "5"))

SYSTEM = """You are a vision-capable computer-use agent. Each user message includes a
screenshot. Reply with one or more action tags only:

  <screenshot/>
  <click x="100" y="200"/>             (button="right" or "middle" optional)
  <double_click x="100" y="200"/>
  <type>text to type</type>
  <key>ctrl+s</key>
  <scroll x="500" y="400" direction="down" amount="3"/>
  <wait seconds="1"/>
  <terminate status="success"/>

Coordinates are absolute pixels [x, y]."""


def main() -> int:
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN missing")
    if not os.environ.get("E2B_API_KEY"):
        sys.exit("E2B_API_KEY missing — GEM runs the sandbox in-process")
    llm = OpenAI(api_key=token, base_url="https://router.huggingface.co/v1")

    print("=" * 80)
    print(f"GEM env: in-process (E2B Desktop)")
    print(f"Model:   {MODEL}")
    print("=" * 80)

    env = DesktopGemEnv(task_index=0, max_turns=MAX_TURNS)
    obs, info = env.reset()

    _, b64 = env._ctrl.screenshot()
    history = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": obs},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]

    finished = False
    try:
        for turn in range(1, MAX_TURNS + 1):
            print(f"──── turn {turn} ────────────────────────────")
            r = llm.chat.completions.create(model=MODEL, messages=history,
                                            max_completion_tokens=512)
            action = r.choices[0].message.content or ""
            print(f"[assistant] {action[:300]}")
            history.append({"role": "assistant", "content": action})

            obs, reward, terminated, truncated, info = env.step(action)
            print(f"[env] {obs[:200]}")
            print(f"[reward={reward}  terminated={terminated}  truncated={truncated}]")
            history.append({"role": "user", "content": obs})

            if terminated or truncated:
                finished = terminated
                break

            _, new_b64 = env._ctrl.screenshot()
            history.append({"role": "user", "content": [
                {"type": "text", "text": "Latest screenshot:"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{new_b64}"}},
            ]})
        print(f"\nFINAL  finished={finished}")
    finally:
        env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
