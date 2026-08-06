import { SlideShell } from "../../components/SlideShell";
import { Stagger, Rise, Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";

export function RHTwistSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The twist" title={<>I changed one thing</>}>
      <div style={{ position: "absolute", top: 260, left: 96, right: 96 }}>
        <Stagger gap={0.15} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 30 }}>
          <Rise>
            <div style={{ fontSize: 40, color: T.text, lineHeight: 1.35, maxWidth: 1080 }}>
              Instead of asking the model to <span style={{ color: T.textMuted }}>solve the math</span>…
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 40, color: T.text, lineHeight: 1.35, maxWidth: 1080 }}>
              …I asked it to write <Accent color="emerald">Python that solves it</Accent> — and{" "}
              <Accent color="emerald">print the answer</Accent>.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
