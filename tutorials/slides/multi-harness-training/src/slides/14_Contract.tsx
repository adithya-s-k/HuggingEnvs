import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { Rise, Stagger } from "../primitives";
import { TokenBar } from "../primitives/diagrams";

/** The payoff, shown as tokens rather than described as fields. */
export function ContractSlide() {
  const { T } = useTheme();
  const turns = [
    { segs: [{ n: 7994, kind: "prompt" as const }, { n: 79, kind: "completion" as const }], l: "7994 ctx · 79 gen" },
    { segs: [{ n: 240, kind: "prompt" as const }, { n: 331, kind: "completion" as const }], l: "240 ctx · 331 gen" },
    { segs: [{ n: 190, kind: "prompt" as const }, { n: 90, kind: "completion" as const }], l: "190 ctx · 90 gen" },
    { segs: [{ n: 150, kind: "prompt" as const }, { n: 57, kind: "discarded" as const }], l: "retry, discarded" },
    { segs: [{ n: 210, kind: "prompt" as const }, { n: 396, kind: "completion" as const }], l: "210 ctx · 396 gen" },
  ];
  const key = [
    ["#94a3b8", "context, masked out (log scale)"],
    [T.accent2, "sampled, trainable"],
    ["#ef4444", "abandoned, excluded"],
  ] as const;

  return (
    <SlideShell kicker="Output" title="What a rollout returns">
      <Stagger style={{ position: "absolute", top: 214, left: 96, right: 96 }}>
        <Rise>
          <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
            {turns.map((t, i) => (
              <TokenBar key={i} segments={t.segs} scale={420} label={t.l} />
            ))}
          </div>
        </Rise>

        <Rise>
          <div style={{ display: "flex", gap: 40, marginTop: 34 }}>
            {key.map(([c, l]) => (
              <div key={l} style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <span style={{ width: 19, height: 19, borderRadius: 3, background: c }} />
                <span style={{ fontSize: 23, color: T.textDim }}>{l}</span>
              </div>
            ))}
          </div>
        </Rise>

        <Rise>
          <div style={{ marginTop: 44, fontSize: 30, color: T.text, lineHeight: 1.6 }}>
            Every sampled token carries its own{" "}
            <code style={{ fontFamily: MONO, color: T.accent2 }}>logprob</code>, plus the task's
            reward.
          </div>
        </Rise>
        <Rise>
          <div style={{ marginTop: 12, fontSize: 25, color: T.textDim }}>
            Not recoverable afterwards: re-rendering a prompt offline drifts.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
