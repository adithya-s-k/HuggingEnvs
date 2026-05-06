"""End-to-end rollout: Qwen3-VL via HF Router driving the in-process SkyRL Desktop env.

The model emits free text containing action tags like <click x="500" y="600"/>
or <type>hello</type>. The env parses tags and dispatches to the desktop
controller. Vision: we embed the latest screenshot in the user message at the
start of each turn (multimodal model).

Run:
    cd envs/desktop_env/skyrl_gym
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

from env import DesktopSkyRLEnv  # noqa: E402

MODEL = os.environ.get("ROLLOUT_MODEL", "Qwen/Qwen3-VL-8B-Instruct:novita")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "5"))

SYSTEM = """You are a vision-capable computer-use agent. Each user message includes a
screenshot. Reply with one or more action tags (and only tags). Available tags:

  <screenshot/>
  <click x="100" y="200"/>             (left click; button="right" for right)
  <double_click x="100" y="200"/>
  <type>text to type</type>
  <key>ctrl+s</key>
  <scroll x="500" y="400" direction="down" amount="3"/>
  <wait seconds="1"/>
  <terminate status="success"/>

Coordinates are absolute pixels [x, y]."""

TASK = (
    "Use Firefox to navigate to https://example.com. When the page shows "
    "'Example Domain', emit <terminate status=\"success\"/>."
)


def main() -> int:
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN missing")
    if not os.environ.get("E2B_API_KEY"):
        sys.exit("E2B_API_KEY missing — SkyRL runs the sandbox in-process")
    llm = OpenAI(api_key=token, base_url="https://router.huggingface.co/v1")

    print("=" * 80)
    print(f"SkyRL Gym env: in-process (E2B Desktop)")
    print(f"Model:         {MODEL}")
    print("=" * 80)

    env = DesktopSkyRLEnv(task=TASK, app="firefox", max_turns=MAX_TURNS)
    prompt = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TASK}]
    messages, info = env.init(prompt)

    # Initial screenshot for the model
    text, b64 = env._ctrl.screenshot()
    history = list(messages)
    history.append({"role": "user", "content": [
        {"type": "text", "text": "Initial screenshot of Firefox:"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]})

    finished = False
    try:
        for turn in range(1, MAX_TURNS + 1):
            print(f"──── turn {turn} ────────────────────────────")
            r = llm.chat.completions.create(model=MODEL, messages=history,
                                            max_completion_tokens=512)
            action_text = r.choices[0].message.content or ""
            print(f"[assistant] {action_text[:300]}")
            history.append({"role": "assistant", "content": action_text})

            out = env.step(action_text)
            # SkyRL's BaseTextEnvStepOutput is a TypedDict — access by key
            obs_list = out["observations"] if isinstance(out, dict) else out.observations
            reward = out["reward"] if isinstance(out, dict) else out.reward
            done = out["done"] if isinstance(out, dict) else out.done
            for obs in obs_list:
                content = obs.get("content", "")
                print(f"[env] {content[:200]}")
                history.append(obs)
            print(f"[reward={reward} done={done}]")
            if done:
                finished = True
                break

            # Refresh screenshot for next turn
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
