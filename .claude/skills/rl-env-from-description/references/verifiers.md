# Verifiers quick reference (for the umbrella skill)

For implementation, defer to `generate-verifiers-env`. Planner-level summary here.

## What Verifiers is

[PrimeIntellect Verifiers](https://github.com/PrimeIntellect-ai/verifiers) — in-process tool-calling RL env framework. No HTTP, no Docker. The trainer or rollout imports tool functions directly. Designed for fast iteration and clean handoff to TRL `GRPOTrainer`.

## Core types

| Symbol | Source | What it is |
|---|---|---|
| `vf.ToolEnv` | `verifiers` | Multi-turn env with structured tools, dataset, and rubric. |
| `vf.Rubric` | `verifiers` | Composable reward graders. `Rubric(funcs=[...])`. |
| Tool functions | (your `env.py`) | Plain Python functions. Signatures + docstrings → OpenAI tool schemas via `inspect`. |
| Toolkit class | (your `env.py`) | Stateful wrapper. Public methods become tools for the TRL adapter. |

## Reward model

**Rubric-based, post-hoc**. Each `func` in the rubric is `async def correctness(completion, answer, **kwargs) -> float`. They run after the rollout completes and the floats are aggregated (averaged or weighted).

## When Verifiers beats OpenEnv / ORS

- You want zero deployment friction.
- The env is pure Python or runs an in-process sandbox per episode.
- You're iterating on reward design and want to redeploy graders without restarting a server.
- You're going straight to TRL training — Verifiers' adapter pattern is the cleanest.

## When Verifiers loses

- The env needs to run on different infra than the trainer (GPU pool vs CPU pool).
- You want HTTP for cross-language consumers.
- You want the agent's screen / terminal output to render in a separate UI for human inspection (Verifiers has no UI).

## Common confusions

- Two consumption paths exist (toolkit class for TRL adapter, free functions for `vf.ToolEnv`). Always provide both — they share state via a module-level shared toolkit.
- `**kwargs` in tool signatures is forbidden by some downstream trainers (vLLM-based) — JSON schema introspection fails. Use explicit params.
- TypedDicts are common in verifiers data structures — access by key, not attribute.
