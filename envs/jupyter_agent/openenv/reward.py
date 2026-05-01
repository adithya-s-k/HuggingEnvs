"""Reward function for Jupyter Agent GRPO training.

Evaluates each environment instance after the episode completes.
"""

import logging
import time

log = logging.getLogger(__name__)

_reward_call_count = 0


def reward_func(environments, expected_output: list[str], **kwargs) -> list[float]:
    """Compute reward for each environment instance after the episode.

    Reward components:
    - Task completion (1.0): expected output found in last output
    - Efficiency bonus (up to 0.2): fewer steps = higher bonus (only if solved)
    - Error penalty (-0.05 per error): discourages trial-and-error spam
    """
    global _reward_call_count
    _reward_call_count += 1

    rewards = []
    solved_count = 0
    total_steps = 0
    total_errors = 0

    for env, expected in zip(environments, expected_output):
        expected_clean = expected.strip()
        last_out = (env.last_output or "").strip()

        if expected_clean and expected_clean in last_out:
            r = 1.0
            r += max(0.0, 0.2 * (1.0 - env.step_count / 10.0))
            solved_count += 1
        else:
            r = 0.0

        r -= 0.05 * env.error_count
        rewards.append(max(r, -1.0))

        total_steps += env.step_count
        total_errors += env.error_count

    n = len(environments)

    # Access timing stats from the environment class (if available)
    env_cls = type(environments[0])
    avg_reset = getattr(env_cls, '_total_reset_time', 0.0) / max(getattr(env_cls, '_total_resets', 0), 1)
    avg_tool = getattr(env_cls, '_total_tool_time', 0.0) / max(getattr(env_cls, '_total_tool_calls', 0), 1)

    # Multi-turn analysis
    step_counts = [env.step_count for env in environments]
    multi_turn_count = sum(1 for s in step_counts if s > 1)
    max_turns = max(step_counts) if step_counts else 0
    turn_distribution = {}
    for s in step_counts:
        turn_distribution[s] = turn_distribution.get(s, 0) + 1

    log.info(
        f"[Reward #{_reward_call_count}] "
        f"solved={solved_count}/{n} "
        f"avg_reward={sum(rewards)/n:.3f} "
        f"min={min(rewards):.3f} max={max(rewards):.3f} "
        f"std={max((sum((r - sum(rewards)/n)**2 for r in rewards) / n) ** 0.5, 0):.3f} | "
        f"avg_steps={total_steps/n:.1f} errors={total_errors} | "
        f"multi_turn={multi_turn_count}/{n} max_turns={max_turns} "
        f"turn_dist={turn_distribution} | "
        f"env_io: avg_reset={avg_reset:.2f}s avg_tool={avg_tool:.2f}s "
        f"total_resets={getattr(env_cls, '_total_resets', 0)} total_tools={getattr(env_cls, '_total_tool_calls', 0)}"
    )

    # Log each episode for visibility
    for i, (env, expected, reward) in enumerate(zip(environments, expected_output, rewards)):
        solved = expected.strip() and expected.strip() in (env.last_output or "").strip()
        status = "OK" if solved else "FAIL"
        conv_summary = " -> ".join(
            f"{c['tool'].replace('add_and_execute_code_cell','code').replace('execute_shell_command','shell')}({'ERR' if c.get('error') else 'ok'})"
            for c in env._conversation
        ) or "(no calls)"
        log.info(
            f"  {status} [{i+1}/{n}] steps={env.step_count} reward={reward:.2f} "
            f"expected='{expected[:30]}' got='{(env.last_output or '')[:30]}' "
            f"trace: {conv_summary}"
        )

    return rewards
