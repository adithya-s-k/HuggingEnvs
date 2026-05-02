"""
FastAPI application for the Wordle Environment.

Usage:
    E2B_API_KEY=... uv run uvicorn server.app:app --reload
    docker run -p 8000:8000 wordle-openenv
"""

import os

from openenv.core.env_server.http_server import create_app
from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation

from .wordle_environment import WordleEnvironment

os.environ["ENABLE_WEB_INTERFACE"] = "false"

app = create_app(
    WordleEnvironment,
    CallToolAction,
    CallToolObservation,
    env_name="wordle_env",
    max_concurrent_envs=int(os.getenv("MAX_CONCURRENT_ENVS", "4")),
)


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
