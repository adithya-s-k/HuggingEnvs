# NeMo Gym quick reference (for the umbrella skill)

For implementation, defer to `generate-nemo-gym-env`. Planner-level summary here.

## What NeMo Gym is

NVIDIA's RL gym layer for LLM agents. Built on Ray. Python package `nemo_gym` (install via `pip install git+https://github.com/NVIDIA-NeMo/Gym`). Targets the NeMo training stack but works fine with TRL/GRPO.

## Core types

| Symbol | Source | What it is |
|---|---|---|
| `SimpleResourcesServer` | `nemo_gym.base_resources_server` | Subclass for the env. Holds `sessions` dict, registers tool endpoints in `setup_webserver()`. |
| `BaseSeedSessionRequest`, `BaseSeedSessionResponse` | same | Body/response for `/seed_session`. |
| `BaseVerifyRequest`, `BaseVerifyResponse` | same | Body/response for `/verify` (the post-episode grader). |
| `BaseResourcesServerConfig` | same | Config base; subclass even if empty. |
| `SESSION_ID_KEY` | `nemo_gym.server_utils` | Key into `request.session` for the SID. |

## Reward model

**Post-episode** via `/verify`. The trainer sends the full trajectory (`body.response.output`) plus `body.ground_truth`; you return `BaseVerifyResponse(**body.model_dump(), reward=...)`. No per-step rewards.

## When NeMo Gym beats OpenEnv / ORS / Verifiers

- You want post-hoc grading from a Ray-orchestrated job (e.g. unit-test execution, LLM-as-judge).
- You're already in NVIDIA's NeMo stack.
- You need cookie-based sessions for tool isolation across concurrent rollouts.
- Aggregate metrics across episodes (`/verify` is the natural seam).

## When NeMo Gym loses

- The user wants per-tool-call reward → ORS.
- The user is on a shared SLURM / HF cluster node where Ray init can't bind → OpenEnv or ORS.
- The user wants tool-discovery via `list_tools()` — NeMo Gym has none; tool schemas are hardcoded in the rollout.

## Common confusions

- **Ray init fails on shared cluster nodes** (`gcs_server` can't bind). Local `python server.py` doesn't work in those environments — only deployed Space does.
- **No client SDK.** The rollout speaks raw `requests` with a `requests.Session()` for cookie persistence.
- **Tool schemas are hardcoded** in the rollout. When the server's Pydantic body changes, manually update the rollout's tool definition list.
- **Dataset format requires `responses_create_params` (JSON-stringified) and `ground_truth` (list of dicts).** The `ground_truth[0]` shape is your call — typically `{"expected_output": "..."}`.
