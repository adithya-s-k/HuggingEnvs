# NeMo Gym architecture (deep)

## What NeMo Gym is

NVIDIA's RL gym layer for LLM agents. Built on Ray for orchestration. The Python package is `nemo_gym` (install via `pip install git+https://github.com/NVIDIA-NeMo/Gym`). It targets NVIDIA's NeMo training stack but works with TRL/GRPO via raw HTTP.

## Wire protocol

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/seed_session` | Initialize a session (sets cookie) |
| `POST` | `/<tool>` | Each tool registered in `setup_webserver()` |
| `POST` | `/verify` | Post-episode reward grading |

The session cookie (set on `/seed_session`, named via `SESSION_ID_KEY`) is the only way to associate subsequent tool calls with state. **There is no SDK client** — rollouts speak raw HTTP.

## `SimpleResourcesServer` lifecycle

1. **`MyResourcesServer.run_webserver()`** at `__main__` — boots Ray, starts FastAPI, registers tools.
2. **`setup_webserver(self)`** — must call `super().setup_webserver()` first to get the `FastAPI` instance with `/seed_session` and `/verify` already registered, then `app.post("/tool")(self.tool)` for each tool.
3. **`seed_session(self, body)`** — called once per session by `POST /seed_session`. Return `BaseSeedSessionResponse()`. Lazy-init resources here or in the first tool call (recommended).
4. **Tool methods** — async, take `(self, body, request)`, return a Pydantic response. Read session id via `request.session[SESSION_ID_KEY]`.
5. **`verify(self, body)`** — async, called once per episode by the trainer. Return `BaseVerifyResponse(**body.model_dump(), reward=...)`. **Always spread the body back** — drops fields silently if you don't.

## Session state pattern

```python
sessions: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

def _sess(self, request: Request) -> Dict[str, Any]:
    sid = request.session[SESSION_ID_KEY]
    if sid not in self.sessions:
        self.sessions[sid] = {"game": MyGame(), "step": 0}
    return self.sessions[sid]
```

Session entries persist for the server's lifetime by default. For long-running deployments, either prune on `verify` or add a TTL.

## Dataset format

NeMo Gym expects datasets with two key fields:

- **`responses_create_params`** — a JSON-stringified OpenAI-Responses-API config (model, tools, system prompt). The trainer feeds this to the model.
- **`ground_truth`** — a list of dicts (typically one) carrying expected outputs / answer keys. `verify()` reads from this.

Example row:
```python
{
    "responses_create_params": json.dumps({
        "model": "gpt-4o-mini",
        "input": [{"role": "user", "content": "Solve 2+2"}],
        "tools": [{"type": "function", "function": {"name": "guess", ...}}],
    }),
    "ground_truth": [{"expected_output": "4"}],
    "metadata": json.dumps({"task_id": "math-001"}),
}
```

## Reward computation in `/verify`

`body.response.output` is a list of items emitted by the model:

| Item type | Field |
|---|---|
| `function_call` | `name`, `arguments` (JSON string) |
| `function_call_output` | `output` (the env's response to that call) |
| `message` | `content` (list of `output_text` etc.) |

Typical patterns:

**Substring match** — pass if expected appears anywhere:
```python
expected = body.ground_truth[0].get("expected_output", "")
reward = 0.0
for item in body.response.output:
    if hasattr(item, "type") and item.type == "function_call_output":
        if expected.strip() in str(getattr(item, "output", "")).strip():
            reward = 1.0; break
```

**Function-call match** — pass if a specific tool was called with success:
```python
for item in body.response.output:
    if getattr(item, "type", "") == "function_call" and item.name == "terminate":
        args = item.arguments or ""
        if "success" in args:
            reward = 1.0; break
```

## Production deployment

`Dockerfile` is multi-stage; the runtime image is ~1.5GB because of Ray. Healthcheck via `/seed_session`. For HF Spaces:

- Port 7860 (one-port limit on Spaces)
- Set `app_port: 7860` in README frontmatter
- HF Spaces handle Ray init reliably (unlike shared SLURM nodes)

## Why `run_webserver()` fails on shared cluster nodes

NeMo Gym's `run_webserver()` calls `ray.init()`, which spawns a `gcs_server` process bound to specific ports. On shared SLURM / HF cluster nodes those ports are already taken, and the bind fails. The error looks like:

```
[gcs_server] Failed to bind on address ...
```

There's no fix from the env author's side — deploy via Docker / Space and connect over network.

## What can go wrong

- **Cookie isn't set on the client** — use `requests.Session()`, not naked `requests.post()`.
- **`gcs_server` crash** — Ray init failure on shared nodes; redirect to deployed Space.
- **`No module named 'anyio'` / `attrs`** — NeMo Gym's transitive deps drift. Pin them explicitly.
- **Reward always 0 in verify** — `ground_truth` is a `list`, not a dict. Use `body.ground_truth[0].get(...)`.
- **`request.session[SESSION_ID_KEY]` raises KeyError** — `/seed_session` wasn't called first; fail fast with a clear error.
