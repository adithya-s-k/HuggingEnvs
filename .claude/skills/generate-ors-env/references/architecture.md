# ORS architecture (deep)

## Wire protocol (REST + SSE)

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/list_environments` | List env names served by this server |
| `GET`  | `/<env>/tools` | List tools (returns `{"tools": [{"name", "description", "input_schema"}, ...]}`) |
| `GET`  | `/<env>/splits` | List splits |
| `POST` | `/<env>/tasks` | Body `{"split": "train"}` → list of `Task` |
| `GET`  | `/<env>/prompt` | Returns the prompt blocks for the current task |
| `POST` | `/<env>/sessions` | Body `{"task_spec": {...}, "secrets": {...}}` → SSE stream returns the `session_id` |
| `POST` | `/<env>/sessions/<sid>/tool` | Body `{"name": "x", "input": {...}}` → SSE stream of the `ToolOutput` |
| `DELETE` | `/<env>/sessions/<sid>` | Tear down |

Endpoint name = `<EnvironmentClassName>.lower()`. So `class WordleORS(Environment)` → `/wordleors/...`.

The `EnvironmentsAPI` Python client wraps this via `aiohttp`. `OpenReward` wraps `EnvironmentsAPI` and rewrites `base_url` to `matrix.<host>` — that's why HF Space targets need `EnvironmentsAPI` direct.

## `Environment` lifecycle

1. **`__init__(task_spec, secrets, **kw)`** — called once per session. Store `task_spec` (already on `self.task_spec` after `super().__init__`); validate or stub.
2. **`setup()`** — called on first tool invocation. Allocate sandbox, init game state.
3. **`teardown()`** — called on `DELETE /sessions/<sid>`. Kill the sandbox, free resources.
4. **`get_prompt() -> [TextBlock | ImageBlock]`** — called when the client asks for the prompt. Reads from `self.task_spec`.
5. **`@classmethod list_splits()`** and **`@classmethod list_tasks(split)`** — class-level (no `self`). Splits are static metadata. Tasks can be plain dicts; ORS wraps them.
6. **Tool methods** — decorated `@tool`, signature `(self, params: BaseModel) -> ToolOutput`.

## ToolOutput shape

```python
ToolOutput(
    blocks=[TextBlock(text="..."), ImageBlock(data=<b64>, mimeType="image/png")],
    metadata={"any": "json"},
    reward=0.5,                  # float | None
    finished=False,              # bool — True ends the session
)
```

Per-step rewards add up across the trajectory; `finished=True` is the only way for the env to signal terminal state.

## Splits & tasks

`Split.type` is `"train" | "validation" | "test"`. The split name and type can differ. List N tasks per split, each a dict that becomes the per-session `task_spec`.

A common pattern:
```python
TASKS = [{"answer": w, "task": "Guess the word"} for w in WORDS[:50]]

@classmethod
def list_tasks(cls, split): return TASKS
```

ORS wraps each dict into a `Task(server_name=cls.__name__, environment_name=..., task_spec=dict)` automatically.

## Secrets

`Environment.__init__` takes `secrets`. The client passes `secrets` per-session in the `POST /sessions` body. Use this for per-rollout API keys (E2B sandbox, etc.) — they don't appear in the server's environment.

## Sync vs async clients

Both `EnvironmentsAPI` and `AsyncEnvironmentsAPI` exist. The sync wrapper runs an async loop under the hood. For multi-rollout scenarios prefer async:

```python
async with AsyncOpenReward(api_key="").environments as api:
    env = api.get(name, base_url=URL)
    async with env.session(task=task) as session:
        ...
```

## Image handling

`ImageBlock.data` is **base64**, not raw bytes. The server-side `ImageBlock(data=base64.b64encode(png).decode(), mimeType="image/png")` matches the client-side `b.data` (still base64). Don't re-encode.

Canonical helper:

```python
def _shot_block(sandbox) -> ImageBlock:
    data = sandbox.screenshot()
    return ImageBlock(data=base64.b64encode(data).decode("utf-8"), mimeType="image/png")
```

## Production deployment

The wordle and desktop ORS variants both deploy to HF Spaces using a minimal `Dockerfile.spaces`:

```dockerfile
FROM python:3.11-slim
RUN useradd -m -u 1000 user
RUN pip install --no-cache-dir openreward pydantic <env-specific>
USER user
WORKDIR /home/user/app
COPY --chown=user . .
EXPOSE 7860
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "7860"]
```

Plus `README.spaces.md` with the HF frontmatter. Push via:

```python
api.add_space_secret(repo_id, "E2B_API_KEY", value)
api.upload_file(path_or_fileobj="Dockerfile.spaces", path_in_repo="Dockerfile", ...)
api.upload_file(path_or_fileobj="README.spaces.md", path_in_repo="README.md", ...)
```

For **OpenReward.ai** deployment (the platform), the same files work — see [docs.openreward.ai](https://docs.openreward.ai/) for the GitHub-integration flow.

## What can go wrong

- `pip install ors-sdk` — package doesn't exist on PyPI.
- Endpoint name mismatch — class `MyEnv` is served at `/myenv`, not `/my_env`.
- `OpenReward(base_url="https://X.hf.space")` ends up calling `https://matrix.X.hf.space` — broken DNS. Use `EnvironmentsAPI`.
- `setup()` not called — happens silently when an `__init__` raises before tools are registered. Check the server log.
