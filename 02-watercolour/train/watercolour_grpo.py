# SPDX-License-Identifier: BSD-3-Clause

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openenv",
#     "trl",
#     "peft",
#     "trackio",
#     "datasets",
#     "torch",
#     "transformers",
#     # Only needed above the 4B this started on. `Qwen3.5-35B-A3B` is a
#     # multimodal MoE (`Qwen3_5MoeForConditionalGeneration`, processor
#     # `Qwen3VLProcessor`), so `AutoProcessor` resolves a video processor whose
#     # backends are not in transformers itself. Without these the run dies in
#     # `GRPOTrainer.__init__` with an `ImportError` carrying an empty message,
#     # which names nothing and looks like a memory problem.
#     "torchvision",
#     "av",
#     "num2words",
# ]
# ///

"""Train a small policy to paint with TRL's GRPOTrainer on `watercolour_env`.

Single-step env, so this is a plain prompt -> completion -> reward GRPO setup.

**The judge is on during training, and it has to be.** Unlike the sibling
`pelican_svg_env`, this environment has no deterministic quality layer to train
against: painterly quality has no cheap proxy, and the one thing that could have
served as one would be the term a policy learns to game. So every rollout costs
vision calls, two per reference, and `--references 1` is the default here rather
than the environment's own default of two.

**The environment cannot be uv-provisioned from its Space repo.** It needs a real
Chromium, which arrives with the image and not with `uv sync`, so this script
talks to an already-running environment over HTTP: a deployed Space, or the
container run locally. That is the one structural difference from the pelican
example.

The system prompt matters more than usual. `reset()` hands over a p5.brush API
reference, and without it no model tested up to 30B emitted a single real
`brush.*` call, so every rollout would fail the gate and the reward would be flat
zero. The script reads it from the environment rather than hardcoding a copy.

Run against a deployed Space:

    hf jobs uv run examples/watercolour_grpo.py --flavor a10g-small \\
        --secrets HF_TOKEN -- --steps 60 --push-to-hub \\
        --env-url https://your-username-watercolour-env.hf.space \\
        --out your-username/watercolour-grpo

Run locally against the container:

    docker run -d -p 8000:8000 -e HF_TOKEN=$HF_TOKEN watercolour-env:test
    python examples/watercolour_grpo.py --steps 5 --n-episodes 8
"""

from __future__ import annotations

import argparse
import datetime
import os
import base64
import contextlib
import itertools
import json
import pathlib
import re
import statistics
import sys
from collections import Counter

from datasets import Dataset
from openenv import GenericEnvClient
from trl import GRPOConfig, GRPOTrainer

DEFAULT_ENV_URL = "http://localhost:8000"

# Mirrors `sketch_source._FENCE` in the environment, which is what decides
# what actually gets rendered. The training script cannot import it: only this
# file travels to the job.
_FENCE = re.compile(r"```(?:js|javascript)?\s*(.*?)```", re.DOTALL)

# `EnvClient` defaults to 60s per message, and a rich sketch takes longer than
# that to paint on modest hardware: the same reference sketch renders in 8s on a
# laptop and 64s on a free-tier Space. The default cuts off legitimate renders as
# if the environment had hung.
#
# 900 rather than 300 because 300 was not enough. A run died at step 18 of 20
# after two and a half hours when one render passed five minutes, and it was the
# policy's own progress that did it: mean completion length had climbed from 1050
# to 1200 tokens, which is a busier sketch, which is a slower render. The env gets
# more expensive exactly as the policy gets better.
PROBE_BATCH = 8
MESSAGE_TIMEOUT_S = 900.0

# How often the paintings are pushed to the Hub during training. Uploading only
# at the end lost 144 of them when that run died: the artefact anybody outside
# the run would actually look at was sitting on a Job's local disk, which goes
# away with the Job. Every few calls it is.
# Every call. At three, two of every three groups were invisible, and the peaks
# kept landing in them: the reward spike that decided a run was in a call nobody
# could look at. One call is eight files and about 1.2 MB, so the cost is commit
# noise and nothing else.
FILM_UPLOAD_EVERY = 1


def _completion_text(completion) -> str:
    """TRL hands over either a list of chat messages or a raw string."""
    if isinstance(completion, list):
        if not completion or not isinstance(completion[-1], dict):
            raise ValueError(f"Unexpected completion shape from TRL: {completion!r}")
        return completion[-1]["content"]
    if isinstance(completion, str):
        return completion
    raise ValueError(f"Unexpected completion type from TRL: {type(completion)!r}")


def fetch_task(base_url: str, subject: str) -> tuple[str, str]:
    """Read the prompt and the API reference over a short-lived connection.

    Deliberately not reusing a long-lived client. An idle WebSocket held across
    the probe, which loads a model and generates completions on the GPU, gets
    closed by the server underneath it and takes the whole run down before step
    one.
    """
    with GenericEnvClient(
        base_url=base_url, message_timeout_s=MESSAGE_TIMEOUT_S
    ).sync() as client:
        observation = client.reset(subject=subject).observation
        return observation["prompt"], observation["system_prompt"]


def build_dataset(
    prompt: str,
    system_prompt: str,
    n_episodes: int,
    model: str,
    enable_thinking: bool,
) -> Dataset:
    """One row per episode, all on the same pinned subject.

    The prompt is identical every row, which is what we want: the variation
    being learned from is in the sampled completions, not in the question.

    The chat template is applied here rather than left to the trainer so that
    `enable_thinking` can be set. Qwen3 is a hybrid reasoning model with thinking
    **on by default**: left alone, a small one spends its whole completion budget
    inside `<think>` and never emits a sketch, so every rollout scores zero and
    GRPO has no variance to learn from.
    """
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model)
    text = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    )
    return Dataset.from_list([{"prompt": text} for _ in range(n_episodes)])


def make_cordura_reward(objetivo: int):
    """A reward that cannot be noisy, to find out whether the model trains at all.

    Every curve this project has produced is flat, and the model is a MoE trained
    through a LoRA that reaches 0.024% of it. Before blaming the watercolour reward
    it is worth knowing that the machinery moves at all, and nothing here can answer
    that: the environment's reward passes through a browser whose randomness was
    unseeded until today, two vision services that returned zero when they timed
    out, and a pairwise judge quantised to nine levels.

    So: count `brush.fill(` in the sketch and pay a smooth bump around `objetivo`.
    Deterministic, local, instant, and known to be reachable, because the layered
    prompt already moved that count from 10 to 22 without any training. If thirty
    steps of GRPO cannot walk it toward the target, the problem is not the reward.
    """
    import math
    import re as _re

    LLAMADA = _re.compile(r"brush\s*\.\s*fill\s*\(")
    call = itertools.count()

    def reward_func(completions, **kwargs) -> list[float]:
        index = next(call)
        cuentas, rewards = [], []
        for completion in completions:
            texto = _completion_text(completion)
            fenced = _FENCE.search(texto)
            fuente = fenced.group(1) if fenced else texto
            n = len(LLAMADA.findall(fuente))
            cuentas.append(n)
            rewards.append(math.exp(-(((n - objetivo) / 10.0) ** 2)))
        print(
            f"    call {index}: formas {cuentas}  "
            f"media {sum(cuentas) / len(cuentas):.1f}  "
            f"reward {sum(rewards) / len(rewards):.3f}",
            flush=True,
        )
        return rewards

    return reward_func


def make_reward_func(
    client,
    subject: str,
    references: int,
    film: pathlib.Path | None,
    push_film: str | None = None,
    film_dir: str = "",
):
    """Score each completion through the environment, never in the trainer.

    When `film` is set, every painting is kept, named by call index, position in
    the group and reward. A curve tells you the reward moved; a strip of the
    paintings in order tells you what moved, and that is the only artefact of a
    run like this that anybody outside it can read. Trackio logs scalars, so
    without this the images do not exist anywhere: the probe only samples the
    checkpoint before and after, which shows the endpoints and none of the climb.

    The cost is one base64 PNG per rollout on the wire, about 150 KB.
    """
    call = itertools.count()

    def reward_func(completions, **kwargs) -> list[float]:
        index = next(call)
        rewards, best, drawn = [], [], []
        sin_puntuar: list[int] = []
        piezas: dict[str, list[float]] = {}
        for position, completion in enumerate(completions):
            try:
                # The seed goes on `reset`, because OpenEnv's client drops
                # `step` kwargs before they reach the wire. Same seed for every
                # rollout in this group, so all of them are judged against the
                # same references and the reward difference between them is about
                # the paintings rather than about the draw.
                client.reset(
                    subject=subject,
                    references=references,
                    return_image=film is not None,
                    seed=index,
                )
                result = client.step({"response": _completion_text(completion)})
            except Exception as exc:
                # A rollout that times out or errors must not take the run down
                # with it: a slow render doing exactly that is how an earlier
                # attempt ended, at step 18 of 20. But it is not worth zero
                # either. This is infrastructure failing, not a bad painting, so
                # it goes as `None` and leaves the group, the same as a render
                # that would not run or a scorer that did not answer.
                #
                # `close()` matters as much as the `None`. OpenEnv's client holds
                # one persistent websocket and `_ensure_connected` only
                # reconnects when the socket came from another event loop, so a
                # socket closed by the far end stays cached and every later call
                # raises `ConnectionClosedError` forever. That killed v21b at
                # step 46 and v21c at step 57: the Space answered `/reset` in
                # 0.3s from outside while the job could not reach it at all.
                # Dropping the client here forces the next call to build a fresh
                # one.
                print(
                    f"    rollout {index}/{position} failed, going as None: "
                    f"{type(exc).__name__}",
                    flush=True,
                )
                try:
                    client.close()
                except Exception:
                    pass
                rewards.append(None)
                sin_puntuar.append(position)
                continue
            observation = result.observation or {}
            # A scorer that could not answer is not a verdict of zero. When the gate
            # passed but `quality_scored` or `judged` came back false, the environment
            # already treated the missing term as zero, and that zero is wrong twice
            # over: it punishes the painting, and by dragging the group mean down it
            # hands every sibling a spurious advantage. Measured on v17, where the
            # judge weighs nothing so the reward inverts cleanly: one rollout in sixty
            # scored 0.068 with the gate satisfied, and the same painting scores +5.94
            # on HPSv3 called by hand, which is pool level.
            #
            # `None` is what TRL wants here. It marks the row NaN, excludes it from the
            # nan-aware group baseline, and forces its advantage to zero, so the other
            # seven still train normally. If every rollout in a group comes back None
            # the trainer raises with the offending prompt instead of continuing in
            # silence.
            # A missing judge verdict only matters when the judge is worth something.
            # With `JUDGE_WEIGHT` at zero the pairwise term contributes nothing to the
            # reward, so discarding the rollout over it threw away a painting that had
            # already paid for its generation, its render and its HPSv3 call: one of
            # v20's six unscored rollouts went that way.
            falta_juez = not observation.get("judged", True) and (
                observation.get("judge_weight", 1.0) > 0.0
            )
            # The browser failing is not the sketch failing. `render_unavailable` says
            # the canvas never appeared and nothing errored, which scored zero and
            # dragged the whole group; see `GateResult.render_unavailable`.
            incompleto = observation.get("render_unavailable") or (
                observation.get("gate_passed")
                and (not observation.get("quality_scored", True) or falta_juez)
            )
            if incompleto:
                sin_puntuar.append(position)
                rewards.append(None)
            else:
                rewards.append(float(result.reward or 0.0))
            reward = float(result.reward or 0.0)
            # Say why the gate refused, out loud. Without this the only trace of a
            # rejection is a missing film file, and counting missing files told us
            # that 30% of a 35B's rollouts were rejected while a 40-sample probe of
            # the same model found none: three separate guesses at the cause were
            # all wrong. The observation already carries the codes.
            # The components, not just the total. The environment returns judge,
            # quality, length and pigment per rollout and only the sum was kept, so
            # answering "which term is moving the reward" meant reconstructing them
            # by difference from the film filenames. That produced impossible
            # negative judge scores and a wrong conclusion stated out loud.
            for clave in ("judge_score", "quality_score", "length_score", "paint_fraction"):
                if not incompleto and observation.get(clave) is not None:
                    piezas.setdefault(clave, []).append(float(observation[clave]))
            if not observation.get("gate_passed"):
                # The text too, not just the code. A 40-sample probe of the base
                # model finds no source rejection while training rejects 30% of
                # the same model at step zero, where the adapter is still zero.
                # Five explanations have been ruled out; what the two paths do not
                # share is that the probe sends the raw generation and this sends
                # whatever TRL hands back, so the text is the thing to look at.
                sent = _completion_text(completion)
                print(
                    f"    rechazo {index}/{position}: "
                    f"{', '.join(observation.get('violations') or []) or 'sin codigo'}"
                    f"  js={(observation.get('js_errors') or ['-'])[0][:50]}"
                    f"  len={len(sent)}  inicio={sent[:70]!r}  fin={sent[-40:]!r}",
                    flush=True,
                )
            judged = ((result.observation or {}).get("breakdown") or {}).get("judge")
            drawn.append(
                tuple(
                    sorted(
                        c["reference"] for c in (judged or {}).get("comparisons", [])
                    )
                )
            )
            if film is not None:
                image = (result.observation or {}).get("image_png_base64")
                if image:
                    film.mkdir(parents=True, exist_ok=True)
                    # `reward` here is the environment's raw number, and for an
                    # unscored rollout it is the reward the environment would have
                    # given, not the one that trained: that row went in as None.
                    # Without the marker every contact sheet reads those as terrible
                    # paintings that scored 0.065, which is how four perfectly good
                    # flowers ended up filed as reward failures.
                    marca = "_none" if incompleto else ""
                    name = f"c{index:04d}_g{position:02d}_r{reward:.3f}{marca}.png"
                    path = film / name
                    path.write_bytes(base64.b64decode(image))
                    best.append((reward, path))
                    # The sketch next to the painting. Of the reference pool we
                    # have all 206 sources, so we can count filled shapes, fill
                    # opacities and vertices per shape; of our own rollouts we had
                    # only images, which is why the question of why our flowers
                    # come out hollow could not be answered on the code side.
                    #
                    # The fenced block, the same thing the environment renders,
                    # not the raw reply. The first version of this wrote the reply
                    # and the files came out with the model's prose and the
                    # backticks in them, so they parsed for counting but would not
                    # render: `sketch created no canvas`.
                    fenced = _FENCE.search(_completion_text(completion))
                    path.with_suffix(".js").write_text(
                        fenced.group(1).strip() if fenced
                        else _completion_text(completion).strip()
                    )
        # The group is only comparable if every rollout faced the same opponents.
        # OpenEnv drops `step` kwargs silently, so the seed goes on `reset`, and a
        # regression there would look like nothing at all: the reward would still
        # move, just partly on the draw. Asserted out loud once per call instead.
        if sin_puntuar:
            print(
                f"    call {index}: {len(sin_puntuar)} rollouts sin puntuar "
                f"(un scorer no respondio), posiciones {sin_puntuar}. "
                "Van como None, no como cero.",
                flush=True,
            )
        seen = {d for d in drawn if d}
        if len(seen) > 1:
            print(
                f"    WARNING call {index}: {len(seen)} different reference sets "
                f"across {len(drawn)} rollouts, so the group is not comparable",
                flush=True,
            )
        elif seen:
            print(
                f"    call {index}: all rollouts judged against the same "
                f"{len(next(iter(seen)))} references",
                flush=True,
            )

        if piezas:
            import statistics as _st

            # Mean *and* spread, per component. GRPO subtracts the group mean, so a term
            # with a big mean and no spread inside the group contributes exactly nothing
            # to the gradient however much weight it carries. Logging only the mean is
            # what made "which term is moving the reward" unanswerable for a whole day.
            partes = {}
            for k, v in piezas.items():
                if not v:
                    continue
                partes[k] = _st.mean(v)
                partes[f"{k}__disp"] = _st.pstdev(v) if len(v) > 1 else 0.0
                partes[f"{k}__min"] = min(v)
                partes[f"{k}__max"] = max(v)
            print(
                f"    call {index} desglose: "
                + "  ".join(
                    f"{k.replace('_score', '')} {partes[k]:.3f}"
                    f"±{partes[k + '__disp']:.3f}"
                    f"[{partes[k + '__min']:.2f},{partes[k + '__max']:.2f}]"
                    for k in sorted(piezas)
                    if k in partes
                )
                + f"   rollouts {len(rewards)}",
                flush=True,
            )
            # The tier each drawn reference came from, because the same twelve paintings
            # scored 1 to 10 zeros out of twelve depending only on which references they
            # faced, and nothing recorded which ones those were.
            gradas = [r.split("_")[0] for d in drawn if d for r in d]
            if gradas:
                import collections as _co

                print(
                    f"    call {index} referencias: "
                    + "  ".join(f"{k} {v}" for k, v in sorted(_co.Counter(gradas).items())),
                    flush=True,
                )
            try:
                import trackio

                trackio.log({f"parte/{k}": v for k, v in partes.items()}, step=index)
            except Exception:
                pass

        if film is not None and best:
            # One painting per call into trackio, the best of the group, so the
            # dashboard shows what the reward curve is made of. Only the best,
            # because eight per call turns the run page into a contact sheet
            # nobody scrolls. The rest are on disk and uploaded with the
            # checkpoint.
            #
            # `step` is deliberately the call index rather than the trainer's
            # global step, which the reward function has no access to. It is
            # monotonic and one per generation batch, which is what the strip
            # needs; it will not line up exactly with the loss curve's x-axis.
            top = max(best)
            try:
                import trackio

                trackio.log(
                    {
                        "painting": trackio.Image(
                            top[1], caption=f"call {index}, reward {top[0]:.3f}"
                        )
                    },
                    step=index,
                )
            except Exception as exc:
                # A dashboard that cannot take an image must not end a training
                # run: the paintings are on disk either way.
                print(
                    f"    trackio image skipped: {type(exc).__name__}: {exc}"[:150],
                    flush=True,
                )

            if push_film and index % FILM_UPLOAD_EVERY == 0:
                # Only this call's files, matched by prefix, so the upload stays
                # small instead of re-walking everything painted so far.
                try:
                    from huggingface_hub import HfApi

                    api = HfApi()
                    # The repo does not exist until `push_to_hub` runs at the very
                    # end, so every intermediate upload before that failed with
                    # "repository not found" and was swallowed by the except
                    # below: five steps in, zero paintings on the Hub.
                    api.create_repo(push_film, repo_type="model", exist_ok=True)
                    api.upload_folder(
                        repo_id=push_film,
                        folder_path=str(film),
                        path_in_repo=f"film/{film_dir}" if film_dir else "film",
                        allow_patterns=[f"c{index:04d}_*"],
                        commit_message=f"Paintings from call {index}",
                    )
                except Exception as exc:
                    print(
                        f"    film upload skipped: {type(exc).__name__}: {exc}"[:200],
                        flush=True,
                    )
        return rewards

    return reward_func



def _load_base(model_id, **kwargs):
    """Load a base model as the class its config names.

    `AutoModelForCausalLM` picks the text-only variant of a multimodal
    checkpoint, which puts the layers at `model.layers` instead of
    `model.language_model.layers` and makes every adapter key miss.
    """
    import transformers

    config = transformers.AutoConfig.from_pretrained(model_id)
    cls = getattr(transformers, config.architectures[0])
    return cls.from_pretrained(model_id, **kwargs)


def probe(
    base_url: str,
    subject: str,
    texts,
    save_to: pathlib.Path | None = None,
) -> dict:
    """Score finished completions and keep the paintings.

    Run before and after training. The paintings themselves are kept, not just
    the scores: a before-and-after pair of actual pictures is the only way a
    reader can judge whether "the reward rose" means anything, and a run that
    discards them leaves the claim resting on the author's word.
    """
    if save_to is not None:
        save_to.mkdir(parents=True, exist_ok=True)
    samples, gate_failures = [], 0
    for index, text in enumerate(texts):
        # A client per sample. One client for the whole probe held a websocket
        # open across every render, and the server closes an idle socket
        # underneath a long call: at twelve samples it survived, at forty it died
        # in `reset` with `ConnectionClosedOK` before a single painting was
        # scored. The sibling revise script already opens one per painting for
        # exactly this reason.
        with GenericEnvClient(
            base_url=base_url, message_timeout_s=MESSAGE_TIMEOUT_S
        ).sync() as client:
            client.reset(subject=subject, return_image=True, seed=index)
            result = client.step({"response": text})
        observation = result.observation
        passed = bool(observation.get("gate_passed", False))
        gate_failures += not passed
        record = {
            "index": index,
            "reward": float(result.reward or 0.0),
            "judge_score": observation.get("judge_score", 0.0),
            "judged": observation.get("judged", False),
            "gate_passed": passed,
            "paint_fraction": observation.get("paint_fraction", 0.0),
            "finished": observation.get("finished", False),
            "violations": observation.get("violations", []),
            "js_errors": observation.get("js_errors", [])[:2],
        }
        if save_to is not None:
            image = observation.get("image_png_base64")
            if image:
                (save_to / f"{index:03d}.png").write_bytes(base64.b64decode(image))
            (save_to / f"{index:03d}.js").write_text(text)
        samples.append(record)

    def mean(key):
        values = [s[key] for s in samples]
        return round(statistics.mean(values), 4) if values else 0.0

    summary = {
        "n": len(samples),
        "reward": mean("reward"),
        "judge_score": mean("judge_score"),
        "paint_fraction": mean("paint_fraction"),
        "gate_failures": gate_failures,
        "unfinished": sum(1 for s in samples if s["gate_passed"] and not s["finished"]),
    }
    if save_to is not None:
        (save_to / "samples.json").write_text(
            json.dumps({"summary": summary, "samples": samples}, indent=2)
        )
    return summary


def sample_completions(
    model_path: str,
    prompt: str,
    system_prompt: str,
    count: int,
    max_new_tokens: int,
    enable_thinking: bool = False,
    top_p: float = 1.0,
    top_k: int = 0,
):
    """Samples from a checkpoint, for the before and after probe.

    Applies the chat template with the same `enable_thinking` and the same
    system prompt the training dataset used. Probing in a different template
    mode, or without the API reference, would measure the wrong thing.
    """
    import torch
    from transformers import AutoTokenizer

    # `AutoModelForCausalLM` resolves Qwen3.5-35B-A3B to its text-only variant,
    # whose layers sit at `model.layers`. The real checkpoint is multimodal and
    # keeps them at `model.language_model.layers`, so 700 of the adapter's 920
    # tensors silently failed to load and the after-probe measured the base model.
    # Instantiating the class the config actually names avoids guessing which Auto
    # class a given model wants.
    # `save_model` on a LoRA run writes an adapter, not a model, and loading an
    # adapter directory with `AutoModelForCausalLM` produces a half-placed model
    # that dies with "mat2 is on cpu" on the first matmul. The adapter has to be
    # applied to its own base.
    # An adapter can arrive as a local directory, which is how the after-probe gets
    # it, or as a Hub id, which is how `--resume-adapter` gets it for the
    # before-probe. Only the local case existed, and the Hub case then fell through
    # to `AutoModelForCausalLM` on a repo that has no base model in it.
    local = pathlib.Path(model_path) / "adapter_config.json"
    adapter = local
    if not local.exists():
        try:
            from huggingface_hub import hf_hub_download

            adapter = pathlib.Path(hf_hub_download(model_path, "adapter_config.json"))
        except Exception:
            adapter = local
    if adapter.exists():
        import json

        from peft import PeftModel

        base_id = json.loads(adapter.read_text())["base_model_name_or_path"]
        tokenizer = AutoTokenizer.from_pretrained(base_id)
        base = _load_base(base_id, torch_dtype=torch.bfloat16, device_map="auto")
        model = PeftModel.from_pretrained(base, model_path)
    else:
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = _load_base(model_path, torch_dtype=torch.bfloat16, device_map="auto")
    text = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    )
    # In chunks, because the whole probe used to go through `generate` as one
    # batch. That held at twelve samples and thrashed the allocator dead at forty:
    # the KV cache is batch x tokens, so asking for forty sequences of 6,144
    # tokens wanted tens of gigabytes on top of the model, and the run sat for an
    # hour emitting allocator warnings with 13MB free of 85GB. The sample count is
    # what makes the probe worth reading, so it is the batching that gives way.
    out: list[str] = []
    for start in range(0, count, PROBE_BATCH):
        batch = min(PROBE_BATCH, count - start)
        inputs = tokenizer([text] * batch, return_tensors="pt").to(model.device)
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.9,
                # Same truncation as training. Sampling the probe untruncated while
                # training truncated would make the before/after measure two different
                # policies.
                top_p=top_p,
                top_k=top_k if top_k else None,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        prompt_length = inputs["input_ids"].shape[1]
        out.extend(
            tokenizer.batch_decode(
                generated[:, prompt_length:], skip_special_tokens=True
            )
        )
    return out


def report(before: dict, after: dict) -> None:
    """Say plainly what moved.

    Gate admission and judged quality are reported apart on purpose. A policy
    can learn to clear the gate, which only asks that it used the library and
    put paint down, without painting anything a judge prefers. That would show
    up here as gate failures falling while the judged score sits still.
    """
    print(
        f"reward {before['reward']:.3f} -> {after['reward']:.3f}, "
        f"judged {before['judge_score']:.3f} -> {after['judge_score']:.3f}, "
        f"gate failures {before['gate_failures']} -> {after['gate_failures']}, "
        f"unfinished {before['unfinished']} -> {after['unfinished']}"
    )
    gate_gain = before["gate_failures"] - after["gate_failures"]
    judge_gain = after["judge_score"] - before["judge_score"]
    if gate_gain > 0 and judge_gain <= 0.02:
        print(
            "WARNING: the policy learned to clear the gate without painting "
            "anything the judge prefers. Read that as learning the admission "
            "rules, not the medium."
        )
    elif judge_gain > 0.02:
        print("The judged score moved, so the paintings themselves got better.")
    else:
        print("Nothing moved to speak of.")


def main() -> None:
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument(
        "--env-url",
        default=DEFAULT_ENV_URL,
        help="A running watercolour_env. The environment needs a real Chromium, "
        "so unlike the pelican example it cannot be provisioned from its Space "
        "repo with uv; point this at a deployed Space or the local container.",
    )
    ap.add_argument(
        "--model",
        default="Qwen/Qwen3-4B-Instruct-2507",
        help="4B rather than something smaller. Measured: with the API "
        "reference in context a 4B emits ten to thirteen real brush calls and "
        "no bare p5 primitives, so the gate is passable and the reward has "
        "variance. Smaller models were not measured and the pelican run at "
        "1.7B had no usable judged signal at all.",
    )
    ap.add_argument(
        "--subject",
        default="a peach hibiscus",
        help="Pinned so training and reporting stay on one question.",
    )
    ap.add_argument(
        "--references",
        type=int,
        default=1,
        help="References per rollout. Each one costs two vision calls, since "
        "every comparison runs in both presentation orders. One is the default "
        "here and two is the environment's own: a training run pays this on "
        "every rollout of every step.",
    )
    ap.add_argument(
        "--top-p",
        type=float,
        default=1.0,
        help="Nucleus cutoff. TRL defaults to 1.0, which truncates nothing; this "
        "model's own generation_config.json asks for 0.95.",
    )
    ap.add_argument(
        "--top-k",
        type=int,
        default=0,
        help="Top-k cutoff. TRL defaults to 0, which truncates nothing; this model's "
        "own generation_config.json asks for 20.",
    )
    ap.add_argument(
        "--enable-thinking",
        action="store_true",
        help="Let a hybrid reasoning model think before answering. Off by "
        "default: the thinking eats the completion budget and no sketch comes "
        "out, so every rollout scores zero.",
    )
    ap.add_argument("--n-episodes", type=int, default=256, help="Dataset size.")
    ap.add_argument(
        "--lr-scheduler",
        default="linear",
        help="`linear` decays to zero at `--steps`, which halves the distance the "
        "optimiser covers and puts the smallest updates on the most informative "
        "late steps. Measured: v17 had spent 79% of its whole run's parameter-space "
        "displacement by step 33 of 60. `constant_with_warmup` keeps the step size.",
    )
    ap.add_argument("--warmup-steps", type=int, default=0)
    ap.add_argument(
        "--scale-rewards",
        default="group",
        help="`group` divides advantages by the group's own standard deviation, so "
        "one gate rejection inflates it and shrinks the other seven rollouts' "
        "advantages. Measured over three runs: rejections appear in 55% of groups "
        "and cost the survivors a factor of 0.76 to 0.84. `none` is Dr. GRPO's "
        "recommendation and removes that coupling.",
    )
    ap.add_argument(
        "--all-linear",
        action="store_true",
        help="Target every linear layer instead of the hand-written module list. "
        "The list is written for a dense transformer and reaches 0.9% of this "
        "model's weights; TRL's LoRA guide asks for `all-linear` and rank 1-32.",
    )
    ap.add_argument("--steps", type=int, default=60)
    ap.add_argument(
        "--lr",
        type=float,
        default=2e-5,
        help="1e-6 is a full fine-tuning rate and was the default for five runs, "
        "all of them with LoRA, where only the adapter moves and the effective "
        "step is far smaller. The symptom was not a bad reward but three flat "
        "signals: entropy, completion length and the paintings themselves "
        "unchanged over thirteen steps while the reward oscillated inside the "
        "noise of the reference draw.",
    )
    ap.add_argument(
        "--per-device-batch-size",
        type=int,
        default=2,
        help="Sequences per forward pass. This is the memory knob, not a "
        "quality knob: the logits tensor is [batch, length, vocab] and "
        "accelerate upcasts it to fp32 regardless of bf16. Keep it small and "
        "raise --gradient-accumulation-steps instead.",
    )
    ap.add_argument("--gradient-accumulation-steps", type=int, default=4)
    ap.add_argument(
        "--num-generations",
        type=int,
        default=8,
        help="Completions per prompt. Must divide "
        "per-device-batch-size x gradient-accumulation-steps.",
    )
    ap.add_argument(
        "--max-completion-length",
        type=int,
        default=1536,
        help="A sketch needs room. Measured sketches from a 4B run 230 to 400 "
        "tokens, and the reference paintings are longer than that, so leave "
        "headroom for the policy to grow into.",
    )
    ap.add_argument(
        "--probe-samples",
        type=int,
        default=24,
        help="Completions to score before and after training. Zero skips the "
        "probe. Do not go small: at n=4 the before and after are noise.",
    )
    ap.add_argument(
        "--lora",
        action="store_true",
        help="Train a LoRA adapter instead of the whole model. On by default in "
        "practice for anything above ~1B: a full-precision GRPO step on a 4B "
        "wants weights plus gradients plus optimiser state, which is roughly "
        "56 GB and does not fit the cheap 24 GB flavours. With LoRA a 4B fits "
        "an a10g-small.",
    )
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument(
        "--cordura",
        type=int,
        default=0,
        help="Control run: replace the environment's reward with a deterministic "
        "count of brush.fill calls, paid on a bump around this target. No browser, "
        "no judge, no HPSv3, no network. Answers whether this MoE trains at all "
        "through this LoRA, which nothing else in this script can.",
    )
    ap.add_argument(
        "--lora-experts",
        action="store_true",
        help="Reach the 256 routed experts and the 30 linear-attention layers as "
        "well, taking the adapter from 8.4M trainable parameters to 941.9M. Costs "
        "roughly twice the wall clock per step.",
    )
    # Off by default so every run before this one still reproduces. A 4B trains
    # fine on the defaults; a 35B does not, because full precision puts 140GB of
    # weights on a card that has 141GB in total.
    # Off by default. A run of the 4B converged to one tiny stereotyped flower and
    # repeated it: visual diversity between the eight paintings of a group fell to
    # 0.016, which is inside the 0.005-0.015 that two renders of the *same* code
    # differ by from p5.brush's own noise. Its reward still rose, because a
    # reliable recipe beats a bold attempt that sometimes floods or throws, and
    # GRPO rewards being above the group mean. Its entropy sat at 0.152 while a
    # 35B that kept diversifying sat at 0.445.
    ap.add_argument(
        "--entropy-target",
        type=float,
        default=0.0,
        help=(
            "Mean per-token entropy to hold, in nats. Zero disables it. TRL's "
            "guidance is to set it near the entropy seen early in training: 0.2 "
            "for the 4B, 0.45 for the 35B."
        ),
    )
    ap.add_argument(
        "--bf16",
        action="store_true",
        help="Load and train in bfloat16. Required above roughly 10B parameters.",
    )
    ap.add_argument(
        "--gradient-checkpointing",
        action="store_true",
        help="Trade compute for activation memory. Required above roughly 10B.",
    )
    ap.add_argument("--out", default="watercolour-grpo-Qwen3-4B")
    ap.add_argument(
        "--push-to-hub",
        action="store_true",
        help="Upload the checkpoint. Worth doing: a Job's filesystem goes away "
        "with the Job, so a run without this leaves nothing behind but stdout.",
    )
    ap.add_argument(
        "--film",
        action="store_true",
        help="Keep every painting made during training, named by call, group "
        "position and reward. This is how the run becomes something anyone can "
        "look at: the reward curve says it improved, the strip of paintings in "
        "order says what improved. Uploaded with the checkpoint.",
    )
    ap.add_argument(
        "--resume-from-checkpoint",
        default=None,
        help="Path or Hub id of a `last-checkpoint` folder to continue from, "
        "restoring the optimiser moments, the scheduler, the step counter and the "
        "RNG state. Unlike `--resume-adapter`, which only reloads the weights and "
        "restarts everything else, this makes a run that died indistinguishable "
        "from one that never stopped.",
    )
    ap.add_argument(
        "--resume-adapter",
        default=None,
        help="A LoRA adapter to continue training instead of starting a new one, "
        "as a Hub id or a local path. Isolates the question of whether more steps "
        "help, since nothing else has to change to ask it.",
    )
    ap.add_argument(
        "--run-tag",
        default=None,
        help="Subdirectory the film goes into, on disk and in the repo. Defaults "
        "to the start time. Without one, every run writes c0000_* over the last "
        "run's c0000_*, because the call index restarts at zero.",
    )
    ap.add_argument("--trackio-space", default=None)
    ap.add_argument("--no-tracking", action="store_true")
    args = ap.parse_args()
    if args.run_tag is None:
        args.run_tag = datetime.datetime.now().strftime("%m%d-%H%M")

    generation_batch = args.per_device_batch_size * args.gradient_accumulation_steps
    if generation_batch % args.num_generations != 0:
        ap.error(
            "--per-device-batch-size x --gradient-accumulation-steps "
            f"({generation_batch}) must be divisible by --num-generations "
            f"({args.num_generations})"
        )

    probe_dir = pathlib.Path(args.out) / "probe"
    prompt, system_prompt = fetch_task(args.env_url, args.subject)
    dataset = build_dataset(
        prompt, system_prompt, args.n_episodes, args.model, args.enable_thinking
    )

    # Phases are kept apart on purpose. Sampling completions takes minutes of
    # GPU time with no environment traffic, and a connection left open across it
    # is closed by the server.
    before = None
    if args.probe_samples and not args.cordura:
        # The before-probe has to sample from whatever training is about to continue
        # from, not from the base model. With `--resume-adapter` pointing at a run
        # that already trained, sampling `args.model` would measure the untrained 4B
        # and the before-and-after would then report every step ever taken instead of
        # the ones this run adds, which is the one thing resuming exists to isolate.
        texts = sample_completions(
            args.resume_adapter or args.model,
            prompt,
            system_prompt,
            args.probe_samples,
            args.max_completion_length,
            args.enable_thinking,
            top_p=args.top_p,
            top_k=args.top_k,
        )
        before = probe(args.env_url, args.subject, texts, probe_dir / "before")
        print("before:", before)

    config = GRPOConfig(
        output_dir=args.out,
        learning_rate=args.lr,
        lr_scheduler_type=args.lr_scheduler,
        warmup_steps=args.warmup_steps,
        scale_rewards=args.scale_rewards,
        max_steps=args.steps,
        per_device_train_batch_size=args.per_device_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        num_generations=args.num_generations,
        max_completion_length=args.max_completion_length,
        # TRL defaults to `top_p 1.0` and `top_k 0`, so every run of this project
        # sampled the untruncated distribution while the model's own
        # `generation_config.json` asks for 0.95 and 20. The base model through an
        # endpoint that applies them produced 24 clean sketches out of 24; training
        # invents a method in about one rollout in eleven, three per step, flat from
        # step zero with the adapter still at zero. Not the adapter, not TRL (a plain
        # text prompt skips `apply_chat_template` entirely), not the prompt.
        #
        # This biases the gradient: samples come from a truncated policy and the
        # log-probs from the full one. It also hides the tail rather than teaching the
        # policy to drop it. What justifies it is that the policy is demonstrably not
        # dropping it: three invented methods per step for eleven steps, flat.
        top_p=args.top_p,
        top_k=args.top_k,
        use_adaptive_entropy=args.entropy_target > 0.0,
        entropy_target=args.entropy_target,
        bf16=args.bf16,
        gradient_checkpointing=args.gradient_checkpointing,
        # The dtype has to reach the model loader too, not just the trainer: the
        # trainer's `bf16` governs the compute, while the weights arrive in
        # whatever `from_pretrained` defaults to.
        model_init_kwargs={"dtype": "bfloat16"} if args.bf16 else None,
        logging_steps=1,
        # Was "no", so everything worth keeping happened after `train()` returned:
        # the adapter, the after-probe and the full film. Cancelling a run therefore
        # threw all three away, which it did twice, and there was no early-stopping
        # point that kept them. Checkpoints every ten steps and pushed as they go.
        save_strategy="steps",
        save_steps=10,
        save_total_limit=2,
        # `every_save`, the default, pushes the adapter and nothing else, so a run
        # that dies at step 73 could only be restarted warm: weights from step 70,
        # Adam reset, step counter back to zero, scheduler re-warming. `checkpoint`
        # adds a `last-checkpoint` folder carrying `optimizer.pt`, `scheduler.pt`
        # and `trainer_state.json`, overwritten on each save, which is exactly what
        # crash recovery needs. It costs about 243MB per push (two Adam moments over
        # 30.4M trainable parameters); the weight history stays available anyway
        # through the `Training in progress, step N` commits.
        hub_strategy="checkpoint",
        push_to_hub=args.push_to_hub,
        hub_model_id=args.out if args.push_to_hub else None,
        report_to="none" if args.no_tracking else "trackio",
    )
    if not args.no_tracking:
        config.trackio_space_id = args.trackio_space or args.out

    peft_config = None
    if args.lora:
        from peft import LoraConfig

        # This list is the one everyone writes for a dense transformer, and on
        # `Qwen3.5-35B-A3B` it reached almost nothing: `gate_proj` matched only
        # `mlp.shared_expert.gate_proj`, and 30 of the 40 layers use linear
        # attention whose projections are `in_proj_qkv` and `out_proj`. The 256
        # routed experts, 32.2B of the 35B, are a fused 3D `nn.Parameter` that no
        # entry in `target_modules` can reach, which is what `target_parameters`
        # is for. Eight runs trained 8.4M parameters, 0.024% of the model.
        # `in_proj_a` and `in_proj_b` are left out: they are 32 wide, so rank 16
        # is nearly the full matrix.
        peft_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_r * 2,
            lora_dropout=0.0,
            task_type="CAUSAL_LM",
            target_modules="all-linear"
            if args.all_linear
            else [
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ]
            + (["in_proj_qkv", "in_proj_z", "out_proj"] if args.lora_experts else []),
            target_parameters=[
                "mlp.experts.gate_up_proj",
                "mlp.experts.down_proj",
            ]
            if args.lora_experts
            else None,
        )

    # Continuing a run rather than starting one. `--lora` always builds a fresh
    # adapter, so forty more steps meant forty more steps from scratch, and the only
    # way to ask whether a run had stopped climbing or merely stopped was to change
    # nothing else and keep going. The adapter is loaded onto the base model here and
    # `peft_config` is dropped, because the trainer must not wrap it a second time.
    #
    # It is not identical to one continuous run: the learning rate decays linearly
    # and ended the last one at 5e-7, so resuming starts it again at the full rate.
    # That is a warm restart, which is a real difference and worth saying rather than
    # burying, though the last ten steps were barely updating anything anyway.
    model_or_id = args.model
    if args.resume_adapter:
        from peft import PeftModel
        base = _load_base(args.model, dtype="auto")
        model_or_id = PeftModel.from_pretrained(
            base, args.resume_adapter, is_trainable=True
        )
        peft_config = None
        print(f"continuando desde {args.resume_adapter}", flush=True)

    film = (pathlib.Path(args.out) / "film") if args.film else None
    # The control run talks to nothing, so it opens no client. `nullcontext` keeps
    # one code path for both, which is the point: the trainer, the LoRA and the
    # config have to be identical to the real runs or the control proves nothing.
    entorno = (
        contextlib.nullcontext(None)
        if args.cordura
        else GenericEnvClient(
            base_url=args.env_url, message_timeout_s=MESSAGE_TIMEOUT_S
        ).sync()
    )
    with entorno as client:
        trainer = GRPOTrainer(
            model=model_or_id,
            reward_funcs=make_cordura_reward(args.cordura)
            if args.cordura
            else make_reward_func(
                client,
                args.subject,
                args.references,
                film,
                # Without this the incremental upload never fires, because the
                # parameter defaults to None: four runs streamed nothing and the
                # film only appeared at the end, swept up by the checkpoint save.
                push_film=args.out if args.push_to_hub else None,
                film_dir=args.run_tag,
            ),
            args=config,
            train_dataset=dataset,
            peft_config=peft_config,
        )

        # Which modules actually got an adapter, not just how many parameters.
        # `target_modules` is written for a dense transformer and this model is a
        # MoE with fused experts and linear attention, so `gate_proj` matched only
        # `mlp.shared_expert.gate_proj` and the 256 routed experts got nothing.
        # PEFT does not warn as long as an entry matches somewhere.
        total = sum(p.numel() for p in trainer.model.parameters())
        entrenables = [
            (n, p.numel()) for n, p in trainer.model.named_parameters() if p.requires_grad
        ]
        vivos = sum(n for _, n in entrenables)
        print(
            f"entrenables {vivos:,} de {total:,} ({100 * vivos / total:.4f}%) "
            f"en {len(entrenables)} tensores"
        )
        familias = Counter(
            re.sub(r"\.\d+\.", ".N.", n.split(".lora_")[0]) for n, _ in entrenables
        )
        for familia, cuantos in sorted(familias.items()):
            print(f"    {cuantos:4d} x {familia}")

        trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    trainer.save_model(args.out)
    if args.push_to_hub:
        trainer.push_to_hub()

    # The after-probe loads the checkpoint as a second model, and with a LoRA run
    # that means a second full copy of the base on top of the trainer's. On a 24GB
    # card the two do not fit: accelerate offloads to CPU, reports "Some
    # parameters are on the meta device", and the probe dies. Dropping the
    # trainer first is what makes the probe affordable at all.
    del trainer
    import gc

    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    if args.probe_samples and not args.cordura:
        texts = sample_completions(
            args.out,
            prompt,
            system_prompt,
            args.probe_samples,
            args.max_completion_length,
            args.enable_thinking,
            top_p=args.top_p,
            top_k=args.top_k,
        )
        after = probe(args.env_url, args.subject, texts, probe_dir / "after")
        print("after:", after)
        report(before, after)

        if args.push_to_hub:
            # A Job's filesystem goes away with the Job, so the before-and-after
            # paintings have to be uploaded or the run leaves nothing behind but
            # a pair of averages. The pictures are the evidence.
            from huggingface_hub import HfApi

            api = HfApi()
            api.upload_folder(
                repo_id=args.out,
                folder_path=str(probe_dir),
                path_in_repo="probe",
                commit_message="Before and after probe paintings",
            )
            if film is not None and film.exists():
                api.upload_folder(
                    repo_id=args.out,
                    folder_path=str(film),
                    path_in_repo=f"film/{args.run_tag}",
                    commit_message="Every painting made during training, in order",
                )
                print(f"film uploaded: {len(list(film.glob('*.png')))} paintings")
            print(
                f"probe uploaded to https://huggingface.co/{args.out}/tree/main/probe"
            )


if __name__ == "__main__":
    main()
    # Exit on the script's own terms. The run that produced the published adapter
    # completed all forty steps, ran the after-probe, uploaded 311 paintings and
    # printed its last line, and HF Jobs still marked it ERROR: something in the
    # interpreter's shutdown path exits non-zero after `main` returns, and it leaves
    # no traceback in the logs to name. A failure status on a run that succeeded is
    # worse than no status, because it is the kind of false signal that costs an hour
    # before anyone checks the artefacts.
    #
    # A real failure inside `main` still propagates and still exits non-zero, because
    # this line is never reached. Only a clean completion forces zero.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
