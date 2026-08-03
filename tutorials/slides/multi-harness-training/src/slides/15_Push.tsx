import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";

/** Local versus hosted topology, side by side. */
export function PushSlide() {
  const { T } = useTheme();

  const box = (label: string, sub: string, accent?: boolean) => (
    <div
      style={{
        padding: "17px 20px",
        borderRadius: 9,
        border: `1px solid ${accent ? T.accent : T.border}`,
        background: accent ? `${T.accent}12` : T.bgRaised,
        textAlign: "center",
        minWidth: 150,
      }}
    >
      <div style={{ fontFamily: MONO, fontSize: 21, color: accent ? T.accent : T.text }}>
        {label}
      </div>
      <div style={{ fontSize: 18, color: T.textDim, marginTop: 5 }}>{sub}</div>
    </div>
  );

  const col = (head: string, accent: string, body: React.ReactNode, foot: string) => (
    <div
      style={{
        padding: "22px 26px",
        borderRadius: 12,
        border: `1px solid ${accent}`,
        background: T.bgRaised,
        height: "100%",
      }}
    >
      <div
        style={{
          fontFamily: MONO,
          fontSize: 21,
          letterSpacing: 3,
          textTransform: "uppercase",
          color: accent,
          marginBottom: 18,
        }}
      >
        {head}
      </div>
      {body}
      <div style={{ fontSize: 23, color: T.textDim, marginTop: 26 }}>{foot}</div>
    </div>
  );

  return (
    <SlideShell kicker="Deploy" title="One command ships it as a Space">
      <Stagger style={{ position: "absolute", top: 198, left: 96, right: 96 }}>
        <Rise>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 25,
              color: T.accent2,
              padding: "14px 20px",
              borderRadius: 10,
              border: `1px solid ${T.border}`,
              background: T.bgRaised,
              marginBottom: 38,
            }}
          >
            openenv harbor push --repo-id you/harbor-env --dataset org/train
          </div>
        </Rise>

        <Rise>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 34 }}>
            {col(
              "Local: two ports",
              T.border,
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                {box(":8000", "env server")}
                {box(":8100", "proxy, published", true)}
              </div>,
              "Only the proxy is exposed.",
            )}
            {col(
              "Hosted: one URL",
              T.accent,
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                {box("space.hf.space", "env server")}
                {box("/capture", "proxy, mounted", true)}
              </div>,
              "Nothing forwarded. Bucket-mounted tasks.",
            )}
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
