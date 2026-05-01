"""Tests for the Jupyter Agent OpenEnv client and adapter.

These tests require a running OpenEnv server. By default they hit the
HF Space deployment. Set JUPYTER_ENV_URL to override.

Usage:
    pytest tests/ -v
    JUPYTER_ENV_URL=http://localhost:8000 pytest tests/ -v
"""

import os
import pytest

ENV_URL = os.getenv("JUPYTER_ENV_URL", "https://AdithyaSK-jupyter-agent-openenv.hf.space")


@pytest.fixture
def client():
    """Create a sync client connected to the OpenEnv server."""
    from jupyter_agent_env import JupyterAgentEnv

    env = JupyterAgentEnv(base_url=ENV_URL).sync()
    env.__enter__()
    yield env
    env.__exit__(None, None, None)


class TestOpenEnvClient:
    """Test the raw OpenEnv client (MCP protocol)."""

    def test_reset(self, client):
        """Server should accept reset and return without error."""
        client.reset()

    def test_list_tools(self, client):
        """Server should expose the expected tool set."""
        client.reset()
        tools = client.list_tools()
        tool_names = sorted([t.name for t in tools])
        assert tool_names == [
            "add_and_execute_code_cell",
            "edit_and_execute_current_cell",
            "execute_shell_command",
            "final_answer",
            "get_notebook_state",
        ]

    def test_execute_code(self, client):
        """Execute simple Python code and verify output."""
        client.reset()
        result = client.call_tool("add_and_execute_code_cell", code="print(2 ** 10)")
        text = _extract_text(result)
        assert "1024" in text

    def test_execute_shell(self, client):
        """Execute a shell command and verify output."""
        client.reset()
        result = client.call_tool("execute_shell_command", command="echo hello")
        text = _extract_text(result)
        assert "hello" in text

    def test_get_notebook_state(self, client):
        """Get notebook state after executing code."""
        client.reset()
        client.call_tool("add_and_execute_code_cell", code="x = 42")
        result = client.call_tool("get_notebook_state")
        text = _extract_text(result)
        assert "42" in text or "x" in text

    def test_state_persists_across_cells(self, client):
        """Variables should persist between code cell executions."""
        client.reset()
        client.call_tool("add_and_execute_code_cell", code="my_var = 123")
        result = client.call_tool("add_and_execute_code_cell", code="print(my_var + 1)")
        text = _extract_text(result)
        assert "124" in text

    def test_edit_cell(self, client):
        """Edit and re-execute the last cell."""
        client.reset()
        client.call_tool("add_and_execute_code_cell", code="print('first')")
        result = client.call_tool("edit_and_execute_current_cell", code="print('second')")
        text = _extract_text(result)
        assert "second" in text


class TestTRLAdapter:
    """Test the TRL environment_factory adapter."""

    def test_adapter_reset(self):
        """Adapter reset should return observation string."""
        import environments.adapters.openenv_adapter as mod
        mod.ENV_URL = ENV_URL

        from environments.adapters.openenv_adapter import JupyterToolEnv

        env = JupyterToolEnv()
        obs = env.reset(task="Print 42")
        assert obs is not None
        assert "Print 42" in obs

    def test_adapter_tool_call(self):
        """Adapter should execute tools and track state."""
        import environments.adapters.openenv_adapter as mod
        mod.ENV_URL = ENV_URL

        from environments.adapters.openenv_adapter import JupyterToolEnv

        env = JupyterToolEnv()
        env.reset(task="test")
        result = env.add_and_execute_code_cell(code="print(7 * 6)")
        assert "42" in result
        assert env.step_count == 1
        assert env.last_output == result

    def test_adapter_has_correct_tools(self):
        """Adapter should expose exactly the right public methods as tools."""
        import environments.adapters.openenv_adapter as mod
        mod.ENV_URL = ENV_URL

        from environments.adapters.openenv_adapter import JupyterToolEnv
        import inspect

        env = JupyterToolEnv()
        # `reset` is the env entrypoint and `close` is a lifecycle method
        # (called via atexit cleanup in GRPOTrainer) — neither is a tool.
        non_tool_methods = {"reset", "close"}
        public_methods = [
            name for name, _ in inspect.getmembers(env, predicate=inspect.ismethod)
            if not name.startswith("_") and name not in non_tool_methods
        ]
        assert sorted(public_methods) == [
            "add_and_execute_code_cell",
            "edit_and_execute_current_cell",
            "execute_shell_command",
            "final_answer",
            "get_notebook_state",
        ]


def _extract_text(result) -> str:
    """Extract text from MCP tool result."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list) and content:
            return content[0].get("text", str(result))
        return str(result.get("result", result))
    return str(result)
