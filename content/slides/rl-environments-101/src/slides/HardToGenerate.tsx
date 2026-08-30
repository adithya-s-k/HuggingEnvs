import { SlideShell } from "../components/SlideShell";
import { Stagger, Rise, Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

export function HardToGenerateSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Generation" title={<>Making environments is hard</>}>
      <div style={{ position: "absolute", top: 260, left: 96, right: 96 }}>
        <Stagger gap={0.15} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 34 }}>
          <Rise>
            <div style={{ fontSize: 38, color: T.text, lineHeight: 1.35, maxWidth: 1080 }}>
              A good environment needs <Accent color="emerald">tasks that mirror the real world</Accent>{" "}
              — and a <Accent color="emerald">reward you can’t game</Accent>.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 30, color: T.textMuted, lineHeight: 1.4, maxWidth: 1020 }}>
              Hand-building that is slow. And RL wants{" "}
              <b style={{ color: T.white }}>thousands of them</b> — so doing it by hand
              <b style={{ color: T.white }}> doesn’t scale</b>.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
