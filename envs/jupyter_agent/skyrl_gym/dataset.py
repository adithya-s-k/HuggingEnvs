"""Dataset builder for Jupyter Agent SkyRL Gym training."""

from datasets import Dataset

try:
    from .tasks import TASKS
except ImportError:
    from tasks import TASKS

SYSTEM_PROMPT = """You are an intelligent data science assistant operating inside a stateful Jupyter notebook environment.
Execute code using <code>...</code> tags, shell commands using <shell>...</shell> tags.
Always execute code to verify — never guess at results."""


def build_dataset(num_repeats: int = 4, max_tasks: int = None) -> Dataset:
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
                "expected_output": task["expected_output"],
                "task_index": i,
            })
    return Dataset.from_list(rows)
