# Reproducing the three runs

Every number in [`README.md`](./README.md) comes from the commands below. All three runs trained on 4×A100 against a hosted copy of the environment, with rewards computed in the trainer rather than read from the environment.

Total spend was about $700: roughly $450 of training and $250 of eval GPUs and hosted-model API calls.

Two things worth knowing before you start. The training script's bare defaults now reproduce run 1, so the only variables you have to set are the ones in each run's block below. And a training Space should be deployed with `GEOGUESSER_PLAY_ROUTES=0`: the browser game's routes hand out a task's coordinates over plain HTTP, which is fine for a Space people play and wrong for one a trainer points at.

## Prerequisites

```bash
git clone https://github.com/adithya-s-k/HuggingEnvs
export OPENENV_GEOGUESSER=$PWD/HuggingEnvs/03-geoguesser/env
```

The environment arrives as a dependency, not a checkout. The PEP 723 header in `train/grpo_geoguesser.py` pip-installs it from the Space repo at a pinned commit, which is what keeps a run reproducible.

Keys go in a `.env` at the project root: `HF_TOKEN`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `MAPILLARY_API_KEY`. Parse that file in Python, never `source` it. The `|` inside a Mapillary key is a shell pipe and leaked a token into a terminal once.

### Deploy your own environment Space

Do not point a run at someone else's. `duplicate_space` copies files but not variables, and the default `MAX_CONCURRENT_ENVS` is 4 while training needs 8. A run against a default-configured duplicate dies with `CAPACITY_REACHED: 4/4 sessions active` about an hour in.

Copy all 12 variables from `HuggingEnvs/geoguesser-env`, then prove it before spending a GPU:

```bash
python - <<'PY'
from geoguesser_env.client import GeoGuesserEnv
envs = [GeoGuesserEnv(base_url="https://<your-space>.hf.space") for _ in range(8)]
for e in envs:
    e.reset()
print("8/8 concurrent sessions OK")
PY
```

## The three runs

Shared across all three: 4×A100, `NUM_GENERATIONS=8`, `MAX_TURNS=12`, `SAVE_STEPS=25`.

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| `SCALE_REWARDS` | `group` | `none` | `group` |
| `BETA` | 0 | 0.02 | 0 |
| `ACCUM` | 2, one task/step | 4, two tasks/step | 4, two tasks/step |
| `COST_SCALE` | 1.0 | 0.2 | 0.2 |
| `MIXTURE_SHORT_WEIGHT` / `LONG_DECAY_KM` | 0.5 / 5000 | 0.6 / 3000 | 0.6 / 3000 |
| `VIEW_PX` | 448 | 640 | 640 |
| steps | 1000 | 300 | 300 |
| paired gain | **+0.1620 ±0.0137** | +0.0326 ±0.0090 (4B), +0.0663 ±0.0091 (2B) | +0.0717 ±0.0105 |
| best checkpoint | ckpt1000, 0.6445 | ckpt175, 0.5095 (4B); ckpt300, 0.4860 (2B) | ckpt175, 0.5526 |

Use `MAX_COMPLETION=6144` for all of them. It sizes the logits tensor at `length × 248064 vocab × 4 bytes` regardless of actual output length, so 12288 reserves 11.4 GiB per step while the model never exceeded about 2,100 tokens. Run 3 OOM'd on it at step 29.

### Run 1

```bash
cd train
hf jobs uv run \
  --flavor a100x4 --timeout 30h --image huggingface/trl --secrets HF_TOKEN \
  -v hf://buckets/<you>/geoguesser-runs:/outputs \
  -e OUTPUT_ROOT=/outputs -e NPROC=4 \
  -e MODEL=Qwen/Qwen3.5-4B \
  -e RUN_NAME=run1 -e ENV_URL=https://<your-space>.hf.space \
  -e SCALE_REWARDS=group -e BETA=0 -e ACCUM=2 -e NUM_ITERATIONS=1 \
  -e COST_SCALE=1.0 \
  -e MAX_TURNS=12 -e MAX_STEPS=250 -e SAVE_STEPS=25 \
  -e VIEW_PX=448 -e MAX_COMPLETION=6144 -e VLLM_MEM=0.20 \
  -e GENERATION_BATCH_SIZE=8 \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  grpo_geoguesser.py
```

Stop at step 250. The original run went to 1000, and the extra 750 steps produced no measurable change across 19 checkpoints spanning a 0.013 band, at a cost of about $70. `ckpt1000` is nominally best at 0.6445 but is statistically indistinguishable from `ckpt200` at 0.6393.

### Runs 2 and 3

The same command with the columns above substituted. Run 2 additionally trained a 2B, `MODEL=Qwen/Qwen3.5-2B`, against its own Space.

## Watching a run

```bash
python train/health_check.py <JOB_ID> --target 250 --run-name run1
```

One line, and it alerts on entropy collapse, truncation, dead groups, gradient spikes and reward drawdown. Two things about it took a while to get right.

Stream the logs rather than polling them: `hf jobs logs -f <id> >> file &`. Hugging Face purges a finished job's logs within about two minutes, so five-minute snapshot polling loses the fatal window every time. Three crashes went undiagnosed before this changed.

Supervise the follower. `hf jobs logs -f` exits on any transient error. One died of a local DNS blip and left a run unobserved for an hour, with a frozen step counter that looked exactly like a stall.

## Evaluating checkpoints

Serve the base plus up to 8 LoRA adapters from one endpoint, then sweep them together. Eight arms for one GPU-hour instead of eight boots.

```bash
hf jobs uv run --flavor a100-large --timeout 5h --image huggingface/trl --secrets HF_TOKEN \
  -v hf://buckets/<you>/geoguesser-runs:/outputs \
  -e MODEL=Qwen/Qwen3.5-4B \
  -e ADAPTERS="ckpt200=/outputs/run1/checkpoint-200,ckpt1000=/outputs/run1/checkpoint-1000" \
  -e MAX_LORAS=8 -e HOLD_S=16000 -d eval/serve_checkpoint.py
```

Always include a base arm in the same sweep. The same frozen base scored 0.465 to 0.500 across different sweeps, a drift wider than most per-checkpoint differences, so a delta read across sweeps is not trustworthy. Every comparison in the reports is paired per task within one sweep.

Verify what the endpoint is actually serving before spending a sweep on it. `eval/serve_checkpoint.py` defaults to `MODEL=Qwen/Qwen3.5-4B`, and pointing 2B adapters at it produces a plausible table of nonsense: vLLM logs `Loaded new LoRA adapter` and serves anyway, even though a 2B adapter cannot fit a 4B base. All four of run 2's 2B checkpoint scores were silently invalid this way. `eval/serve_checkpoint.py` now refuses to serve on a mismatch: it checks that every requested adapter appears in `/v1/models`, and that each adapter's own `adapter_config.json` names the base being served.

Then the sweep:

```bash
cd eval
RUN=passk-run1 PASSES=4 SHARDS=6 WORKERS=8 TASKS=200 \
  MODELS=arms.json BASELINE=base bash run_passes.sh
```

Six local environment servers, four passes at distinct sample offsets pooled into pass@4. Passes compose, so a killed sweep resumes by running the offsets it is missing.

## Scoring the field

```bash
cd eval && bash board_sweep.sh full     # 9 off-the-shelf models, about 2.5 h
```

See [`eval/README.md`](./eval/README.md). Both sides must be at the same `k`. While the baselines sat at pass@1 they read Sonnet 0.6798 and gpt-5.4-mini 0.6037; completed to pass@4 they read 0.6952 and 0.5732. Those moves flipped one verdict in each direction.
