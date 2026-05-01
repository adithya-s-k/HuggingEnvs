"""Reward for Wordle OpenEnv — external string matching."""
import logging
log = logging.getLogger(__name__)
_call_count = 0

def reward_func(completions, environments, answer: list[str] = None, **kwargs):
    global _call_count
    _call_count += 1
    if answer is None:
        answer = [""] * len(environments)
    rewards = []
    for env, ans in zip(environments, answer):
        last = (env.last_output or "").lower()
        if "correct" in last:
            rewards.append(1.0)
        else:
            rewards.append(0.0)
    won = sum(1 for r in rewards if r > 0)
    log.info(f"[Wordle OpenEnv Reward #{_call_count}] won={won}/{len(environments)}")
    return rewards
