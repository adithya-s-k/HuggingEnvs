# ORS (OpenReward) quick reference (for the umbrella skill)

For implementation, defer to `generate-ors-env`. This is the planner-level summary.

## What ORS is

HTTP REST + Server-Sent Events protocol from [openrewardstandard.io](https://openrewardstandard.io). Official Python SDK is **`openreward`** on PyPI (the `ors-sdk` name does not exist — common mistake). Servers expose:

- `GET  /list_environments`
- `GET  /<env_name>/tools`
- `POST /<env_name>/sessions` (with `task_spec` body)
- `POST /<env_name>/sessions/<sid>/tool` (call a tool)
- `GET  /<env_name>/splits` and `POST /<env_name>/tasks`

The Python server does this for you when you subclass `Environment` and decorate `@tool`.

## Core types

| Symbol | Source | What it is |
|---|---|---|
| `Environment` | `openreward.environments` | Subclass for the env. Has `setup()`, `teardown()`, `list_splits()`, `list_tasks()`, `get_prompt()`. |
| `tool` (decorator) | `openreward.environments` | Marks a method as a callable tool. Method signature: `(self, params: PydanticModel) -> ToolOutput`. |
| `ToolOutput` | `openreward.environments` | `blocks=[TextBlock | ImageBlock], reward=float|None, finished=bool, metadata=dict`. |
| `TextBlock`, `ImageBlock` | `openreward.environments` | Content blocks. `ImageBlock(data=<base64>, mimeType="image/png")`. |
| `Split` | `openreward.environments` | `Split(name="train", type="train")`. |
| `Server` | `openreward.environments` | `Server([EnvCls]).run(host=, port=)`. Endpoint name is the lowercased class name. |
| `EnvironmentsAPI` | `openreward` | Sync client. `EnvironmentsAPI(base_url, api_key="").get(name)`. |
| `OpenReward` | `openreward` | High-level client; **rewrites base_url** with `matrix.` subdomain — avoid for HF Spaces. |

## Reward model

**Per tool call**. Every `ToolOutput` carries a `reward` field. Use `None` for "no reward this step" and a float for "scored". The session ends when `finished=True`.

## When ORS beats OpenEnv / Verifiers

- You want **per-step** rewards (env-side, not trainer-side).
- You want declarative `task_spec` + train/val/test splits without writing your own dataset code.
- You want to deploy to OpenReward.ai's hosted infrastructure.

## When ORS loses

- The MCP ecosystem matters more than reward ergonomics → OpenEnv.
- No HTTP server desired → Verifiers.

## Common confusions

- `ors-sdk` is **not on PyPI**. Always use `openreward`.
- Endpoint name is the lowercased class name: `WordleORS` → `wordleors`.
- `OpenReward(base_url=URL)` mangles URL with subdomain prefixes — use `EnvironmentsAPI` direct for HF Space targets.
- `Task` lives in `openreward.api.environments.types`, but you usually return plain dicts from `list_tasks()` — ORS auto-wraps them.
