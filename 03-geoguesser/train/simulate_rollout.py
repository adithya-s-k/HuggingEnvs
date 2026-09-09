# /// script
# requires-python = ">=3.11"
# dependencies = [
#   # This imports grpo_geoguesser to reuse its environment wiring. Only trl and
#   # datasets are stubbed; trl is the heavy one and no gradient path runs here.
#   # torch and peft cannot be stubbed, because importing
#   # transformers.TrainerCallback pulls real symbols from both. CPU torch is
#   # enough, since nothing on the GPU path executes.
#   "openai>=1.55.0",
#   "transformers>=5.2.0",
#   "torch>=2.4.0",
#   "peft>=0.14.0",
#   "pillow>=10.0.0",
#   "numpy>=1.26.0",
#   "matplotlib>=3.8.0",
#   "fastmcp>=3.0.0",
#   "openenv>=0.3.1",
# ]
# ///
"""Simulate a TRL training rollout before paying for a GPU.

Mirrors what `GRPOTrainer(environment_factory=...)` does: derive tool schemas
from the environment class, call `reset` with a dataset row, let the model drive
the tool loop, then read `get_reward()`. The real trainer renders the
conversation through the chat template and feeds vLLM directly; here it goes
over the OpenAI-compatible API instead. The template puts a tool result in a
*user* turn wrapped in <tool_response> (verified separately), so sending the
result as a user message with an image block is a faithful stand-in.

What this can prove without a GPU: the model emits valid calls for our schemas,
the loop reaches a `guess`, the reward is non-zero, and an episode fits the
completion budget. What it cannot: anything about gradients.
"""

from __future__ import annotations

import argparse
import base64
import importlib.machinery
import inspect
import io
import os
import pathlib
import statistics as st
import sys
import types

from openai import OpenAI
from transformers.utils import get_json_schema  # before the stubs below

# peft, trl and datasets are stubbed so importing grpo_geoguesser does not drag
# the training stack onto a laptop. torch is deliberately NOT stubbed: importing
# transformers.TrainerCallback resolves through real torch, and a stub module
# with no `Tensor` breaks that import rather than avoiding it.
for name in ("trl", "datasets"):
    stub = types.ModuleType(name)
    # transformers probes `__spec__` and `__version__` on optional
    # dependencies, and raises on a stub that has neither.
    stub.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    stub.__version__ = "0.0.0"
    sys.modules[name] = stub
sys.modules["trl"].GRPOConfig = sys.modules["trl"].GRPOTrainer = object
sys.modules["datasets"].Dataset = object
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import grpo_geoguesser as g  # noqa: E402


def blocks_to_openai(blocks: list[dict]) -> list[dict]:
    """Environment content blocks -> OpenAI content parts."""
    parts = []
    for b in blocks:
        if b["type"] == "image":
            buf = io.BytesIO()
            b["image"].save(buf, format="JPEG", quality=88)
            url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
            parts.append({"type": "image_url", "image_url": {"url": url}})
        else:
            parts.append({"type": "text", "text": b["text"]})
    return parts


def rollout(client, model, env, row, tools, tool_map, max_turns):
    """One episode. Returns a record of what happened."""
    opening = env.reset(**row)
    messages = [{"role": "user", "content": blocks_to_openai(opening)}]
    calls, names, tokens_out, errors = 0, [], 0, []

    for _ in range(max_turns):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                max_tokens=1024,
                temperature=1.0,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {str(exc)[:120]}")
            break
        tokens_out += (r.usage.completion_tokens or 0) if r.usage else 0
        msg = r.choices[0].message
        if not msg.tool_calls:
            # No call: the model answered in prose. In training this ends the
            # rollout, which is exactly the failure to watch for.
            # In TRL's loop a reply with no tool call *ends* the rollout, so
            # this is terminal and scores zero. Keep the text: it says whether
            # the model was refusing, hedging, or answering in prose.
            errors.append(
                f"no tool_call (finish={r.choices[0].finish_reason}): "
                f"{(msg.content or '')[:150]!r}"
            )
            break
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [t.model_dump() for t in msg.tool_calls],
            }
        )
        for call in msg.tool_calls:
            calls += 1
            name = call.function.name
            names.append(name)
            fn = tool_map.get(name)
            if fn is None:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": name,
                        "content": f"no such tool: {name}",
                    }
                )
                errors.append(f"hallucinated tool {name}")
                continue
            import json as _json

            try:
                kwargs = _json.loads(call.function.arguments or "{}")
                out = fn(**kwargs)
            except Exception as exc:  # noqa: BLE001
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": name,
                        "content": f"error: {exc}",
                    }
                )
                errors.append(
                    f"{name}({call.function.arguments}) raised "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            # The template renders a tool result inside a user turn, so the
            # image travels as a user content block.
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": "(see next message)",
                }
            )
            messages.append({"role": "user", "content": blocks_to_openai(out)})
        if env._done:
            break

    return {
        "calls": calls,
        "tools": names,
        "tokens_out": tokens_out,
        "guessed": env._done and env._distance_km is not None,
        "distance_km": env._distance_km,
        "cost": env._cost,
        "reward": env.get_reward(),
        "errors": errors,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--endpoint",
        required=True,
        help="An OpenAI-compatible endpoint serving the model, with "
        "tool calling enabled (vLLM: --enable-auto-tool-choice).",
    )
    ap.add_argument("--model", default="Qwen/Qwen3.5-4B")
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument(
        "--same-task",
        type=int,
        default=None,
        help="Run every episode on this task index -- a real GRPO group.",
    )
    ap.add_argument(
        "--api-key-env",
        default="HF_TOKEN",
        help="Environment variable holding the endpoint's key. A local vLLM "
        "ignores it; the HF router needs it, which is what lets this run "
        "before you have a GPU.",
    )
    args = ap.parse_args()

    client = OpenAI(
        base_url=args.endpoint,
        api_key=os.getenv(args.api_key_env) or "dummy",
    )
    env = g.GeoGuesserTrainingEnv()
    probe = g.GeoGuesserTrainingEnv()
    methods = [
        m
        for name, m in inspect.getmembers(probe, predicate=inspect.ismethod)
        if name not in ("reset", "get_reward") and not name.startswith("_")
    ]
    tools = [get_json_schema(m) for m in methods]
    tool_map = {m.__name__: getattr(env, m.__name__) for m in methods}
    print(f"{len(tools)} tools: {sorted(tool_map)}")
    print(
        f"model {args.model} · {args.episodes} episodes · {args.max_turns} turns max\n"
    )

    rows = []
    for i in range(args.episodes):
        idx = args.same_task if args.same_task is not None else 100 + i * 37
        rec = rollout(
            client,
            args.model,
            env,
            {"prompt": [], "split": "train", "index": idx},
            tools,
            tool_map,
            args.max_turns,
        )
        rows.append(rec)
        d = (
            f"{rec['distance_km']:.0f} km"
            if rec["distance_km"] is not None
            else "no guess"
        )
        print(
            f"  ep{i}: {rec['calls']:>2} calls  {d:>10}  rw {rec['reward']:.3f}  "
            f"tok {rec['tokens_out']:>4}  {'/'.join(rec['tools'][:6])}"
            + (f"  ERR {rec['errors'][:1]}" if rec["errors"] else "")
        )

    print(f"\n{'':-<62}")
    guessed = [r for r in rows if r["guessed"]]
    print(f"reached a guess     : {len(guessed)}/{len(rows)}")
    print(f"mean reward         : {st.fmean(r['reward'] for r in rows):.3f}")
    if len(rows) > 1:
        print(
            f"reward spread (sd)  : {st.pstdev([r['reward'] for r in rows]):.3f}  <- GRPO needs this > 0"
        )
    print(f"mean tool calls     : {st.fmean(r['calls'] for r in rows):.1f}")
    print(f"mean output tokens  : {st.fmean(r['tokens_out'] for r in rows):.0f}")
    est = (
        st.fmean(r["tokens_out"] for r in rows)
        + st.fmean(r["calls"] for r in rows) * 196
    )
    print(f"est. completion len : ~{est:.0f} tokens (budget 6144)")
    errs = [e for r in rows for e in r["errors"]]
    print(f"errors              : {len(errs)}" + (f"  {errs[:3]}" if errs else ""))


if __name__ == "__main__":
    main()
