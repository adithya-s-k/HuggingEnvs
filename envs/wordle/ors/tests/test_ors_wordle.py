"""
Tests for Wordle ORS environment.

Tests are split into:
1. Dataset tests — no server needed
2. Server tests — require a running ORS server (set ORS_SERVER_URL)
3. Adapter tests — require a running ORS server

Usage:
    # Dataset only (no server):
    PYTHONPATH=. pytest environments/wordle/ors/tests/ -v -k "dataset"

    # With running server:
    ORS_SERVER_URL=http://localhost:8080 pytest environments/wordle/ors/tests/ -v
"""

import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

ORS_SERVER_URL = os.getenv("ORS_SERVER_URL", "")
requires_server = pytest.mark.skipif(
    not ORS_SERVER_URL,
    reason="ORS_SERVER_URL not set — start server to run these tests"
)


class TestDataset:
    """Test dataset building (no server needed)."""

    def test_build_dataset(self):
        from environments.wordle.ors.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "prompt" in ds.column_names
        assert "task_spec" in ds.column_names
        assert "answer" in ds.column_names

    def test_dataset_has_correct_format(self):
        from environments.wordle.ors.dataset import build_dataset
        ds = build_dataset(num_repeats=2, max_tasks=2)
        assert len(ds) == 4  # 2 tasks * 2 repeats
        row = ds[0]
        assert isinstance(row["prompt"], list)
        assert row["prompt"][0]["role"] == "system"
        assert isinstance(row["task_spec"], dict)
        assert "answer" in row["task_spec"]

    def test_tasks_list(self):
        from environments.wordle.game import TASKS
        assert len(TASKS) == 50
        for task in TASKS:
            assert "task" in task
            assert "answer" in task
            assert len(task["answer"]) == 5


@requires_server
class TestORSServer:
    """Test the ORS server (requires running server)."""

    def test_health(self):
        import requests
        resp = requests.get(f"{ORS_SERVER_URL}/health")
        assert resp.status_code == 200

    def test_list_tools(self):
        import requests
        resp = requests.get(f"{ORS_SERVER_URL}/tools", allow_redirects=True)
        assert resp.status_code == 200
        data = resp.json()
        tools = data.get("tools", data)
        tool_names = sorted([t["name"] for t in tools])
        assert "guess" in tool_names
        assert "get_history" in tool_names


@requires_server
class TestORSAdapter:
    """Test the TRL adapter (requires running server)."""

    def test_adapter_init(self):
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        assert hasattr(env, "reset")
        assert hasattr(env, "close")
        env.close()

    def test_adapter_discovers_tools(self):
        import inspect
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        methods = [
            name for name, _ in inspect.getmembers(env, predicate=inspect.ismethod)
            if not name.startswith("_") and name != "reset" and name != "close"
        ]
        assert "guess" in methods
        assert "get_history" in methods
        env.close()

    def test_adapter_play_game(self):
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        env.reset(task_index=0)
        result = env.guess(word="apple")
        assert isinstance(result, str)
        assert len(result) > 0
        env.close()
