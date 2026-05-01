"""
Reward function for Jupyter Agent ORS training.

ORS embeds rewards in ToolOutput — the adapter captures them into env.reward.
This reward function simply reads the accumulated reward from each environment.
"""

import logging

log = logging.getLogger(__name__)

_reward_call_count = 0


def reward_func(completions, environments, **kwargs) -> list[float]:
    """Read rewards from ORS environments.

    Unlike OpenEnv where reward is computed externally via string matching,
    ORS rewards come from the server embedded in each ToolOutput.reward.
    The adapter captures these into env.reward during tool execution.
    """
    global _reward_call_count
    _reward_call_count += 1

    rewards = [env.reward for env in environments]
    n = len(environments)

    solved_count = sum(1 for r in rewards if r > 0)
    avg_reward = sum(rewards) / n if n else 0
    total_steps = sum(env.step_count for env in environments)

    log.info(
        f"[ORS Reward #{_reward_call_count}] "
        f"solved={solved_count}/{n} "
        f"avg_reward={avg_reward:.3f} "
        f"avg_steps={total_steps / n:.1f}"
    )

    return rewards
