"""Jupyter Agent — SkyRL Gym implementation.

In-process Gymnasium-style environment: BaseTextEnv with step(action) → reward.
No server needed — runs directly in the training process.

Usage:
    cd skyrl_gym && uv venv && uv sync
    .venv/bin/python -c "from env import JupyterTextEnv; print('OK')"
"""
