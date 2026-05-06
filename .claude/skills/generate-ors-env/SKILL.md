---
name: generate-ors-env
description: Builds an Open Reward Standard (ORS) variant of an RL environment using the official `openreward` Python package. Use whenever someone asks to scaffold an ORS env, port to OpenReward, add per-tool-call rewards, deploy to OpenReward.ai, or wrap an existing env in the ORS protocol. ORS is the right framework when the user wants HTTP+REST+SSE, rewards arriving inline with each tool call (not post-episode), task-spec-driven sessions, splits (train/val/test), or deployment to OpenReward.ai or HF Spaces. Output is a runnable `<env_dir>/ors/` folder with `server.py`, `tasks.py`, `pyproject.toml`, `Dockerfile.spaces`, and `rollout.py`. Use for prompts like "wrap my env in ORS", "make an OpenReward env for X", or "add per-call reward to my env".
---

# generate-ors-env

Build the ORS variant of an env using the official **`openreward >= 0.1.33`** package (the `ors-sdk` name is a common mistake — it does not exist on PyPI).

## Concept

ORS is the Open Reward Standard ([openrewardstandard.io](https://openrewardstandard.io)) — an HTTP REST + Server-Sent Events protocol for agent envs. Reward arrives **inline** with every `ToolOutput`, which is the framework's defining feature compared to OpenEnv (external/post-hoc reward) and NeMo Gym (post-episode `/verify`).

When the user has a shared domain module (`<domain>.py`) and wants an ORS variant, **never duplicate domain logic into the framework folder** — wrap it.

## Archetypes

| Archetype | Hallmarks |
|---|---|
| **Pure-Python game** | Single `@tool`, `tasks.py` with N task dicts forming the `train` split, terminal reward via `finished=True`. |
| **Stateful sandbox** | `setup()` allocates resources from `task_spec`; `teardown()` frees them; per-tool reward stubs. |
| **Vision / computer-use** | `ImageBlock(data=<base64>, mimeType="image/png")` returns; `terminate(status)` tool emits the terminal reward. |

## Imports — exactly these

Server side:
```python
from openreward.environments import (
    Environment, Server, tool, ToolOutput, TextBlock, Split, ImageBlock,
)
```

Client side (rollouts):
```python
from openreward import EnvironmentsAPI
api = EnvironmentsAPI(base_url=URL, api_key="")
env = api.get(ENV_NAME)
```

> **Don't use `OpenReward(api_key=..., base_url=...)`** even though it's the high-level client. It prepends `matrix.` / `api.` / `construct.` subdomains to the base URL — that breaks HF Space URLs. `EnvironmentsAPI` talks to `base_url` verbatim.

## Architecture

```
<env_dir>/ors/
├── pyproject.toml         # openreward>=0.1.33 + e2b-* (if needed) + pydantic
├── __init__.py
├── Dockerfile             # local dev image
├── Dockerfile.spaces      # HF Space (port 7860, single-stage pip install)
├── README.spaces.md       # HF Space frontmatter
├── server.py              # the Environment subclass + main()
├── tasks.py               # list of dicts (task_spec for each task)
├── rollout.py             # or rollout_openai.py + rollout_qwen.py
└── README.md              # one-page dev README
```

## Implementation order

### 1. Tasks file — `tasks.py`

A list of plain dicts. Each dict becomes a `task_spec` per session. ORS auto-wraps these into `Task` objects on `list_tasks()`.

```python
TASKS = [
    {"answer": "apple", "task": "Guess the 5-letter word."},
    # ...
]
```

### 2. The Environment subclass — `server.py`

```python
from pydantic import BaseModel
from openreward.environments import Environment, Server, tool, ToolOutput, TextBlock, Split

class GuessInput(BaseModel):
    word: str

class WordleORS(Environment):
    def __init__(self, task_spec=None, secrets=None, **kw):
        super().__init__(task_spec=task_spec or {}, secrets=secrets or {})
        self._game = None

    def setup(self):                      # called on first tool invocation
        self._game = WordleGame(self.task_spec.get("answer"))

    def teardown(self):                   # called on session delete
        self._game = None

    @classmethod
    def list_splits(cls): return [Split(name="train", type="train")]

    @classmethod
    def list_tasks(cls, split): return TASKS

    def get_prompt(self):
        return [TextBlock(text="Play Wordle. Guess the 5-letter word.")]

    @tool
    def guess(self, params: GuessInput) -> ToolOutput:
        feedback = self._game.guess(params.word)
        return ToolOutput(
            blocks=[TextBlock(text=feedback)],
            reward=self._game.reward,
            finished=self._game.done,
        )
```

Key contracts:
- **Tools take a `params: PydanticModel`** as the second arg. ORS uses the model's JSON schema as the tool's `input_schema`.
- **Empty inputs** still need a Pydantic model (`class _Empty(BaseModel): pass`). Don't omit the param.
- **`ToolOutput.blocks`** is `[TextBlock | ImageBlock]`. For images: `ImageBlock(data=<base64>, mimeType="image/png")`. **Vision models actually see this.**
- **`reward`** is `float | None`. `None` means "no reward this step"; `0.0` means "stepped, scored zero". For pure terminal reward, return `None` everywhere except in the last `ToolOutput`.
- **`finished=True`** ends the session. Pair with `reward=1.0` (or whatever) to give the rollout a clean stop.
- **`task_spec`** is a `dict` you read from `self.task_spec` — no schema validation. If you want validation, do it in `setup()`.

### 3. Server entry point — `server.py` main

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    Server([WordleORS]).run(host=args.host, port=args.port)
```

The endpoint name is auto-derived from the class name lowercased — `WordleORS` → `wordleors`. Tell the user this so they know what `ENV_NAME` to pass.

### 4. Rollout

Always discover tools and tasks from the env. Don't hardcode names:

```python
api = EnvironmentsAPI(base_url=ENV_URL, api_key="")
env = api.get("wordleors")
tasks = env.list_tasks("train")
tools = env.list_tools(format="openai")     # built-in OpenAI tool-schema converter
with env.session(task=tasks[0]) as session:
    prompt = session.get_prompt()
    result = session.call_tool("guess", {"word": "crane"})
    # result.blocks, result.reward, result.finished
```

For **vision envs**, the screenshot tool returns an `ImageBlock` — read it as `b.data` (already base64). Pass that into the model's image content.

### 5. Dockerfiles

`Dockerfile.spaces` is the HF Space deploy image. Keep it minimal:

```dockerfile
FROM python:3.11-slim
RUN useradd -m -u 1000 user
RUN pip install --no-cache-dir openreward pydantic <other-deps>
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app
COPY --chown=user . $HOME/app
EXPOSE 7860
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "7860"]
```

`README.spaces.md`:
```yaml
---
title: My Env ORS
emoji: 🎯
colorFrom: pink
colorTo: indigo
sdk: docker
app_port: 7860
tags: [ors, openreward]
---
```

## Pushing to HF Spaces

Create a Space named `<owner>/<env_name>-ors`. Set `E2B_API_KEY` (and any other secrets) as **Space secrets**, not environment variables — they survive rebuilds. The local `.env` file should not be uploaded.

```python
api.add_space_secret(repo_id="<owner>/<env>-ors", key="E2B_API_KEY", value="...")
api.upload_file(path_or_fileobj="Dockerfile.spaces", path_in_repo="Dockerfile", repo_id=...)
api.upload_file(path_or_fileobj="README.spaces.md", path_in_repo="README.md", repo_id=...)
# upload server.py, tasks.py, __init__.py, pyproject.toml
```

## Validation gates

1. **Local server** — `uv run python server.py --port 8772` then `curl http://localhost:8772/list_environments` returns `["<envname>"]`.
2. **Tool discovery** — `curl http://localhost:8772/<envname>/tools | jq '.tools | length'` matches the number of `@tool` methods.
3. **End-to-end** — `MAX_TURNS=3 uv run python rollout.py` drives the model through at least one tool call without errors.

## Gotchas (from real-world ORS work)

- **`from openreward.environments.types import Task`** — wrong; `Task` is in `openreward.api.environments.types` and you usually don't import it. `list_tasks` can return plain dicts; ORS wraps them.
- **`OpenReward(base_url=URL)` rewrites the URL** — prepends `matrix.` / `api.` / `construct.` subdomains. For HF Spaces, use `EnvironmentsAPI(base_url=URL, api_key="")` directly.
- **`e2b-desktop` without `e2b`** — `e2b-desktop` imports from `e2b`, but doesn't pin it. Add both to `dependencies`.
- **Endpoint name is the lowercased class name** — `MyEnvORS` becomes `myenvors`. Tell users this explicitly so their `ENV_NAME` env var is right.

## Reference

- `references/architecture.md` — protocol shape + Server / Environment / Session lifecycle

## Official documentation

- [openrewardstandard.io](https://openrewardstandard.io) — protocol specification
- [docs.openreward.ai](https://docs.openreward.ai) — Python SDK + platform docs
- [openreward on PyPI](https://pypi.org/project/openreward/) — current package (latest 0.1.81+)
- [Talc-AI/OpenReward on GitHub](https://github.com/Talc-AI/OpenReward) — source
