import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";

/** The frame for the whole talk, with the shape of each shown beneath the word. */
export function TwoKindsSlide() {
  const { T } = useTheme();

  const mini = (nodes: string[], accent: string, dashed: boolean) => (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 20 }}>
      {nodes.map((n, i) => (
        <div key={n} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 19,
              padding: "10px 15px",
              borderRadius: 7,
              border: `1px ${dashed && i === nodes.length - 1 ? "dashed" : "solid"} ${accent}`,
              color: accent,
            }}
          >
            {n}
          </div>
          {i < nodes.length - 1 ? (
            <span style={{ color: accent, fontSize: 22 }}>{dashed ? "→" : "⇄"}</span>
          ) : null}
        </div>
      ))}
    </div>
  );

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        paddingLeft: 96,
        paddingRight: 96,
      }}
    >
      <Stagger>
        <Rise>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 19,
              letterSpacing: 4,
              textTransform: "uppercase",
              color: T.textDim,
              marginBottom: 26,
            }}
          >
            Two kinds of RL environment
          </div>
        </Rise>
        <Rise>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 60 }}>
            <div>
              <div style={{ fontSize: 66, fontWeight: 700, color: T.text }}>white box</div>
              {mini(["trainer", "env"], T.accent2, false)}
              <div style={{ marginTop: 24, fontSize: 25, color: T.textDim }}>
                you drive the loop
              </div>
            </div>
            <div>
              <div style={{ fontSize: 66, fontWeight: 700, color: T.accent }}>black box</div>
              {mini(["trainer", "sandbox"], T.accent, true)}
              <div style={{ marginTop: 18, fontSize: 22, color: T.textDim }}>
                the agent drives it
              </div>
            </div>
          </div>
        </Rise>
        <Rise>
          <div style={{ marginTop: 60, fontSize: 31, color: T.text }}>
            The difference is not the task. It is who drives the rollout.
          </div>
        </Rise>
      </Stagger>
    </div>
  );
}
