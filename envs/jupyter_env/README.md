# Jupyter Agent Environment

Stateful Jupyter notebook environment powered by E2B sandbox. The agent can execute code, edit cells, run shell commands, and inspect notebook state via 4 tools. Implemented in multiple frameworks — same environment, same tasks, different protocols.

## Tools

| Tool | Description |
|------|-------------|
| `add_and_execute_code_cell(code)` | Execute Python in persistent kernel |
| `edit_and_execute_current_cell(code)` | Replace and re-run last cell |
| `execute_shell_command(command)` | Run shell (pip install, ls, etc.) |
| `get_notebook_state()` | Summary of last 10 cells + outputs |

## Framework Implementations

| Framework | Status | Protocol | Reward Source | Deployed |
|-----------|--------|----------|---------------|----------|
| `openenv/` | **Working** | JSON-RPC (MCP) | External string matching | [HF Space](https://huggingface.co/spaces/AdithyaSK/jupyter-agent-openenv) |
| `ors/` | **Working** | HTTP REST + SSE | `ToolOutput.reward` per call | [HF Space](https://huggingface.co/spaces/AdithyaSK/jupyter-agent-ors) |
| `nemo_gym/` | **Working** | HTTP (Resources Server) | `/verify` endpoint | [HF Space](https://huggingface.co/spaces/AdithyaSK/jupyter-agent-nemo-gym) |
| `verifiers/` | Planned | In-process Python | Rubric scoring | N/A (in-process) |
| `skyrl_gym/` | Planned | In-process (Gym API) | `step()` return | N/A (in-process) |

## Quick Start

### OpenEnv (deployed on HF Spaces)

```bash
# Run server locally
cd openenv && uv sync
E2B_API_KEY=... python -m uvicorn server.app:app --port 8000

# Or use the deployed HF Space
# https://AdithyaSK-jupyter-agent-openenv.hf.space

# Train with TRL
python dev/scripts/grpo.py \
    --config dev/recipes/Qwen3-4B/grpo/config_jupyter_smoke.yaml
```

### ORS (deployed on HF Spaces)

```bash
# Run server locally
cd ors && uv sync
E2B_API_KEY=... python server.py --port 8080

# Or use the deployed HF Space
# https://AdithyaSK-jupyter-agent-ors.hf.space

# Test the server
curl https://AdithyaSK-jupyter-agent-ors.hf.space/health
curl https://AdithyaSK-jupyter-agent-ors.hf.space/list_environments
curl -sL https://AdithyaSK-jupyter-agent-ors.hf.space/tools | python -m json.tool

# Train with TRL
python dev/scripts/grpo.py \
    --config dev/recipes/Qwen3-4B/grpo/config_jupyter_ors_smoke.yaml \
    --env_type jupyter_agent_ors \
    --env_url https://AdithyaSK-jupyter-agent-ors.hf.space

# Slurm (4 GPUs)
sbatch --gres=gpu:4 dev/slurm/train.slurm \
    --model Qwen3-4B --task grpo --config jupyter_ors_smoke --accelerator deepspeed_zero2 \
    --args "--env_type=jupyter_agent_ors --env_url=https://AdithyaSK-jupyter-agent-ors.hf.space --max_tasks=3"
```

### NeMo Gym (deployed on HF Spaces)

```bash
# Run server locally (requires Python 3.12 + nemo_gym from git)
cd nemo_gym && uv venv --python 3.12 && uv sync
E2B_API_KEY=... python server.py

# Or use the deployed HF Space
# https://AdithyaSK-jupyter-agent-nemo-gym.hf.space

# Test the server
curl -s -X POST https://AdithyaSK-jupyter-agent-nemo-gym.hf.space/seed_session -H "Content-Type: application/json" -d '{}' -c cookies.txt
curl -s -X POST https://AdithyaSK-jupyter-agent-nemo-gym.hf.space/add_and_execute_code_cell -H "Content-Type: application/json" -d '{"code":"print(42)"}' -b cookies.txt

# Train with TRL
python dev/scripts/grpo.py \
    --config dev/recipes/Qwen3-4B/grpo/config_jupyter_nemo_gym_smoke.yaml \
    --env_type jupyter_agent_nemo_gym \
    --env_url https://AdithyaSK-jupyter-agent-nemo-gym.hf.space

# Slurm (4 GPUs)
sbatch --gres=gpu:4 dev/slurm/train.slurm \
    --model Qwen3-4B --task grpo --config jupyter_nemo_gym_smoke --accelerator deepspeed_zero2 \
    --args "--env_type=jupyter_agent_nemo_gym --env_url=https://AdithyaSK-jupyter-agent-nemo-gym.hf.space --max_tasks=3"
```

## Using with TRL

All frameworks use the same pattern — `environment_factory` + `environment_config`:

```python
# OpenEnv
from environments.adapters.openenv_adapter import OpenEnvEnvironment
trainer = GRPOTrainer(
    environment_factory=OpenEnvEnvironment,
    environment_config={"base_url": "https://AdithyaSK-jupyter-agent-openenv.hf.space"},
    reward_funcs=reward_func,
    ...
)

# ORS
from environments.adapters.ors_adapter import ORSEnvironment
trainer = GRPOTrainer(
    environment_factory=ORSEnvironment,
    environment_config={"base_url": "https://AdithyaSK-jupyter-agent-ors.hf.space"},
    reward_funcs=reward_func,
    ...
)

# NeMo Gym
from environments.adapters.nemo_gym_adapter import NemoGymEnvironment
trainer = GRPOTrainer(
    environment_factory=NemoGymEnvironment,
    environment_config={"resources_url": "https://AdithyaSK-jupyter-agent-nemo-gym.hf.space"},
    reward_funcs=reward_func,
    ...
)
```

## Key Differences Between Frameworks

### Reward signal
- **OpenEnv**: Reward computed externally in `reward.py` (string matching `expected_output` against `env.last_output`). The server has no reward concept.
- **ORS**: Reward embedded in every tool response (`ToolOutput.reward`). The server computes it inline — reward function just reads `env.reward`.
- **NeMo Gym**: Reward computed by `/verify` endpoint post-episode. The server checks if expected output appears in the tool call results.

### Tool discovery
- **OpenEnv**: 4 tools hardcoded as methods on the adapter class.
- **ORS**: Tools discovered dynamically from the server's `list_tools()` endpoint and bound as methods at runtime.
- **NeMo Gym**: 4 tools hardcoded in the adapter (matching the NeMo Gym Resources Server endpoints).

### Session lifecycle
- **OpenEnv**: MCP client manages WebSocket connection. Reset creates new E2B sandbox.
- **ORS**: HTTP sessions with `X-Session-ID`. `create_session` → `create` → `call` → `delete`.
- **NeMo Gym**: Cookie-based sessions via Starlette SessionMiddleware. `seed_session` → tool calls → `verify`.

## Dataset

46 deterministic coding tasks (13 hard multi-turn + 33 easy). Each task has:
- `task`: instruction string
- `expected_output`: exact string that must appear in final output

Tasks are identical across all frameworks — see `openenv/dataset.py` or `ors/tasks.py`.

### Task categories
- Multi-turn: pip install + compute (2 tasks)
- Multi-turn: file I/O pipelines (2 tasks)
- Multi-turn: complex algorithms (3 tasks)
- Multi-turn: data analysis (2 tasks)
- Multi-turn: shell + code (1 task)
- Multi-turn: error handling (2 tasks)
- Arithmetic (8 tasks)
- String processing (6 tasks)
- NumPy / Math (5 tasks)
- Pandas (4 tasks)
- Data structures (4 tasks)
- Logic / Algorithms (4 tasks)
- File / Shell (1 task)
- Multi-step (2 tasks)

## Tests

```bash
# OpenEnv tests (requires running server or HF Space)
cd openenv && uv sync
pytest tests/ -v

# ORS tests (requires running server or HF Space)
cd ors && uv sync
ORS_SERVER_URL=https://AdithyaSK-jupyter-agent-ors.hf.space pytest tests/ -v

# ORS dataset tests (no server needed)
cd ors && pytest tests/test_ors_env.py -v -k "dataset"

# NeMo Gym tests (20 tests against HF Space)
NEMO_GYM_URL=https://AdithyaSK-jupyter-agent-nemo-gym.hf.space \
  PYTHONPATH=../../../ pytest nemo_gym/tests/ -v

# NeMo Gym dataset only (no server):
PYTHONPATH=../../../ pytest nemo_gym/tests/ -v -k "dataset"
```

## Docker Deployment

Both frameworks have Dockerfiles for self-contained deployment:

```bash
# OpenEnv
cd openenv && docker build -t jupyter-agent-openenv .
docker run -p 8000:8000 -e E2B_API_KEY=... jupyter-agent-openenv

# ORS
cd ors && docker build -t jupyter-agent-ors .
docker run -p 8080:8080 -e E2B_API_KEY=... jupyter-agent-ors

# NeMo Gym (requires Python 3.12)
cd nemo_gym && docker build -t jupyter-agent-nemo-gym .
docker run -p 11000:11000 -e E2B_API_KEY=... jupyter-agent-nemo-gym
```

ORS can also be deployed on [openreward.ai](https://openreward.ai) — push to GitHub and connect via their dashboard.
