# Jupyter Agent — NeMo Gym

A multi-turn Jupyter notebook agent environment, packaged using **[NeMo Gym](https://github.com/NVIDIA-NeMo/Gym)** (NVIDIA's HTTP-server framework with REST endpoints + cookie-based sessions). The environment is a real Jupyter kernel running inside an [E2B](https://e2b.dev) cloud sandbox.

**Deployed:** [`AdithyaSK/jupyter-agent-nemo-gym`](https://huggingface.co/spaces/AdithyaSK/jupyter-agent-nemo-gym)

## What this environment exposes

NeMo Gym registers each tool as a plain FastAPI `POST` endpoint. Sessions are managed via cookies (set by `POST /seed_session`).

| Endpoint | Body | Description |
|---|---|---|
| `POST /seed_session` | `{}` | Initialize an E2B sandbox for this client; sets a session cookie. |
| `POST /add_and_execute_code_cell` | `{"code": "..."}` | Run Python in the persistent notebook. |
| `POST /edit_and_execute_current_cell` | `{"code": "..."}` | Replace the last cell and re-run. |
| `POST /execute_shell_command` | `{"command": "..."}` | Shell command inside the sandbox. |
| `POST /get_notebook_state` | `{"include_images": false}` | Compact summary of executed cells. |
| `POST /final_answer` | `{"answer": "..."}` | Submit the final answer for the task. |
| `POST /verify` | `{"responses_create_params": ..., "response": ...}` | **Post-episode** reward computation (called *after* the rollout, not per turn). |

All tool responses look like `{"output": "..."}`. Reward is **not returned per call** (Pattern 3 in the COMPARE doc) — it's computed post-episode by `/verify`.

## How to consume it (raw HTTP — no SDK needed)

NeMo Gym's protocol is plain REST + cookies. The cleanest client is just `requests`:

```python
import requests

s = requests.Session()
s.post("https://AdithyaSK-jupyter-agent-nemo-gym.hf.space/seed_session", json={}).raise_for_status()

r = s.post(
    "https://AdithyaSK-jupyter-agent-nemo-gym.hf.space/add_and_execute_code_cell",
    json={"code": "print(2 ** 10)"},
)
print(r.json()["output"])   # -> '1024'
```

The cookie set by `/seed_session` keeps subsequent calls bound to the same E2B sandbox.

> Tool schemas are also discoverable from `GET /openapi.json` at runtime. Our `rollout.py` hardcodes them inline for clarity, but a generic version could parse OpenAPI to auto-generate the OpenAI tool schemas.

## Run the rollout

`rollout.py` opens a session, drives a multi-turn loop with **Qwen3-Coder-480B** (HF Inference Providers via the `openai` client), and dispatches each tool-call as a `POST /<tool_name>` against the server.

### Setup

A `.env` at the **repo root** (`RL_Envs_101/.env`) is required:

```bash
HF_TOKEN=hf_...        # for HF Inference Providers (Qwen)
OPENAI_API_KEY=sk-...  # only if you swap ROLLOUT_MODEL to an OpenAI model
E2B_API_KEY=e2b_...    # only needed if you run the server locally
```

### Run (against deployed Space — recommended)

```bash
cd 00-environments-101/envs/jupyter/nemo_gym
uv sync
uv run python rollout.py
```

### Sample output

```
NeMo Gym server: https://AdithyaSK-jupyter-agent-nemo-gym.hf.space
Provider:        hf-router
Model:           Qwen/Qwen3-Coder-480B-A35B-Instruct:together

[seed_session] 200; cookies={'JupyterAgentResourcesServer___jupyter_agent': '...'}

──── turn 1 ────────────────────────────────────────
[tool-call] add_and_execute_code_cell({'code': 'import numpy as np\n...'})
[tool-result]
Mean: 17.9
Standard Deviation: 8.080222769206305

──── turn 2 ────────────────────────────────────────
[tool-call] final_answer({'answer': 'The mean is 17.9, std is approximately 8.08.'})
[tool-result]
Answer submitted: The mean is 17.9, std is approximately 8.08.
```

### Configuration knobs (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `NEMO_GYM_URL` | `https://AdithyaSK-jupyter-agent-nemo-gym.hf.space` | NeMo Gym server URL. |
| `ROLLOUT_MODEL` | `Qwen/Qwen3-Coder-480B-A35B-Instruct:together` | If model id contains `:`, route via HF Router. Else use OpenAI. |
| `MAX_TURNS` | `6` | Hard cap on tool-call turns. |

## Running the env locally

> ⚠️ **NeMo Gym requires Ray.** The server entry point calls `ray.init()` before binding the FastAPI app. On cluster nodes where Ray's `gcs_server` can't reserve a port (shared HF / SLURM nodes), `python server.py` fails with `Timed out while waiting for GCS to become available`. We hit this on the HF cluster, and the issue is not fixable from our side — Ray is tightly coupled with NeMo Gym's internal config validation, so monkey-patching `initialize_ray()` away breaks downstream Hydra / OmegaConf checks.
>
> For local dev, either:
>
> 1. Run on a machine where Ray can bind freely (laptop, dedicated VM, non-shared node), or
> 2. **Use the deployed HF Space** — same code, just leave `NEMO_GYM_URL` unset (default points at the Space).
>
> Unlike OpenEnv and ORS where local Python servers are the recommended path, NeMo Gym is the one framework where the deployed Space is genuinely the easier route in this environment.

### When Ray is happy on your machine:

```bash
cd 00-environments-101/envs/jupyter/nemo_gym
uv sync                                  # needs Python 3.12
export E2B_API_KEY=e2b_...               # or rely on the repo-root .env
uv run python server.py                  # serves on :11000
# in another shell:
NEMO_GYM_URL=http://localhost:11000 uv run python rollout.py
```

## What's in this folder

| Path | What it is |
|---|---|
| `rollout.py` | Self-contained consumer demo — raw HTTP, no SDK. |
| `server.py` | The `SimpleResourcesServer` subclass deployed to the HF Space. |
| `tasks.py` | The 46 tasks the server uses internally. |
| `e2b_sandbox.py`, `notebook_tracker.py` | Backend logic invoked from the tools. |
| `configs/jupyter_agent.yaml` | NeMo Gym Hydra config. |
| `Dockerfile` | Used to build the deployable image for HF Spaces. |
| `pyproject.toml` | Lists `nemo_gym` (git), `e2b-code-interpreter`, plus rollout-side `openai`, `python-dotenv`, `requests`. **Requires Python 3.12.** |

## References

- [NeMo Gym GitHub](https://github.com/NVIDIA-NeMo/Gym)
- [HF Inference Providers — Chat Completion API](https://huggingface.co/docs/inference-providers/en/tasks/chat-completion)
- [E2B Code Interpreter](https://e2b.dev)
