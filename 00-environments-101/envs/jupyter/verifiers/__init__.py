"""Jupyter Agent — PrimeIntellect Verifiers implementation.

In-process environment: tools are Python functions, rewards via rubric scoring.
No server needed — runs directly in the training process.

Usage:
    cd verifiers && uv venv && uv sync
    .venv/bin/python -c "from env import create_jupyter_tool_env; print('OK')"
"""
