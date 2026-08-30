import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";

/** Black box: an opaque agent with exactly one wire coming out. */
export function BlackBoxSlide() {
  const { T } = useTheme();
  const agents = ["claude-code", "codex", "opencode", "gemini-cli", "goose", "swe-agent"];

  return (
    <SlideShell kicker="Black box" title="The agent is a binary you do not control">
      <Stagger style={{ position: "absolute", top: 226, left: 96, right: 96 }}>
        <Rise>
          <div style={{ display: "flex", alignItems: "center", gap: 26 }}>
            {/* the opaque box */}
            <div
              style={{
                width: 470,
                padding: "30px 34px",
                borderRadius: 14,
                border: `1px dashed ${T.borderStrong}`,
                background: `repeating-linear-gradient(45deg, ${T.bgRaised}, ${T.bgRaised} 9px, transparent 9px, transparent 18px)`,
              }}
            >
              <div style={{ fontFamily: MONO, fontSize: 24, color: T.textDim, marginBottom: 16 }}>
                its own loop, its own tools
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 9 }}>
                {agents.map((a) => (
                  <span
                    key={a}
                    style={{
                      fontFamily: MONO,
                      fontSize: 21,
                      padding: "9px 15px",
                      borderRadius: 7,
                      border: `1px solid ${T.border}`,
                      color: T.text,
                      background: T.bg,
                    }}
                  >
                    {a}
                  </span>
                ))}
              </div>
            </div>

            {/* the one wire */}
            <svg width="180" height="90" viewBox="0 0 180 90" style={{ flexShrink: 0 }}>
              <defs>
                <marker id="bb" markerWidth="9" markerHeight="9" refX="7" refY="3"
                        orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L0,6 L8,3 z" fill={T.accent} />
                </marker>
              </defs>
              <path d="M0,45 L168,45" stroke={T.accent} strokeWidth="2"
                    markerEnd="url(#bb)" />
              <text x="84" y="32" textAnchor="middle" fill={T.accent}
                    fontFamily={MONO} fontSize="20">one endpoint</text>
            </svg>

            <div
              style={{
                padding: "22px 26px",
                borderRadius: 12,
                border: `1px solid ${T.border}`,
                background: T.bgRaised,
                textAlign: "center",
              }}
            >
              <div style={{ fontFamily: MONO, fontSize: 26, color: T.text }}>your model</div>
              <div style={{ fontSize: 20, color: T.textDim, marginTop: 7 }}>OpenAI-compatible</div>
            </div>
          </div>
        </Rise>
        <Rise>
          <div style={{ marginTop: 68, fontSize: 33, color: T.text }}>
            That single wire is the only place you can stand.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
