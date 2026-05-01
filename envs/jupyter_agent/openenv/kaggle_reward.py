"""Multi-component reward function for Kaggle Jupyter Agent training.

Designed for GRPO — rewards range 0-7 for maximum variance.

Components:
  +2.0  code executed without errors
  +0.5  code executed with errors (some credit)
  +1.0  called final_answer
  +3.0  answer correctness (exact=3, close=2, partial=1)
  +1.0  efficiency bonus (fewer steps)
"""

import logging
import re

log = logging.getLogger(__name__)
_call_count = 0


def normalize(text: str) -> str:
    """Normalize answer text for comparison."""
    if not text:
        return ""
    t = text.strip().lower()
    # Remove common formatting
    t = t.replace("$", "").replace(",", "").replace("%", "")
    t = t.replace("'", "").replace('"', "")
    t = t.replace("_", " ")  # treat underscores as spaces for matching
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t)
    return t


def extract_numbers(text: str) -> list[float]:
    """Extract all numbers from text."""
    nums = re.findall(r"-?\d+\.?\d*", text)
    result = []
    for n in nums:
        try:
            result.append(float(n))
        except ValueError:
            pass
    return result


def match_answer(model_answer: str, reference: str) -> float:
    """Compare model answer to reference. Returns 0.0, 0.33, 0.66, or 1.0."""
    if not model_answer or not reference:
        return 0.0

    m = normalize(model_answer)
    r = normalize(reference)

    # Exact match after normalization
    if m == r or r in m or m in r:
        return 1.0

    # Number comparison within 5% tolerance
    m_nums = extract_numbers(m)
    r_nums = extract_numbers(r)
    if r_nums and m_nums:
        for rn in r_nums:
            for mn in m_nums:
                if abs(rn) < 1e-9:
                    continue
                if abs(mn - rn) / abs(rn) < 0.05:
                    return 0.66

    # Keyword overlap (for text answers like "sulphates")
    r_words = set(r.split())
    m_words = set(m.split())
    if r_words:
        overlap = len(r_words & m_words) / len(r_words)
        if overlap > 0.5:
            return 0.33

    return 0.0


def reward_func(completions, environments, answer: list[str] = None, **kwargs) -> list[float]:
    """Multi-component reward for GRPO training.

    Args:
        completions: Model completions (not used directly)
        environments: List of environment instances
        answer: List of reference answers from dataset
    """
    global _call_count
    _call_count += 1

    if answer is None:
        answer = [""] * len(environments)

    rewards = []
    for env, ref_answer in zip(environments, answer):
        r = 0.0

        # 1. Code execution (+2.0 clean, +0.5 with errors)
        if env.step_count > 0 and env.error_count == 0:
            r += 2.0
        elif env.step_count > 0:
            r += 0.5

        # 2. Called final_answer (+1.0)
        submitted = getattr(env, "_submitted_answer", None)
        if submitted:
            r += 1.0

        # 3. Answer correctness (+3.0 max)
        if submitted and ref_answer:
            score = match_answer(submitted, ref_answer)
            r += score * 3.0
        elif not submitted and ref_answer:
            # Check if answer appears in last_output (fallback)
            last = (env.last_output or "").strip()
            if ref_answer.strip() and normalize(ref_answer) in normalize(last):
                r += 2.0  # less credit than using final_answer

        # 4. Efficiency bonus (+1.0 max)
        if env.step_count > 0:
            r += max(0.0, 1.0 * (1.0 - env.step_count / 15.0))

        rewards.append(r)

    n = len(environments)
    solved = sum(1 for r in rewards if r >= 4.0)
    avg = sum(rewards) / max(n, 1)
    log.info(
        f"[Kaggle Reward #{_call_count}] "
        f"solved={solved}/{n} "
        f"avg_reward={avg:.2f} "
        f"avg_steps={sum(e.step_count for e in environments)/max(n,1):.1f}"
    )
    return rewards
