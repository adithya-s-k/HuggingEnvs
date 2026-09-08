"""
Guards the reference reward and flags when training drifts away from it.

`train/grpo_geoguesser.py` must stay a single self-contained file, because
`hf jobs uv run` uploads exactly one script -- so it cannot import
`geoeval.py` and the reward constants exist twice.

Two distinct things are checked, because they fail differently:

1. **The reference curve is pinned.** the curve at the top of `geoeval.py` is the yardstick every
   checkpoint from every run is measured on. Silently "fixing" it to match a
   retuned training reward would make all previously recorded numbers
   incomparable, which is worse than an obvious mismatch.
2. **Training defaults still equal the reference.** When they do, the trained
   objective and the yardstick coincide and reward is directly interpretable.
   When a run deliberately retunes the reward, this test fails and names what
   diverged -- so the divergence is a decision someone made rather than
   something nobody noticed. Update `REFERENCE` here only when you intend to
   abandon comparability with earlier runs.

Run with `pytest eval/test_reward_parity.py`.
"""

import math
import pathlib

import re

import geoeval as reference
from geoeval import (
    DECAY_KM,
    LONG_DECAY_KM,
    MAX_COST_FRACTION,
    MIXTURE_SHORT_WEIGHT,
    training_reward,
)

TRAIN_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1] / "train" / "grpo_geoguesser.py"
)

# Run 1's curve, and the axis every checkpoint is scored on. Changing these
# numbers invalidates comparison with every result recorded so far.
REFERENCE = {
    "DECAY_KM": 1492.7,
    "LONG_DECAY_KM": 5000.0,
    "MIXTURE_SHORT_WEIGHT": 0.5,
    "MAX_COST_FRACTION": 0.2,
}


def _constants() -> dict[str, float]:
    """The reward constants as literally written in the training script."""
    source = TRAIN_SCRIPT.read_text()
    found = {}
    for name in ("DECAY_KM", "LONG_DECAY_KM", "MIXTURE_SHORT_WEIGHT"):
        # Some constants are plain literals and some became env-driven with a
        # default; match either, since what matters for parity is the value a
        # plain launch uses.
        match = re.search(
            rf'^{name} = (?:float\(os\.getenv\("{name}", "([0-9.]+)"\)\)|([0-9.]+))$',
            source,
            re.M,
        )
        assert match, f"{name} not found in {TRAIN_SCRIPT.name}"
        found[name] = float(match.group(1) or match.group(2))
    # This one is env-driven; the default is what a plain launch uses.
    match = re.search(
        r'^MAX_COST_FRACTION = float\(os\.getenv\("MAX_COST_FRACTION", "([0-9.]+)"\)\)$',
        source,
        re.M,
    )
    assert match, f"MAX_COST_FRACTION default not found in {TRAIN_SCRIPT.name}"
    found["MAX_COST_FRACTION"] = float(match.group(1))
    return found


def test_reference_curve_is_pinned():
    """The yardstick has not moved, so old and new results remain comparable."""
    assert {
        "DECAY_KM": DECAY_KM,
        "LONG_DECAY_KM": LONG_DECAY_KM,
        "MIXTURE_SHORT_WEIGHT": MIXTURE_SHORT_WEIGHT,
        "MAX_COST_FRACTION": MAX_COST_FRACTION,
    } == REFERENCE


def test_training_defaults_match_the_reference():
    """Training's defaults still coincide with the yardstick.

    A failure here is informative, not necessarily a bug: it means the training
    reward was retuned. Accept it by reading conclusions from the
    reward-independent metrics (median distance, country accuracy, turns), and
    do not "fix" it by editing the reference.
    """
    found = _constants()
    drift = {k: (v, REFERENCE[k]) for k, v in found.items() if v != REFERENCE[k]}
    assert not drift, (
        "training reward diverges from the pinned reference "
        f"(training, reference): {drift}. The reference is deliberately fixed; "
        "compare runs on median km / country% / turns instead."
    )


def test_reference_ignores_training_cost_scaling():
    """`COST_SCALE` is a training incentive knob, not part of the yardstick.

    Checked as a missing module attribute rather than a missing string, since
    the docstring names it precisely to explain why it is absent.
    """
    assert not hasattr(reference, "COST_SCALE")


def test_no_usable_guess_scores_zero():
    assert training_reward(None, cost=0.0) == 0.0
    assert training_reward(None, cost=0.9) == 0.0


def test_cost_scales_but_never_erases():
    # A positive factor cannot collapse an ordering, which is the whole reason
    # the cost is multiplicative rather than subtracted with a floor.
    near, far = training_reward(500.0, cost=0.9), training_reward(9000.0, cost=0.0)
    assert near > far > 0.0


def test_cost_is_capped_at_the_fraction():
    uncapped = training_reward(1000.0, cost=0.0)
    assert training_reward(1000.0, cost=MAX_COST_FRACTION) == training_reward(
        1000.0, cost=5.0
    )
    assert math.isclose(
        training_reward(1000.0, cost=5.0), uncapped * (1.0 - MAX_COST_FRACTION)
    )


def test_matches_a_recorded_episode():
    # A real hosted-Space guess: 1348.52 km at 0.05 cost. The environment
    # reported 0.3852 for the same episode on the *game's* curve -- the gap is
    # the point of this module, not a discrepancy.
    assert math.isclose(training_reward(1348.52, cost=0.05), 0.5552, abs_tol=5e-4)
