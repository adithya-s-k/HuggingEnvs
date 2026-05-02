# Global Tests

Sanity checks for the **openai client setup** shared across every rollout in this repo. These are not framework tests, they verify that the credentials in the repo-root `.env` work and that both providers we use return sensible responses.

The same pattern (the `openai` Python client pointed at either OpenAI directly or the HF Router) is reused in every `rollout.py` under `envs/<env>/<framework>/`.

## Setup

A `.env` at the repo root is required:

```bash
# /fsx/adithyaskolavi/projects/RL_Envs_101/.env
OPENAI_API_KEY=sk-...
HF_TOKEN=hf_...
```

## Run

```bash
cd tests
uv sync
uv run python test_openai_clients.py     # basic chat completion against both providers
uv run python test_qwen_tool_calling.py  # tool-calling against Qwen via HF Router
```

## What each test checks

| File | Purpose |
|---|---|
| `test_openai_clients.py` | Calls `chat.completions.create` against (a) OpenAI native (gpt-4o-mini fallback if gpt-5 isn't available with `max_tokens`) and (b) HF Router with `Qwen/Qwen3-Coder-480B-A35B-Instruct:together`. |
| `test_qwen_tool_calling.py` | Verifies that Qwen Coder via HF Router actually emits tool-calls in the OpenAI tool-call schema (this is what every Jupyter agent rollout depends on). |

## Why these matter

Every rollout in `envs/jupyter_agent/<framework>/rollout.py` follows the same recipe:

```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["HF_TOKEN"],
                base_url="https://router.huggingface.co/v1")
client.chat.completions.create(
    model="Qwen/Qwen3-Coder-480B-A35B-Instruct:together",
    messages=[...],
    tools=[...],   # discovered from the env
)
```

If these tests pass, every rollout should be one (env-specific) glue layer away from working.
