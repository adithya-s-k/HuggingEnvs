import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";

/**
 * The argument for a middle layer, as a picture rather than a list.
 *
 * Left: every harness needs its own wiring to every sandbox, and the line count is
 * the point. Right: one integration in the middle, and the same lines become two
 * fans. The audience should get it before the caption is read.
 */
export function WhySlide() {
  const { T } = useTheme();

  const H = 250;
  const harnesses = ["claude-code", "codex", "opencode", "gemini-cli"];
  const sandboxes = ["e2b", "modal", "docker", "gke"];
  const yFor = (i: number, n: number) => (H / (n + 1)) * (i + 1);

  const chip = (label: string, colour: string) => (
    <div
      key={label}
      style={{
        fontFamily: MONO,
        fontSize: 18,
        padding: "9px 12px",
        borderRadius: 6,
        border: `1px solid ${colour}`,
        color: colour,
        textAlign: "center",
        background: T.bg,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </div>
  );

  const column = (items: string[], colour: string) => (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-around",
        height: H,
        width: 158,
      }}
    >
      {items.map((i) => chip(i, colour))}
    </div>
  );

  return (
    <SlideShell kicker="Why here" title="One integration, not one per pair">
      <Stagger style={{ position: "absolute", top: 200, left: 96, right: 96 }}>
        <Rise>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 44 }}>
            {/* every pair wired by hand */}
            <div>
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 20,
                  letterSpacing: 2,
                  textTransform: "uppercase",
                  color: T.textDim,
                  marginBottom: 14,
                }}
              >
                Without a middle layer
              </div>
              <div style={{ display: "flex", alignItems: "center" }}>
                {column(harnesses, T.textDim)}
                <svg width="150" height={H} viewBox={`0 0 150 ${H}`}>
                  {harnesses.map((_, i) =>
                    sandboxes.map((__, j) => (
                      <line
                        key={`${i}-${j}`}
                        x1="0"
                        y1={yFor(i, harnesses.length)}
                        x2="150"
                        y2={yFor(j, sandboxes.length)}
                        stroke="#ef4444"
                        strokeWidth="1"
                        opacity="0.42"
                      />
                    )),
                  )}
                </svg>
                {column(sandboxes, T.textDim)}
              </div>
              <div style={{ fontSize: 23, color: "#ef4444", marginTop: 14, whiteSpace: "nowrap" }}>
                16 paths to maintain
              </div>
            </div>

            {/* one hub */}
            <div>
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 17,
                  letterSpacing: 2,
                  textTransform: "uppercase",
                  color: T.accent2,
                  marginBottom: 14,
                }}
              >
                With OpenEnv in the middle
              </div>
              <div style={{ display: "flex", alignItems: "center" }}>
                {column(harnesses, T.text)}
                <svg width="150" height={H} viewBox={`0 0 150 ${H}`}>
                  {harnesses.map((_, i) => (
                    <line
                      key={i}
                      x1="0"
                      y1={yFor(i, harnesses.length)}
                      x2="72"
                      y2={H / 2}
                      stroke={T.accent2}
                      strokeWidth="1.4"
                      opacity="0.85"
                    />
                  ))}
                  {sandboxes.map((_, j) => (
                    <line
                      key={`s${j}`}
                      x1="78"
                      y1={H / 2}
                      x2="150"
                      y2={yFor(j, sandboxes.length)}
                      stroke={T.accent}
                      strokeWidth="1.4"
                      opacity="0.85"
                    />
                  ))}
                  <circle cx="75" cy={H / 2} r="12" fill={T.bg} stroke={T.accent2} strokeWidth="2" />
                </svg>
                {column(sandboxes, T.text)}
              </div>
              <div style={{ fontSize: 23, color: T.accent2, marginTop: 14, whiteSpace: "nowrap" }}>
                one capture layer, shared
              </div>
            </div>
          </div>
        </Rise>

        <Rise>
          <div style={{ display: "flex", gap: 40, marginTop: 26 }}>
            {[
              ["Consistency", "one contract, any pair"],
              ["Failures return", "a bad rollout cannot hang a rank"],
              ["Adding a harness", "a table entry, not a package"],
            ].map(([h, s]) => (
              <div key={h} style={{ flex: 1 }}>
                <div style={{ fontSize: 24, color: T.text }}>{h}</div>
                <div style={{ fontFamily: MONO, fontSize: 17, color: T.textDim, marginTop: 6 }}>
                  {s}
                </div>
              </div>
            ))}
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
