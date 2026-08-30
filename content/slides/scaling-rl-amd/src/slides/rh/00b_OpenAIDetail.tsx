import { SlideShell } from "../../components/SlideShell";
import { Stagger, Rise, Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";

const RED = "#ff3b5c";

export function RHOpenAIDetailSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="What happened" title={<>Hyperfocused on the score</>}>
      <div style={{ position: "absolute", top: 210, left: 96, right: 96 }}>
        <Stagger gap={0.13} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <Rise>
            <div style={{ fontSize: 30, color: T.text, lineHeight: 1.4, maxWidth: 1060 }}>
              GPT-5.6 <b style={{ color: T.white }}>“Sol”</b> (+ an unreleased model) was tested on{" "}
              <Accent color="emerald">ExploitGym</Accent> — 898 real vulnerabilities, scored
              pass/fail.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 30, color: T.textMuted, lineHeight: 1.4, maxWidth: 1060 }}>
              Instead of solving them, it <b style={{ color: T.white }}>escaped the sandbox</b>,
              chained zero-days, and read the answer key straight from{" "}
              <span style={{ color: RED, fontWeight: 700 }}>Hugging Face’s production DB</span>.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 30, color: T.textMuted, lineHeight: 1.4, maxWidth: 1060 }}>
              Both caught it. The experts’ word for it?{" "}
              <b style={{ color: T.white }}>Reward hacking</b> — score high by gaming the setup, not
              doing the task.
            </div>
          </Rise>
          <Rise>
            <div
              style={{
                marginTop: 8,
                fontFamily: MONO,
                fontSize: 22,
                color: T.textMuted,
                borderLeft: `3px solid ${RED}`,
                paddingLeft: 18,
              }}
            >
              Frontier models. Same failure mode — just bolder.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
