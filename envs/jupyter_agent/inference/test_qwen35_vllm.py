"""End-to-end smoke test for a deployed Qwen3.5-4B vLLM server.

Tests every mode documented in the Qwen3.5-4B model card:
  1. Raw HTTP /v1/models and /v1/chat/completions
  2. OpenAI SDK — text-only, instruct (non-thinking) mode
  3. OpenAI SDK — text-only, thinking mode (default)
  4. OpenAI SDK — tool/function calling
  5. OpenAI SDK — image input (VLM)

Usage:
    # On the compute node hosting vllm:
    python test_qwen35_vllm.py --base-url http://localhost:8000/v1

    # From another node on the cluster:
    python test_qwen35_vllm.py --base-url http://ip-26-0-xxx-xxx:8000/v1

    # Skip a specific test:
    python test_qwen35_vllm.py --base-url ... --skip image
"""

import argparse
import json
import sys
import time

import requests
from openai import OpenAI

MODEL = "Qwen/Qwen3.5-4B"

# Image from the Qwen3.5-4B model card "Image Input" example.
DEMO_IMAGE_URL = (
    "https://qianwen-res.oss-accelerate.aliyuncs.com/Qwen3.5/demo/CI_Demo/mathv-1327.jpg"
)

# Sampling parameters from the model card "Best Practices" section.
INSTRUCT_SAMPLING = {
    "temperature": 0.7,
    "top_p": 0.8,
    "presence_penalty": 1.5,
    "extra_body": {"top_k": 20, "chat_template_kwargs": {"enable_thinking": False}},
}
THINKING_SAMPLING = {
    "temperature": 1.0,
    "top_p": 0.95,
    "presence_penalty": 1.5,
    "extra_body": {"top_k": 20},  # thinking is the default
}


def hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def truncate(s: str, n: int = 600) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n] + f"... [truncated, {len(s)} chars total]"


# -----------------------------------------------------------------------------
# Test 1 — raw HTTP
# -----------------------------------------------------------------------------
def test_raw_http(base_url: str) -> bool:
    hr("TEST 1 — Raw HTTP")
    try:
        # /v1/models
        r = requests.get(f"{base_url}/models", timeout=30)
        r.raise_for_status()
        models = r.json()
        served = [m["id"] for m in models["data"]]
        print(f"GET /v1/models → {served}")
        assert any(MODEL in m for m in served), f"{MODEL} not in served models"

        # /v1/chat/completions
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
            "max_tokens": 64,
            "temperature": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        t0 = time.time()
        r = requests.post(f"{base_url}/chat/completions", json=payload, timeout=120)
        elapsed = time.time() - t0
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        print(f"POST /v1/chat/completions ({elapsed:.1f}s) → {truncate(content, 200)}")
        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


# -----------------------------------------------------------------------------
# Test 2 — OpenAI SDK, text, instruct mode
# -----------------------------------------------------------------------------
def test_text_instruct(client: OpenAI) -> bool:
    hr("TEST 2 — OpenAI SDK · text · instruct (non-thinking) mode")
    try:
        t0 = time.time()
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": "In one sentence, what is the capital of France?"},
            ],
            max_tokens=128,
            **INSTRUCT_SAMPLING,
        )
        elapsed = time.time() - t0
        msg = resp.choices[0].message
        print(f"({elapsed:.1f}s) content: {truncate(msg.content)}")
        # In instruct mode, reasoning_content should be empty / absent.
        rc = getattr(msg, "reasoning_content", None)
        print(f"reasoning_content (should be empty): {rc!r}")
        return bool(msg.content)
    except Exception as e:
        print(f"FAIL: {e}")
        return False


# -----------------------------------------------------------------------------
# Test 3 — OpenAI SDK, text, thinking mode (default)
# -----------------------------------------------------------------------------
def test_text_thinking(client: OpenAI) -> bool:
    hr("TEST 3 — OpenAI SDK · text · thinking mode (default)")
    try:
        t0 = time.time()
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": "What's 17 * 23? Show your reasoning briefly."},
            ],
            max_tokens=2048,
            **THINKING_SAMPLING,
        )
        elapsed = time.time() - t0
        msg = resp.choices[0].message
        rc = getattr(msg, "reasoning_content", None)
        print(f"({elapsed:.1f}s)")
        print(f"reasoning_content: {truncate(rc, 400) if rc else '(none — server may not parse <think>)'}")
        print(f"content: {truncate(msg.content, 400)}")
        return bool(msg.content)
    except Exception as e:
        print(f"FAIL: {e}")
        return False


# -----------------------------------------------------------------------------
# Test 4 — Function calling
# -----------------------------------------------------------------------------
def test_function_calling(client: OpenAI) -> bool:
    hr("TEST 4 — OpenAI SDK · tool/function calling")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a given city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name, e.g. 'Paris'"},
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature unit",
                        },
                    },
                    "required": ["city"],
                },
            },
        }
    ]
    try:
        t0 = time.time()
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": "What's the weather in Tokyo right now? Use celsius.",
                }
            ],
            tools=tools,
            tool_choice="auto",
            max_tokens=512,
            **INSTRUCT_SAMPLING,
        )
        elapsed = time.time() - t0
        msg = resp.choices[0].message
        print(f"({elapsed:.1f}s)")
        print(f"finish_reason: {resp.choices[0].finish_reason}")
        print(f"content: {truncate(msg.content)}")
        if not msg.tool_calls:
            print("FAIL: model did not emit a tool call")
            return False
        for tc in msg.tool_calls:
            print(f"tool_call.name: {tc.function.name}")
            print(f"tool_call.args: {tc.function.arguments}")
            try:
                parsed = json.loads(tc.function.arguments)
                assert parsed.get("city", "").lower() in {"tokyo"}, "wrong city"
            except Exception as e:
                print(f"WARN: tool args malformed or unexpected: {e}")
        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


# -----------------------------------------------------------------------------
# Test 5 — Image input (VLM)
# -----------------------------------------------------------------------------
def test_image_input(client: OpenAI) -> bool:
    hr("TEST 5 — OpenAI SDK · image input (VLM)")
    try:
        t0 = time.time()
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": DEMO_IMAGE_URL}},
                        {
                            "type": "text",
                            "text": "Describe what you see in this image in one sentence.",
                        },
                    ],
                }
            ],
            max_tokens=512,
            **INSTRUCT_SAMPLING,
        )
        elapsed = time.time() - t0
        msg = resp.choices[0].message
        print(f"({elapsed:.1f}s)")
        print(f"content: {truncate(msg.content)}")
        return bool(msg.content) and len(msg.content) > 10
    except Exception as e:
        print(f"FAIL: {e}")
        return False


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base-url",
        required=True,
        help="vLLM OpenAI-compatible base URL, e.g. http://ip-26-0-xxx-xxx:8000/v1",
    )
    parser.add_argument(
        "--api-key", default="EMPTY", help="API key (vLLM ignores it; default 'EMPTY')"
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        choices=["raw", "instruct", "thinking", "tools", "image"],
        help="Skip one or more tests (repeatable)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Target: {base_url}  (model: {MODEL})")

    client = OpenAI(base_url=base_url, api_key=args.api_key, timeout=300.0)

    tests = [
        ("raw", lambda: test_raw_http(base_url)),
        ("instruct", lambda: test_text_instruct(client)),
        ("thinking", lambda: test_text_thinking(client)),
        ("tools", lambda: test_function_calling(client)),
        ("image", lambda: test_image_input(client)),
    ]

    results: dict[str, bool] = {}
    for name, fn in tests:
        if name in args.skip:
            print(f"\n[skipped] {name}")
            results[name] = None
            continue
        results[name] = fn()

    hr("SUMMARY")
    width = max(len(n) for n, _ in tests)
    for name, _ in tests:
        r = results[name]
        flag = "SKIP" if r is None else ("PASS" if r else "FAIL")
        print(f"  {name:<{width}}  {flag}")

    failed = [n for n, r in results.items() if r is False]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
