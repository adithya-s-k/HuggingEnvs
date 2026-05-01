"""Tests for the Jupyter Agent GEM environment.

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
        from environments.jupyter_agent.gem.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "expected_output" in ds.column_names

    def test_tasks_list(self):
        from environments.jupyter_agent.gem.tasks import TASKS
        assert len(TASKS) == 46


@requires_e2b
class TestNativeEnv:
    """Test the native GEM Env (kept for native GEM training pipelines)."""

    def test_reset_and_step(self):
        from environments.jupyter_agent.gem.env import JupyterGemEnv
        env = JupyterGemEnv(task="Print 42", expected_output="42")
        obs, info = env.reset()
        assert "Print 42" in obs
        obs, reward, done, trunc, info = env.step("<code>print(42)</code>")
        assert "42" in obs
        assert reward > 0
        env.close()

    def test_gymnasium_api(self):
        from environments.jupyter_agent.gem.env import JupyterGemEnv
        env = JupyterGemEnv(task="Sum 1-100", expected_output="5050")
        obs, info = env.reset()
        obs, reward, terminated, truncated, info = env.step("<code>print(sum(range(1,101)))</code>")
        assert terminated is True
        assert truncated is False
        env.close()


@requires_e2b
class TestGEMAdapter:
    """Test the TRL adapter (4 proper tools, multi-turn)."""

    def test_adapter_has_4_tools(self):
        import inspect
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment()
        methods = [n for n, _ in inspect.getmembers(env, predicate=inspect.ismethod)
                   if not n.startswith("_") and n not in ("reset", "close")]
        assert sorted(methods) == [
            "add_and_execute_code_cell", "edit_and_execute_current_cell",
            "execute_shell_command", "get_notebook_state",
        ]
        env.close()

    def test_tool_signatures(self):
        import inspect
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment()
        sig = inspect.signature(env.add_and_execute_code_cell)
        assert "code" in sig.parameters
        sig2 = inspect.signature(env.execute_shell_command)
        assert "command" in sig2.parameters
        env.close()

    def test_reset_and_execute(self):
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment()
        obs = env.reset(task="Print 42")
        assert "Print 42" in obs
        result = env.add_and_execute_code_cell(code="print(42)")
        assert "42" in result
        assert env.step_count == 1
        env.close()

    def test_multi_turn(self):
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment()
        env.reset(task="Install sympy and count primes")
        env.execute_shell_command(command="pip install sympy -q")
        result = env.add_and_execute_code_cell(
            code="from sympy import isprime; print(sum(1 for n in range(900,1001) if isprime(n)))"
        )
        assert "14" in result
        assert env.step_count == 2
        env.close()

    def test_state_persists(self):
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment()
        env.reset(task="test")
        env.add_and_execute_code_cell(code="x = 42")
        result = env.add_and_execute_code_cell(code="print(x + 1)")
        assert "43" in result
        env.close()

    def test_edit_cell(self):
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment()
        env.reset(task="test")
        env.add_and_execute_code_cell(code="print('wrong')")
        result = env.edit_and_execute_current_cell(code="print('fixed')")
        assert "fixed" in result
        env.close()

    def test_factory_pattern(self):
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment(**{})
        env.reset(task="Sum 1-100")
        result = env.add_and_execute_code_cell(code="print(sum(range(1,101)))")
        assert "5050" in result
        env.close()

    def test_reward_function(self):
        from environments.adapters.gem_adapter import GEMEnvironment
        from environments.jupyter_agent.gem.reward import reward_func
        env = GEMEnvironment()
        env.reset(task="test")
        env.add_and_execute_code_cell(code="print(42)")
        rewards = reward_func(completions=[""], environments=[env], expected_output=["42"])
        assert rewards[0] > 0
        env.close()
