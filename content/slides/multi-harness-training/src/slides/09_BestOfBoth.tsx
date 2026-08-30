import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Bullet, Panel, Rise, Stagger } from "../primitives";

/**
 * What each side already owns, and the narrow band that is actually new.
 *
 * Two columns for the two projects, then one full-width strip underneath: the
 * columns are the argument that nothing there is rebuilt, and the strip is the only
 * thing this integration adds.
 */
export function BestOfBothSlide() {
  const { T } = useTheme();

  const columns = [
    {
      head: "OpenEnv already has",
      accent: T.accent2,
      items: ["env server + Task API", "typed client", "sandbox transport", "one CLI"],
    },
    {
      head: "Harbor already has",
      accent: T.accent,
      items: ["tasks + verifiers", "37 agent harnesses", "23 sandbox backends", "trial concurrency"],
    },
  ];

  return (
    <SlideShell kicker="Integration" title="Each layer keeps what it is good at">
      <Stagger style={{ position: "absolute", top: 200, left: 96, right: 96 }}>
        <Rise>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 34 }}>
            {columns.map((c) => (
              <Panel key={c.head} accent={c.accent} style={{ padding: "28px 32px" }}>
                <div
                  style={{
                    fontFamily: MONO,
                    fontSize: 21,
                    letterSpacing: 2,
                    textTransform: "uppercase",
                    color: c.accent,
                    marginBottom: 22,
                  }}
                >
                  {c.head}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {c.items.map((it) => (
                    <Bullet key={it} size={26} marker="·" markerColor={T.textDim}>
                      {it}
                    </Bullet>
                  ))}
                </div>
              </Panel>
            ))}
          </div>
        </Rise>

        {/* the only new code, given its own band so the asymmetry is obvious */}
        <Rise>
          <div
            style={{
              marginTop: 28,
              padding: "22px 30px",
              borderRadius: 12,
              border: `1px solid ${T.accent}`,
              background: `${T.accent}12`,
              boxShadow: `0 0 40px ${T.accent}22`,
              display: "flex",
              alignItems: "center",
              gap: 28,
            }}
          >
            <span
              style={{
                fontFamily: MONO,
                fontSize: 19,
                letterSpacing: 3,
                textTransform: "uppercase",
                color: T.accent,
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              all that is new
            </span>
            {/* chips rather than one run of prose: the row cannot wrap */}
            <div style={{ display: "flex", gap: 16, flex: 1 }}>
              {["capture proxy", "rollout graph", "trainable tokens"].map((n) => (
                <div
                  key={n}
                  style={{
                    flex: 1,
                    textAlign: "center",
                    padding: "12px 10px",
                    borderRadius: 8,
                    border: `1px solid ${T.accent}55`,
                    background: T.bgRaised,
                    fontSize: 25,
                    color: T.text,
                    whiteSpace: "nowrap",
                  }}
                >
                  {n}
                </div>
              ))}
            </div>
          </div>
        </Rise>

        <Rise>
          <div style={{ marginTop: 22, fontSize: 25, color: T.textDim }}>
            No sandbox code written twice. No agent wrapped twice.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
