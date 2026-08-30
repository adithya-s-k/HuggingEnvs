"""
Desktop Computer-Use Environment Client.

Connects to a running desktop-openenv server and exposes
desktop interaction tools via the MCP tool-calling interface.

Example:
    >>> with DesktopEnv(base_url="http://localhost:8000") as env:
    ...     obs = env.reset(app="libreoffice-calc")
    ...     print("Stream:", obs["metadata"]["stream_url"])
    ...
    ...     # Discover tools
    ...     tools = env.list_tools()
    ...     print([t.name for t in tools])
    ...     # ['screenshot', 'click', 'double_click', 'right_click',
    ...     #  'type_text', 'press_key', 'scroll', 'drag',
    ...     #  'run_command', 'get_cursor_position', 'get_screen_size']
    ...
    ...     # Take screenshot
    ...     img_b64 = env.call_tool("screenshot")
    ...
    ...     # Click on something
    ...     env.call_tool("click", x=500, y=300)
    ...
    ...     # Type text
    ...     env.call_tool("type_text", text="Hello world")
    ...
    ...     # Press key combo
    ...     env.call_tool("press_key", key="ctrl+s")
"""

from openenv.core.mcp_client import MCPToolClient


class DesktopEnv(MCPToolClient):
    """
    Client for the Desktop Computer-Use environment.

    Inherits all MCP tool-calling functionality from MCPToolClient:
    - ``list_tools()``              — discover available desktop tools
    - ``call_tool(name, **kwargs)`` — call a tool by name
    - ``reset(**kwargs)``           — start new episode with chosen app
    - ``step(action)``              — low-level action execution

    Reset kwargs:
    - ``app``: Preset name ("libreoffice-calc", "firefox", "blender", etc.)
               or a raw shell command to launch.
    - ``resolution``: Tuple (width, height). Default (1920, 1080).
    - ``timeout``: Sandbox timeout in seconds. Default 600.
    - ``install_commands``: List of shell commands to run before launch.

    Available tools (exposed by server):
    - ``screenshot()``                          — capture screen as base64 PNG
    - ``click(x, y)``                           — left click
    - ``double_click(x, y)``                    — double click
    - ``right_click(x, y)``                     — right click
    - ``type_text(text)``                       — type at cursor
    - ``press_key(key)``                        — press key/combo ("enter", "ctrl+s")
    - ``scroll(direction, amount)``             — scroll up/down
    - ``drag(start_x, start_y, end_x, end_y)`` — drag mouse
    - ``run_command(command)``                  — shell command
    - ``get_cursor_position()``                 — current mouse position
    - ``get_screen_size()``                     — screen dimensions
    """

    pass
