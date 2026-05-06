# Verifiers architecture (deep)

## Conceptual model

Verifiers is **not** a server framework. It's a Python library that gives you:

1. A `vf.ToolEnv` class that runs a multi-turn tool-calling rollout against any OpenAI-compatible client.
2. A `vf.Rubric` class that aggregates async grader functions into a single reward.
3. Adapters into TRL (`GRPOTrainer`) so the env can be a plain Python object passed to the trainer.

The trainer or rollout owns the LLM client. The env owns the tools and the grader. There's no HTTP layer.

## `vf.ToolEnv` shape

```python
env = vf.ToolEnv(
    tools: list[Callable],          # plain Python functions, signatures = OpenAI tool schemas
    max_turns: int,                  # hard cap per rollout
    dataset: Dataset,                # HF Dataset with `question`, `answer` columns
    rubric: vf.Rubric,               # grader composition
    system_prompt: str = "",
    parser: Optional[Parser] = None, # optional output parsing
)
```

Tool functions are introspected via `inspect.signature` + `get_type_hints` + the docstring. The first paragraph of the docstring becomes the tool description.

## Rubric

```python
async def correctness(completion, answer, **kwargs) -> float: ...
async def efficiency(completion, answer, **kwargs) -> float: ...

rubric = vf.Rubric(funcs=[correctness, efficiency])
```

`completion` is the message trajectory (list of dicts in OpenAI message format). `answer` is the ground truth from the dataset row. Each grader returns a float; the rubric averages them by default. Per-grader weights via `Rubric(funcs=[...], weights=[...])`.

The rubric runs **after** the rollout completes. There's no per-step reward — that's an ORS feature, not a Verifiers one.

## TRL adapter

For training with `GRPOTrainer`, Verifiers exposes an adapter that wraps a toolkit class:

```python
from trl import GRPOTrainer
trainer = GRPOTrainer(
    model=...,
    environment_factory=DesktopToolkit,    # the class, not an instance
    environment_config={"app": "firefox"},
    reward_funcs=[correctness],            # the rubric's funcs
    ...
)
```

The factory is invoked once per rollout. The toolkit's public methods (those without leading `_`) become the tools available to the model.

## Toolkit class contract

```python
class DesktopToolkit:
    def __init__(self, **config): ...
    def initialize(self): ...     # lazy backend init (E2B, browser, etc.)
    def cleanup(self): ...        # release backend
    def reset(self): ...          # cleanup + new episode
    def my_tool(self, x: int) -> str:
        """One-line description (becomes the tool description).

        Optional longer block (ignored).
        """
        ...
```

Public methods → tools. Private (leading `_`) → not exposed. Use this for shared helpers.

## Two consumption paths in one file

Provide **both** in `env.py`:

```python
# Path A — for the TRL adapter:
class DesktopToolkit: ...

# Path B — for native vf.ToolEnv:
_shared = None
def _kit(): ...
def my_tool(x: int) -> str: return _kit().my_tool(x)
TOOL_FUNCTIONS = [my_tool, ...]

def create_verifiers_env() -> vf.ToolEnv: ...
```

Why both: the TRL adapter expects a class with per-rollout instances (state isolation between concurrent rollouts in a batch). `vf.ToolEnv` expects free functions. The shared `_kit()` lazy-loads a single toolkit when used the second way.

## Tool-schema introspection rules

- Type hints become JSON-schema types: `int → integer`, `float → number`, `bool → boolean`, `str → string`, `List[int] → {type: array, items: {type: integer}}`.
- Default values mark parameters as optional.
- The first paragraph of the docstring is the description. Subsequent text is dropped.
- `**kwargs` is **forbidden** by some downstream trainers (vLLM-based) — JSON schema generation fails. Always use explicit params.

## Grader patterns

| Pattern | Use when |
|---|---|
| **Substring match** — `answer in completion[-1]["content"]` | Deterministic answer (math, code output). |
| **Multi-criterion** — return 0.0 / 0.5 / 1.0 based on combinations | Tasks needing both an action AND a state check (e.g. computer-use envs). |
| **LLM judge** — call another model in the grader | Subjective tasks (writing quality, creative). |
| **Unit tests** — execute test code in a sandbox | Coding tasks. |

Always return floats in `[0.0, 1.0]` unless you're explicitly using a different scale.

## What can go wrong

- `**kwargs in tool` — vLLM JSON-schema fail. Use explicit params.
- TypedDicts everywhere — `BaseTextEnvStepOutput` from skyrl-gym, similar in verifiers internals. Access by key.
- Returning huge strings from tools — fills the context. Truncate / summarize at the tool boundary.
- Forgetting `cleanup()` in the rollout `finally` — leaks sandboxes; cost adds up.
- Module-level shared state without lazy init — instantiates the backend at import time, which breaks `python -c "from env import ..."` smoke tests.
