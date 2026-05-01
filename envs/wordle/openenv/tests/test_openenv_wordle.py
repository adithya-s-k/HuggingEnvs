"""
Tests for Wordle OpenEnv environment.

Tests are split into:
1. Dataset tests — no server needed
2. Server tests — require running OpenEnv server (set OPENENV_URL)

Usage:
    # Dataset only:
    PYTHONPATH=. pytest environments/wordle/openenv/tests/ -v -k "dataset"

    # With server:
    OPENENV_URL=http://localhost:8002 pytest environments/wordle/openenv/tests/ -v
"""

import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

OPENENV_URL = os.getenv("OPENENV_URL", "")
requires_server = pytest.mark.skipif(
    not OPENENV_URL,
    reason="OPENENV_URL not set — start server to run these tests"
)


class TestDataset:
    """Test dataset building (no server needed)."""

    def test_build_dataset(self):
        from environments.wordle.openenv.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "prompt" in ds.column_names
        assert "answer" in ds.column_names

    def test_dataset_has_correct_format(self):
        from environments.wordle.openenv.dataset import build_dataset
        ds = build_dataset(num_repeats=2, max_tasks=2)
        assert len(ds) == 4
        row = ds[0]
        assert isinstance(row["prompt"], list)
        assert row["prompt"][0]["role"] == "system"
        assert len(row["answer"]) == 5


@requires_server
class TestOpenEnvServer:
    """Test the OpenEnv server (requires running server)."""

    def test_server_responds(self):
        import requests
        resp = requests.get(f"{OPENENV_URL}/health")
        assert resp.status_code == 200
