import { SlideShell } from "../components/SlideShell";
import { CodeBlock } from "../components/CodeBlock";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

const CODE = `from fastmcp import FastMCP
from openenv.core.env_server.mcp_environment import MCPEnvironment

class CodingEnv(MCPEnvironment):
    def __init__(self):
        mcp = FastMCP("coding_env")

        ⟪@mcp.tool⟫
        def bash(command: str) -> str:
            "Run a shell command in the sandbox."
            result = self._sandbox.run_shell(command)
            self._state.step_count += 1
            return result.stdout + result.stderr

        super().__init__(mcp)   # actions route to @mcp.tool fns`;

export function BuildToolSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={18} kicker="Build · OpenEnv" title={<>A bash tool</>}>
      <div style={{ position: "absolute", top: 158, left: 96, right: 96, fontSize: 24, color: T.textMuted }}>
        The action space is <Accent color="emerald">just functions</Accent> — decorate them with{" "}
        <code>@mcp.tool</code>.
      </div>
      <div style={{ position: "absolute", top: 208, left: 96, right: 96 }}>
        <CodeBlock filename="coding_environment.py" code={CODE} fontSize={17} />
      </div>
    </SlideShell>
  );
}
