import { SlideShell } from "../components/SlideShell";
import { Timeline } from "../components/Timeline";
import { Stagger, Rise, Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

export function SFTSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={5} kicker="SFT" title={<>Show it good answers</>}>
      <div style={{ position: "absolute", top: 210, left: 96, right: 96 }}>
        <Timeline active={1} compact animate={false} />
      </div>

      <div style={{ position: "absolute", top: 320, left: 96, right: 96 }}>
        <Stagger gap={0.14} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 30 }}>
          <Rise>
            <div style={{ fontSize: 34, color: T.text, lineHeight: 1.35, maxWidth: 1060 }}>
              Collect <Accent color="emerald">curated examples</Accent> — a question and its ideal
              answer — and train the model to reproduce them.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 26, color: T.textMuted, lineHeight: 1.45, maxWidth: 1020 }}>
              It works, but it <b style={{ color: T.white }}>saturates</b>: great data is slow and
              expensive, and the model never gets better than the answers we hand it.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
