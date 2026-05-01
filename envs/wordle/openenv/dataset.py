"""Dataset for Wordle OpenEnv training."""
import sys
from pathlib import Path
from datasets import Dataset

_parent = str(Path(__file__).resolve().parents[1])
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from game import TASKS

SYSTEM_PROMPT = """You are playing Wordle. Guess the hidden 5-letter word in 6 attempts.
Use the guess tool to submit each attempt. Use get_history to review past guesses."""


def build_dataset(num_repeats=4, max_tasks=None):
    task_list = TASKS[:max_tasks] if max_tasks else TASKS
    rows = []
    for _ in range(num_repeats):
        for i, task in enumerate(task_list):
            rows.append({
                "prompt": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": task["task"]}],
                "task": task["task"],
                "answer": task["answer"],
                "task_index": i,
            })
    return Dataset.from_list(rows)
