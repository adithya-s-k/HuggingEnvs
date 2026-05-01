"""Reward function for Jupyter Agent GEM training.

GEM rewards come from step().reward (Gymnasium pattern).
The adapter captures them per turn.
"""

import logging

log = logging.getLogger(__name__)

_reward_call_count = 0


def reward_func(completions, environments, expected_output: list[str] = None, **kwargs) -> list[float]:
    global _reward_call_count
    _reward_call_count += 1

    if expected_output is None:
        expected_output = [""] * len(environments)

    rewards = []
    for env, expected in zip(environments, expected_output):
        if env.reward > 0:
            rewards.append(env.reward)
        else:
            expected_clean = expected.strip() if expected else ""
            last_out = (env.last_output or "").strip()
            if expected_clean and expected_clean in last_out:
                rewards.append(1.0)
            else:
                rewards.append(0.0)

    n = len(environments)
    solved = sum(1 for r in rewards if r > 0)
    log.info(
        f"[GEM Reward #{_reward_call_count}] "
        f"solved={solved}/{n} "
        f"avg_reward={sum(rewards)/n:.3f} "
        f"avg_steps={sum(e.step_count for e in environments)/n:.1f}"
    )
    return rewards
