# Scoring a model

Everything is one CLI. It talks to a served environment over HTTP and does not import it, so it runs against a local server or the hosted Space with no checkout, no imagery and no GPU.

```bash
pip install -r requirements.txt

python geoeval.py run --env space --provider anthropic \
    --model claude-sonnet-5 --split eval --limit 5
```

## Commands

| command | does |
|---|---|
| `run` | drive rollouts and record one JSONL row per episode |
| `report` | pool passes into a pass@k table with paired confidence intervals |
| `probe` | check endpoints answer, and can actually see an image |
| `replay` | re-render a recorded episode and compare image hashes |

## Naming the environment

`--env` takes four shapes, so the same command works wherever it is served:

```
--env space          the hosted Space
--env local          127.0.0.1:8000
--env local:8161     another port
--env http://host:8000
```

`replay` is the exception: it re-renders frames itself, so it needs the environment installed and runs as `uv run --with ../env python geoeval.py replay …`.

## Providers

One adapter pair covers everything. `--provider anthropic` uses the Messages API; `--provider openai` uses any OpenAI-compatible endpoint, which includes the HF router and a local vLLM server.

| provider | `base_url` |
|---|---|
| Anthropic | n/a |
| OpenAI | `https://api.openai.com/v1` |
| HF router | `https://router.huggingface.co/v1` |
| local vLLM | `http://127.0.0.1:8000/v1` |

Keys come from the environment: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `HF_TOKEN`. Put them in a `.env` at the project root and let the tooling parse it. Never `source` that file: a Mapillary key contains a `|`, which the shell reads as a pipe.

Thinking is off by default. `--thinking on|low|medium|high` sets a budget where the provider supports one; `probe` reports what each endpoint actually accepted, which is worth checking before a sweep rather than after.

## Running the board

`board_sweep.sh` brings up one environment server per shard, runs every arm in `board_models.json` across N independent passes, and reports the pooled table.

```bash
SHARDS=6 WORKERS=8 PASSES=4 bash board_sweep.sh full
```

Passes compose: each is an independent pass@1 over every arm, recorded with its own sample index, so N passes pool into a clean pass@N with no re-running. That is why `report` accepts several roots at once.

Two guards are built in, both from real failures. The sweep refuses to start if another is already running, and it aborts if too large a fraction of turns come back dead. A tunnel that 404s records empty replies, which reads exactly like a checkpoint regression rather than an outage.

## Scoring checkpoints

`serve_checkpoint.py` serves a base model with up to 8 LoRA adapters at once, so eight arms cost one GPU-hour rather than eight. It runs as its own HF Job:

```bash
hf jobs uv run --flavor a100 --timeout 6h \
  -e MODEL=Qwen/Qwen3.5-4B -e MAX_LORAS=8 -e HOLD_S=16000 \
  -d serve_checkpoint.py
```

`MODEL` defaults to `Qwen/Qwen3.5-4B`. Pointing 2B adapters at it produces numbers rather than an error. vLLM accepts the impossible pairing silently, and it invalidated four checkpoint scores here before it was caught. Set `MODEL` to match the adapters, and let `probe` confirm what is being served.

Tear the job down as soon as the eval finishes. An idle A100 bills like a busy one.

## Two reward scales

An episode's stored `outcome.reward` is the environment's own curve. Everything `report` prints is recomputed from `distance_km` through the pinned curve at the top of `geoeval.py`. The same guess scores 0.0107 on one and 0.135 on the other, so never compare across them. `test_reward_parity.py` fails if that curve drifts from the one the training script uses.

## Reading a table

`report` prints both averages because they answer different questions. Mean-of-k is how the policy does on a typical attempt; best-of-k is pass@k proper and says whether the ability is there at all. A checkpoint that lifts best-of-k but not mean-of-k has become more capable and less reliable.

Where a base arm is present it also prints per-task paired deltas with 95% confidence intervals. Use those, not a difference of two means: per-checkpoint gains here are about 0.008 and the noise on 200 tasks is ±0.011.
