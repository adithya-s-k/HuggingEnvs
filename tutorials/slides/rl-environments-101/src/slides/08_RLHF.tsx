import { SlideShell } from "../components/SlideShell";
import { Timeline } from "../components/Timeline";
import { Stagger, Rise, Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

export function RLHFSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={6} kicker="RLHF" title={<>Let people pick the better answer</>}>
      <div style={{ position: "absolute", top: 210, left: 96, right: 96 }}>
        <Timeline active={2} compact animate={false} />
      </div>

      <div style={{ position: "absolute", top: 320, left: 96, right: 96 }}>
        <Stagger gap={0.14} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 30 }}>
          <Rise>
            <div style={{ fontSize: 34, color: T.text, lineHeight: 1.35, maxWidth: 1060 }}>
              We can’t write the perfect answer for everything. So let the model try — and have a
              person say <Accent color="emerald">which answer is better</Accent>.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 26, color: T.textMuted, lineHeight: 1.45, maxWidth: 1020 }}>
              “Better” becomes the <b style={{ color: T.white }}>reward</b>, and we nudge the model
              toward it. This is where <Accent color="emerald">RL enters</Accent> — but people can’t
              rate everything.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
