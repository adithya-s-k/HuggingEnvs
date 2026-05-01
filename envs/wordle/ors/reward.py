"""Reward function for Wordle ORS training.

ORS embeds rewards in ToolOutput — the adapter captures them.
This function reads the adapter's accumulated reward.
"""

import logging

log = logging.getLogger(__name__)
_call_count = 0


def reward_func(completions, environments, **kwargs) -> list[float]:
    global _call_count
    _call_count += 1

    rewards = []
    for env in environments:
        rewards.append(getattr(env, "reward", 0.0))

    n = len(environments)
    won = sum(1 for r in rewards if r >= 1.0)
    log.info(
        f"[Wordle ORS Reward #{_call_count}] won={won}/{n} "
        f"avg_reward={sum(rewards)/n:.3f}"
    )
    return rewards
