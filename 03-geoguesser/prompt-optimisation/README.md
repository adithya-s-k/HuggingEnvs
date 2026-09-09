# Prompt optimisation with GEPA

**These prompts are not what the board was scored with.** `eval/run_passes.sh` never passes
`--prompt`, so every arm in `results/summaries/` ran the harness's default prompt. Treat what is
here as an experiment in prompt optimisation, not as part of the reported results.

A prompt a frontier model follows regardless is not doing much work. A 2B model that emits prose instead of JSON, or explores until its turn budget is gone, is failing for reasons a prompt can fix. So the search targets the small self-hosted models, one run per model.

| | |
|---|---|
| Optimiser | [GEPA](https://github.com/gepa-ai/gepa), `optimize_anything` |
| Seed | `prompts/v2_seed.txt`, 1,839 chars |
| Reflection model | `claude-sonnet-5` |
| Search split | `train`, 3,452 tasks, never `eval` |
| Budget | 300 episode evaluations per model, 8 workers |
| Validation | 40 paired tasks on the frozen `eval` split |

## Results

Validated on the eval split over 40 tasks, with both prompts playing the same task indices so the comparison is within-task.

| model | seed | GEPA | Δ reward | zero-reward episodes | adopt |
|---|---:|---:|---:|---|---|
| Qwen3.5-2B | 0.200 | 0.320 | +0.120 | 48% to 22% | yes |
| Qwen3.5-4B | 0.318 | 0.374 | +0.057 | 28% to 32% | undecided |
| Qwen3.5-9B | 0.372 | 0.324 | −0.048 | 30% to 40% | no |

The 2B is the clear win. +0.120 is about 2.5 standard errors at n=40, and halving the zero-reward episodes is a consistent mechanism rather than a lucky mean: the prompt gets the model to commit to a plausible guess instead of missing by a continent.

The 4B and 9B are unresolved. Both deltas are roughly one standard error at n=40, where reward standard deviation is about 0.30. Neither can be called. Resolving the 4B matters most, since it is the RL target.

GEPA independently gave the 2B a prompt 45% longer than the other two, 4,132 chars against 2,842 and 2,876. The smallest model wanted more explicit hand-holding while the larger two converged near the seed's length. That divergence is the argument for per-model searches over one shared prompt.

## The held-out valset did not predict the eval result

GEPA's own 24-task validation set, against the frozen eval split.

| model | valset said | eval said |
|---|---|---|
| 2B | +10.8% | +60%, understated |
| 4B | +0.0% | +18%, missed entirely |
| 9B | +7.3% | −13%, wrong sign |

Twenty-four tasks is too few and the search overfit them. The 9B is the cautionary case: adopting on the interim number would have shipped a regression. Any prompt is a hypothesis until it is scored on held-out eval tasks.

## Why the search uses a different reward

GEPA optimises `0.5·exp(-d/1492.7) + 0.5·exp(-d/5000)`, scaled by `(1 - action_cost)`, rather than the environment's shipped reward.

The shipped reward is `max(0, exp(-d/1492.7) - cost)`. Mean action cost for these models is about 0.13, and the curve falls below that at roughly 3,300 km, so every worse guess clamps to exactly 0.0. Measured over 2,600 eval episodes, 30% to 48% of these models' episodes land there. On those tasks every candidate prompt scores identically, so the search would be choosing blind on a third of its data.

| distance | shipped reward | search metric |
|---:|---:|---:|
| 3,400 km | 0.0000 | 0.2650 |
| 8,000 km | 0.0000 | 0.0899 |
| 18,000 km | 0.0000 | 0.0119 |
| no guess | 0.0 | 0.0 |

A guess anywhere on Earth still beats no guess, so "never committed" stays the worst outcome, which is the failure a prompt most directly fixes. Reported numbers use the game curve either way. This only changes what the search can see.

## Running it

Needs a served model. See [`../eval/README.md`](../eval/README.md) for `serve_checkpoint.py`, or point it at any OpenAI-compatible endpoint.

```bash
# one config per model, so each search is independent
cat > /tmp/opt_4b.json <<'JSON'
[{"name": "local-qwen3.5-4b", "provider": "openai",
  "model": "Qwen/Qwen3.5-4B", "base_url": "http://127.0.0.1:8130/v1"}]
JSON

python optimise_prompt.py \
    --models /tmp/opt_4b.json --base-url http://127.0.0.1:8130 \
    --budget 300 --tasks 24 --workers 8 \
    --seed-prompt v2 --reflection-lm anthropic/claude-sonnet-5

# then score the winner against the seed on eval, never before
python optimise_prompt.py --validate runs/optimised_prompt.txt \
    --models /tmp/opt_4b.json --tasks 40
```

Output lands in `runs/`, which is not committed. GEPA's own run state, meaning candidate trees and per-iteration logs, is about 600 KB per model and stays there too.

## Files

| file | status |
|---|---|
| `prompts/v2_seed.txt` | the seed all three searches started from |
| `prompts/gepa_qwen3.5-2b.txt` | 2B winner, adopted |
| `prompts/gepa_qwen3.5-4b.txt` | 4B winner, pending a 200-task validation |
| `prompts/gepa_qwen3.5-9b.txt` | 9B winner, rejected as worse than seed on eval |

All four carry the `{max_turns}` and `{tools}` placeholders and are verified to `format()` without raising. A candidate that drops them crashes every episode, so the optimiser validates before running one and scores it zero with an explanation. That teaches the reflection model the contract instead of failing the run, and it fired 10 times during the 2B search.

## Known gaps

- Qwen3.5-0.8B was not optimised. Its endpoint was taken down before this run, and it is the model with the most to gain: 54% of its episodes score exactly zero, the worst of any model measured.
- The validator recorded per-model means rather than per-task pairs, so the paired test that would roughly halve the noise on the 4B and 9B deltas could not be run. Fixed for the next round.
- A quarter to a third of each search was spent on 0.0-against-0.0 comparisons. For the 2B those were the 10 malformed candidates above. For the 4B, 19 of 21, and the 9B, 14 of 18, there were no rejections, no failed episodes, and healthy valset scores throughout. That points at GEPA's own subsample bookkeeping and is not yet understood. Worth resolving before spending a larger budget.
