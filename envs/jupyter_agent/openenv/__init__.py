"""
Jupyter Agent OpenEnv — E2B-powered stateful notebook environment.

Example:
    >>> from jupyter_agent_env import JupyterAgentEnv
    >>>
    >>> with JupyterAgentEnv(base_url="http://localhost:8000") as env:
    ...     env.reset()
    ...     tools = env.list_tools()
    ...     print([t.name for t in tools])
    ...     result = env.call_tool("add_and_execute_code_cell", code="print(2 ** 10)")
    ...     print(result)  # "1024"
"""

def __getattr__(name):
    """Lazy imports — only resolve when accessed, so dataset.py/reward.py work without openenv installed."""
    if name == "CallToolAction":
        from openenv.core.env_server.mcp_types import CallToolAction
        return CallToolAction
    if name == "ListToolsAction":
        from openenv.core.env_server.mcp_types import ListToolsAction
        return ListToolsAction
    if name == "JupyterAgentEnv":
        from .client import JupyterAgentEnv
        return JupyterAgentEnv
    if name == "JupyterState":
        from .models import JupyterState
        return JupyterState
    if name == "NotebookCell":
        from .models import NotebookCell
        return NotebookCell
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "JupyterAgentEnv",
    "JupyterState",
    "NotebookCell",
    "CallToolAction",
    "ListToolsAction",
]
