import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { Rise, Stagger } from "../primitives";
import { Funnel } from "../primitives/diagrams";

/** Four dialects converging on one upstream shape. */
export function DialectsSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The proxy" title="Four wire dialects, one upstream">
      <Stagger style={{ position: "absolute", top: 212, left: 96, right: 96 }}>
        <Rise>
          <Funnel
            inputs={[
              "chat-completions  ·  12 agents",
              "OpenAI Responses  ·  codex",
              "Anthropic Messages  ·  claude-code",
              "Google generateContent  ·  gemini-cli",
            ]}
            hub="one shape"
            out="then replayed back out"
          />
        </Rise>
        <Rise>
          <div style={{ marginTop: 44, fontSize: 31, color: T.text }}>
            Replayed in the agent's own dialect, streaming included.
          </div>
        </Rise>
        <Rise>
          <div style={{ marginTop: 14, fontSize: 26, color: T.textDim }}>
            Supporting all four is what buys codex, claude-code and gemini-cli.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
