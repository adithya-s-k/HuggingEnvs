import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";

/** The asymmetry, drawn: who is inside the loop and who is outside it. */
export function BlackBoxHardSlide() {
  const { T } = useTheme();

  const panel = (
    title: string,
    accent: string,
    body: React.ReactNode,
    caption: string,
  ) => (
    <div
      style={{
        padding: "30px 34px",
        borderRadius: 12,
        border: `1px solid ${accent}`,
        background: T.bgRaised,
        height: "100%",
      }}
    >
      <div
        style={{
          fontFamily: MONO,
          fontSize: 22,
          letterSpacing: 3,
          textTransform: "uppercase",
          color: accent,
          marginBottom: 20,
        }}
      >
        {title}
      </div>
      {body}
      <div style={{ fontSize: 25, color: T.textDim, marginTop: 26 }}>{caption}</div>
    </div>
  );

  const node = (label: string, colour: string, dashed = false) => (
    <div
      style={{
        padding: "16px 20px",
        borderRadius: 9,
        border: `1px ${dashed ? "dashed" : "solid"} ${colour}`,
        fontFamily: MONO,
        fontSize: 22,
        color: colour,
        textAlign: "center",
      }}
    >
      {label}
    </div>
  );

  return (
    <SlideShell kicker="Black box" title="Which is why training on one is hard">
      <Stagger
        style={{
          position: "absolute",
          top: 215,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 36,
        }}
      >
        <Rise>
          {panel(
            "White box",
            T.accent2,
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {node("trainer", T.accent2)}
              <div style={{ textAlign: "center", color: T.accent2, fontSize: 26 }}>&#8645;</div>
              {node("env: run_bash()", T.text)}
            </div>,
            "The loop is yours. Tokens are already in hand.",
          )}
        </Rise>
        <Rise>
          {panel(
            "Black box",
            T.accent,
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {node("trainer", T.textDim, true)}
              <div style={{ textAlign: "center", color: T.textDim, fontSize: 21 }}>
                no visibility
              </div>
              <div
                style={{
                  border: `1px dashed ${T.borderStrong}`,
                  borderRadius: 9,
                  padding: 10,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <div style={{ fontFamily: MONO, fontSize: 18, color: T.textDim }}>sandbox</div>
                {node("agent loop", T.accent)}
              </div>
            </div>,
            "The loop is the agent's. You see nothing.",
          )}
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
