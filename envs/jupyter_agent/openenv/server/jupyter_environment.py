"""
Jupyter Agent MCP Environment.

Exposes 4 notebook interaction tools via FastMCP:
  1. add_and_execute_code_cell    — primary execution tool
  2. edit_and_execute_current_cell — error-recovery (replace last cell)
  3. execute_shell_command         — shell access inside sandbox
  4. get_notebook_state            — compact history for agent memory

Each episode (reset → step* → [reset]) maps to exactly one E2B sandbox,
giving clean variable scope boundaries for RL training loops.
"""

import logging
import os
from typing import Any, Optional
from uuid import uuid4

log = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastmcp import FastMCP
from openenv.core.env_server.mcp_environment import MCPEnvironment
from openenv.core.env_server.types import Action, Observation

from .e2b_sandbox import E2BSandbox
from .notebook_tracker import NotebookTracker

load_dotenv()


class JupyterEnvironment(MCPEnvironment):
    """
    Stateful Jupyter notebook environment backed by an E2B Code Interpreter sandbox.

    Inherits from MCPEnvironment which auto-routes ListToolsAction and
    CallToolAction to the registered FastMCP tools. Only non-MCP actions fall
    through to ``_step_impl``.

    Concurrent sessions: each WebSocket connection gets its own instance
    (``SUPPORTS_CONCURRENT_SESSIONS = True``), so each agent has an isolated
    sandbox.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._api_key = os.environ["E2B_API_KEY"]
        self._sandbox: Optional[E2BSandbox] = None
        self._tracker = NotebookTracker()

        # Import here to avoid circular imports at module load time
        # Support both package and flat-layout execution
        try:
            from ..models import JupyterState, NotebookCell
        except ImportError:
            from models import JupyterState, NotebookCell

        self._JupyterState = JupyterState
        self._NotebookCell = NotebookCell
        self._state = JupyterState(episode_id=str(uuid4()))
        self._submitted_answer = None

        # ── Register MCP tools ──────────────────────────────────────────────
        mcp = FastMCP("jupyter_agent_env")

        @mcp.tool
        def add_and_execute_code_cell(code: str) -> str:
            """
            Execute Python code in the stateful Jupyter notebook.

            Variables, imports, and side-effects persist between calls within
            the same episode. Use this as the primary tool for all computation.

            Args:
                code: Python code to execute. Can span multiple lines.

            Returns:
                Stdout, expression results, and a note if images were generated.
                On error, returns the full traceback.
            """
            if not self._sandbox:
                return "Error: environment not reset. Call reset() first."
            result = self._sandbox.run_code(code)
            cell = self._tracker.add_code_cell(code, result)
            self._state.cells.append(self._NotebookCell(**_cell_to_model_kwargs(cell)))
            self._state.last_cell_success = result.success
            self._state.step_count += 1
            return _format_for_llm(result)

        @mcp.tool
        def edit_and_execute_current_cell(code: str) -> str:
            """
            Replace the last code cell with new code and re-execute it.

            Use this to fix errors in the previous cell instead of creating a
            new cell. This keeps the notebook clean.

            Args:
                code: Replacement Python code for the current cell.

            Returns:
                Same format as add_and_execute_code_cell.
            """
            if not self._sandbox:
                return "Error: environment not reset. Call reset() first."
            result = self._sandbox.run_code(code)
            cell = self._tracker.update_last_code_cell(code, result)
            if self._state.cells:
                self._state.cells.pop()
            self._state.cells.append(self._NotebookCell(**_cell_to_model_kwargs(cell)))
            self._state.last_cell_success = result.success
            self._state.step_count += 1
            return _format_for_llm(result)

        @mcp.tool
        def execute_shell_command(command: str) -> str:
            """
            Run a shell command inside the sandbox.

            Useful for package installation, file system inspection, or
            running scripts. Examples: "pip install polars", "ls -la", "cat data.csv".

            Args:
                command: Shell command string to execute.

            Returns:
                Combined stdout and stderr. On error, includes traceback.
            """
            if not self._sandbox:
                return "Error: environment not reset."
            result = self._sandbox.run_shell(command)
            cell = self._tracker.add_shell_cell(command, result)
            self._state.cells.append(self._NotebookCell(**_cell_to_model_kwargs(cell)))
            self._state.step_count += 1
            return _format_for_llm(result)

        @mcp.tool
        def get_notebook_state(include_images: bool = False) -> str:
            """
            Return a compact summary of all executed cells and their outputs.

            Useful at the start of a task (to check what has already been done)
            or when context about previous computations is needed.

            Args:
                include_images: If True, include base64-encoded PNG image data
                    inline (for multimodal models). If False (default), only
                    note that images were generated (for text-only models).

            Returns:
                Text summary of the last 10 cells with truncated outputs.
            """
            return self._tracker.get_state_summary(include_images=include_images)

        @mcp.tool
        def final_answer(answer: str) -> str:
            """
            Submit your final answer to the question.

            Call this when you have computed the answer and are ready to submit.
            This ends the current task.

            Args:
                answer: Your final answer as a string.

            Returns:
                Confirmation that the answer was submitted.
            """
            self._submitted_answer = answer
            self._state.step_count += 1
            return f"Answer submitted: {answer}"

        super().__init__(mcp)

    # ── OpenEnv lifecycle ───────────────────────────────────────────────────

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Observation:
        """
        Start a new episode.

        Kills any existing E2B sandbox and creates a fresh one.
        If kaggle_dataset_name and files are provided, loads CSV files
        into /home/user/input/ in the sandbox.
        """
        if self._sandbox:
            self._sandbox.kill()

        self._sandbox = E2BSandbox(api_key=self._api_key)
        self._tracker.reset()
        self._submitted_answer = None
        self._state = self._JupyterState(
            episode_id=episode_id or str(uuid4()),
            sandbox_id=self._sandbox.sandbox_id,
            step_count=0,
        )

        # Load Kaggle files into sandbox if provided
        kaggle_name = kwargs.get("kaggle_dataset_name", "")
        files = kwargs.get("files", [])
        files_loaded = []
        if kaggle_name and files:
            kaggle_data_dir = os.environ.get("KAGGLE_DATA_DIR", f"/fsx/{os.environ.get('USER', '')}/data/kaggle-data-10000")
            from pathlib import Path
            data_dir = Path(kaggle_data_dir) / kaggle_name
            if data_dir.exists():
                # Ensure /home/user/input/ exists
                self._sandbox.run_shell("mkdir -p /home/user/input")
                for filename in files:
                    candidates = list(data_dir.rglob(filename))
                    if not candidates:
                        candidates = [f for f in data_dir.rglob("*") if f.name.lower() == filename.lower()]
                    if candidates:
                        try:
                            with open(candidates[0], "rb") as f:
                                self._sandbox._sandbox.files.write(f"/home/user/input/{filename}", f)
                            files_loaded.append(filename)
                        except Exception as e:
                            log.warning(f"Failed to upload {filename}: {e}")

        msg = "Jupyter environment ready. Use add_and_execute_code_cell to start."
        if files_loaded:
            msg += f" Files loaded: {', '.join(files_loaded)}"

        return Observation(
            done=False,
            reward=None,
            metadata={
                "status": "ready",
                "sandbox_id": self._state.sandbox_id,
                "message": msg,
                "files_loaded": files_loaded,
            },
        )

    def _step_impl(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        """Fallback for non-MCP actions — direct users to use MCP tools."""
        return Observation(
            done=False,
            reward=None,
            metadata={
                "error": f"Unknown action type: {type(action).__name__}. "
                "Use ListToolsAction or CallToolAction for MCP interactions."
            },
        )

    def step(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        self._state.step_count += 1
        return super().step(action, timeout_s=timeout_s, **kwargs)

    async def step_async(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        self._state.step_count += 1
        return await super().step_async(action, timeout_s=timeout_s, **kwargs)

    @property
    def state(self):
        return self._state


# ── Helpers ─────────────────────────────────────────────────────────────────

def _cell_to_model_kwargs(cell: dict) -> dict:
    """Extract fields matching NotebookCell from a tracker cell dict."""
    keys = {"cell_id", "cell_type", "code", "output", "error",
            "execution_count", "has_image", "images", "success"}
    return {k: v for k, v in cell.items() if k in keys}


def _get_notebook_cell_class():
    try:
        from ..models import NotebookCell
    except ImportError:
        from models import NotebookCell
    return NotebookCell


def _format_for_llm(result) -> str:
    """Format a CellResult as a concise string for the LLM."""
    parts = []
    if result.stdout:
        parts.append(result.stdout.strip())
    if result.text_results:
        parts.extend(result.text_results)
    if result.images:
        parts.append(f"[Image output: {len(result.images)} image(s) generated]")
    if result.error:
        parts.append(f"ERROR:\n{result.error}")
    return "\n".join(parts) if parts else "(no output)"
