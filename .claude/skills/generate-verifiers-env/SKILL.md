---
name: generate-verifiers-env
description: Builds a Verifiers (PrimeIntellect) variant of an RL environment. Use whenever someone asks to scaffold a Verifiers env, port to Verifiers, build an in-process toolkit, set up a `vf.ToolEnv` with a Rubric, or wire up a TRL `GRPOTrainer` rollout. Verifiers is the right framework when the user wants in-process tools (no HTTP server), structured tool calling driven by plain Python functions, composable reward rubrics with multiple grader functions, fast iteration with no Docker, or the cleanest path from prototype to TRL training. Output is a runnable `<env_dir>/verifiers/` folder with `env.py` (toolkit + standalone tool functions + `create_verifiers_env`), `rollout.py`, and `pyproject.toml`. Use for prompts like "make a verifiers env for X", "wrap my game in verifiers", or "set up a vf.ToolEnv".
---

# generate-verifiers-env

Build the Verifiers variant of an env. Verifiers is **in-process** — no HTTP server, no Docker, no HF Space. The trainer (or a manual rollout) imports tool functions directly from `env.py`.

## Concept

[PrimeIntellect Verifiers](https://github.com/PrimeIntellect-ai/verifiers) is a Python library — not a server framework. It provides `vf.ToolEnv` (multi-turn rollout), `vf.Rubric` (composable async graders), and adapters into TRL `GRPOTrainer`. The trainer or rollout owns the LLM client; the env owns the tools and the grader.

When the user has a shared domain module (`<domain>.py`) and wants a Verifiers variant, wrap it as a toolkit class plus standalone tool functions. Don't duplicate domain logic.

## Archetypes

| Archetype | Hallmarks |
|---|---|
| **Pure-Python game** | One `@tool`-style function, terminal reward via rubric checking the trajectory. |
| **Stateful sandbox in-process** | Toolkit owns the sandbox (E2B, browser); `initialize()` is lazy; `cleanup()` is mandatory in `finally`. |
| **Vision env** | Drive the toolkit manually (skip `vf.ToolEnv` since vision content blocks aren't first-class in verifiers' rollout). Send the screenshot in the user message each turn. |

## Two consumption paths (always provide both)

### Path A — `DesktopToolkit`-style class (used by TRL adapter + manual rollout)

```python
class WordleToolkit:
    def __init__(self): ...
    def initialize(self): ...     # lazy E2B / state init
    def cleanup(self): ...        # kill sandbox
    def reset(self): ...          # new episode
    def guess(self, word: str) -> str:
        """Submit a 5-letter word guess. Returns colored feedback."""
        ...
```

Public methods are introspected as tools by the TRL adapter. Docstrings become tool descriptions.

### Path B — `vf.ToolEnv` for native verifiers `env.evaluate(client, model)`

```python
def create_verifiers_env():
    import verifiers as vf
    from datasets import Dataset
    dataset = Dataset.from_list([{"question": t["task"], "answer": t["expected_output"]} for t in TASKS])
    async def correctness(completion, answer, **kwargs) -> float:
        # read from the completion trajectory; return 0.0–1.0
        ...
    rubric = vf.Rubric(funcs=[correctness])
    return vf.ToolEnv(tools=TOOL_FUNCTIONS, max_turns=8, dataset=dataset, rubric=rubric, system_prompt="...")
```

`TOOL_FUNCTIONS` is a list of **plain Python functions** (not bound methods). They can share state via a module-level toolkit instance.

## Recommended file layout

The user picks the actual paths. The canonical shape:

```
<env_dir>/verifiers/
├── pyproject.toml      # verifiers + e2b-* + datasets + python-dotenv + openai
├── __init__.py
├── env.py              # Toolkit class + standalone tool fns + create_verifiers_env()
├── rollout.py          # Drives the toolkit manually with the openai client
└── README.md
```

## Implementation order

### 1. The toolkit class

- `__init__` takes config (`api_key=""`, `app="firefox"`, etc.). **Don't** create the sandbox here — too eager.
- `initialize()` is the lazy creation hook. Always call it from each tool method.
- `cleanup()` kills the sandbox. Always call it from `finally` in the rollout.
- `reset()` calls `cleanup()` + reinitializes. Used between episodes by the TRL adapter.
- Each tool method:
  - takes typed args (used for OpenAI tool-schema generation via `inspect`)
  - has a docstring (becomes the tool description — first paragraph only)
  - calls `self.initialize()` first, mutates state, returns a string

### 2. Standalone tool functions for `vf.ToolEnv`

Module-level shared toolkit, plus thin wrappers:

```python
_shared: Optional[WordleToolkit] = None
def _kit():
    global _shared
    if _shared is None:
        _shared = WordleToolkit()
    return _shared

def guess(word: str) -> str:
    """Submit a 5-letter word guess."""
    return _kit().guess(word)

TOOL_FUNCTIONS = [guess]
```

Why both? The TRL adapter wants the toolkit class (per-rollout instance, isolated state). `vf.ToolEnv` wants free functions. Don't pick one — provide both.

### 3. The rubric

Rubrics are composable graders. Each grader is `async def func(completion, answer, **kwargs) -> float`. Combine multiple in a `vf.Rubric(funcs=[...])` and they're averaged (or weighted, see verifiers docs).

For a single-criterion env, one grader suffices:

```python
async def correctness(completion, answer, **kwargs) -> float:
    if not completion: return 0.0
    last = completion[-1].get("content", "") if isinstance(completion[-1], dict) else str(completion[-1])
    return 1.0 if answer.strip() in last.strip() else 0.0
```

For multi-criterion (e.g. computer-use envs that need both `terminate(success)` AND a state check):

```python
async def correctness(completion, answer, **kwargs) -> float:
    seen_success = any("terminated: success" in str(m) for m in completion)
    seen_expected = any(answer in str(m) for m in completion)
    return 1.0 if (seen_success and seen_expected) else (0.5 if seen_success else 0.0)
```

### 4. Rollout — `rollout.py`

Build OpenAI tool schemas from the function signatures + docstrings via `inspect`:

```python
def func_to_openai_tool(fn):
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    doc = (fn.__doc__ or "").strip().split("\n\n")[0]
    properties, required = {}, []
    for name, p in sig.parameters.items():
        ann = hints.get(name, str)
        origin = get_origin(ann)
        if origin in (list, "list"):
            inner = get_args(ann)
            properties[name] = {"type": "array", "items": {"type": "integer" if (inner and inner[0] is int) else "string"}}
        elif ann is int:    properties[name] = {"type": "integer"}
        elif ann is float:  properties[name] = {"type": "number"}
        elif ann is bool:   properties[name] = {"type": "boolean"}
        else:               properties[name] = {"type": "string"}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "function", "function": {
        "name": fn.__name__, "description": doc,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}
```

This pattern works for any toolkit. Use it as the standard adapter from Python signatures to OpenAI tool schemas.

For multimodal envs, drive the toolkit manually (don't use `vf.ToolEnv` since vision-content blocks aren't first-class in verifiers' rollout). Send the latest screenshot in the user message every turn:

```python
text, b64 = kit._ctrl.screenshot()      # if you exposed _ctrl
messages.append({"role": "user", "content": [
    {"type": "text", "text": "Latest screenshot:"},
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
]})
```

## Validation gates

1. **Toolkit imports cleanly** — `uv run python -c "from env import DesktopToolkit, TOOL_FUNCTIONS"`
2. **`vf.ToolEnv` builds** — `uv run python -c "from env import create_verifiers_env; env = create_verifiers_env(); print(env)"`
3. **Manual rollout** — `MAX_TURNS=3 uv run python rollout.py` runs end-to-end. Hits a real backend (E2B or whatever the env uses).

## Gotchas

- **`ModuleNotFoundError: attrs`** — `e2b-desktop` transitively needs `attrs` but doesn't pin it. Add `attrs>=23.0` to `dependencies`.
- **TypedDict vs dataclass for verifiers data structures** — most are TypedDicts. Access by key, not attribute. (Same trap exists in skyrl-gym; we hit it during the desktop_env port.)
- **Tool-schema `**kwargs` is forbidden** — vLLM (used by some trainers) can't introspect `**kwargs` for JSON schema generation. Define explicit params, even if empty.
- **Don't return huge strings** — verifiers passes the result through to the model verbatim. A 100KB log dump will blow your context. Truncate / summarize in the tool method.

## Reference

- `references/architecture.md` — `vf.ToolEnv` internals + Rubric composition + TRL adapter shape

## Official documentation

- [PrimeIntellect-ai/verifiers](https://github.com/PrimeIntellect-ai/verifiers) — source repo
- [Prime Intellect Verifiers docs](https://docs.primeintellect.ai/verifiers/overview)
- [verifiers/docs/environments.md](https://github.com/PrimeIntellect-ai/verifiers/blob/main/docs/environments.md) — `ToolEnv` / `StatefulToolEnv` / `MultiTurnEnv` reference
- [verifiers on PyPI](https://pypi.org/project/verifiers/) — latest is 0.1.9+ (Jan 2026)
