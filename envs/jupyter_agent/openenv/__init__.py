"""
Jupyter Agent OpenEnv. E2B-powered stateful notebook environment.

This package contains the server-side env definition under `server/`.

To consume the deployed environment, point the generic openenv-core MCP client
at the HF Space (no env-specific install required):

    from openenv.core.mcp_client import MCPToolClient
    with MCPToolClient(base_url="https://AdithyaSK-jupyter-agent-openenv.hf.space").sync() as env:
        env.reset()
        env.call_tool("add_and_execute_code_cell", code="print(2 ** 10)")
"""

