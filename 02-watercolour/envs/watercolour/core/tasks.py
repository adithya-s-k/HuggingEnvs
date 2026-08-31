# SPDX-License-Identifier: BSD-3-Clause

"""What the model is asked to paint.

Subjects are things watercolour is traditionally good at: soft edges, layered
washes, colour bleeding into wet paper. They are deliberately not the point of
the reward. The judge is told to ignore what a painting depicts and weigh only
how it is painted, so the subject exists to vary the composition rather than to
be scored for likeness.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

SUBJECTS = (
    "a peach hibiscus",
    "two ripe plums",
    "a windswept pine branch",
    "coastal cliffs under haze",
    "a single white peony",
    "a bowl of figs",
    "wet slate rooftops in rain",
    "an olive branch with fruit",
    "three eucalyptus leaves",
    "a harbour at dusk",
    "a stem of lavender",
    "a pomegranate cut open",
)

PROMPT = "Paint {subject} in loose watercolour."


@dataclass(frozen=True)
class Task:
    """One painting request.

    Attributes:
        subject (`str`):
            What to paint.
        prompt (`str`):
            The instruction handed to the model.
        task_id (`str`):
            Stable identifier, the subject in snake_case.
    """

    subject: str
    prompt: str
    task_id: str


def make_task(subject: str) -> Task:
    """Build a task for a subject.

    Args:
        subject (`str`):
            One of [`SUBJECTS`], or any phrase for an ad-hoc task.

    Returns:
        [`Task`]: The task.

    Examples:

    ```python
    task = make_task("two ripe plums")
    print(task.prompt)
    ```
    """
    return Task(
        subject=subject,
        prompt=PROMPT.format(subject=subject),
        task_id=subject.replace(" ", "_"),
    )


def sample_task(seed: int | None = None, subjects=None) -> Task:
    """Draw a task at random.

    Args:
        seed (`int`, *optional*):
            Makes the choice reproducible.
        subjects (`tuple[str, ...]`, *optional*):
            Draw from these instead of [`SUBJECTS`]. A domain supplies its own.

    Returns:
        [`Task`]: The sampled task.
    """
    return make_task(random.Random(seed).choice(tuple(subjects or SUBJECTS)))
