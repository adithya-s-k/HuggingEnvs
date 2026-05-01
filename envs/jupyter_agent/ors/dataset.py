"""
Dataset builder for Jupyter Agent ORS training.

Pulls tasks from a running ORS server or uses the built-in TASKS list.
"""

from datasets import Dataset

SYSTEM_PROMPT = """You are an intelligent data science assistant operating inside a stateful Jupyter notebook environment.
Your goal is to solve analytical and computational tasks through careful, iterative code execution.
Always execute code to verify — never guess at results. Use the available tools to write and run Python code."""


def build_dataset_from_server(base_url: str = "http://localhost:8080",
                               env_name: str = "jupiteragentors",
                               split: str = "train",
                               num_repeats: int = 4,
                               max_tasks: int = None) -> Dataset:
    """Pull tasks from a running ORS server and build HF Dataset."""
    from ors.client import ORS

    client = ORS(base_url=base_url)
    env = client.environment(env_name)
    tasks = env.list_tasks(split=split)
    client.close()

    if max_tasks:
        tasks = tasks[:max_tasks]

    rows = []
    for _ in range(num_repeats):
        for i, task in enumerate(tasks):
            task_spec = task if isinstance(task, dict) else task.task_spec
            rows.append({
                "prompt": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Complete the task using the available tools."},
                ],
                "task_spec": task_spec,
                "task_index": i,
                "expected_output": task_spec.get("expected_output", ""),
            })

    return Dataset.from_list(rows)


def build_dataset(num_repeats: int = 4, max_tasks: int = None) -> Dataset:
    """Build dataset from built-in TASKS list (no server needed).

    This mirrors the OpenEnv dataset format for comparison.
    """
    from .tasks import TASKS

    task_list = TASKS[:max_tasks] if max_tasks else TASKS
    rows = []
    for _ in range(num_repeats):
        for i, task in enumerate(task_list):
            rows.append({
                "prompt": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": task["task"]},
                ],
                "task": task["task"],
                "task_spec": task,
                "task_index": i,
                "expected_output": task["expected_output"],
            })

    return Dataset.from_list(rows)


if __name__ == "__main__":
    ds = build_dataset()
    print(f"Dataset size: {len(ds)}")
    print(f"Columns: {ds.column_names}")
    print(f"Sample: {ds[0]['task_spec']}")
