# Results

Curves as data, not as a screenshot of a dashboard.

## Why the numbers live here

Training metrics went to [trackio](https://github.com/gradio-app/trackio), one Space
and one bucket per run. The live dashboards are published in the org:
[`watercolour-trackio-judge-led`](https://huggingface.co/spaces/HuggingEnvs/watercolour-trackio-judge-led),
[`watercolour-trackio-hps-led`](https://huggingface.co/spaces/HuggingEnvs/watercolour-trackio-hps-led)
and
[`watercolour-trackio-hps-only`](https://huggingface.co/spaces/HuggingEnvs/watercolour-trackio-hps-only).
A dashboard can be paused or moved, so the per-step series are also exported here as
CSV, versioned alongside the code that produced them.

## Files

| file | what it is |
|---|---|
| `curve-hps-only.csv` | every metric, per step, for the `hps-only` run. 60 steps |
| `curve-judge-led.csv` | the same, for the `judge-led` run. 110 steps |
| `curve-hps-led.csv` | the same, for the `hps-led` run. 110 steps |
| `VERSIONS.md` | the package versions the uv header resolved around launch day |
| `fig-flat-controls-vs-hps-only.png` | `hps-only` against the three flat controls that came before it |

Every painting of every run is browsable in [the gallery Space](https://huggingface.co/spaces/HuggingEnvs/watercolour-gallery), by step and by reward, with the sketch that made each one.

Columns: `reward`, `reward_std`, `frac_reward_zero_std`, `entropy`, `loss`,
`grad_norm`, `learning_rate`, `step_time`, `completions/mean_length`,
`clipped_ratio`, and the group means of each reward term (`judge_mean`,
`length_mean`, `paint_fraction_mean`, `quality_mean`).

## The headline, and how to recompute it

```python
import csv, statistics

rows = list(csv.DictReader(open("curve-hps-only.csv")))
r = [float(x["reward"]) for x in rows]
k = len(r) // 3
print([round(statistics.mean(r[i*k:(i+1)*k]), 3) for i in range(3)])
# [0.578, 0.634, 0.701]
```

Slope over all 60 steps is +0.0035 per step, **t = +6.41**. The judge runs: `judge-led`
0.451 / 0.647 / 0.721 across thirds (t = +10.5), `hps-led` 0.573 / 0.740 / 0.815
(t = +15.6), both over 110 steps and both still inching upward when stopped.

`frac_reward_zero_std` is 0.000 in every row of all three runs: no group ever collapsed
to identical rewards, the GRPO failure mode that kills the gradient.

## Per-rollout data

The curve is the group mean. Every individual rollout, with its sketch, its reward
and its step, is in the rollouts datasets:
[`watercolour-rollouts-hps-only`](https://huggingface.co/datasets/HuggingEnvs/watercolour-rollouts-hps-only),
[`watercolour-rollouts-judge-led`](https://huggingface.co/datasets/HuggingEnvs/watercolour-rollouts-judge-led)
and
[`watercolour-rollouts-hps-led`](https://huggingface.co/datasets/HuggingEnvs/watercolour-rollouts-hps-led).
Anything asserted about a run is recomputable from its rows.
