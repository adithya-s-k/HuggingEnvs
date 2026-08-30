"""Pydantic models for Jupyter Agent environment state."""

from typing import Any, Dict, List, Optional

from openenv.core.env_server.types import State
from pydantic import BaseModel, Field


class NotebookCell(BaseModel):
    """Represents a single executed cell in the notebook."""

    cell_id: str
    cell_type: str  # "code" | "shell"
    code: str
    output: str  # plain text for LLM
    error: Optional[str] = None  # traceback string if failed
    execution_count: int
    has_image: bool = False  # True if result includes PNG
    images: List[str] = Field(default_factory=list)  # base64-encoded PNG strings
    success: bool = True


class JupyterState(State):
    """Extended state tracking notebook cells and sandbox info."""

    cells: List[NotebookCell] = Field(default_factory=list)
    sandbox_id: Optional[str] = None
    last_cell_success: bool = True
