"""Tests for the Jupyter Agent ORS environment.

Tests are split into:
1. Server tests — require a running ORS server (set ORS_SERVER_URL)
2. Adapter tests — require a running ORS server
3. Dataset tests — no server needed (uses built-in TASKS)

Usage:
    # Test dataset (no server needed):
    pytest tests/test_ors_env.py -v -k "dataset"

    # Test with running server:
    ORS_SERVER_URL=http://localhost:8080 pytest tests/test_ors_env.py -v

    # Test all (start server first):
    python -m server --port 8080 &
    ORS_SERVER_URL=http://localhost:8080 pytest tests/test_ors_env.py -v
"""

import os
import pytest

ORS_SERVER_URL = os.getenv("ORS_SERVER_URL", "")
requires_server = pytest.mark.skipif(
    not ORS_SERVER_URL,
    reason="ORS_SERVER_URL not set — start server and set env var to run these tests"
)


class TestDataset:
    """Test dataset building (no server needed)."""

    def test_build_dataset(self):
        from environments.jupyter_agent.ors.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "prompt" in ds.column_names
        assert "task_spec" in ds.column_names
        assert "expected_output" in ds.column_names

    def test_dataset_has_correct_format(self):
        from environments.jupyter_agent.ors.dataset import build_dataset
        ds = build_dataset(num_repeats=2, max_tasks=2)
        assert len(ds) == 4  # 2 tasks * 2 repeats
        row = ds[0]
        assert isinstance(row["prompt"], list)
        assert row["prompt"][0]["role"] == "system"
        assert isinstance(row["task_spec"], dict)
        assert "task" in row["task_spec"]
        assert "expected_output" in row["task_spec"]

    def test_tasks_list(self):
        from environments.jupyter_agent.ors.tasks import TASKS
        assert len(TASKS) == 46
        for task in TASKS:
            assert "task" in task
            assert "expected_output" in task


@requires_server
class TestORSServer:
    """Test the ORS server (requires running server)."""

    def test_health(self):
        import requests
        resp = requests.get(f"{ORS_SERVER_URL}/health")
        assert resp.status_code == 200

    def test_list_environments(self):
        import requests
        resp = requests.get(f"{ORS_SERVER_URL}/list_environments")
        assert resp.status_code == 200
        envs = resp.json()
        assert len(envs) >= 1
        assert "jupyteragentors" in envs

    def test_list_tools(self):
        """Server should expose tools via /tools endpoint."""
        import requests
        resp = requests.get(f"{ORS_SERVER_URL}/tools", allow_redirects=True)
        assert resp.status_code == 200
        data = resp.json()
        tools = data.get("tools", data)
        tool_names = sorted([t["name"] for t in tools])
        assert "add_and_execute_code_cell" in tool_names
        assert "execute_shell_command" in tool_names

    def test_get_prompt(self):
        """Adapter should get prompt from server."""
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        obs = env.reset(task_index=0)
        assert obs is not None
        assert "Solve" in obs
        env.close()

    def test_call_tool_with_reward(self):
        """Execute code and verify reward is returned via adapter."""
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        env.reset(task_index=13)  # 2^20 = 1048576
        result = env.add_and_execute_code_cell(code="print(2**20)")
        assert "1048576" in result
        assert env.reward > 0
        assert env.finished is True
        env.close()

    def test_shell_command(self):
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        env.reset(task_index=0)
        result = env.execute_shell_command(command="echo hello")
        assert "hello" in result
        env.close()


@requires_server
class TestORSAdapter:
    """Test the TRL adapter (requires running server)."""

    def test_adapter_init(self):
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        assert hasattr(env, "reset")
        assert hasattr(env, "close")
        assert hasattr(env, "reward")
        env.close()

    def test_adapter_discovers_tools(self):
        import inspect
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        methods = [
            name for name, _ in inspect.getmembers(env, predicate=inspect.ismethod)
            if not name.startswith("_") and name != "reset" and name != "close"
        ]
        assert "add_and_execute_code_cell" in methods
        assert "execute_shell_command" in methods
        env.close()

    def test_adapter_reset_and_tool_call(self):
        from environments.adapters.ors_adapter import ORSEnvironment
        env = ORSEnvironment(base_url=ORS_SERVER_URL)
        # Task index 14: "Calculate factorial of 10" → "3628800"
        obs = env.reset(task_index=14)
        assert obs is not None
        assert "factorial" in obs.lower() or "10" in obs

        result = env.add_and_execute_code_cell(code="import math; print(math.factorial(10))")
        assert "3628800" in result
        assert env.reward > 0
        assert env.finished is True
        assert env.step_count == 1
        env.close()

    def test_adapter_as_environment_factory(self):
        """Test that the adapter works as TRL environment_factory."""
        from environments.adapters.ors_adapter import ORSEnvironment
        # Simulate what TRL does: call class with **config
        config = {"base_url": ORS_SERVER_URL}
        env = ORSEnvironment(**config)
        obs = env.reset(task_index=15)  # "Sum of 1 to 100" → "5050"
        assert obs is not None
        result = env.add_and_execute_code_cell(code="print(sum(range(1, 101)))")
        assert "5050" in result
        assert env.reward > 0
        env.close()
