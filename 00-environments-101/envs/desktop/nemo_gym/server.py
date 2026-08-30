"""Desktop NeMo Gym Resources Server.

Exposes the 19 desktop computer-use tools as NeMo Gym tool endpoints, plus
the standard `/seed_session` and `/verify` endpoints. Each session owns a
fresh E2B Desktop sandbox.

Run:
    python server.py
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from nemo_gym.base_resources_server import (
    BaseResourcesServerConfig,
    BaseSeedSessionRequest,
    BaseSeedSessionResponse,
    BaseVerifyRequest,
    BaseVerifyResponse,
    SimpleResourcesServer,
)
from nemo_gym.server_utils import SESSION_ID_KEY

# allow `from desktop import ...`
_parent = str(Path(__file__).resolve().parents[1])
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from core.desktop import DesktopController  # noqa: E402
from core.tasks import TASKS  # noqa: E402

load_dotenv()


class DesktopAgentConfig(BaseResourcesServerConfig):
    pass


# ──────── Request/response models ────────

class _Empty(BaseModel):
    pass


class _Coord(BaseModel):
    coordinate: List[int]
    text: Optional[str] = None


class _Move(BaseModel):
    coordinate: List[int]


class _OptCoord(BaseModel):
    coordinate: Optional[List[int]] = None


class _Drag(BaseModel):
    start_coordinate: List[int]
    coordinate: List[int]
    text: Optional[str] = None


class _Scroll(BaseModel):
    coordinate: List[int]
    scroll_direction: str
    scroll_amount: int
    text: Optional[str] = None


class _Type(BaseModel):
    text: str


class _Key(BaseModel):
    keys: str


class _HoldKey(BaseModel):
    keys: str
    duration: float


class _Wait(BaseModel):
    duration: float


class _Terminate(BaseModel):
    status: str


class _Cmd(BaseModel):
    command: str


class _ResetReq(BaseModel):
    """Override sandbox app/resolution at session start."""
    app: str = "desktop"
    resolution: List[int] = [1024, 768]


class ToolResponse(BaseModel):
    output: str
    image_b64: Optional[str] = None  # populated for screenshot


class DesktopVerifyRequest(BaseVerifyRequest):
    ground_truth: list = []


# ──────── Server ────────

class DesktopResourcesServer(SimpleResourcesServer):
    """NeMo Gym Resources Server — one E2B sandbox per session."""

    config: DesktopAgentConfig
    sessions: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def setup_webserver(self) -> FastAPI:
        app = super().setup_webserver()
        # 19 action endpoints + reset
        app.post("/reset")(self.reset_env)
        app.post("/screenshot")(self.screenshot)
        app.post("/cursor_position")(self.cursor_position)
        app.post("/get_screen_size")(self.get_screen_size)
        app.post("/left_click")(self.left_click)
        app.post("/right_click")(self.right_click)
        app.post("/middle_click")(self.middle_click)
        app.post("/double_click")(self.double_click)
        app.post("/triple_click")(self.triple_click)
        app.post("/mouse_move")(self.mouse_move)
        app.post("/left_click_drag")(self.left_click_drag)
        app.post("/left_mouse_down")(self.left_mouse_down)
        app.post("/left_mouse_up")(self.left_mouse_up)
        app.post("/scroll")(self.scroll)
        app.post("/type")(self.type_text)
        app.post("/key")(self.key)
        app.post("/hold_key")(self.hold_key)
        app.post("/wait")(self.wait)
        app.post("/terminate")(self.terminate)
        app.post("/run_command")(self.run_command)
        return app

    # -- session lifecycle --

    async def seed_session(self, body: BaseSeedSessionRequest) -> BaseSeedSessionResponse:
        return BaseSeedSessionResponse()

    def _sess(self, request: Request) -> Dict[str, Any]:
        sid = request.session[SESSION_ID_KEY]
        if sid not in self.sessions:
            controller = DesktopController(api_key=os.environ.get("E2B_API_KEY", ""))
            self.sessions[sid] = {"ctrl": controller, "task": None}
        return self.sessions[sid]

    async def reset_env(self, body: _ResetReq, request: Request) -> ToolResponse:
        s = self._sess(request)
        s["ctrl"].close()
        s["ctrl"] = DesktopController(
            api_key=os.environ.get("E2B_API_KEY", ""),
            app=body.app,
            resolution=tuple(body.resolution),
        )
        msg = s["ctrl"].start()
        return ToolResponse(output=msg)

    # -- helpers --

    def _emit(self, result) -> ToolResponse:
        text, image = result
        return ToolResponse(output=text, image_b64=image)

    # -- tool endpoints --

    async def screenshot(self, body: _Empty, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].screenshot())

    async def cursor_position(self, body: _Empty, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].cursor_position())

    async def get_screen_size(self, body: _Empty, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].get_screen_size())

    async def left_click(self, body: _Coord, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].left_click(body.coordinate, body.text))

    async def right_click(self, body: _Coord, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].right_click(body.coordinate, body.text))

    async def middle_click(self, body: _Coord, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].middle_click(body.coordinate, body.text))

    async def double_click(self, body: _Coord, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].double_click(body.coordinate, body.text))

    async def triple_click(self, body: _Coord, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].triple_click(body.coordinate, body.text))

    async def mouse_move(self, body: _Move, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].mouse_move(body.coordinate))

    async def left_click_drag(self, body: _Drag, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].left_click_drag(
            body.start_coordinate, body.coordinate, body.text))

    async def left_mouse_down(self, body: _OptCoord, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].left_mouse_down(body.coordinate))

    async def left_mouse_up(self, body: _OptCoord, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].left_mouse_up(body.coordinate))

    async def scroll(self, body: _Scroll, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].scroll(
            body.coordinate, body.scroll_direction, body.scroll_amount, body.text))

    async def type_text(self, body: _Type, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].type(body.text))

    async def key(self, body: _Key, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].key(body.keys))

    async def hold_key(self, body: _HoldKey, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].hold_key(body.keys, body.duration))

    async def wait(self, body: _Wait, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].wait(body.duration))

    async def terminate(self, body: _Terminate, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].terminate(body.status))

    async def run_command(self, body: _Cmd, request: Request) -> ToolResponse:
        return self._emit(self._sess(request)["ctrl"].run_command(body.command))

    # -- verify --

    async def verify(self, body: DesktopVerifyRequest) -> BaseVerifyResponse:
        """Reward = 1.0 if the agent called terminate(status='success'), else 0.0.

        For richer grading, override this to inspect ground_truth or scan
        function_call_outputs for an expected substring.
        """
        reward = 0.0
        for item in body.response.output:
            if hasattr(item, "type") and item.type == "function_call":
                # Function name and arguments
                name = getattr(item, "name", "")
                if name == "terminate":
                    args = getattr(item, "arguments", "") or ""
                    if "success" in args:
                        reward = 1.0
                        break
        return BaseVerifyResponse(**body.model_dump(), reward=reward)


if __name__ == "__main__":
    DesktopResourcesServer.run_webserver()
