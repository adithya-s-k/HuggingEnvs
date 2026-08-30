import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";
import { Tree } from "../primitives/diagrams";

/** Structure comes from the tokens, not from metadata. */
export function GraphSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The proxy" title="Turns link by exact token prefix">
      <Stagger style={{ position: "absolute", top: 212, left: 120, right: 96 }}>
        <Rise>
          <Tree
            nodes={[
              { label: "root", note: "system + first user turn", depth: 0, kind: "root" },
              { label: "turn 1", depth: 1, kind: "turn" },
              { label: "turn 2", depth: 2, kind: "turn" },
              { label: "turn 3", depth: 3, kind: "turn" },
              { label: "turn 3'", note: "retry, abandoned", depth: 3, kind: "discarded" },
              { label: "root", note: "subagent, own system prompt", depth: 0, kind: "aux" },
            ]}
          />
        </Rise>
        <Rise>
          <div style={{ marginTop: 40, fontSize: 29, color: T.text, lineHeight: 1.6 }}>
            A call whose <code style={{ fontFamily: MONO, color: T.accent2 }}>prompt_token_ids</code>{" "}
            begin with a node's full sequence becomes its child.
          </div>
        </Rise>
        <Rise>
          <div style={{ marginTop: 14, fontSize: 25, color: T.textDim }}>
            No request ids, no timestamps. Those are per-agent; the prefix is not.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
