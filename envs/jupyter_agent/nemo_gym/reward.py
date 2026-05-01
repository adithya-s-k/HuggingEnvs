"""
Reward function for Jupyter Agent NeMo Gym training.

NeMo Gym computes rewards via the /verify endpoint on the Resources Server.
The adapter calls /verify post-episode and stores the result in env.reward.
This reward function simply reads it.
"""

import logging

log = logging.getLogger(__name__)

_reward_call_count = 0


def reward_func(completions, environments, **kwargs) -> list[float]:
    """Read rewards from NeMo Gym environments.

    Rewards come from the /verify endpoint called by the adapter
    after each episode. The verify() method checks if the expected
    output appears in the execution results.
    """
    global _reward_call_count
    _reward_call_count += 1

    # Call /verify on each environment to compute reward post-episode
    for env in environments:
        if hasattr(env, "verify"):
            env.verify()
    rewards = [env.reward for env in environments]
    n = len(environments)

    solved_count = sum(1 for r in rewards if r > 0)
    avg_reward = sum(rewards) / n if n else 0
    total_steps = sum(env.step_count for env in environments)

    log.info(
        f"[NeMo Gym Reward #{_reward_call_count}] "
        f"solved={solved_count}/{n} "
        f"avg_reward={avg_reward:.3f} "
        f"avg_steps={total_steps / n:.1f}"
    )

    return rewards
