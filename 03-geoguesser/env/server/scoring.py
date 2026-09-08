# SPDX-License-Identifier: BSD-3-Clause

"""Distance scoring and action costs.

The distance curve is GeoGuessr's own, `5000 * exp(-d / 1492.7)`, normalised
to `[0, 1]`. Keeping the real curve means scores are directly interpretable
against the game most people already know.
"""

from __future__ import annotations

import math


# GeoGuessr's decay constant, in kilometres.
DECAY_KM = 1492.7

# A second, much slower decay used only by the `"mixture"` reward shape. The
# game curve is worth 0.018 across the whole 6000-20000 km range, so a policy
# that lands on the wrong continent -- a third of rollouts for a 4B model --
# gets no gradient for getting *less* wrong. This scale restores one.
LONG_DECAY_KM = 5000.0

# Fraction of the mixture carried by the game curve; the rest is the long scale.
MIXTURE_SHORT_WEIGHT = 0.5

REWARD_SHAPES = ("geoguessr", "mixture")

EARTH_RADIUS_KM = 6371.0088

# Action costs. Information gathering is cheap but not free, so an episode has
# to trade breadth of search against committing to a guess.
COST_LOOK = 0.01
COST_MAP = 0.01
COST_PIN = 0.02
COST_MOVE = 0.05

# Partial credit weights, used when the reward is hierarchical.
WEIGHT_COUNTRY = 0.15
WEIGHT_REGION = 0.10


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """
    Great-circle distance between two points in kilometres.

    Args:
        lat_a (`float`):
            Latitude of the first point in degrees.
        lon_a (`float`):
            Longitude of the first point in degrees.
        lat_b (`float`):
            Latitude of the second point in degrees.
        lon_b (`float`):
            Longitude of the second point in degrees.

    Returns:
        `float`: Distance in kilometres.

    Examples:

    ```python
    d = haversine_km(-16.4897, -68.1193, -17.7833, -63.1821)
    ```
    """
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    d_phi = phi_b - phi_a
    d_lambda = math.radians(lon_b - lon_a)
    h = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


def distance_score(distance_km: float, shape: str = "geoguessr") -> float:
    """
    Map a distance to a score in `[0, 1]`.

    Args:
        distance_km (`float`):
            Distance between guess and truth in kilometres.
        shape (`str`, *optional*, defaults to `"geoguessr"`):
            `"geoguessr"` for the game's own curve, or `"mixture"` for the
            two-scale curve used when training. The mixture is deliberately
            *not* the default: reported scores stay comparable to the game.

    Returns:
        `float`: For `"geoguessr"`, `exp(-distance_km / 1492.7)` -- 0 km scores
        `1.0`, 150 km about `0.90`, 5000 km about `0.035`. For `"mixture"`,
        half that plus half of `exp(-distance_km / 5000)`, which keeps the
        mid-range sharp while leaving real gradient past 3000 km.

    Examples:

    ```python
    near = distance_score(200.0)                     # 0.875
    far = distance_score(8000.0, shape="mixture")    # 0.104, versus 0.005
    ```
    """
    if distance_km < 0:
        raise ValueError(f"distance_km must be non-negative, got {distance_km}")
    if shape not in REWARD_SHAPES:
        raise ValueError(f"shape must be one of {REWARD_SHAPES}, got {shape!r}")
    short = math.exp(-distance_km / DECAY_KM)
    if shape == "geoguessr":
        return short
    long = math.exp(-distance_km / LONG_DECAY_KM)
    return MIXTURE_SHORT_WEIGHT * short + (1.0 - MIXTURE_SHORT_WEIGHT) * long


def action_cost(
    n_looks: int = 0, n_maps: int = 0, n_pins: int = 0, n_moves: int = 0
) -> float:
    """
    Total cost of the information gathering done this episode.

    Args:
        n_looks (`int`, *optional*, defaults to `0`):
            Number of view renders.
        n_maps (`int`, *optional*, defaults to `0`):
            Number of map views that were not pins.
        n_pins (`int`, *optional*, defaults to `0`):
            Number of pins placed.
        n_moves (`int`, *optional*, defaults to `0`):
            Number of moves taken.

    Returns:
        `float`: Cost to subtract from the distance score.
    """
    return (
        COST_LOOK * n_looks
        + COST_MAP * n_maps
        + COST_PIN * n_pins
        + COST_MOVE * n_moves
    )


# The multiplicative cost is capped so a very long episode scales the score down
# rather than erasing it. Without a cap a 20-move episode would reach zero.
MAX_COST_FRACTION = 0.5


def compute_reward(
    distance_km: float | None,
    *,
    cost: float = 0.0,
    country_hit: bool = False,
    region_hit: bool = False,
    hierarchical: bool = False,
    shape: str = "geoguessr",
    cost_mode: str = "subtract",
) -> float:
    """
    Combine distance, partial credit and action cost into one reward.

    Args:
        distance_km (`float` or `None`):
            Distance from guess to truth. `None` means the guess could not be
            parsed, which scores zero before costs.
        cost (`float`, *optional*, defaults to `0.0`):
            Accumulated action cost.
        country_hit (`bool`, *optional*, defaults to `False`):
            Whether the guessed country matched.
        region_hit (`bool`, *optional*, defaults to `False`):
            Whether the guessed region matched.
        hierarchical (`bool`, *optional*, defaults to `False`):
            Whether to add country and region partial credit.
        shape (`str`, *optional*, defaults to `"geoguessr"`):
            Distance curve, passed to [`~scoring.distance_score`].
        cost_mode (`str`, *optional*, defaults to `"subtract"`):
            `"subtract"` reproduces the game: the cost comes off the score and
            the result is floored at zero. `"multiply"` scales the score by
            `1 - cost` instead, which is what training wants -- see below.

    Returns:
        `float`: Reward in `[0, 1]`.

    <Tip warning={true}>

    `"subtract"` and a floor at zero destroy the ordering of bad guesses. Mean
    cost for a 4B model is 0.13, and the game curve falls below that at about
    3300 km, so a 3324 km miss and an 18723 km miss both score exactly 0.0 --
    measured across 200 episodes, 77 of them collapsed to a single value with
    zero variance. A GRPO group drawn from those has no advantage and therefore
    contributes no gradient. `"multiply"` cannot do this: scaling by a positive
    factor preserves the ordering whatever the cost.

    </Tip>

    Examples:

    ```python
    # Training: gradient survives on the wrong continent.
    reward = compute_reward(8000.0, cost=0.13, shape="mixture", cost_mode="multiply")
    ```
    """
    if distance_km is None:
        return 0.0
    score = distance_score(distance_km, shape=shape)
    if hierarchical:
        score += WEIGHT_COUNTRY * country_hit + WEIGHT_REGION * region_hit
    score = min(1.0, score)
    if cost_mode == "multiply":
        return score * (1.0 - min(max(cost, 0.0), MAX_COST_FRACTION))
    if cost_mode != "subtract":
        raise ValueError(
            f"cost_mode must be 'subtract' or 'multiply', got {cost_mode!r}"
        )
    return max(0.0, score - cost)


def verdict(distance_km: float) -> str:
    """
    Short human-readable label for a distance, for UIs and logs.

    Args:
        distance_km (`float`):
            Distance between guess and truth in kilometres.

    Returns:
        `str`: One of `"Perfect"`, `"Pinpoint"`, `"Close"`, `"Right region"`
        or `"Wrong continent"`.
    """
    if distance_km < 0.025:
        return "Perfect"
    if distance_km < 25:
        return "Pinpoint"
    if distance_km < 200:
        return "Close"
    if distance_km < 1500:
        return "Right region"
    return "Wrong continent"
