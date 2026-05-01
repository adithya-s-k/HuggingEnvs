"""Reward function for Wordle NeMo Gym training.

NeMo Gym computes rewards server-side via /verify endpoint.
The adapter calls verify() and stores the reward.
"""

import logging

log = logging.getLogger(__name__)
_call_count = 0


def reward_func(completions, environments, **kwargs) -> list[float]:
    global _call_count
    _call_count += 1

    rewards = []
    for env in environments:
        # Try verify first, then fallback to checking last_output
        r = getattr(env, "reward", 0.0)
        if r == 0.0 and hasattr(env, "last_output"):
            if "Correct" in (env.last_output or ""):
                r = 1.0
        rewards.append(r)

    n = len(environments)
    won = sum(1 for r in rewards if r >= 1.0)
    log.info(
        f"[Wordle NeMo Reward #{_call_count}] won={won}/{n} "
        f"avg_reward={sum(rewards)/n:.3f}"
    )
    return rewards
