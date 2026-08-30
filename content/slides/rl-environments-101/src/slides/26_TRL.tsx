import { SlideShell } from "../components/SlideShell";
import { Bullet, Accent, Stagger, Rise } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { HFMark } from "../components/figures";

export function TRLSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={23} kicker="TRL" title={<>Train with it — directly</>}>
      <div
        style={{
          position: "absolute",
          top: 236,
          left: 96,
          display: "flex",
          alignItems: "center",
          gap: 14,
          fontFamily: MONO,
          fontSize: 22,
          color: T.textMuted,
        }}
      >
        <HFMark size={30} />
        <span>
          <b style={{ color: T.emerald }}>TRL</b> — the RL post-training library, maintained by
          Hugging Face
        </span>
      </div>

      <div style={{ position: "absolute", top: 320, left: 96, right: 96 }}>
        <Stagger gap={0.12} delay={0.35} style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <Rise>
            <Bullet>
              Trains against an environment <Accent color="emerald">directly</Accent> — pass the env,
              get GRPO
            </Bullet>
          </Rise>
          <Rise>
            <Bullet>
              <Accent color="emerald">OpenEnv</Accent> — first-class support
            </Bullet>
          </Rise>
          <Rise>
            <Bullet>
              Also supports <b style={{ color: T.white }}>OpenReward</b> &amp;{" "}
              <b style={{ color: T.white }}>Harbor</b> environments{" "}
              <span style={{ color: T.textDim }}>(experimental)</span>
            </Bullet>
          </Rise>
          <Rise>
            <Bullet marker="★">
              A few lines of config → training on <Accent color="emerald">any environment</Accent>
            </Bullet>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
