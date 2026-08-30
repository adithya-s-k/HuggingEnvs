import { SlideShell } from "../../components/SlideShell";
import { Stagger, Rise, Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";

export function RH2TaskSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The task" title={<>One real bug</>}>
      <div style={{ position: "absolute", top: 275, left: 96, right: 96 }}>
        <Stagger gap={0.16} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          <Rise>
            <div style={{ fontSize: 36, color: T.text, lineHeight: 1.4, maxWidth: 1060 }}>
              Patch <span style={{ fontFamily: MONO, color: T.emerald }}>CVE-2026-48156</span> in{" "}
              <b style={{ color: T.white }}>pypdf</b> — a crafted PDF loops forever (DoS).
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 28, color: T.textMuted }}>
              Agent: <b style={{ color: T.white }}>Opus</b> · reward: a hidden test —{" "}
              <Accent color="emerald">gold 1.0 · no-op 0.0</Accent>.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
