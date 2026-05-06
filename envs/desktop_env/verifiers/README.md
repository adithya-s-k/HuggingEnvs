# Desktop · Verifiers

In-process Verifiers env. The `DesktopToolkit` owns one E2B Desktop sandbox per episode; its public methods are introspected as tools by both the TRL adapter and `vf.ToolEnv`.

## Tools (12 exposed; subset of the full 19-tool action set, picked for what models actually use)

`screenshot`, `left_click`, `right_click`, `double_click`, `mouse_move`, `left_click_drag`, `scroll`, `type`, `key`, `wait`, `terminate`, `run_command`.

`screenshot()` returns the screenshot as a base64 PNG inside markdown — vision models that accept image-in-tool-result content blocks see pixels; text-only models see the encoded string and should rely on `run_command` for state.

## Two consumption paths

```python
# Native verifiers
from env import create_verifiers_env
env = create_verifiers_env()
results = await env.evaluate(client=AsyncOpenAI(...), model="gpt-4o")
```

```python
# Manual rollout / TRL adapter
from env import DesktopToolkit
kit = DesktopToolkit(app="firefox")
kit.left_click([500, 600])
kit.type("hello")
kit.terminate("success")
```

## Run

```bash
cd envs/desktop_env/verifiers
uv sync
uv run python rollout.py        # Qwen3-VL via HF Router, drives the kit manually
```

`E2B_API_KEY` must be set — Verifiers runs the sandbox in-process.
