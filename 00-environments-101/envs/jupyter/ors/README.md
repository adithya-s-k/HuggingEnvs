# Jupyter Agent — ORS (Open Reward Standard)

A multi-turn Jupyter notebook agent environment, packaged using **[ORS / OpenReward](https://openrewardstandard.io)** (General Reasoning's HTTP server protocol with REST + SSE). The environment is a real Jupyter kernel running inside an [E2B](https://e2b.dev) cloud sandbox, exposed via the ORS Server.

**Deployed:** [`AdithyaSK/jupyter-agent-ors`](https://huggingface.co/spaces/AdithyaSK/jupyter-agent-ors)

## What this environment exposes

The ORS server registers five `@tool`-decorated methods on a single `Environment` subclass. Tools are auto-discovered via `env.list_tools()`:

| Tool | Description |
|---|---|
| `add_and_execute_code_cell(code: str)` | Run Python in the persistent notebook. Variables, imports, and side-effects persist between calls. |
| `edit_and_execute_current_cell(code: str)` | Replace the last cell with new code and re-run. |
| `execute_shell_command(command: str)` | Run a shell command inside the sandbox (`pip install`, `ls`, `curl`, …). |
| `get_notebook_state(include_images: bool = False)` | Compact summary of the cell history. |
| `final_answer(answer: str)` | Submit the final answer for the task. |

ORS environments **bundle their tasks** with the env: the server exposes a `train` split with 46 hand-crafted tasks (see `tasks.py`). Every tool call returns a `ToolOutput` with **per-call `reward`** (Pattern 2 in the COMPARE doc) and a `finished` flag.

## How to consume it (the canonical ORS pattern)

The env is just a deployed HTTP server. The [`openreward`](https://pypi.org/project/openreward/) client connects, lists tasks/tools, opens a session, and calls tools. **No env-specific install needed**:

```python
from openreward import EnvironmentsAPI

api = EnvironmentsAPI(base_url="https://AdithyaSK-jupyter-agent-ors.hf.space", api_key="")
env = api.get("jupyteragentors")                   # name comes from /list_environments
tasks = env.list_tasks("train")                    # 46 tasks in this env
tools = env.list_tools()                           # ToolSpec(name, description, input_schema)

with env.session(task=tasks[0]) as session:
    prompt = session.get_prompt()                  # [TextBlock(text="...")]
    out = session.call_tool("add_and_execute_code_cell", {"code": "print(2+2)"})
    # ToolOutput(blocks=[TextBlock(text='4')], reward=0.0, finished=False)
```

Compared to OpenEnv's MCP path: ORS uses plain REST + SSE (no JSON-RPC), tasks live on the server, and reward arrives **per tool call** instead of being computed externally.

## Run the rollout

`rollout.py` shows end-to-end consumption: pick a task from the deployed Space's `train` split, open a session, auto-discover the tools, then drive a multi-turn loop with **Qwen3-Coder-480B** through Hugging Face Inference Providers using the `openai` client. Swap the model id to anything OpenAI-compatible.

### Setup

A `.env` at the **repo root** (`RL_Envs_101/.env`) is required:

```bash
HF_TOKEN=hf_...        # for HF Inference Providers (Qwen)
OPENAI_API_KEY=sk-...  # only needed if you switch ROLLOUT_MODEL to an OpenAI model
```

### Run (against deployed Space — zero setup)

```bash
cd 00-environments-101/envs/jupyter/ors
uv sync
uv run python rollout.py
```

For local server, see [Running the env locally](#running-the-env-locally-recommended-for-real-work) below.

### What it does

1. `EnvironmentsAPI(base_url=..., api_key="")` connects to the deployed Space.
2. `env.list_tasks("train")` pulls the 46 tasks; `TASK_INDEX` env var picks one (default `0`).
3. `env.list_tools()` returns `ToolSpec` dataclasses; `rollout.py` converts them to OpenAI tool schemas.
4. `with env.session(task=tasks[i]) as session:` opens a stateful HTTP session (each client call is tagged with the session id; the server keeps a sandbox per session).
5. The first user message is `session.get_prompt()` (the task text from the server).
6. Multi-turn loop: model emits tool-calls → `session.call_tool(name, args)` → append the `ToolOutput.blocks` text back as a `tool` message. Cumulative reward is summed across calls. Stop when `out.finished=True`, the model emits no tool calls, or `MAX_TURNS` is hit.
7. Print every step + final cumulative reward.

### Sample output (Qwen via HF Router)

```
ORS server: https://AdithyaSK-jupyter-agent-ors.hf.space
Env name:   jupyteragentors
Split:      train  task_index=0
Provider:   hf-router
Model:      Qwen/Qwen3-Coder-480B-A35B-Instruct:together

46 tasks in 'train' split. Using task #0.
Discovered 5 tools: ['add_and_execute_code_cell', 'edit_and_execute_current_cell',
                     'execute_shell_command', 'final_answer', 'get_notebook_state']

[task] Solve this task using the Jupyter notebook tools:
       Install the 'sympy' library using pip, then use sympy.isprime to count how
       many numbers between 900 and 1000 are prime. Print the count.

──── turn 1 ────────────────────────────────────────
[tool-call] execute_shell_command({'command': 'pip install sympy'})
[tool-result reward=1.18 finished=True]
Requirement already satisfied: sympy in /usr/local/lib/python3.13/site-packages (1.14.0)
...
[done] env reported finished=True, stopping.

FINAL  cumulative_reward=1.18  finished=True
```

### Configuration knobs (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `ORS_URL` | `https://AdithyaSK-jupyter-agent-ors.hf.space` | ORS server URL. Set to `http://localhost:8080` for local. |
| `ORS_ENV_NAME` | `jupyteragentors` | Env name registered on the server (verify via `GET /list_environments`). |
| `ORS_SPLIT` | `train` | Split to draw the task from. |
| `TASK_INDEX` | `0` | Which task in the split. |
| `ROLLOUT_MODEL` | `Qwen/Qwen3-Coder-480B-A35B-Instruct:together` | If it contains `:` it's routed via HF Router; otherwise OpenAI native. |
| `MAX_TURNS` | `8` | Hard cap on tool-call turns. |

## What's in this folder

| Path | What it is |
|---|---|
| `rollout.py` | Self-contained consumer demo (the only file you need to write to use a deployed ORS env). |
| `server.py` | The ORS `Environment` subclass deployed to the HF Space. `@tool` methods + `list_tasks()` + `get_prompt()`. |
| `tasks.py` | The 46 task definitions used by the server. |
| `e2b_sandbox.py`, `notebook_tracker.py` | Backend logic invoked from the tools. |
| `Dockerfile` | Used to build the deployable image for HF Spaces. |
| `pyproject.toml` | Lists `openreward`, `e2b-code-interpreter`, plus rollout-side `openai`, `python-dotenv`. |

## Running the env locally (recommended for real work)

The HF Space is mainly for convenience. For development run the env locally — fast, full control, no shared-Space concurrency limits.

```bash
cd 00-environments-101/envs/jupyter/ors
uv sync
export E2B_API_KEY=e2b_...           # or rely on the repo-root .env
uv run python server.py              # serves on http://0.0.0.0:8080
# in another shell:
curl http://localhost:8080/list_environments    # -> ["jupyteragentors"]
```

Then run the rollout against it:

```bash
ORS_URL=http://localhost:8080 uv run python rollout.py
```

(Verified working end-to-end: rollout returns `cumulative_reward=1.18 finished=True` on task 0.)

## References

- [Open Reward Standard](https://openrewardstandard.io)
- [openreward on PyPI](https://pypi.org/project/openreward/)
- [OpenReward docs](https://docs.openreward.ai/) · [python-sdk source](https://github.com/openrewardstandard/python-sdk)
- [HF Inference Providers — Chat Completion API](https://huggingface.co/docs/inference-providers/en/tasks/chat-completion)
- [E2B Code Interpreter](https://e2b.dev)
