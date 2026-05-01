"""
FastAPI application for the Jupyter Agent Environment.

The Gradio web UI is mounted at root (/). API endpoints (/health, /reset,
/step, /mcp, etc.) are registered first and take priority over Gradio routes.

Usage:
    # Development:
    E2B_API_KEY=... uv run uvicorn server.app:app --reload

    # Via uv project script:
    E2B_API_KEY=... uv run --project . server

    # Docker:
    docker run -p 8000:8000 -e E2B_API_KEY=... jupyter-agent-openenv
"""

import os

import gradio as gr

# Support both in-repo and standalone imports
try:
    from openenv.core.env_server.gradio_theme import OPENENV_GRADIO_CSS, OPENENV_GRADIO_THEME
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from openenv.core.env_server.web_interface import WebInterfaceManager
    from .jupyter_environment import JupyterEnvironment
    from .gradio_ui import jupyter_ui_builder
except ImportError:
    from openenv.core.env_server.gradio_theme import OPENENV_GRADIO_CSS, OPENENV_GRADIO_THEME
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from openenv.core.env_server.web_interface import WebInterfaceManager
    from server.jupyter_environment import JupyterEnvironment
    from server.gradio_ui import jupyter_ui_builder

# ── 1. Create the WebSocket/HTTP API server (no Gradio — we mount it ourselves)
os.environ["ENABLE_WEB_INTERFACE"] = "false"

app = create_app(
    JupyterEnvironment,
    CallToolAction,
    CallToolObservation,
    env_name="jupyter_agent_env",
    max_concurrent_envs=int(os.getenv("MAX_CONCURRENT_ENVS", "4")),
)

# ── 2. Build and mount our custom Gradio UI at /
_web_manager = WebInterfaceManager(
    JupyterEnvironment,
    CallToolAction,
    CallToolObservation,
)

_demo = jupyter_ui_builder(
    web_manager=_web_manager,
    action_fields=[],
    metadata=None,
    is_chat_env=False,
    title="Jupyter Agent",
    quick_start_md=None,
)

app = gr.mount_gradio_app(
    app,
    _demo,
    path="/",
    theme=OPENENV_GRADIO_THEME,
    css=OPENENV_GRADIO_CSS,
)


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
