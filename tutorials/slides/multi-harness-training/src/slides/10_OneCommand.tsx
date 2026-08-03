import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";
import { CodeBlock } from "../primitives/CodeBlock";

/** The whole surface, in one command. */
export function OneCommandSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Integration" title="The whole thing is one command">
      <Stagger style={{ position: "absolute", top: 216, left: 96, right: 96 }}>
        <Rise>
          <CodeBlock
            language="bash"
            fontSize={24}
            showLineNumbers={false}
            code={`openenv harbor serve --llm-url $VLLM --dataset org/my-tasks`}
          />
        </Rise>
        <Rise>
          <div style={{ marginTop: 52, fontSize: 32, color: T.text, lineHeight: 1.6 }}>
            Task API for discovery. One{" "}
            <code style={{ fontFamily: MONO, color: T.accent }}>run_rollout</code> tool. A UI.
          </div>
        </Rise>
        <Rise>
          <div style={{ marginTop: 24, fontSize: 29, color: T.textDim, lineHeight: 1.6 }}>
            Harness and sandbox are arguments, <b style={{ color: T.text }}>per rollout</b>.
            <br />
            One server covers the whole matrix.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
