"""Dataset builder for Kaggle-based Jupyter Agent training.

Loads the prepared RL dataset from HF Hub (or local path).
Each row has: prompt, answer, kaggle_dataset_name, files, etc.

Usage:
    ds = build_dataset(hub_name="AdithyaSK/jupyter-agent-rl-10")
    ds = build_dataset(local_path="/path/to/dataset-10")
"""

from datasets import Dataset, load_dataset, load_from_disk


def build_dataset(
    hub_name: str = "AdithyaSK/jupyter-agent-rl-1000",  # also: rl-10, rl-100, rl-10000
    local_path: str = None,
    num_repeats: int = 1,
    max_tasks: int = None,
) -> Dataset:
    """Load the Kaggle RL dataset.

    Args:
        hub_name: HuggingFace dataset name (ignored if local_path is set)
        local_path: Path to local dataset saved with save_to_disk()
        num_repeats: Repeat each task N times (for GRPO advantage)
        max_tasks: Limit to first N tasks (for testing)
    """
    if local_path:
        ds = load_from_disk(local_path)
    else:
        ds = load_dataset(hub_name, split="train")

    if max_tasks:
        ds = ds.select(range(min(max_tasks, len(ds))))

    if num_repeats > 1:
        # Repeat by concatenating
        from datasets import concatenate_datasets
        ds = concatenate_datasets([ds] * num_repeats)
        ds = ds.shuffle(seed=42)

    return ds
