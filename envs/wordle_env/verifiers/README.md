# Wordle — Verifiers

A multi-turn Wordle environment, packaged using **[Verifiers](https://github.com/PrimeIntellect-ai/verifiers)** (PrimeIntellect's in-process Python framework). Pure Python, no external sandbox.

In-process — no server. The `WordleToolkit` class exposes 2 tool methods that the rollout discovers via `inspect`.

## What this environment exposes

`WordleToolkit` (in `env.py`) wraps the shared `WordleGame` from `envs/wordle_env/game.py` and exposes two methods as tools:

| Method | Description |
|---|---|
| `guess(word: str)` | Submit a 5-letter word. Returns colored feedback (`🟩🟨⬛`). |
| `get_history()` | View all previous guesses with their feedback. |

Plus a `reward` property (set by `WordleGame` based on win / partial-credit) and `set_answer(answer)` to fix the target word for deterministic rollouts.

## How to consume it

```python
from env import WordleToolkit

tk = WordleToolkit()
tk.reset()
print(tk.guess("crane"))   # '⬛⬛🟨🟨⬛ — 5 guesses remaining.'
print(tk.guess("slate"))
print(tk.get_history())
print(tk.reward)
```

## Run the rollout

`rollout.py` uses `inspect` to auto-build OpenAI tool schemas from `WordleToolkit`'s public methods, then drives a multi-turn loop with **Qwen3-Coder-480B** via HF Inference Providers.

### Setup

Repo-root `.env`:

```bash
HF_TOKEN=hf_...        # for HF Inference Providers (Qwen)
OPENAI_API_KEY=sk-...  # only if you swap to an OpenAI model
```

(No E2B key needed — Wordle is pure Python.)

### Run

```bash
cd envs/wordle_env/verifiers
uv sync
uv run python rollout.py
```

### Sample output

```
Verifiers env: in-process WordleToolkit (pure Python, no E2B)
Provider:      hf-router    Model: Qwen/Qwen3-Coder-480B-A35B-Instruct:together
Tools:         ['get_history', 'guess']

──── turn 1 ────────────────────────────────────────
[tool-call] guess({'word': 'crane'})
[tool-result] ⬛⬛⬛⬛⬛ — 5 guesses remaining.
...
[tool-result] ⬛🟩⬛⬛🟩 — Game over! The word was 'vivid'.

[done] game ended (reward=0.2).
```

### Configuration knobs

| Variable | Default | Purpose |
|---|---|---|
| `ROLLOUT_MODEL` | `Qwen/Qwen3-Coder-480B-A35B-Instruct:together` | Provider auto-detect by `:` suffix. |
| `MAX_TURNS` | `6` | Hard cap matching Wordle's 6-guess limit. |

## What's in this folder

| Path | What it is |
|---|---|
| `rollout.py` | Self-contained consumer demo using `inspect` to discover tools. |
| `env.py` | `WordleToolkit` class wrapping the shared `WordleGame`. |
| `pyproject.toml` | `verifiers` + rollout-side `openai`, `python-dotenv`. |

The `WordleGame` itself lives at `envs/wordle_env/game.py` (sibling), shared across all six framework folders.

## In-process means: no server to run

There's nothing to deploy. The toolkit creates a `WordleGame` instance the first time `guess()` is called.

## References

- [Verifiers GitHub](https://github.com/PrimeIntellect-ai/verifiers)
