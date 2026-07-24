import { SlideShell } from "../../components/SlideShell";
import { Stagger, Rise, Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";

export function RHSetupSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Reward hacking · setup" title={<>Rewind to last year</>}>
      <div style={{ position: "absolute", top: 250, left: 96, right: 96 }}>
        <Stagger gap={0.15} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 32 }}>
          <Rise>
            <div style={{ fontSize: 38, color: T.text, lineHeight: 1.35, maxWidth: 1080 }}>
              <Accent color="emerald">GRPO</Accent> had just landed in TRL. Everyone was fine-tuning
              tiny models — <b style={{ color: T.white }}>Qwen 0.5B</b>, Llama 1B / 3B.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 30, color: T.textMuted, lineHeight: 1.4, maxWidth: 1020 }}>
              The task: get better at <Accent color="emerald">GSM8K</Accent> — grade-school math word
              problems.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
