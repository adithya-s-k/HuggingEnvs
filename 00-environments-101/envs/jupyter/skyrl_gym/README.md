# Jupyter Agent — SkyRL Gym

A multi-turn Jupyter notebook agent environment, packaged using **[SkyRL Gym](https://github.com/NovaSky-AI/SkyRL/tree/main/skyrl-gym)** (NovaSky-AI's in-process Gym-style framework). The environment is a real Jupyter kernel running inside an [E2B](https://e2b.dev) cloud sandbox.

SkyRL Gym is **in-process** — there is no server. The env subclasses `BaseTextEnv` and dispatches tools by parsing tags out of the model's raw text.

## What this environment exposes

A single `JupyterSkyRLEnv(BaseTextEnv)` class. Tools are dispatched by **regex parsing** of the model's free-text action:

| Tag the model emits | Tool dispatched |
|---|---|
| `<code>...</code>` | Run Python in the persistent notebook |
| `<shell>...</shell>` | Run a shell command in the sandbox |
| `<edit>...</edit>` | Replace and re-run the last code cell |
| ` ```python ... ``` ` (fallback) | Treated like `<code>` if no tags present |

`step(action)` returns a `BaseTextEnvStepOutput` (or dict, depending on installed version) with:
- `observations`: a list of `{"role": "user", "content": "..."}` messages with the new tool output
- `reward`: 1.0 if `expected_output` substring appears in the latest tool output, else 0.0
- `done`: True once a non-zero reward is achieved or `max_turns` is hit

This is a fundamentally different paradigm from OpenEnv / ORS / Verifiers: there is **no OpenAI tool-calling**. The model just emits text, the env parses it.

## How to consume it

### Native pattern

```python
import skyrl_gym
env = skyrl_gym.make("jupyter:JupyterAgent-v0")  # the env registers itself on import
obs, info = env.init([{"role": "user", "content": "Print 42"}])
out = env.step("<code>print(42)</code>")
# out.observations -> [{"role": "user", "content": "[Code]: 42"}]
```

Or instantiate directly with an expected-output reward:

```python
from env import JupyterSkyRLEnv
env = JupyterSkyRLEnv(expected_output="42", max_turns=6)
env.init([{"role": "user", "content": "Print 42 using <code>...</code>"}])
out = env.step("<code>print(42)</code>")
print(out.reward, out.done)   # 1.0, True
```

### Manual rollout (`rollout.py` — what we ship)

The rollout drives the loop manually:
1. Instantiate the env with `expected_output`.
2. Call the LLM (Qwen via HF Router by default).
3. Pass the **raw assistant text** as `action` to `env.step()`.
4. Append `out.observations` as the next `user` message.
5. Stop when `done=True` or `MAX_TURNS` hit.

Same code transitions cleanly to native SkyRL training — just register the env in `skyrl_gym` (already done) and use SkyRL's trainer.

## Run the rollout

### Setup

Repo-root `.env`:

```bash
HF_TOKEN=hf_...        # for HF Inference Providers (Qwen)
OPENAI_API_KEY=sk-...  # only if you switch ROLLOUT_MODEL to an OpenAI model
E2B_API_KEY=e2b_...    # ALWAYS required — the sandbox is created in-process
```

### Run

```bash
cd 00-environments-101/envs/jupyter/skyrl_gym
uv sync
uv run python rollout.py
```

### Sample output

```
SkyRL Gym env: in-process JupyterSkyRLEnv (sandbox = E2B)
Provider:      hf-router
Model:         Qwen/Qwen3-Coder-480B-A35B-Instruct:together

[init] info={'max_turns': 6}

──── turn 1 ────────────────────────────────────────
[assistant]
<code>
import numpy as np
data = [12, 19, 23, 31, 7, 14, 28, 5, 22, 18]
print(f"Mean: {np.mean(data)}")
print(f"Standard Deviation: {np.std(data)}")
</code>

[env-result reward=1.0 done=True]
[Code]: Mean: 17.9
Standard Deviation: 8.080222769206305

[done] env reported done=True, stopping.

FINAL  cumulative_reward=1.0  done=True
```

### Configuration knobs

| Variable | Default | Purpose |
|---|---|---|
| `ROLLOUT_MODEL` | `Qwen/Qwen3-Coder-480B-A35B-Instruct:together` | If model id contains `:`, route via HF Router. Else use OpenAI native. |
| `MAX_TURNS` | `6` | Hard cap on text-action turns. |

## What's in this folder

| Path | What it is |
|---|---|
| `rollout.py` | Self-contained consumer demo: instantiate env, send raw text, parse step output. |
| `env.py` | `JupyterSkyRLEnv(BaseTextEnv)` with `init()` / `step()` / `close()`. Auto-registers as `jupyter:JupyterAgent-v0`. |
| `tasks.py` | The 46 task definitions. |
| `e2b_sandbox.py`, `notebook_tracker.py` | Backend logic invoked from `step()`. |
| `pyproject.toml` | `skyrl-gym`, `e2b-code-interpreter`, `openai`, `python-dotenv`. |

## Why no OpenAI tool-calling here?

SkyRL Gym is text-action-first by design — the model can emit arbitrary content (reasoning + tags + commentary) in a single turn, and the env decides what to dispatch. This makes it lighter to integrate with non-tool-calling models, but loses the strict argument validation that a JSON-schema tool-call provides.

If you want OpenAI tool-calling against the same backend, the **Verifiers** sibling folder exposes the same 4 tools as plain Python functions — see `00-environments-101/envs/jupyter/verifiers/`.

## In-process means: no server to run

There's nothing to deploy. The E2B sandbox is created on the first `env.init()` call and torn down by `env.close()`.

## References

- [SkyRL GitHub](https://github.com/NovaSky-AI/SkyRL)
- [HF Inference Providers — Chat Completion API](https://huggingface.co/docs/inference-providers/en/tasks/chat-completion)
- [E2B Code Interpreter](https://e2b.dev)
