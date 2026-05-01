"""
Dataset builder for Jupyter Agent NeMo Gym training.

NeMo Gym uses JSONL format with responses_create_params containing
input messages and tool definitions in OpenAI Responses API format.
"""

import json
from pathlib import Path

from datasets import Dataset

try:
    from .tasks import TASKS
except ImportError:
    from tasks import TASKS

SYSTEM_PROMPT = """You are an intelligent data science assistant operating inside a stateful Jupyter notebook environment.
Your goal is to solve analytical and computational tasks through careful, iterative code execution.
Always execute code to verify — never guess at results. Use the available tools to write and run Python code."""

# Tool definitions in OpenAI function calling format (NeMo Gym standard)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "add_and_execute_code_cell",
        "description": "Execute Python code in the stateful Jupyter notebook. Variables persist between calls.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python code to execute"}},
            "required": ["code"],
        },
    },
    {
        "type": "function",
        "name": "edit_and_execute_current_cell",
        "description": "Replace the last code cell with new code and re-execute. Use to fix errors.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Replacement Python code"}},
            "required": ["code"],
        },
    },
    {
        "type": "function",
        "name": "execute_shell_command",
        "description": "Run a shell command inside the sandbox. Use for pip install, ls, etc.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Shell command to execute"}},
            "required": ["command"],
        },
    },
    {
        "type": "function",
        "name": "get_notebook_state",
        "description": "Return a compact summary of all executed cells and their outputs.",
        "parameters": {
            "type": "object",
            "properties": {
                "include_images": {"type": "boolean", "description": "Include base64 images", "default": False}
            },
        },
    },
]


def build_dataset(num_repeats: int = 4, max_tasks: int = None) -> Dataset:
    """Build HF Dataset from TASKS in NeMo Gym format."""
    task_list = TASKS[:max_tasks] if max_tasks else TASKS

    rows = []
    for _ in range(num_repeats):
        for i, task in enumerate(task_list):
            # NeMo Gym JSONL format
            metadata = {
                "responses_create_params": {
                    "input": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": task["task"]},
                    ],
                    "tools": TOOL_DEFINITIONS,
                    "parallel_tool_calls": False,
                    "temperature": 1.0,
                },
                "ground_truth": [{"expected_output": task["expected_output"]}],
                "environment_name": "jupyter_agent",
            }

            rows.append({
                "prompt": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": task["task"]},
                ],
                "task": task["task"],
                "expected_output": task["expected_output"],
                "task_index": i,
                "metadata": json.dumps(metadata),  # NeMo Gym stores as JSON string
            })

    return Dataset.from_list(rows)


def export_jsonl(output_path: str = "data/train.jsonl", max_tasks: int = None):
    """Export tasks as NeMo Gym JSONL file."""
    task_list = TASKS[:max_tasks] if max_tasks else TASKS
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for task in task_list:
            item = {
                "responses_create_params": {
                    "input": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": task["task"]},
                    ],
                    "tools": TOOL_DEFINITIONS,
                    "parallel_tool_calls": False,
                    "temperature": 1.0,
                },
                "ground_truth": [{"expected_output": task["expected_output"]}],
                "environment_name": "jupyter_agent",
            }
            f.write(json.dumps(item) + "\n")

    print(f"Exported {len(task_list)} tasks to {output_path}")


if __name__ == "__main__":
    ds = build_dataset(num_repeats=1, max_tasks=3)
    print(f"Dataset: {len(ds)} rows, columns: {ds.column_names}")
    export_jsonl("data/train.jsonl")
