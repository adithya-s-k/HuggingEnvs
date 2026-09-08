# Training

Multi-turn GRPO against the environment, on 4×A100. One script, run as a Hugging Face Job.

```bash
# 1. Simulate first. Catches the bugs that cost a whole run, for pennies.
#    Any OpenAI-compatible endpoint with tool calling: a local vLLM, or the
#    HF router, which needs no GPU of your own.
export HF_TOKEN=...
python simulate_rollout.py --endpoint https://router.huggingface.co/v1 \
    --model "Qwen/Qwen3.5-9B:deepinfra" --episodes 6

# 2. Train. Run 1's config; see ../REPRODUCE.md for runs 2 and 3.
hf jobs uv run --flavor a100x4 --timeout 30h --image huggingface/trl \
  --secrets HF_TOKEN -v hf://buckets/<you>/geoguesser-runs:/outputs \
  -e OUTPUT_ROOT=/outputs -e NPROC=4 -e MODEL=Qwen/Qwen3.5-4B \
  -e RUN_NAME=run1 -e ENV_URL=https://<your-space>.hf.space \
  -e SCALE_REWARDS=group -e BETA=0 -e ACCUM=2 -e COST_SCALE=1.0 \
  -e MAX_TURNS=12 -e MAX_STEPS=250 -e SAVE_STEPS=25 \
  -e VIEW_PX=448 -e MAX_COMPLETION=6144 \
  grpo_geoguesser.py

# 3. Watch it. Job logs are purged about two minutes after a job ends.
python health_check.py <JOB_ID> --target 250 --run-name run1
```

## Files

| file | does |
|---|---|
| `grpo_geoguesser.py` | the whole run. A PEP 723 script, so the same file works on Jobs or a local GPU |
| `simulate_rollout.py` | drives the rollout loop against a served model, no gradient. Run this first |
| `health_check.py` | reads a live job's logs and reports step, reward and whether it is stuck |

## Before you start

Deploy your own environment Space. Training opens one session per rank plus generation. `MAX_CONCURRENT_ENVS` defaults to 4 and you need 8. Duplicating a Space copies its files but not its variables, so set them again and check you can really open 8 concurrent sessions before launching.

Use `MAX_COMPLETION=6144`. It sizes a logits tensor at `length × 248064 vocab × 4 bytes` regardless of what the model actually emits. 12288 reserves 11.4 GiB per step; our longest output was 2,114 tokens.

Point `output_dir` at a mounted bucket. The Jobs filesystem is deleted when the job exits. With `SAVE_STEPS` set, a timeout then costs you the tail of a run instead of all of it.

Cut run 1 at step 250. Steps 250 to 1000 produced no measurable change across 19 checkpoints spanning a 0.013 band, and cost about $70 of A100.

Some routed providers cap images per request, and a 12-turn visual episode exceeds it. deepinfra allows 4, so a simulation there stops after 4 looks with `At most 4 image(s) may be provided in one prompt`. That is a provider limit rather than an environment bug, and it does not affect training, which serves the model itself. Use a local vLLM if you want a full-length simulated episode.

The full set of traps, and what each failure looked like before it was understood, is in the [HF Jobs field manual](https://claude.ai/code/artifact/500ad1f0-0e91-4a24-a66b-fa331fef9e90).

## Watching a run

`train/reward` going up is not the thing to watch first. Watch `frac_reward_zero_std`: GRPO's advantage is the spread *within* a group, so if that is near 1 most groups teach nothing and no amount of training helps.

Metrics land in the unified dashboard, [`HuggingEnvs/geoguesser-trackio`](https://huggingface.co/spaces/HuggingEnvs/geoguesser-trackio). Plot against `train/global_step`: TRL logs twice per optimiser step here, so the step axis runs at about 2× the true count.
