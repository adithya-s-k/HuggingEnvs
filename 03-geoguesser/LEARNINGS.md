# What three GRPO runs taught us

Every number here is mean-of-4 over the same 200 eval tasks, paired per task, rewards recomputed from raw distances through [the curve at the top of `eval/geoeval.py`](./eval/geoeval.py).

## The headline

A 4B LoRA beats eight of nine off-the-shelf models and loses only to Sonnet 5. The best checkpoint is step 1000, but step 200 is statistically indistinguishable from it: 0.6393 against 0.6445, a paired delta of +0.0052 with a 95% CI of [-0.0066, +0.0170] (`results/summaries/run1-vs-ckpt200.txt`). So the useful run is 200 steps long.

| arm | score | median error | never submitted |
|---|---:|---:|---:|
| claude-sonnet-5 | 0.6952 | 324 km | 14.2% |
| **run 1 ckpt1000** | **0.6445** | **662 km** | **0.5%** |
| gpt-5.4-mini | 0.5732 | 753 km | 24.6% |
| claude-haiku-4.5 | 0.5374 | 939 km | 22.6% |
| Qwen3.5-122B-A10B | 0.5338 | 767 km | 24.5% |
| *Qwen3.5-4B, untrained* | *0.4825* | *1226 km* | *29.5%* |
| Qwen3.5-9B | 0.4776 | 1203 km | 31.0% |
| Qwen3.5-35B-A3B | 0.4483 | 1485 km | 36.0% |
| Qwen3.5-27B | 0.4478 | 1289 km | 36.3% |
| Qwen3.5-397B-A17B | 0.4466 | 1420 km | 38.0% |
| gpt-5.4-nano | 0.3748 | 2541 km | 45.8% |

800 episodes per arm. Regenerate with `python eval/geoeval.py report results/raw/board-passk results/raw/passk-run1-full`.

## 1. The gain came from not failing

Run 1's +0.1620 is almost entirely one behavioural change.

| | base | ckpt1000 |
|---|---:|---:|
| turns per episode | 6.7 | 1.1 |
| output tokens | 1062 | 66 |
| episodes scoring zero | 29.5% | 0.5% |
| action cost | 0.108 | 0.001 |

An episode that deliberates for 12 turns and never submits scores exactly zero, and that was happening to nearly a third of episodes. Guessing immediately makes it structurally impossible.

The effect generalises past our own checkpoints. Across the nine models we did not train, score correlates with turn count at r = -0.75, and with the share of episodes scoring exactly zero at r = -0.96. That second one is partly circular, since both are functions of the same distances; the turn count is the finding. Note also that the zero-scoring share is not non-submission: in these sweeps every arm answered, and the zero-scoring episodes are guesses past the reward's cliff, which sits at roughly 3,500 km.

Pooling our checkpoints in raises those correlations, but that is partly circular: training drove turns down, zero-scoring episodes down and score up together, so our arms sit at both extremes by construction. The nine-model figure is the one that means something.

The transferable version: before tuning anything else, find out what your reward cannot distinguish. Ours flattened to exactly zero past about 4,500 km, which covered nearly a third of untrained episodes, so a third of the data carried no gradient at all.

## 2. The reward has a cliff, and only an under-regularised optimiser jumps it

Winning here needs a qualitative switch to "commit early", not incremental refinement. Run 1's config could make that jump and run 2's could not.

Run 3 was the controlled test. It reverted only `SCALE_REWARDS=group` and `BETA=0`, keeping run 2's `COST_SCALE=0.2` and `ACCUM=4`. It recovered 44% of run 1's gain, +0.0717 against +0.1620. It reproduced run 1's dynamics, with entropy falling 0.46 to 0.04, group spread collapsing to 0.001 and grad norm rising 0.18 to 3.7, but stalled with about 24% of episodes still scoring zero where run 1 got that down to 0.5%.

So amplification starts the transition and action cost finishes it.

- `SCALE_REWARDS=group` divides advantages by group standard deviation, amplifying up to about 99× as spread collapses.
- `ACCUM=2` meant one task per step, so the group standard deviation *was* the within-task spread, which does collapse. At `ACCUM=4` it pools two tasks and includes between-task variance, which never does.
- `BETA=0` left no anchor to a base that deliberates for about 7 turns.
- `COST_SCALE=1.0` made each action cost real reward. Run 1 drove action cost down 100×.

The instability was the mechanism. Run 1's entropy collapse and grad-norm spike to 6.34 were alarming and produced two recommendations to stop the run, both overruled and both wrong. Run 2 was then designed to suppress exactly those dynamics and lost 80% of the gain.

## 3. Neither run needed most of its steps

Run 1 plateaued by step 200 to 250. The remaining 750 steps span a 0.013 band across 19 checkpoints and cost about $70 for nothing.

Normalised by data rather than steps, since run 1 saw one task per step against runs 2 and 3's two, run 1 reached +0.142 after 200 unique tasks where run 3 needed 400 to reach +0.074.

Even a full 1000-step run touches only 58% of the 3,452-task split, one episode-group per task, never repeated. This is not a memorisation regime.

## 4. What it cost to trust the numbers

Six measurement bugs, each of which produced plausible results rather than errors.

| bug | what it looked like | what it was |
|---|---|---|
| Wrong base served | 2B checkpoints scoring 0.469–0.479 | vLLM accepted 2B LoRAs on a 4B base and served anyway. All four scores invalid |
| Dead tunnel | ckpt75 regressing to 0.4475 | 13% of requests got an HTML 404 recorded as an empty reply, so the episode burned its turns and scored 0 |
| Two reward scales | run 2 deltas incomparable to run 1's | the stored reward is the environment's; `geoeval report` recomputes through the pinned curve. Same guess: 0.0107 against 0.135 |
| No base arm | deltas read across sweeps | the same frozen base scored 0.465–0.500 between sweeps, wider than most differences being claimed |
| Comparing across `k` | run 1 tying Sonnet 5 | baselines at pass@1 read Sonnet 0.6798; at pass@4, 0.6952. Mean-of-k is unbiased in k, so that gap is single-pass sampling noise (SE about 0.02 at n=200) rather than a k artefact. Only best-of-k depends on k. Either way: compare arms measured with the same number of passes |
| Concurrent sweeps | `k = 1.8` with `PASSES=1` | two sweeps writing one directory. Arithmetically impossible, and the only tell |

Three guards exist because of these, all verified against known-bad data. The endpoint is asked what it is serving and the sweep refuses on a mismatch. Any sweep with more than 2% of turns lacking a `finish_reason` is discarded and retried. One sweep per output directory is enforced by a lock.

The meta-lesson: per-checkpoint gains here are about +0.008, smaller than the noise used to measure them, ±0.011 at 200 tasks. Single checkpoints cannot be ranked, only trends across many. Resolving a 25-step gain needs about 800 tasks per arm, not more checkpoints.

## 5. The win is real, but it is not the agent we set out to build

Run 1's policy stopped looking. One glance, then a major city's coordinates. That is not leakage and not memorisation, and it is genuinely more accurate, 662 km against the base's 1226 km. But it is not a visual agent reasoning over a panorama.

The reward pays for accuracy and charges for actions, so its optimum is to know the answer immediately. That is a statement about reward design as much as about RL. Run 3's policies, at 2.4 turns and still calling tools, are closer to a model that uses the environment while scoring lower.

## Where to go next

Change only `COST_SCALE`, from 0.2 back to 1.0, on top of run 3's config. Run 3 established that the algorithmic revert buys half the gain and that the residual sits in the zero-scoring episodes. Action cost is the remaining lever. 300 steps, about 5 hours.
