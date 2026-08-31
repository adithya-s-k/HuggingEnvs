# Results

Curves as data, not as a screenshot of a dashboard.

## Why the numbers live here

Training metrics went to [trackio](https://github.com/gradio-app/trackio), one Space
and one bucket per run. **Those Spaces will be shut down**, and a dashboard that is
switched off is not a result. So the per-step series are exported here as CSV,
versioned alongside the code that produced them.

## Files

| file | what it is |
|---|---|
| `curve-hps-only.csv` | every metric, per step, for the `hps-only` run. 60 steps, 14 columns |
| `fig-flat-controls-vs-hps-only.png` | the same run against the three flat controls that came before it |

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

Slope over all 60 steps is +0.0035 per step, **t = +6.41**. Over the last 15 it is
+0.0084, steeper than the run as a whole, so it was cut by the step counter.

`frac_reward_zero_std` is 0.000 in all 60 rows: no step ever lost its gradient.

## Not here yet

Two sibling runs are still training, `judge-led` and `hps-led`. Their curves, their
step timings and their totals go here when they finish. Until then the numbers in the
project README describe `hps-only` only.

## Per-rollout data

The curve is the group mean. Every individual rollout, with its sketch, its reward
and its step, is in
[`watercolour-rollouts-hps-only`](https://huggingface.co/datasets/HuggingEnvs/watercolour-rollouts-hps-only).
Anything asserted about this run is recomputable from those 470 rows.
