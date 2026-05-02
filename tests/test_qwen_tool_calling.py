"""Verify Qwen Coder via HF Router supports tool-calling through openai client.

Run:  cd tests && uv run python test_qwen_tool_calling.py
"""
import os, json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

client = OpenAI(api_key=os.environ["HF_TOKEN"], base_url="https://router.huggingface.co/v1")

tools = [{
    "type": "function",
    "function": {
        "name": "execute_code",
        "description": "Execute Python code in a notebook cell and return stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python source"}},
            "required": ["code"],
        },
    },
}]

r = client.chat.completions.create(
    model="Qwen/Qwen3-Coder-480B-A35B-Instruct:together",
    messages=[
        {"role": "system", "content": "You are a Python REPL agent. Use the execute_code tool."},
        {"role": "user", "content": "What is 17 * 23? Compute it with the tool."},
    ],
    tools=tools,
    max_tokens=256,
)
msg = r.choices[0].message
print("content:", msg.content)
print("tool_calls:", msg.tool_calls)
if msg.tool_calls:
    tc = msg.tool_calls[0]
    print(f"  name: {tc.function.name}")
    print(f"  args: {tc.function.arguments}")
    try:
        print(f"  parsed: {json.loads(tc.function.arguments)}")
    except Exception as e:
        print(f"  parse fail: {e}")
