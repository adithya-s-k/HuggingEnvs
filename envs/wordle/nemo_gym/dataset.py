"""Dataset for Wordle NeMo Gym training."""

import json
import sys
from pathlib import Path
from datasets import Dataset

_parent = str(Path(__file__).resolve().parents[1])
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from game import TASKS

SYSTEM_PROMPT = """You are playing Wordle. Guess the hidden 5-letter word in 6 attempts.
After each guess, you'll see feedback:
  🟩 = correct letter, correct position
  🟨 = correct letter, wrong position
  ⬛ = letter not in the word
Use the guess tool to submit each attempt. Use get_history to review past guesses."""

# NeMo Gym tool definitions for the dataset metadata
NEMO_GYM_TOOLS = [
    {
        "type": "function",
        "name": "guess",
        "description": "Submit a 5-letter word guess to the Wordle game.",
        "parameters": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "A 5-letter English word guess.",
                }
            },
            "required": ["word"],
        },
    },
    {
        "type": "function",
        "name": "get_history",
        "description": "View all previous guesses and their feedback.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def build_dataset(num_repeats: int = 4, max_tasks: int = None) -> Dataset:
    task_list = TASKS[:max_tasks] if max_tasks else TASKS
    rows = []
    for _ in range(num_repeats):
        for i, task in enumerate(task_list):
            metadata = json.dumps({
                "responses_create_params": {
                    "input": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": task["task"]},
                    ],
                    "tools": NEMO_GYM_TOOLS,
                },
                "ground_truth": [{"answer": task["answer"]}],
            })
            rows.append({
                "prompt": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": task["task"]},
                ],
                "task": task["task"],
                "answer": task["answer"],
                "metadata": metadata,
                "task_index": i,
            })
    return Dataset.from_list(rows)
