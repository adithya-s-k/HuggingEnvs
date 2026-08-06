import { SlideShell } from "../components/SlideShell";
import { Timeline } from "../components/Timeline";
import { Stagger, Rise, Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

export function PretrainingSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={4} kicker="Pretraining" title={<>Read the whole internet</>}>
      <div style={{ position: "absolute", top: 250, left: 96, right: 96 }}>
        <Timeline active={0} compact animate={false} />
      </div>

      <div style={{ position: "absolute", top: 380, left: 96, right: 96 }}>
        <Stagger gap={0.14} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          <Rise>
            <div style={{ fontSize: 36, color: T.text, lineHeight: 1.35, maxWidth: 1040 }}>
              Take <Accent color="emerald">trillions of tokens</Accent> of raw web text —
              and predict the next one.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 26, color: T.textMuted, lineHeight: 1.45, maxWidth: 1000 }}>
              You get a model that <b style={{ color: T.white }}>knows a lot</b> — but doesn’t
              yet know how to <b style={{ color: T.white }}>behave</b>.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
