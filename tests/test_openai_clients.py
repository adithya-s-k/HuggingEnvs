"""Probe: does the openai package work against (a) OpenAI and (b) HF Router?

Verifies the credentials and client setup that every rollout in this repo
relies on. Reads OPENAI_API_KEY and HF_TOKEN from the repo-root .env.

Run:  cd tests && uv run python test_openai_clients.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# .env at repo root: ../.env from this file
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")
print(f"OPENAI_API_KEY: {'set' if OPENAI_API_KEY else 'MISSING'}")
print(f"HF_TOKEN:       {'set' if HF_TOKEN else 'MISSING'}")
if not OPENAI_API_KEY or not HF_TOKEN:
    sys.exit("missing creds in .env")

OPENAI_MODELS = ["gpt-5", "gpt-4o-mini"]
HF_MODELS = [
    "Qwen/Qwen3-Coder-480B-A35B-Instruct:together",
    "Qwen/Qwen2.5-Coder-32B-Instruct:nscale",
]

def probe(label, client, model):
    """Try max_completion_tokens (gpt-5 era) first, fall back to max_tokens."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
    }
    for token_kw in ("max_completion_tokens", "max_tokens"):
        try:
            r = client.chat.completions.create(**payload, **{token_kw: 8})
            msg = r.choices[0].message.content
            print(f"  [{label}] {model}: OK ({token_kw})  -> {msg!r}")
            return True
        except Exception as e:
            err = str(e)
            if "max_tokens" in err or "max_completion_tokens" in err:
                continue  # try the other param
            print(f"  [{label}] {model}: FAIL ({type(e).__name__}: {e})")
            return False
    print(f"  [{label}] {model}: FAIL (neither max_tokens nor max_completion_tokens accepted)")
    return False

print("\n--- OpenAI native ---")
oai = OpenAI(api_key=OPENAI_API_KEY)
for m in OPENAI_MODELS:
    probe("openai", oai, m)

print("\n--- HF Router (OpenAI-compatible) ---")
hf = OpenAI(api_key=HF_TOKEN, base_url="https://router.huggingface.co/v1")
for m in HF_MODELS:
    probe("hf-router", hf, m)
