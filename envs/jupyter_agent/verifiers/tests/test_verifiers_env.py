"""Tests for the Jupyter Agent Verifiers environment.

Tests are split into:
1. Dataset tests — no E2B or verifiers needed
2. Toolkit tests — require E2B_API_KEY
3. Adapter tests — require E2B_API_KEY

Usage:
    # Dataset only:
    PYTHONPATH=../../.. pytest tests/ -v -k "dataset"

    # Full (needs E2B_API_KEY):
    E2B_API_KEY=... PYTHONPATH=../../.. pytest tests/ -v
"""

import os
import pytest

HAS_E2B = bool(os.getenv("E2B_API_KEY", ""))
requires_e2b = pytest.mark.skipif(not HAS_E2B, reason="E2B_API_KEY not set")


class TestDataset:
    def test_build_dataset(self):
        from environments.jupyter_agent.verifiers.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "prompt" in ds.column_names
        assert "expected_output" in ds.column_names

    def test_tasks_list(self):
        from environments.jupyter_agent.verifiers.tasks import TASKS
        assert len(TASKS) == 46


@requires_e2b
class TestToolkit:
    def test_toolkit_execute_code(self):
        from environments.jupyter_agent.verifiers.env import JupyterToolkit
        tk = JupyterToolkit()
        result = tk.add_and_execute_code_cell("print(2**20)")
        assert "1048576" in result
        assert tk.step_count == 1
        tk.cleanup()

    def test_toolkit_state_persists(self):
        from environments.jupyter_agent.verifiers.env import JupyterToolkit
        tk = JupyterToolkit()
        tk.add_and_execute_code_cell("x = 42")
        result = tk.add_and_execute_code_cell("print(x + 1)")
        assert "43" in result
        assert tk.step_count == 2
        tk.cleanup()

    def test_toolkit_shell(self):
        from environments.jupyter_agent.verifiers.env import JupyterToolkit
        tk = JupyterToolkit()
        result = tk.execute_shell_command("echo hello_verifiers")
        assert "hello_verifiers" in result
        tk.cleanup()

    def test_toolkit_reset(self):
        from environments.jupyter_agent.verifiers.env import JupyterToolkit
        tk = JupyterToolkit()
        tk.add_and_execute_code_cell("x = 1")
        tk.reset()
        assert tk.step_count == 0
        assert tk.last_output == ""
        tk.cleanup()


@requires_e2b
class TestVerifiersAdapter:
    def test_adapter_init(self):
        import inspect
        from environments.adapters.verifiers_adapter import VerifiersEnvironment
        env = VerifiersEnvironment()
        methods = [n for n, _ in inspect.getmembers(env, predicate=inspect.ismethod)
                   if not n.startswith("_") and n not in ("reset", "close")]
        assert sorted(methods) == [
            "add_and_execute_code_cell", "edit_and_execute_current_cell",
            "execute_shell_command", "get_notebook_state",
        ]
        env.close()

    def test_adapter_reset_and_execute(self):
        from environments.adapters.verifiers_adapter import VerifiersEnvironment
        env = VerifiersEnvironment()
        obs = env.reset(task="Print 42")
        assert "Print 42" in obs
        result = env.add_and_execute_code_cell(code="print(42)")
        assert "42" in result
        assert env.step_count == 1
        env.close()

    def test_adapter_as_factory(self):
        from environments.adapters.verifiers_adapter import VerifiersEnvironment
        config = {}  # E2B_API_KEY from env var
        env = VerifiersEnvironment(**config)
        env.reset(task="Sum 1 to 100")
        result = env.add_and_execute_code_cell(code="print(sum(range(1,101)))")
        assert "5050" in result
        env.close()

    def test_adapter_reward_function(self):
        from environments.adapters.verifiers_adapter import VerifiersEnvironment
        from environments.jupyter_agent.verifiers.reward import reward_func
        env = VerifiersEnvironment()
        env.reset(task="test")
        env.add_and_execute_code_cell(code="print(42)")
        rewards = reward_func(
            completions=[""],
            environments=[env],
            expected_output=["42"],
        )
        assert rewards[0] > 0
        env.close()
