import { SlideShell } from "../deck/SlideShell";
import { Rise } from "../primitives";
import { CodeBlock } from "../primitives/CodeBlock";

/** What a white-box env looks like in OpenEnv: expose a tool, nothing more. */
export function WhiteBoxCodeSlide() {
  return (
    <SlideShell kicker="White box" title="In OpenEnv: expose a tool">
      <Rise style={{ position: "absolute", top: 216, left: 96, right: 96 }}>
        <CodeBlock
          language="python"
          fontSize={26}
          highlight={[4, 5]}
          code={`class CodingEnvironment(MCPEnvironment):

    @mcp.tool
    def run_bash(command: str) -> str:
        """Execute a command in the sandbox."""
        return self._sandbox.exec(command).stdout`}
        />
      </Rise>
    </SlideShell>
  );
}
