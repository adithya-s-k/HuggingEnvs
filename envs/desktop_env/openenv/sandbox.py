"""
E2B Desktop Sandbox wrapper for computer-use environments.

Provides a simple interface to spin up cloud desktop sandboxes with
pre-installed applications, take screenshots, and send mouse/keyboard actions.
Scales horizontally — each sandbox is an isolated cloud VM.

Usage:
    from sandbox import DesktopSandbox

    sandbox = DesktopSandbox(app="libreoffice-calc")
    sandbox.start()
    print("Stream URL:", sandbox.stream_url)

    screenshot = sandbox.screenshot()  # PIL Image
    sandbox.click(500, 300)
    sandbox.type_text("Hello world")
    sandbox.press("enter")

    sandbox.stop()
"""

import io
import os
from dataclasses import dataclass, field
from typing import Optional

from e2b_desktop import Sandbox
from PIL import Image


@dataclass
class SandboxConfig:
    """Configuration for a desktop sandbox."""
    resolution: tuple[int, int] = (1920, 1080)
    dpi: int = 96
    timeout: int = 600  # seconds
    api_key: Optional[str] = None
    install_commands: list[str] = field(default_factory=list)
    app_launch: Optional[str] = None  # command to launch after install
    app_wait_ms: int = 5000  # ms to wait after launching app


# Pre-built configs for common environments
CONFIGS = {
    "libreoffice-calc": SandboxConfig(
        install_commands=[
            "sudo apt-get update -qq",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-calc",
        ],
        app_launch="libreoffice --calc",
        app_wait_ms=5000,
    ),
    "libreoffice-writer": SandboxConfig(
        install_commands=[
            "sudo apt-get update -qq",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-writer",
        ],
        app_launch="libreoffice --writer",
        app_wait_ms=5000,
    ),
    "libreoffice-impress": SandboxConfig(
        install_commands=[
            "sudo apt-get update -qq",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice-impress",
        ],
        app_launch="libreoffice --impress",
        app_wait_ms=5000,
    ),
    "firefox": SandboxConfig(
        install_commands=[
            "sudo apt-get update -qq",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq firefox",
        ],
        app_launch="firefox",
        app_wait_ms=5000,
    ),
    "terminal": SandboxConfig(
        app_launch="xfce4-terminal",
        app_wait_ms=2000,
    ),
    "blender": SandboxConfig(
        install_commands=[
            "sudo apt-get update -qq",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq blender",
        ],
        app_launch="blender",
        app_wait_ms=8000,
    ),
}


class DesktopSandbox:
    """
    Cloud desktop sandbox powered by E2B.

    Each instance is an isolated VM with a full Linux desktop.
    Scales horizontally — spin up as many as you need.
    """

    def __init__(self, config: Optional[SandboxConfig] = None, app: Optional[str] = None):
        """
        Args:
            config: Full SandboxConfig, or use `app` for a preset.
            app: Preset name from CONFIGS (e.g., "libreoffice-calc", "blender").
        """
        if config:
            self.config = config
        elif app and app in CONFIGS:
            self.config = CONFIGS[app]
        elif app:
            # Treat as a raw launch command
            self.config = SandboxConfig(app_launch=app, app_wait_ms=3000)
        else:
            self.config = SandboxConfig()

        self._sandbox: Optional[Sandbox] = None
        self._stream_url: Optional[str] = None

    @property
    def stream_url(self) -> Optional[str]:
        return self._stream_url

    @property
    def sandbox_id(self) -> Optional[str]:
        return self._sandbox.sandbox_id if self._sandbox else None

    def start(self) -> str:
        """Create sandbox, install software, launch app, start stream. Returns stream URL."""
        api_key = self.config.api_key or os.environ.get("E2B_API_KEY")
        if not api_key:
            raise ValueError("E2B_API_KEY not set. Pass api_key in config or set env var.")

        print(f"Creating E2B Desktop sandbox ({self.config.resolution[0]}x{self.config.resolution[1]})...")
        self._sandbox = Sandbox.create(
            resolution=self.config.resolution,
            dpi=self.config.dpi,
            timeout=self.config.timeout,
            api_key=api_key,
        )
        print(f"Sandbox created: {self._sandbox.sandbox_id}")

        # Install software
        for cmd in self.config.install_commands:
            print(f"  Running: {cmd[:80]}...")
            result = self._sandbox.commands.run(cmd, timeout=300)
            if result.exit_code != 0:
                print(f"  WARNING: command exited {result.exit_code}")
                if result.stderr:
                    print(f"  stderr: {result.stderr[:200]}")

        # Launch app in background
        if self.config.app_launch:
            print(f"  Launching: {self.config.app_launch}")
            self._sandbox.commands.run(
                self.config.app_launch,
                background=True,
            )
            self._sandbox.wait(self.config.app_wait_ms)

        # Start stream
        self._sandbox.stream.start()
        self._stream_url = self._sandbox.stream.get_url()
        print(f"Stream URL: {self._stream_url}")

        return self._stream_url

    def screenshot(self, save_path: Optional[str] = None) -> Image.Image:
        """Take a screenshot. Returns PIL Image."""
        data = self._sandbox.screenshot()
        img = Image.open(io.BytesIO(data))
        if save_path:
            img.save(save_path)
        return img

    def click(self, x: int, y: int):
        """Left click at (x, y)."""
        self._sandbox.left_click(x, y)

    def right_click(self, x: int, y: int):
        """Right click at (x, y)."""
        self._sandbox.right_click(x, y)

    def double_click(self, x: int, y: int):
        """Double click at (x, y)."""
        self._sandbox.double_click(x, y)

    def type_text(self, text: str):
        """Type text at current cursor position."""
        self._sandbox.write(text)

    def press(self, keys):
        """Press key(s). Can be a string or list for combos like ['ctrl', 'c']."""
        self._sandbox.press(keys)

    def scroll(self, direction: str = "down", amount: int = 3):
        """Scroll. direction is 'up' or 'down'."""
        self._sandbox.scroll(direction=direction, amount=amount)

    def drag(self, start: tuple[int, int], end: tuple[int, int]):
        """Drag from start to end coordinates."""
        self._sandbox.drag(start, end)

    def move_mouse(self, x: int, y: int):
        """Move mouse to (x, y) without clicking."""
        self._sandbox.move_mouse(x, y)

    def run_command(self, cmd: str, timeout: int = 60) -> str:
        """Run a shell command inside the sandbox. Returns stdout."""
        result = self._sandbox.commands.run(cmd, timeout=timeout)
        return result.stdout or ""

    def write_file(self, path: str, content: str):
        """Write a file inside the sandbox."""
        self._sandbox.files.write(path, content)

    def launch(self, app: str):
        """Launch an application by name."""
        self._sandbox.launch(app)

    def wait(self, ms: int):
        """Wait for specified milliseconds."""
        self._sandbox.wait(ms)

    def stop(self):
        """Kill the sandbox."""
        if self._sandbox:
            try:
                self._sandbox.stream.stop()
            except Exception:
                pass
            try:
                self._sandbox.kill()
            except Exception:
                pass
            self._sandbox = None
            print("Sandbox stopped.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def __repr__(self):
        status = "running" if self._sandbox else "stopped"
        return f"DesktopSandbox(id={self.sandbox_id}, status={status})"
