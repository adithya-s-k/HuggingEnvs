# Jupyter Agent — GEM

A multi-turn Jupyter notebook agent environment, packaged using **[GEM](https://github.com/axon-rl/gem)** (Axon-RL's in-process Gymnasium-style framework). The environment is a real Jupyter kernel running inside an [E2B](https://e2b.dev) cloud sandbox.

GEM is **in-process** — there is no server. It uses the classic Gymnasium API: `reset()` / `step()` returning the 5-tuple `(observation, reward, terminated, truncated, info)`.

## What this environment exposes

A single `JupyterGemEnv(gem.Env)` class. Tools are dispatched by **regex parsing** of the model's free-text action:

| Tag the model emits | Tool dispatched |
|---|---|
| `<code>...</code>` | Run Python in the persistent notebook |
| `<shell>...</shell>` | Run a shell command in the sandbox |
| `<edit>...</edit>` | Replace and re-run the last code cell |
| `<state/>` | Get a compact summary of executed cells |
| ` ```python ... ``` ` (fallback) | Treated like `<code>` if no tags present |

`step(action)` returns the **Gymnasium 5-tuple**:

```python
observation, reward, terminated, truncated, info = env.step("<code>print(42)</code>")
```

- `observation` — string with the formatted tool output(s)
- `reward` — `1.0` (or higher with bonuses) if `expected_output` substring appears in the latest tool output, else `0.0`
- `terminated` — natural episode end (correct answer reached)
- `truncated` — episode hit `max_turns` cap
- `info` — diagnostics (turns, errors)

GEM is the only one of the six frameworks that distinguishes `terminated` (won/lost) from `truncated` (max steps) — same convention as Gymnasium / classical RL.

## How to consume it

### Native pattern

```python
import gem
from env import JupyterGemEnv      # auto-registers as "jupyter:JupyterAgent-v0" on import

env = gem.make("jupyter:JupyterAgent-v0", task="Print 42", expected_output="42")
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step("<code>print(42)</code>")
```

Or instantiate directly:

```python
from env import JupyterGemEnv
env = JupyterGemEnv(task="Print 42", expected_output="42", max_turns=6)
obs, info = env.reset()
out = env.step("<code>print(42)</code>")
print(out)   # ('[Code output]: 42', 1.18, True, False, {...})
```

### Manual rollout (`rollout.py` — what we ship)

The rollout drives the loop manually:
1. Instantiate the env, `obs, info = env.reset()`.
2. Call the LLM (Qwen via HF Router by default).
3. Pass the **raw assistant text** as `action` to `env.step()`.
4. Append `obs` as the next `user` message.
5. Stop when `terminated` or `truncated` is True, or `MAX_TURNS` is hit.

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
cd 00-environments-101/envs/jupyter/gem
uv sync
uv run python rollout.py
```

### Sample output

```
GEM env:    in-process JupyterGemEnv (sandbox = E2B)
Provider:   hf-router
Model:      Qwen/Qwen3-Coder-480B-A35B-Instruct:together

[reset]
  instruction: Solve this task by writing code....
  info: {'task': '...', 'expected_output': '8.080222769206305', 'suffix': '...'}

──── turn 1 ────────────────────────────────────────
[assistant]
<code>
import numpy as np
data = [12, 19, 23, 31, 7, 14, 28, 5, 22, 18]
print(f"Mean: {np.mean(data)}")
print(f"Standard Deviation: {np.std(data)}")
</code>

[env-result reward=1.18 terminated=True truncated=False]
[Code output]: Mean: 17.9
Standard Deviation: 8.080222769206305

[done] terminated=True truncated=False, stopping.

FINAL  cumulative_reward=1.18  done=True
```

### Configuration knobs

| Variable | Default | Purpose |
|---|---|---|
| `ROLLOUT_MODEL` | `Qwen/Qwen3-Coder-480B-A35B-Instruct:together` | If model id contains `:`, route via HF Router. Else use OpenAI native. |
| `MAX_TURNS` | `6` | Hard cap on text-action turns. |

## What's in this folder

| Path | What it is |
|---|---|
| `rollout.py` | Self-contained consumer demo: `reset()` + manual `step()` loop. |
| `env.py` | `JupyterGemEnv(gem.Env)` with `reset()` / `step()` / `close()`. Auto-registers as `jupyter:JupyterAgent-v0`. |
| `tasks.py` | The 46 task definitions used when no explicit task is passed. |
| `e2b_sandbox.py`, `notebook_tracker.py` | Backend logic invoked from `step()`. |
| `pyproject.toml` | `gem-llm`, `e2b-code-interpreter`, `openai`, `python-dotenv`. |

## In-process means: no server to run

Same as SkyRL Gym and Verifiers: nothing to deploy. The E2B sandbox is created lazily in `step()` after the first `reset()`, and torn down by `env.close()`.

## How GEM compares to the SkyRL Gym sibling

GEM and SkyRL Gym are very similar — both are in-process, both parse text-action tags, both use E2B as the backend, both reward by string match. The differences:

| | GEM | SkyRL Gym |
|---|---|---|
| Base class | `gem.Env` | `BaseTextEnv` |
| `step()` returns | Gymnasium 5-tuple `(obs, r, terminated, truncated, info)` | `BaseTextEnvStepOutput(observations, reward, done, ...)` |
| Done semantics | `terminated` (won) vs `truncated` (max steps) | single `done` bool |
| Parallel rollouts | `make_vec()` / `AsyncVectorEnv` | Per-worker instance |
| Native trainer | None (BYO) | SkyRL trainer |

If you want classical Gymnasium compatibility, pick GEM. If you want to use SkyRL's training stack, pick SkyRL.

## References

- [GEM GitHub](https://github.com/axon-rl/gem)
- [HF Inference Providers — Chat Completion API](https://huggingface.co/docs/inference-providers/en/tasks/chat-completion)
- [E2B Code Interpreter](https://e2b.dev)
