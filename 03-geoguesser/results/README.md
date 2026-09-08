# Results

Every number in [`../README.md`](../README.md), [`../LEARNINGS.md`](../LEARNINGS.md) and the per-run reports in [`../train/`](../train/) is derived from the episode records described here.

## summaries/, committed

Plain-text output of `eval/geoeval.py report`, one file per sweep. These are the tables the write-ups cite, and they are small enough to live in git so that a change to a published number shows up in review.

| file | what it covers | episodes |
|---|---|---:|
| `board-passk.txt` | the 9 off-the-shelf arms, pass@4 | 7,190 |
| `board-plus-run1.txt` | those plus run 1's checkpoints, the headline table | 13,589 |
| `run1-full.txt` | run 1, 7 checkpoints + base | 6,399 |
| `run2-4b.txt` | run 2 on Qwen3.5-4B, 9 checkpoints + base | 13,599 |
| `run2-2b.txt` | run 2 on Qwen3.5-2B, 3 checkpoints + base | 4,000 |
| `run3-4b.txt` | run 3 on Qwen3.5-4B, 12 checkpoints + base | 19,184 |

Each file carries both averages, because they answer different questions: mean-of-k is how the policy does on a typical attempt, best-of-k is pass@k proper and says whether the ability is there at all. Where a base arm is present it also prints per-task paired deltas with 95% confidence intervals. Use those, not a difference of two means.

## raw/, not in git

1.3 GB of episode records across 30 sweeps, gitignored. Layout:

```
raw/<sweep>/pass-<n>/shard-<m>/episodes.jsonl   one JSON object per episode
                              /run.json         the arm config for that shard
```

Each episode holds the full turn sequence: the prompt, the model's raw reply, token counts and latency, the action parsed from it, the environment's feedback, the image SHA-256, and the reward with its action cost broken out. That is enough to re-score an episode under a different reward curve without re-running it, which is exactly what `geoeval report` does. The stored `outcome.reward` is the environment's curve, and the report recomputes from `distance_km` through the pinned curve at the top of `eval/geoeval.py`. The two differ by more than 10× on the same guess, so never mix them.

Passes compose: each is an independent pass@1 over every arm, recorded with its own `sample` index, so N passes pool into a clean pass@N with no re-running. That is why several roots can be passed to `geoeval report` at once.

### Getting the raw episodes

Like the panorama imagery, these belong in object storage rather than git: too large to version, and append-only in practice.

They are not uploaded yet. They currently exist only on the machine that produced them; the intended home is the runs bucket beside the checkpoints:

```bash
# to publish (one-off, from this directory)
hf cp -r ./raw hf://buckets/HuggingEnvs/geoguesser-runs/results

# to fetch, once it is published
hf sync hf://buckets/HuggingEnvs/geoguesser-runs/results ./raw
```

You do not need them to read the results. `summaries/` has every published number. Sync them if you want to re-score under a different reward, inspect individual rollouts, or check a claim about turn counts and non-submission.

### `raw/_quarantined/`

Two sweeps that were excluded from every published number, kept so the record of *why* survives:

- `board-pilot.contaminated-1909`, where two sweeps wrote to this directory concurrently, pooling passes from different arms and reporting k=1.8 for a single-pass run.
- `passk-r3-ckpt25.dead-*`, scored against a dead tunnel, whose 404s were recorded as empty model replies and looked exactly like a regression.

## Regenerating any table

```bash
cd ..
python eval/geoeval.py report results/raw/board-passk results/raw/passk-run1-full
```

The aggregator is deterministic given the same roots, so a summary that no longer matches its raw data is a bug in one of them.
