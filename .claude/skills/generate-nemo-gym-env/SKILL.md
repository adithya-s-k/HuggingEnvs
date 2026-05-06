---
name: generate-nemo-gym-env
description: Builds a NeMo Gym (NVIDIA) variant of an RL environment. Use whenever someone asks to scaffold a NeMo Gym Resources Server, port an existing env to NeMo Gym, expose tools as `app.post()` endpoints with cookie-based sessions, add a post-episode `/verify` reward grader, or deploy a NeMo Gym env to HF Spaces. NeMo Gym is the right framework when the user wants HTTP+REST with cookie session handling, raw `requests`-driven rollouts (no SDK client), Ray-based orchestration, or NVIDIA NeMo / TRL training integration with a `responses_create_params` + `ground_truth` dataset format. Output is a runnable `<env_dir>/nemo_gym/` folder with `server.py`, `pyproject.toml`, `Dockerfile`, `configs/<env>.yaml`, and `rollout.py`. Use for prompts like "wrap my env in NeMo Gym", "make a NeMo resources server for X", or "add a post-episode grader to my env".
---

# generate-nemo-gym-env

Build the NeMo Gym variant of an env. NeMo Gym is NVIDIA's RL gym layer, optimized for Ray-based orchestration and post-episode grading. The Python package is `nemo_gym` (installed via `pip install git+https://github.com/NVIDIA-NeMo/Gym`).

## Concept

NeMo Gym is NVIDIA's RL gym layer for LLM agents. It's built on Ray and ships a FastAPI-based `SimpleResourcesServer` that exposes one `POST /<tool>` endpoint per tool, plus the standard `/seed_session` (cookie-based session bootstrap) and `/verify` (post-episode grader). Targets [docs.nvidia.com/nemo/gym/latest](https://docs.nvidia.com/nemo/gym/latest/).

When the user has a shared domain module (`<domain>.py`) and wants a NeMo Gym variant, wrap it. Don't duplicate logic.

## Archetypes

| Archetype | Hallmarks |
|---|---|
| **Pure-Python game** | Single tool endpoint; `/verify` does substring match against `ground_truth`. |
| **Stateful sandbox** | Per-session sandbox in `self.sessions`; lazy init on first tool call. |
| **Vision / computer-use** | One endpoint per action; `/verify` rewards trajectories that called `terminate(success)`. |

## Recommended file layout

The user picks the actual paths. The canonical shape:

```
<env_dir>/nemo_gym/
├── pyproject.toml         # nemo_gym (git+) + e2b-* + fastapi + uvicorn + requests
├── __init__.py
├── Dockerfile             # Ray-aware multi-stage
├── configs/<env>.yaml     # NeMo Gym config (entrypoint, domain, description)
├── server.py              # SimpleResourcesServer subclass with tool endpoints
├── rollout.py             # raw requests + cookie session
└── README.md
```

Note: NeMo Gym requires **Python 3.12+**.

## Implementation order

### 1. Server class — `server.py`

```python
from nemo_gym.base_resources_server import (
    BaseResourcesServerConfig,
    BaseSeedSessionRequest, BaseSeedSessionResponse,
    BaseVerifyRequest, BaseVerifyResponse,
    SimpleResourcesServer,
)
from nemo_gym.server_utils import SESSION_ID_KEY
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from typing import Any, Dict

class MyConfig(BaseResourcesServerConfig):
    pass

class GuessReq(BaseModel):
    word: str

class ToolResponse(BaseModel):
    output: str

class MyVerifyRequest(BaseVerifyRequest):
    ground_truth: list = []

class MyResourcesServer(SimpleResourcesServer):
    config: MyConfig
    sessions: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def setup_webserver(self) -> FastAPI:
        app = super().setup_webserver()
        app.post("/guess")(self.guess)
        return app

    async def seed_session(self, body: BaseSeedSessionRequest) -> BaseSeedSessionResponse:
        return BaseSeedSessionResponse()

    def _sess(self, request: Request) -> Dict[str, Any]:
        sid = request.session[SESSION_ID_KEY]
        if sid not in self.sessions:
            self.sessions[sid] = {"game": WordleGame(), "step": 0}
        return self.sessions[sid]

    async def guess(self, body: GuessReq, request: Request) -> ToolResponse:
        sess = self._sess(request)
        feedback = sess["game"].guess(body.word)
        sess["step"] += 1
        return ToolResponse(output=feedback)

    async def verify(self, body: MyVerifyRequest) -> BaseVerifyResponse:
        # Compute reward from the response trajectory + ground truth
        expected = ""
        if body.ground_truth and isinstance(body.ground_truth, list):
            expected = body.ground_truth[0].get("expected_output", "")
        reward = 0.0
        for item in body.response.output:
            if hasattr(item, "type") and item.type == "function_call_output":
                if expected and expected in getattr(item, "output", ""):
                    reward = 1.0; break
        return BaseVerifyResponse(**body.model_dump(), reward=reward)

if __name__ == "__main__":
    MyResourcesServer.run_webserver()
```

Key contracts:
- **One endpoint per tool.** Register them in `setup_webserver()`. Pydantic models on the request body become the JSON shape.
- **Sessions live in `self.sessions`** keyed by `request.session[SESSION_ID_KEY]`. Lazy-init on first call. NeMo Gym sets the session cookie on `POST /seed_session`.
- **`verify()` is the grader.** Read `body.ground_truth` (passed by the trainer) and `body.response.output` (the trajectory). Return `BaseVerifyResponse(**body.model_dump(), reward=...)`.

### 2. NeMo Gym config — `configs/<name>.yaml`

```yaml
my_env_resources_server:
  resources_servers:
    my_env:
      entrypoint: server.py
      domain: agent
      description: "What this env does"
```

This is the file the NeMo Gym CLI looks for when launching via `ng_run "+config_paths=[configs/my_env.yaml]"`.

### 3. Rollout — `rollout.py`

NeMo Gym has **no Python client SDK**. The rollout speaks raw HTTP via `requests` with a `Session` for cookie persistence:

```python
import requests
session = requests.Session()
session.post(f"{ENV_URL}/seed_session", json={}).raise_for_status()
r = session.post(f"{ENV_URL}/guess", json={"word": "crane"})
result = r.json()["output"]
```

Tool definitions for the LLM are **hardcoded** in `rollout.py` (no introspection endpoint). Mirror the request schemas from `server.py` exactly.

### 4. Dockerfile

Multi-stage build. NeMo Gym pulls Ray and a fairly heavy stack — the Docker image is ~1.5GB. The container exposes port 11000 by default. For HF Spaces deployment, override to port 7860 (one-port limit on Spaces).

## Validation gates

1. **Import** — `uv run python -c "import os; os.environ.setdefault('E2B_API_KEY','x'); from server import MyResourcesServer"` succeeds.
2. **Local server** — try `uv run python server.py`. **Note**: NeMo Gym's `run_webserver()` initializes a Ray cluster, which fails on shared SLURM / HF cluster nodes (`gcs_server` can't bind). On those machines, only Docker / HF Space deploy works.
3. **Endpoint smoke** — when running, `curl http://localhost:11000/seed_session -X POST` returns 200 and sets a session cookie.
4. **Rollout** — `MAX_TURNS=3 uv run python rollout.py` drives end-to-end against the deployed Space.

## Common gotchas

- **`No module named 'anyio'`** — `nemo_gym` doesn't pin its full transitive set on every install. Add `anyio>=4.0`, `attrs>=23.0`, `fastapi>=0.115`, `uvicorn`, `requests` to your `dependencies` explicitly.
- **`Address already in use` or `gcs_server` crash** — Ray init failed. Almost always a shared cluster issue. Document this and tell the user to deploy via Space.
- **Cookie not set on the rollout** — make sure to use `requests.Session()`, not raw `requests.post()`. The session cookie is the SID handle.
- **`/verify` returns reward 0 unexpectedly** — `ground_truth` is wrapped in a list. Check `body.ground_truth[0].get("expected_output")` not `body.ground_truth.get(...)`.
- **Hardcoded tool schemas drift** — when you change a server endpoint's Pydantic body, manually update the matching tool definition in `rollout.py`. There's no `list_tools()`.

## Reference

- `references/architecture.md` — Ray orchestration, dataset format with `responses_create_params`, deployment notes

## Official documentation

- [NVIDIA-NeMo/Gym](https://github.com/NVIDIA-NeMo/Gym) — source repo
- [NeMo Gym latest docs](https://docs.nvidia.com/nemo/gym/latest/)
- [Creating a Resource Server tutorial](https://docs.nvidia.com/nemo/gym/latest/tutorials/creating-resource-server.html)
- [Creating a Training Environment tutorial](https://docs.nvidia.com/nemo/gym/latest/environment-tutorials/creating-training-environment.html)
