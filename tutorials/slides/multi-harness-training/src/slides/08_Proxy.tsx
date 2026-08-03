import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";
import { Flow } from "../primitives/diagrams";

/** The one idea the rest of the talk rests on. */
export function ProxySlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The idea" title="Put a proxy on the wire">
      <Stagger style={{ position: "absolute", top: 232, left: 96, right: 96 }}>
        <Rise>
          <Flow
            width={212}
            nodes={[
              { label: "agent", sub: "in a sandbox" },
              { label: "proxy", sub: "records every call", accent: true },
              { label: "vLLM", sub: "your policy" },
            ]}
          />
        </Rise>

        {/* what the proxy takes off the wire */}
        <Rise>
          <div style={{ display: "flex", gap: 34, marginTop: 40, marginLeft: 292 }}>
            <svg width="30" height="34" viewBox="0 0 30 34">
              <path d="M15,0 L15,26" stroke={T.accent} strokeWidth="2" strokeDasharray="4 3" />
              <path d="M9,22 L15,32 L21,22" fill="none" stroke={T.accent} strokeWidth="2" />
            </svg>
            <div
              style={{
                fontFamily: MONO,
                fontSize: 22,
                color: T.textDim,
                lineHeight: 1.95,
              }}
            >
              <div>
                <span style={{ color: T.accent2 }}>prompt_token_ids</span> · the engine's own
                tokenisation
              </div>
              <div>
                <span style={{ color: T.accent2 }}>completion_token_ids</span> · what it sampled
              </div>
              <div>
                <span style={{ color: T.accent2 }}>per_token_logps</span> · behaviour-policy logprobs
              </div>
            </div>
          </div>
        </Rise>

        <Rise>
          <div style={{ marginTop: 44, fontSize: 31, color: T.text }}>
            The agent is unmodified. It gets a byte-identical response back.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
