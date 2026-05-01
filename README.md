# RL Environments 101: A Guide to Building RL Environments

A practical, hands-on guide to building RL environments for LLMs.

The idea is simple. Take the **same environment** and reimplement it across **multiple RL environment frameworks** (currently OpenEnv, ORS, NeMo Gym, Verifiers, SkyRL Gym, and GEM) so you can see, side by side, how each one models tools, state, rewards, and episodes. The goal isn't training. It's helping you understand the ecosystem: what each framework actually gives you, where the boundaries are, and what code you have to write yourself.

We start with two reference environments, a **Jupyter agent** (multi-turn, real code execution in an E2B sandbox) and a **Wordle solver** (multi-turn, pure Python), and will keep adding more over time. Each new environment is another "Rosetta stone" entry: same logic, different framework dialects.

If you've ever wondered:
- What is an "RL environment" really made of?
- Why do six frameworks call the same thing by six different names?
- Should I build my env as an HTTP server, or run it in-process?
- How do I plug any of these into TRL's `GRPOTrainer`?

…this repo is the answer. Each framework folder is a **runnable, minimal example** showing how to set up the environment and do a sample LLM rollout against it. We also walk through **how to think about designing an environment** in the first place: the components, the key decisions, and the common pitfalls, independent of any framework.

---

[![Blog post](./assets/blog_thumbnail.png)](https://huggingface.co/spaces/AdithyaSK/rl-environments-guide)

> 📝 **This repo is the companion code to the blog post:** **[RL Environments Guide →](https://huggingface.co/spaces/AdithyaSK/rl-environments-guide)**
> Read the blog for the full write-up. This repo contains the runnable implementations referenced throughout.

---

## Table of Contents

- [Repository Layout](#repository-layout)
- [The Reference Environments](#the-reference-environments)
- [Framework Cheat Sheet](#framework-cheat-sheet)
- [How to Set Up the Jupyter Agent Environment](#how-to-set-up-the-jupyter-agent-environment)
- [How to Set Up the Wordle Environment](#how-to-set-up-the-wordle-environment)
- [How to Build an RL Environment](#how-to-build-an-rl-environment) (framework-agnostic)
- [Further Reading](#further-reading)
- [Contributing](#contributing)

---

## Repository Layout

```
RL_Envs_101/
├── README.md                       # this file
├── assets/                         # blog thumbnail, diagrams
└── envs/
    ├── adapters/                   # unified BaseEnvironment to TRL adapter layer
    ├── jupyter_agent/              # E2B-sandboxed Jupyter agent (multi-turn, 4 tools)
    │   ├── openenv/                # HTTP, MCP protocol
    │   ├── ors/                    # HTTP, REST + SSE
    │   ├── nemo_gym/               # HTTP, REST + cookies
    │   ├── verifiers/              # in-process (Python)
    │   ├── skyrl_gym/              # in-process (Gym-style)
    │   ├── gem/                    # in-process (Gymnasium)
    │   ├── inference/              # standalone vLLM rollout server
    │   └── dataprep/               # dataset prep scripts
    └── wordle/                     # Wordle solver (multi-turn, 1 tool)
        ├── openenv/
        ├── ors/
        ├── nemo_gym/
        ├── verifiers/
        ├── skyrl_gym/
        └── gem/
```

---

## The Reference Environments

### Jupyter Agent (multi-turn, tool-using)
- **What the model does:** writes and executes Python in a real Jupyter kernel running inside an E2B cloud sandbox, until it answers the question.
- **Tools (4):** `add_and_execute_code_cell`, `edit_and_execute_current_cell`, `execute_shell_command`, `get_notebook_state`.
- **Why it's interesting:** real code execution, persistent state across turns, a real external backend (E2B).

### Wordle (multi-turn, deterministic)
- **What the model does:** plays Wordle over multiple turns. It guesses a 5-letter word, sees per-letter feedback, refines, and repeats until it solves the puzzle or runs out of attempts.
- **Tools (1):** `guess(word)`.
- **Why it's interesting:** pure-Python logic, no external services, persistent state across turns. The cleanest way to see how each framework models multi-turn episodes without the noise of a sandbox backend.

The Wordle environment is the *adapter proof*: it shows the same TRL adapter layer works on a totally different domain with zero changes.

---

## Framework Cheat Sheet

| Framework  | Type             | Tool syntax            | Reward model     | Deployable | Best for |
|------------|------------------|------------------------|------------------|------------|----------|
| **OpenEnv**    | HTTP (MCP)       | `@mcp.tool`            | External         | ✅ Docker / HF Space | Long-running sandboxes; MCP ecosystem |
| **ORS**        | HTTP (REST+SSE)  | `@tool` + Pydantic     | Per-tool-call    | ✅ Docker / HF Space / OpenReward | Server-decided rewards; OpenReward marketplace |
| **NeMo Gym**   | HTTP (REST)      | `app.post()`           | Post-episode `/verify` | ✅ Docker / HF Space | NVIDIA stack; Ray-based scaling |
| **Verifiers**  | in-process       | plain Python `def`     | `Rubric` system  | ❌          | Fast prototyping; bundled datasets |
| **SkyRL Gym**  | in-process       | inside `step()`        | `step()` returns | ❌          | Gym-style RL; SkyRL training stack |
| **GEM**        | in-process       | inside `step()`        | `step()` returns | ❌          | Gymnasium API; pure-Python games |

### The unified adapter pattern

All six frameworks plug into TRL's `GRPOTrainer` via the same `BaseEnvironment` contract under [`envs/adapters/`](./envs/adapters/):

```python
class BaseEnvironment:
    def __init__(self, **config): ...      # from environment_config
    def reset(self, **kwargs): ...         # kwargs = dataset row
    def close(self): ...                   # cleanup at end of episode
    reward: float                          # set during/after tool calls
    finished: bool                         # episode-done signal
    # any public method = a tool (auto-discovered via inspect)
```

TRL discovers tools by introspecting public methods on the env instance. Name, docstring, and type hints become the JSON schema the model sees. HTTP frameworks (OpenEnv, ORS, NeMo Gym) wrap a remote server. In-process frameworks (Verifiers, SkyRL, GEM) run the env class in the same Python process as the trainer.

---

## How to Set Up the Jupyter Agent Environment

The Jupyter agent uses **E2B** (a cloud Python sandbox) as its execution backend. You'll need an `E2B_API_KEY` regardless of framework.

```bash
export E2B_API_KEY=e2b_xxx          # https://e2b.dev
export HF_TOKEN=hf_xxx              # only needed for model downloads on rollouts
```

### 1. OpenEnv (HTTP server, MCP protocol)

```bash
cd envs/jupyter_agent/openenv
uv sync                              # installs openenv-core, fastmcp, e2b
cp .env.example .env                 # paste your E2B_API_KEY
python -m server.app                 # serves on :8000
```
The model talks to the server via MCP (JSON-RPC over HTTP). Tools are registered with `@mcp.tool` inside an `MCPEnvironment`. Already deployed: [`AdithyaSK/jupyter-agent-openenv`](https://huggingface.co/spaces/AdithyaSK/jupyter-agent-openenv).

### 2. ORS (HTTP server, REST + SSE)

```bash
cd envs/jupyter_agent/ors
uv sync                              # installs ors-sdk, e2b
cp .env.example .env
python server.py                     # serves on :8080
```
Tools are methods on an `ors.Environment` subclass. Each `@tool` returns a `ToolOutput(blocks=..., reward=..., finished=...)`, so **reward is server-side, per tool call**. Already deployed: [`AdithyaSK/jupyter-agent-ors`](https://huggingface.co/spaces/AdithyaSK/jupyter-agent-ors).

### 3. NeMo Gym (HTTP server, REST + cookies)

```bash
cd envs/jupyter_agent/nemo_gym
uv sync                              # installs nemo_gym (git), e2b. needs Python 3.12
cp .env.example .env
python server.py                     # serves on :11000
```
Tools are FastAPI `POST` endpoints on a `SimpleResourcesServer`. Sessions are managed via cookies. **Reward is computed post-episode** by a separate `/verify` endpoint. Already deployed: [`AdithyaSK/jupyter-agent-nemo-gym`](https://huggingface.co/spaces/AdithyaSK/jupyter-agent-nemo-gym).

### 4. Verifiers (in-process, plain Python)

```bash
cd envs/jupyter_agent/verifiers
uv sync                              # installs verifiers, e2b-code-interpreter
python rollout.py                    # runs an example rollout
```
No server. Tools are plain Python functions. Reward comes from a `Rubric`. The toolkit class is instantiated once per rollout and discovered via `inspect`.

### 5. SkyRL Gym (in-process, Gym-style)

```bash
cd envs/jupyter_agent/skyrl_gym
uv sync                              # installs skyrl-gym, e2b-code-interpreter
python rollout.py
```
A `BaseTextEnv` subclass with `init()` and `step()`. Tools are dispatched inside `step()` by parsing the model's text output. Reward and `done` flag are returned from `step()`.

### 6. GEM (in-process, Gymnasium 5-tuple)

```bash
cd envs/jupyter_agent/gem
uv sync                              # installs gem-llm, e2b-code-interpreter
python rollout.py
```
A `gem.Env` subclass with the classic `reset()` / `step()` Gymnasium API returning `(obs, reward, terminated, truncated, info)`. Has `spawn()` for parallel rollouts.

> Each subfolder has its own `README.md` with full deployment instructions (Docker, HF Spaces, etc.).

---

## How to Set Up the Wordle Environment

Wordle has **no external backend**. It's pure Python. This makes it the cleanest way to see what each framework actually requires.

```bash
# OpenEnv (HTTP, MCP)
cd envs/wordle/openenv && uv sync && python -m server.app

# ORS (HTTP, REST+SSE)
cd envs/wordle/ors && uv sync && python server.py

# NeMo Gym (HTTP, REST)
cd envs/wordle/nemo_gym && uv sync && python server.py

# Verifiers (in-process)
cd envs/wordle/verifiers && uv sync && python rollout.py

# SkyRL Gym (in-process)
cd envs/wordle/skyrl_gym && uv sync && python rollout.py

# GEM (in-process)
cd envs/wordle/gem && uv sync && python rollout.py
```

The same `guess(word)` tool, the same dictionary, the same scoring, but written six different ways. Compare any two `server.py` (or env class) files side-by-side and you'll learn more about the frameworks in 10 minutes than from any docs page.

A standalone `game.py` and `test_all_adapters.py` at the top of `envs/wordle/` lets you sanity-check all six implementations in one shot.

---

## How to Build an RL Environment

Framework-agnostic. This section is about **how to think** before you start writing code.

### Step 1. Define the loop in plain English

Before opening any framework's docs, write down:

1. **What is the model trying to do?** ("Solve coding tasks", "Play Wordle", "Browse the web until it finds X").
2. **What can it DO?** List the actions and tools.
3. **What does it SEE back?** The observation format.
4. **When is it done?** Termination condition.
5. **How do you score it?** The reward function, even a sketch.

If you can't write this in 10 lines, you don't have an environment yet. You have an idea.

### Step 2. Identify the components

Every RL environment, regardless of framework, is made of these eight pieces:

| Component | What it answers | Decide before coding |
|-----------|----------------|----------------------|
| **Tasks / Dataset** | *What problems should the model solve?* | List 5 to 10 example tasks by hand. |
| **Prompt template** | *How is the task presented?* | Write the system + user prompt. |
| **Tools / Actions** | *What can the model DO?* | Sketch function signatures. |
| **Observations** | *What does the model SEE back?* | Decide: raw string? structured? |
| **Execution backend** | *Where do actions actually run?* | Sandbox? In-process Python? None? |
| **State** | *What persists across turns?* | Session-scoped dict? File system? |
| **Reward / Rubric** | *How is success measured?* | Exact match? LLM-as-judge? Unit tests? |
| **Termination** | *When does it end?* | Max turns? `done` from a tool? |

Picking a framework before you've written these down is putting the cart before the horse.

### Step 3. Make four key decisions

These four decisions, more than any framework feature, determine what your environment will look like.

#### Decision A. In-process or HTTP server?

| Factor | Pick **in-process** if… | Pick **HTTP server** if… |
|---|---|---|
| Backend | Pure Python (game logic, math) | Sandbox / Docker / external service |
| Scale | <100 parallel rollouts | 100s to 1000s of concurrent sessions |
| Iteration speed | You're prototyping | Production deployment |
| Resource isolation | Doesn't matter | Env shouldn't share GPU node deps |
| Languages | Python only | Mixed (env can be in any language) |

**Rule of thumb:** start in-process. Move to HTTP only when you outgrow it.

#### Decision B. Single-turn or multi-turn?

- **Single-turn:** the model produces one output, you score it, done. (A math problem, classification, single-shot guess.) Reward is a function over the final answer.
- **Multi-turn:** the model takes multiple actions, sees results, decides what to do next. (Coding agent, Wordle, web browser, dialog.) State must persist, and you must decide *who* controls the loop (trainer, framework, or env).

Multi-turn is **far** more complex. If you can frame your task as single-turn, do it.

#### Decision C. Where does the reward come from?

| Pattern | When to use | Example framework |
|---|---|---|
| **External** (training script computes from final output) | Reward depends on the trajectory as a whole | OpenEnv, Verifiers, SkyRL, GEM |
| **Per tool call** (env returns reward with each action) | You can score every step independently | ORS |
| **Post-episode `/verify`** (separate endpoint scores the run) | Holistic LLM-as-judge or unit-test scoring | NeMo Gym |

If you're unsure, **start with external**. It's the most flexible and the easiest to debug.

#### Decision D. Stateless or stateful tools?

- **Stateless tools** (`add(a,b)` returning `a+b`) are trivial: no session needed.
- **Stateful tools** (`run_code(...)` in a Jupyter kernel) need session management. Every concurrent rollout needs its own isolated state. This is where session IDs, cookies, and sandbox lifetimes start to matter.

If your tools are stateful, you'll spend half your engineering time on state management. Plan for it.

### Step 4. Pick the framework that matches your decisions

| If you decided… | Strong match |
|---|---|
| In-process + bundled dataset + rubric system | **Verifiers** |
| In-process + Gymnasium API + parallel `make_vec()` | **GEM** |
| In-process + Gym-style + SkyRL trainer | **SkyRL Gym** |
| HTTP + MCP / community + HF Spaces | **OpenEnv** |
| HTTP + per-call rewards + OpenReward marketplace | **ORS** |
| HTTP + post-episode verify + NVIDIA stack | **NeMo Gym** |

When in doubt: **prototype in Verifiers (fastest), productionize in OpenEnv or ORS (deployable).**

### Step 5. Implement the smallest possible version first

Don't try to build the final environment on day one. Build the dumbest possible version:

1. **One task.** Hardcoded.
2. **One tool.** Even if your real env has ten.
3. **No reward.** Just print "got result: X".
4. **One rollout.** With a known model, e.g. `Qwen3-4B`, no training.

Get that working end-to-end. Only then add: more tasks, more tools, real rewards, batching, async, deployment.

### Step 6. Validate with a rollout, not with training

Training is a slow, expensive way to find out your environment is broken. Before you run *any* training:

- Manually call `env.reset()`, then call each tool, then `env.close()`.
- Run a single LLM rollout and **read the trajectory by hand**. Did the model see what you expected? Did the tool returns make sense? Did the reward fire correctly?
- If a human can't read the trajectory and tell whether the model did well, neither can a reward function.

The biggest mistakes in RL env design are caught by reading 5 trajectories. They will *not* be caught by 1000 training steps.

### Common pitfalls

- **Reward is too sparse.** Every rollout returns 0.0, so GRPO has no signal. Fix: design partial credit, or pick easier tasks for the smoke test.
- **Reward is too dense or leaky.** Model gets reward for behaviors that don't generalize. Fix: read trajectories, look for shortcuts.
- **Tasks are too easy.** Model solves them in one tool call, so there's no learning signal in multi-turn settings.
- **Tools are too powerful.** One tool can solve everything, so there's no exploration and no interesting behavior.
- **State leaks across rollouts.** Same sandbox or dict reused without reset, so episodes contaminate each other.
- **No timeout or max turns.** A buggy model loops forever and stalls training.
- **Observation format the model can't parse.** Huge JSON dumps, or stack traces longer than the context window.

---

## Further Reading

📝 **Blog post:** [RL Environments Guide](https://huggingface.co/spaces/AdithyaSK/rl-environments-guide), the full write-up this repo accompanies.

### Framework links

- [OpenEnv](https://github.com/meta-pytorch/OpenEnv) (Meta)
- [ORS / OpenReward](https://openrewardstandard.io/) (General Reasoning)
- [NeMo Gym](https://github.com/NVIDIA-NeMo/Gym) (NVIDIA)
- [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) (PrimeIntellect)
- [SkyRL Gym](https://github.com/NovaSky-AI/SkyRL/tree/main/skyrl-gym) (NovaSky-AI)
- [GEM](https://github.com/axon-rl/gem) (Axon-RL)

---

## Contributing

🚧 **More environments and framework implementations are on the way. PRs welcome!**

Good ways to contribute:
- **Port an existing env to a new framework** (e.g. add a 7th implementation).
- **Add a new reference environment.** Pick something with a clear loop and reward, and ship it across as many frameworks as you can.
- **Improve the rollout or setup scripts.** Make them clearer, faster, more portable.
- **Fix bugs or docs.** Typos, broken commands, outdated links.

Open an issue first if you're planning anything larger than a small fix.
