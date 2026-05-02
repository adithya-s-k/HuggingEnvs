# Jupyter Agent — Verifiers

A multi-turn Jupyter notebook agent environment, packaged using **[Verifiers](https://github.com/PrimeIntellect-ai/verifiers)** (PrimeIntellect's in-process Python framework). The environment is a real Jupyter kernel running inside an [E2B](https://e2b.dev) cloud sandbox.

Verifiers is **in-process** — there is no server. Tools are plain Python functions, the env runs in the same process as the trainer / rollout script.

## What this environment exposes

`env.py` defines four tools as plain Python functions, plus a `JupyterToolkit` class for stateful sandbox management:

| Tool | Description |
|---|---|
| `add_and_execute_code_cell(code: str)` | Run Python in the persistent notebook. |
| `edit_and_execute_current_cell(code: str)` | Replace the last cell with new code and re-run. |
| `execute_shell_command(command: str)` | Shell command inside the sandbox (`pip install`, …). |
| `get_notebook_state(include_images: bool = False)` | Compact summary of cell history. |

The functions share a single `_shared_sandbox` (E2B Code Interpreter) and `_shared_tracker` (notebook history) at module level. Each rollout reuses the same sandbox unless you explicitly close and reopen.

## How to consume it

Two paths:

### A) Native Verifiers (`vf.ToolEnv` + `env.evaluate`)

Verifiers ships its own multi-turn rollout harness. `env.py` exposes `create_verifiers_env()` which returns a `vf.ToolEnv` with the 4 tools, the 46 tasks dataset, and a string-match `Rubric`:

```python
from openai import AsyncOpenAI
from env import create_verifiers_env

env = create_verifiers_env()
results = await env.evaluate(
    client=AsyncOpenAI(api_key=..., base_url="https://router.huggingface.co/v1"),
    model="Qwen/Qwen3-Coder-480B-A35B-Instruct:together",
)
```

### B) Manual rollout (`rollout.py` — what we ship)

For full visibility into every step, drive the loop yourself with the `openai` client. Import the tool functions, auto-generate OpenAI tool schemas from their signatures + docstrings, dispatch tool calls by name. **Same pattern transitions cleanly to TRL training** as `environment_factory=JupyterToolkit`.

This is what `rollout.py` does. No server, no SDK — just function calls.

## Run the rollout

### Setup

Repo-root `.env`:

```bash
HF_TOKEN=hf_...        # for HF Inference Providers (Qwen)
OPENAI_API_KEY=sk-...  # only if you switch ROLLOUT_MODEL to an OpenAI model
E2B_API_KEY=e2b_...    # ALWAYS required — the sandbox is created in-process
```

> Verifiers is in-process, so the E2B sandbox is created on the rollout machine, not on a remote server. You always need `E2B_API_KEY`.

### Run

```bash
cd envs/jupyter_env/verifiers
uv sync
uv run python rollout.py
```

### Sample output

```
Verifiers env: in-process (sandbox = E2B)
Provider:      hf-router
Model:         Qwen/Qwen3-Coder-480B-A35B-Instruct:together
Tools:         ['add_and_execute_code_cell', 'edit_and_execute_current_cell',
                'execute_shell_command', 'get_notebook_state']

──── turn 1 ────────────────────────────────────────
[tool-call] add_and_execute_code_cell({'code': 'import numpy as np\n...'})
[tool-result]
Mean: 17.9
Standard Deviation: 8.080222769206305

──── turn 2 ────────────────────────────────────────
[assistant] FINAL: mean=17.9, std=8.080222769206305
[done] no tool calls.

[cleanup] E2B sandbox closed.
```

### Configuration knobs

| Variable | Default | Purpose |
|---|---|---|
| `ROLLOUT_MODEL` | `Qwen/Qwen3-Coder-480B-A35B-Instruct:together` | If model id contains `:`, route via HF Router. Else use OpenAI native. |
| `MAX_TURNS` | `6` | Hard cap on tool-call turns. |

## What's in this folder

| Path | What it is |
|---|---|
| `rollout.py` | Self-contained consumer demo: import tools, auto-build schemas, drive loop manually. |
| `env.py` | The 4 tool functions + `JupyterToolkit` class + `create_verifiers_env()` for native usage. |
| `tasks.py` | The 46 task definitions used by `create_verifiers_env()`. |
| `e2b_sandbox.py`, `notebook_tracker.py` | Backend logic for the tools. |
| `pyproject.toml` | `verifiers`, `e2b-code-interpreter`, `openai`, `python-dotenv`. |

## In-process means: no server to run

There's nothing to deploy. The E2B sandbox is the only external dependency, and it's created lazily inside `_get_sandbox()` the first time a tool is called.

If you want to use the sandbox sandbox manually:

```python
from env import JupyterToolkit
toolkit = JupyterToolkit()
toolkit.reset()
out = toolkit.add_and_execute_code_cell("print(2 ** 10)")    # '1024'
toolkit.close()
```

## References

- [Verifiers GitHub](https://github.com/PrimeIntellect-ai/verifiers)
- [HF Inference Providers — Chat Completion API](https://huggingface.co/docs/inference-providers/en/tasks/chat-completion)
- [E2B Code Interpreter](https://e2b.dev)
