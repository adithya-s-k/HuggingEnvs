"""
FastAPI application for the Desktop Computer-Use Environment.

Usage:
    # Development:
    E2B_API_KEY=... uvicorn server.app:app --reload --port 8000

    # Docker:
    docker build -t desktop-openenv .
    docker run -p 8000:8000 --env-file .env desktop-openenv
"""

import os

try:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from .desktop_environment import DesktopEnvironment
    from .gradio_ui import desktop_ui_builder
except ImportError:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from server.desktop_environment import DesktopEnvironment
    from server.gradio_ui import desktop_ui_builder


def _custom_gradio_builder(web_manager, action_fields, metadata, is_chat_env, title, quick_start_md):
    """Custom Gradio builder that replaces the default OpenEnv UI."""
    return desktop_ui_builder(env_factory=DesktopEnvironment)


# Enable web interface with our custom Gradio builder
os.environ["ENABLE_WEB_INTERFACE"] = "true"

app = create_app(
    DesktopEnvironment,
    CallToolAction,
    CallToolObservation,
    env_name="desktop_env",
    max_concurrent_envs=int(os.getenv("MAX_CONCURRENT_ENVS", "4")),
    gradio_builder=_custom_gradio_builder,
)


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
