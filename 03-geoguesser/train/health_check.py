"""
One-line health verdict for a running GRPO job, for a polling monitor.

Reads the job log rather than the rollout traces: the log already carries all 26
per-step metrics, so a check costs no bandwidth as the traces grow past 20 MB.

Prints `OK` when healthy and `ALERT` with the specific reasons when not. Every
terminal stage is covered, so silence never has to be read as success.

The thresholds are chosen around how *this* run is shaped -- one group of 8
rollouts per optimizer step, 24 turns, a 12288-token completion budget:

- **entropy**, against a baseline taken from the run's own first steps rather
  than an absolute number. Entropy collapse is the standard GRPO failure: the
  policy goes deterministic, stops exploring, and the reward curve flattens
  with nothing in the reward column to explain why.
- **clip fraction.** A rising share of clipped tokens means the updates are
  bigger than the trust region allows, which is the signal to drop the LR.
- **completion truncation.** A rollout cut off at the token budget never
  reaches `guess`, so it scores zero for a reason that has nothing to do with
  geolocation. This must stay at zero.
- **call frequency**, banded at both ends. Collapsing toward 1-2 calls means the
  policy learned to guess immediately to dodge the action cost -- reward hacking
  the cost term. Pinned near 24 means it is running out of turns instead of
  committing.

Usage:
    python health_check.py <JOB_ID> [--target 300] [--budget-hours 24]
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import pathlib
import re
import statistics
import subprocess
import time
import tempfile

# Compared against a baseline from the run's own first steps, not an absolute.
ENTROPY_COLLAPSE_RATIO = 0.6
# Entropy falling on its own is what a converging policy looks like, and firing
# on it alone cries wolf at exactly the moment a run is working: this one hit
# 34% of baseline while posting its best reward of the run, with the gradient
# intact. What actually ends learning is the within-group reward spread going to
# zero -- in GRPO that spread IS the gradient. So collapse is only an alert when
# entropy is down AND the spread has gone with it; entropy alone is reported.
SPREAD_FLOOR = 0.10
# Once a policy has converged, low entropy and thin spread are the expected
# state, not a fault: this run held spread under 0.10 for most of 20 steps with
# 0/108 dead groups and its reward still climbing. From that point the signal
# worth waking someone for is the reward giving back what it gained -- a
# drawdown from the best trailing window seen so far. With no clipping (IS
# correction off) and no KL anchor (beta=0), nothing damps a large update, so
# the failure mode is abrupt rather than gradual.
REWARD_DRAWDOWN = 0.25
# Above this share of clipped tokens the updates exceed the trust region.
CLIP_FRACTION_MAX = 0.15
# A truncated rollout never reaches `guess`, so this must stay ~0.
TRUNCATION_MAX = 0.02
# Only the upper end is a fault. A low call count looked like blind guessing,
# but pass@4 over 4000 episodes showed the one-call policy is the strongest
# checkpoint on both reward and median error -- so the floor was flagging the
# best behaviour we have. Turn exhaustion is still worth knowing about.
CALLS_MAX = 23.0
# A malformed tool call from the model counts as a failure here, and one in a
# few hundred is normal for a 4B policy -- as is the occasional blip from an
# environment reached over HTTP. Only a sustained rate is worth waking anyone.
TOOL_FAILURE_MAX = 0.02
GRAD_SPIKE_FACTOR = 5.0
# Fallback for recovering the step number from a single logged `epoch` when the
# tail holds only one metric line.
#
# Tasks per step is (per_device_batch x world_size x ACCUM) / num_generations.
# Run 2 uses ACCUM=4 over 4 GPUs with 8 generations, so it is 2 -- not 1, as
# this assumed while it was written against run 1's ACCUM=2. Verified against a
# live run: epoch 0.029550 x 3452 / 2 = 51.0, the step TRL reported.
TASKS_PER_STEP = float(os.getenv("TASKS_PER_STEP", "2"))
EPOCH_PER_STEP = TASKS_PER_STEP / 3452
BASELINE_STEPS = 5
BUCKET = "hf://buckets/AdithyaSK/geoguesser-runs"
TREND_WINDOW = 10


def run(*args: str) -> str:
    """Capture a command's combined output, empty on failure."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=180)
        return (done.stdout or "") + (done.stderr or "")
    except (subprocess.SubprocessError, OSError):
        return ""


def steps_from_log(log: str) -> list[dict]:
    """Every per-step metric dict TRL logged, in order."""
    out = []
    for raw in re.findall(r"\{'loss'.*?\}", log):
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            continue
        # TRL logs every value as a preformatted string.
        row = {}
        for key, value in parsed.items():
            try:
                row[key] = float(value)
            except (TypeError, ValueError):
                pass
        out.append(row)
    return out


def after_resume(log: str) -> str:
    """
    Only the part of the log written since the last resume.

    On `resume_from_checkpoint` TRL replays the restored `trainer_state.json`
    log history, so the whole of the previous attempt's metrics reappear in the
    new job's log. Parsing those reports the step the *old* run died at as
    current progress: this read `step 71` on a job eleven minutes into a resume
    from `checkpoint-50`, and the stale `step_time` it averaged put the run
    over budget. `epoch` stays absolute across a resume, so cutting the
    replayed history still recovers the true global step from the first fresh
    metric line. Returns the log unchanged when it holds no resume marker.
    """
    index = log.rfind("resuming from ")
    return log[index:] if index != -1 else log


def bucket_step(run_name: str) -> int | None:
    """
    Step number from the bucket, which does not depend on the job log.

    The trainer writes `completions/completions_NNNNN.parquet` once per step, so
    the highest index is the step it has finished. This matters because
    `hf jobs logs` is not a reliable progress source on a long run: it returns
    only a tail, that tail shrinks unpredictably (62,865 lines one minute, 635
    the next), and an empty response is indistinguishable from a run that has
    not started. Checkpoints are also authoritative but only land every 50
    steps, so they are too coarse on their own.

    Args:
        run_name (`str`):
            Run directory on the bucket.

    Returns:
        `int` or `None`: Highest completions index, or `None` if none exist.
    """
    listing = run("hf", "buckets", "ls", "-R", f"{BUCKET}/{run_name}/completions")
    steps = [int(m) for m in re.findall(r"completions_(\d+)\.parquet", listing)]
    return max(steps) if steps else None


def latest_checkpoint(run_name: str) -> int | None:
    """
    Highest checkpoint step saved to the bucket, or `None` if there are none.

    The bucket is the authority on progress: a checkpoint directory is named for
    the trainer's own `global_step`, so it cannot drift. Two other sources can:
    `hf jobs logs` returns only the tail once a log is large, and the Trackio
    dashboard advances its own row counter for automatic GPU and system metrics
    as well as training rows, so its "step" runs well ahead of `global_step`.

    Args:
        run_name (`str`):
            Run directory on the bucket.

    Returns:
        `int` or `None`: The highest saved checkpoint step.
    """
    listing = run("hf", "buckets", "ls", f"{BUCKET}/{run_name}")
    steps = [int(m) for m in re.findall(r"checkpoint-(\d+)/", listing)]
    return max(steps) if steps else None


def series(rows: list[dict], key: str) -> list[float]:
    """Every finite value logged for one metric."""
    return [r[key] for r in rows if key in r and math.isfinite(r[key])]


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--target", type=int, default=300)
    parser.add_argument("--budget-hours", type=float, default=24.0)
    parser.add_argument(
        "--run-name",
        default=None,
        help="Bucket run directory, to report the newest saved checkpoint.",
    )
    args = parser.parse_args()

    state_path = pathlib.Path(tempfile.gettempdir()) / f"health_{args.job_id}.json"
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            state = {}

    inspect = run("hf", "jobs", "inspect", args.job_id)
    found = re.findall(r'"stage": *"([A-Z]+)"', inspect)
    stage = found[-1] if found else "?"
    log = run("hf", "jobs", "logs", args.job_id)
    # A resumed job's log opens with the previous attempt's replayed
    # history; only what follows the resume describes this process.
    log = after_resume(log)
    rows = steps_from_log(log)
    # `hf jobs logs` returns only the tail once a run's log is large, so counting
    # metric lines undercounts the step number badly -- it read "step 1/1000" on
    # a run at step 108, wrecking the ETA and the progress figure. `epoch` is an
    # absolute position: TRL advances it by (tasks per step / dataset size) every
    # step, so it recovers the true step count from any single line.
    done = len(rows)
    epochs = series(rows, "epoch")
    if re.search(r"resuming from \S*?checkpoint-(\d+)", log):
        # The replayed history is strictly increasing and then jumps *back* to
        # one past the checkpoint when this process starts logging. That
        # descent is the only boundary between the two available here: both
        # halves are plain metric dicts with no timestamp to separate them.
        # Rows after the last descent belong to this process. No descent means
        # only one of the two is present -- which one is not decidable from the
        # rows alone, so the rows are used as they stand and the step number
        # comes from the progress bar below rather than from this inference.
        descents = [i for i in range(len(epochs) - 1) if epochs[i + 1] < epochs[i]]
        if descents:
            rows = rows[descents[-1] + 1 :]
            epochs = epochs[descents[-1] + 1 :]
    if epochs:
        # The *last* epoch, not the largest. On resume TRL replays the restored
        # `trainer_state.json` log history, so the log holds the previous
        # attempt's rows up to the step it died at, followed by this process's
        # fresh rows starting one past the checkpoint. Taking the maximum
        # reports the old high-water mark and stays frozen there until the run
        # overtakes it -- it read step 71 on a resume from checkpoint-50 that
        # had genuinely reached step 51, and averaged the old step_time into a
        # false over-budget alert. The last row is always the newest.
        #
        # Spacing likewise comes from the median positive gap rather than
        # (max - min) / (n - 1): a replayed history is not monotonic (it jumps
        # back at the resume), which deflates a range-based estimate.
        gaps = sorted(b - a for a, b in zip(epochs, epochs[1:]) if b > a)
        per_step = gaps[len(gaps) // 2] if gaps else EPOCH_PER_STEP
        if per_step > 0:
            done = round(epochs[-1] / per_step)

    # tqdm prints the trainer's true global step, which beats every inference
    # from `epoch`. It is right when the log holds replayed history (the bar
    # sits at the checkpoint, not the step the old attempt died at) and when it
    # holds only fresh rows -- the two cases the epoch maths cannot tell apart,
    # having twice reported the wrong one. Anchored to the step target so the
    # vLLM graph-capture bars ("0/3") cannot match.
    bars = re.findall(rf"(\d+)/{args.target} \[", log)
    if bars:
        done = int(bars[-1])

    if stage in ("ERROR", "CANCELED", "DELETED"):
        # `hf jobs logs` returns only a tail, so a crashed run whose metric
        # lines have scrolled away parses as zero steps and the report read
        # "after 0 steps" on a run that had done 69. The bucket is the
        # durable record of progress, so prefer whichever is further along.
        reached = max(
            done,
            (bucket_step(args.run_name) or 0) if args.run_name else 0,
            (latest_checkpoint(args.run_name) or 0) if args.run_name else 0,
        )
        print(f"ALERT {args.job_id} stage={stage} after {reached} steps")
        for line in re.findall(
            r"^.*(?:Traceback|Error:|CUDA out of memory|Killed).*$", log, re.M
        )[-3:]:
            print("  " + line.strip()[:160])
        raise SystemExit(9)
    if stage == "COMPLETED":
        print(f"OK {args.job_id} COMPLETED after {done} steps")
        raise SystemExit(8)
    if not rows:
        # A thin or empty log is common on a long run and is not itself a
        # fault, so fall back to the bucket rather than alerting: it answers
        # "is it progressing" even when no metrics can be parsed.
        from_bucket = bucket_step(args.run_name) if args.run_name else None
        checkpoint = latest_checkpoint(args.run_name) if args.run_name else None
        if from_bucket:
            print(
                f"OK {args.job_id} stage={stage} step {from_bucket}/{args.target} "
                f"(from bucket; job log returned no metrics)"
                + (f"  ckpt {checkpoint}" if checkpoint else "")
            )
            return
        # A readable log with no metric lines yet is startup, not a stall:
        # model load plus vLLM init takes ~8 minutes before the first step, and
        # the bucket has nothing until step 1 writes its completions parquet.
        # Only the case where the log itself cannot be read is a real unknown.
        if log.strip():
            print(f"OK {args.job_id} stage={stage} starting up (no step logged yet)")
            return
        print(f"ALERT {args.job_id} stage={stage} could not read job log (no data)")
        raise SystemExit(1)

    last = rows[-1]
    recent = rows[-TREND_WINDOW:]

    def mean(key: str, source: list[dict] = recent) -> float:
        values = series(source, key)
        return statistics.fmean(values) if values else float("nan")

    # Baseline entropy from the run's own opening steps, recorded once.
    entropies = series(rows, "entropy")
    baseline = state.get("entropy_baseline")
    if baseline is None and len(entropies) >= BASELINE_STEPS:
        baseline = statistics.fmean(entropies[:BASELINE_STEPS])

    step_time = mean("step_time")
    elapsed = done * step_time / 3600.0 if math.isfinite(step_time) else float("nan")
    eta = (
        (args.target - done) * step_time / 3600.0
        if math.isfinite(step_time)
        else float("nan")
    )

    reward10 = mean("reward")
    entropy = last.get("entropy", float("nan"))
    clip = mean("clip_ratio/region_mean")
    trunc = mean("completions/clipped_ratio")
    calls = mean("tools/call_frequency")
    fails = mean("tools/failure_frequency")
    grad = last.get("grad_norm", float("nan"))
    grads = series(rows, "grad_norm")
    dead = sum(1 for r in recent if (r.get("frac_reward_zero_std") or 0) > 0)

    notes = []
    # One or two dead groups in ten accompanied the run's best checkpoints, so
    # they are reported in the status line rather than alerted on. Only a
    # majority of the window carrying no gradient means learning has stopped.
    if dead >= 5:
        notes.append(f"dead-groups={dead}/{len(recent)}")
    if math.isfinite(fails) and fails > TOOL_FAILURE_MAX:
        notes.append(f"tool-failures={fails:.4f}")
    # Judged on the trailing mean, not the latest step: step-to-step entropy
    # varies by about 0.09 here, so a single dip is noise and would otherwise
    # trip the one alarm that matters most.
    entropy10 = mean("entropy")
    spread10 = mean("reward_std")
    entropy_low = (
        baseline
        and math.isfinite(entropy10)
        and entropy10 < ENTROPY_COLLAPSE_RATIO * baseline
    )
    spread_low = math.isfinite(spread10) and spread10 < SPREAD_FLOOR
    # Peak trailing reward so far, carried in the state file across checks.
    peak = state.get("reward_peak")
    if math.isfinite(reward10):
        peak = reward10 if peak is None else max(peak, reward10)
    if (
        peak
        and peak > 0
        and math.isfinite(reward10)
        and reward10 < peak * (1.0 - REWARD_DRAWDOWN)
    ):
        notes.append(f"reward-drawdown(10-step {reward10:.3f} vs peak {peak:.3f})")
    if entropy_low and spread_low and dead:
        notes.append(
            f"entropy-collapse(10-step {entropy10:.3f} vs base {baseline:.3f}, "
            f"spread {spread10:.3f})"
        )
    elif dead >= 5:
        # A thin spread accompanied convergence onto the best checkpoint, so it
        # is only a fault once most steps in the window carry no gradient.
        notes.append(f"no-gradient({dead}/{len(recent)} steps with zero spread)")
    if math.isfinite(clip) and clip > CLIP_FRACTION_MAX:
        notes.append(f"clipping-high={clip:.3f}")
    if math.isfinite(trunc) and trunc > TRUNCATION_MAX:
        notes.append(f"truncation={trunc:.3f}")
    if math.isfinite(calls) and calls > CALLS_MAX:
        notes.append(f"turn-exhaustion(calls={calls:.1f})")
    if len(grads) > TREND_WINDOW:
        typical = statistics.median(grads[:-1])
        if typical > 0 and math.isfinite(grad) and grad > GRAD_SPIKE_FACTOR * typical:
            notes.append(f"grad-spike({grad:.3f} vs median {typical:.3f})")
    if math.isfinite(elapsed + eta) and elapsed + eta > args.budget_hours:
        notes.append(f"over-budget({elapsed:.1f}h+{eta:.1f}h>{args.budget_hours:g}h)")
    # Stalled only if the step count has not moved for materially longer than a
    # step takes. Equality alone false-alarms whenever two checks land inside
    # one step, which at ~240s a step is easy to do.
    stalled_for = time.time() - (state.get("steps_seen_at") or time.time())
    if done == state.get("steps") and stalled_for > max(3 * step_time, 900):
        notes.append(f"no-progress(step {done} for {stalled_for / 60:.0f}min)")
    if re.search(r"Traceback|CUDA out of memory", log):
        notes.append("traceback-in-log")

    # Both of these have to survive the write or the two alerts that depend on
    # them can never fire: the drawdown check compares against `reward_peak`,
    # and the stall check measures elapsed time since `steps_seen_at`. They were
    # being dropped on every write, which is why neither ever alerted.
    seen_at = state.get("steps_seen_at")
    if done != state.get("steps") or not seen_at:
        seen_at = time.time()
    state_path.write_text(
        json.dumps(
            {
                "steps": done,
                "entropy_baseline": baseline,
                "reward_peak": peak,
                "steps_seen_at": seen_at,
            }
        )
    )

    checkpoint = latest_checkpoint(args.run_name) if args.run_name else None
    if args.run_name:
        # The log's tail can lag well behind; trust whichever is further along.
        from_bucket = bucket_step(args.run_name)
        if from_bucket and from_bucket > done:
            done = from_bucket
    status = "ALERT" if notes else "OK"
    print(
        f"{status} step {done}/{args.target}  "
        f"reward {last.get('reward', float('nan')):.3f} (10-step {reward10:.3f})  "
        f"spread {last.get('reward_std', float('nan')):.3f} (10-step {spread10:.3f})  "
        f"entropy {entropy:.3f} (10-step {entropy10:.3f})"
        + (f"/base {baseline:.3f}" if baseline else "")
        + f"  clip {clip:.3f}  trunc {trunc:.3f}  calls {calls:.1f}  "
        f"grad {grad:.3f}  fail {fails:.4f}  {step_time:.0f}s  "
        f"{elapsed:.1f}h+{eta:.1f}h"
        + (f"  ckpt {checkpoint}" if checkpoint else "")
        + ("  " + " ".join(notes) if notes else "")
    )


if __name__ == "__main__":
    main()
