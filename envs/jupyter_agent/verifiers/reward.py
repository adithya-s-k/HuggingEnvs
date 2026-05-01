"""Reward function for Jupyter Agent Verifiers training.

Uses simple string matching (same as OpenEnv) since verifiers' rubric
scoring is designed for its own eval loop. For TRL integration, we
match expected_output against the toolkit's last_output.
"""

import logging

log = logging.getLogger(__name__)

_reward_call_count = 0


def reward_func(completions, environments, expected_output: list[str] = None, **kwargs) -> list[float]:
    """Compute reward by checking expected output in last tool result."""
    global _reward_call_count
    _reward_call_count += 1

    if expected_output is None:
        expected_output = [""] * len(environments)

    rewards = []
    for env, expected in zip(environments, expected_output):
        expected_clean = expected.strip() if expected else ""
        last_out = (env.last_output or "").strip()

        if expected_clean and expected_clean in last_out:
            r = 1.0
            r += max(0.0, 0.2 * (1.0 - env.step_count / 10.0))
        else:
            r = 0.0

        r -= 0.05 * env.error_count
        rewards.append(max(r, -1.0))

    n = len(environments)
    solved = sum(1 for r in rewards if r > 0)
    log.info(
        f"[Verifiers Reward #{_reward_call_count}] "
        f"solved={solved}/{n} "
        f"avg_reward={sum(rewards)/n:.3f} "
        f"avg_steps={sum(e.step_count for e in environments)/n:.1f}"
    )
    return rewards
