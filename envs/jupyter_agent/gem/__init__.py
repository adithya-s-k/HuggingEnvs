"""Jupyter Agent — GEM (General Experience Maker) implementation.

In-process Gymnasium-style environment following the GEM Env API.
Subclasses gem.Env with reset()/step() for Jupyter notebook interaction.

Usage:
    cd gem && uv venv && uv sync
    .venv/bin/python -c "from env import JupyterGemEnv; print('OK')"
"""
