"""Pydantic models for Desktop environment state."""

from typing import List, Optional

from openenv.core.env_server.types import State
from pydantic import BaseModel, Field


class ScreenAction(BaseModel):
    """A recorded screen action."""
    action_type: str  # "click", "type", "press", "scroll", "screenshot", "command"
    detail: str       # human-readable description
    step: int


class DesktopState(State):
    """Extended state tracking desktop interactions."""
    app: Optional[str] = None
    sandbox_id: Optional[str] = None
    stream_url: Optional[str] = None
    screen_width: int = 1920
    screen_height: int = 1080
    actions: List[ScreenAction] = Field(default_factory=list)
    last_screenshot_b64: Optional[str] = None
