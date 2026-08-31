# SPDX-License-Identifier: BSD-3-Clause

"""Where the reference paintings come from.

The pool used to ship inside this package, 98MB of PNGs in `reference_pool/`, and
that had three costs. The repository carried binary data that belongs on the Hub.
Every deployed copy of this environment held its own duplicate, and one of them
silently drifted from the others once. And "the pool" was a concept rather than an
identifiable object: nothing recorded which 178 paintings a given run was scored
against.

Pinning a dataset revision fixes all three. What the pool contains *is* the reward
function, so the revision is part of the environment's configuration, not an
implementation detail.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path

DATASET = "HuggingEnvs/watercolour-reference-pool"

# Pinned rather than tracking `main`: a new revision of the dataset is a new reward
# function, and it should take an explicit change here to adopt one.
REVISION = "50da8bb183aa472bdf6538852b652778f539a2af"


@functools.cache
def _snapshot() -> Path:
    from huggingface_hub import snapshot_download

    return Path(
        snapshot_download(
            repo_id=os.environ.get("WATERCOLOUR_POOL_DATASET", DATASET),
            revision=os.environ.get("WATERCOLOUR_POOL_REVISION", REVISION),
            repo_type="dataset",
            allow_patterns=["images/*", "sources/*", "metadata.jsonl"],
        )
    )


def pool_dir() -> Path:
    """Resolve the directory holding the reference PNGs.

    Set `WATERCOLOUR_POOL_DIR` to score against a pool on disk instead, which is
    how a replacement pool is tried without publishing it first.

    Returns:
        `Path`: A directory of PNGs whose filename prefix is the tier.

    Examples:

    ```python
    print(len(list(pool_dir().glob("*.png"))))
    ```
    """
    local = os.environ.get("WATERCOLOUR_POOL_DIR")
    return Path(local) if local else _snapshot() / "images"


def pool_sources() -> Path:
    """Resolve the directory holding the sketch that produced each reference.

    Returns:
        `Path`: A directory of `.js` files named after the PNGs.

    Examples:

    ```python
    print(len(list(pool_sources().glob("*.js"))))
    ```
    """
    return _snapshot() / "sources"
