# OpenEnv architecture (deep)

## Wire protocol

OpenEnv uses MCP over HTTP. The server exposes:

- `GET  /health` → `{"status": "healthy"}`
- `GET  /metadata` → env name + description
- `GET  /openapi.json` → full OpenAPI schema
- `POST /reset` → start a new episode (body matches `reset()`'s kwargs)
- `POST /step` → execute an `Action` (`CallToolAction` for tool calls)
- `GET  /state` → fetch the current `State` object
- `GET  /web/...` → optional Gradio UI mount (when `ENABLE_WEB_INTERFACE=true`)

The MCP-specific surface lives behind `/step`: a `CallToolAction(tool_name="x", arguments={...})` returns a `CallToolObservation(result={"content": [...], "data": ..., "is_error": ...})`. Tool discovery is via a **list-tools action**, not a separate REST endpoint — `MCPToolClient.list_tools()` does this transparently.

## `MCPEnvironment` lifecycle

1. **`__init__`** — register tools on a `FastMCP` instance, then `super().__init__(mcp)`. Don't allocate per-episode state here; it'll outlive episodes.
2. **`reset(seed, episode_id, **kwargs)`** — called once per episode. Allocate the sandbox, store session ids in `self._state`, return an `Observation(done=False, reward=None, metadata={...})`.
3. **`step(action, timeout_s, **kwargs)`** — inherited; dispatches `CallToolAction` to the right `@mcp.tool` function. Override only if you need pre/post hooks (step counter, terminate detection).
4. **`step_async(...)`** — same but async. If you override `step`, override this too.
5. **`_step_impl(action, ...)`** — fallback for non-MCP `Action` types. Usually return an error observation.
6. **`state` property** — returns the current state for `/state` endpoint.

## Concurrent sessions

`SUPPORTS_CONCURRENT_SESSIONS = True` enables the framework to multiplex sessions inside one process. **Only set this if you actually isolate state per session-id** — otherwise sessions clobber each other.

For sandbox-per-episode envs: usually *don't* set this true. Run multiple replicas of the env instead (set `max_concurrent_envs` in `create_app`).

## Tool returns

FastMCP serializes tool returns by inspecting the type:

| Return type | Becomes | Model sees |
|---|---|---|
| `str` | `TextContent(type="text", text=...)` | the string |
| `Image(data=bytes, format="png")` | `ImageContent(type="image", data=<base64>, mimeType="image/png")` | the actual pixels |
| `dict` | `TextContent` with JSON-serialized `text` | the JSON string |
| Pydantic model | structured `data` field | depends on client |

For computer-use / vision envs, **always** use `Image`. Returning base64 in a string makes the model effectively blind.

## Custom Gradio UI

Pass `gradio_builder=` to `create_app`. The signature is:

```python
def builder(web_manager, action_fields, metadata, is_chat_env, title, quick_start_md) -> gr.Blocks: ...
```

You can ignore most args and just instantiate the env yourself inside the builder. For computer-use envs, the canonical pattern includes an iframe panel showing the E2B sandbox stream URL alongside text controls.

## Dual-import idiom

Inside `server/`, files use:

```python
try:
    from .models import State          # works in repo (PYTHONPATH=src:envs)
except ImportError:
    from models import State           # works in Docker (PYTHONPATH=/app/env)
```

Same applies inside `server/<env>_environment.py` for sibling modules. **Always include both.** OpenEnv's CLI builds Docker images that flatten the package layout; the relative import will fail there.

## Production deployment

`Dockerfile` uses `ghcr.io/meta-pytorch/openenv-base:latest` as a multi-stage builder. The runtime image copies the venv and source. Healthcheck via `/health`. For HF Spaces:

- `app_port: 8000` in README frontmatter
- `base_path: /web` if you want the Gradio UI mounted
- `E2B_API_KEY` (and any other secrets) as Space secrets, not env vars
- `MAX_CONCURRENT_ENVS=2` typically — sandbox-per-episode is RAM-heavy

## What can go wrong

- `KeyError: 'tools'` from `POST /list_tools` — that endpoint doesn't exist. Use `MCPToolClient`.
- Screenshot returns `None` from `env.call_tool("screenshot")` — the convenience method strips to structured `data`. Use `env.step(CallToolAction(...))` and read `obs.result["content"]`.
- `from ..module import X` fails in Docker — missing dual-import.
- `ENABLE_WEB_INTERFACE=true` set but no `gradio_builder` passed — Gradio mounts a default UI; set `os.environ["ENABLE_WEB_INTERFACE"]` before `create_app` if you want the custom one.
