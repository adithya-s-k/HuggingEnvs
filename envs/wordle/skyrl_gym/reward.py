"""Reward function for Wordle training."""

import logging

log = logging.getLogger(__name__)
_call_count = 0


def reward_func(completions, environments, **kwargs) -> list[float]:
    global _call_count
    _call_count += 1

    rewards = []
    for env in environments:
        # The toolkit tracks game reward internally
        if hasattr(env, '_toolkit') and hasattr(env._toolkit, 'reward'):
            rewards.append(env._toolkit.reward)
        elif hasattr(env, 'reward'):
            rewards.append(env.reward)
        else:
            rewards.append(0.0)

    n = len(environments)
    won = sum(1 for r in rewards if r >= 1.0)
    log.info(
        f"[Wordle Reward #{_call_count}] won={won}/{n} "
        f"avg_reward={sum(rewards)/n:.3f}"
    )
    return rewards
