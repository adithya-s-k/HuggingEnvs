import { SlideShell } from "../components/SlideShell";
import { CodeBlock } from "../components/CodeBlock";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

const CODE = `from openenv.core.env_server.http_server import create_app
from openenv.core.env_server.mcp_types import (
    CallToolAction, CallToolObservation,
)
from .coding_environment import CodingEnv

app = create_app(
    CodingEnv, CallToolAction, CallToolObservation,
    env_name="coding_env",
    ⟪max_concurrent_envs=8,⟫      # parallel rollouts
)
# uvicorn server.app:app --port 8000`;

export function BuildServeSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={21} kicker="Build · OpenEnv" title={<>Serve the env</>}>
      <div style={{ position: "absolute", top: 158, left: 96, right: 96, fontSize: 24, color: T.textMuted }}>
        <code>create_app</code> turns the class into an <Accent color="emerald">HTTP + MCP server</Accent> —{" "}
        <code>/reset</code>, <code>/step</code>, <code>/state</code>.
      </div>
      <div style={{ position: "absolute", top: 208, left: 96, right: 96 }}>
        <CodeBlock filename="server/app.py" code={CODE} fontSize={17} />
      </div>
    </SlideShell>
  );
}
