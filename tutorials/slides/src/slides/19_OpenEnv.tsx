import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { Bullet, Accent, Stagger, Rise } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { HFMark } from "../components/figures";
import { PyTorchLogo, MetaLogo } from "../components/logos";

export function OpenEnvSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={17} kicker="OpenEnv" title={<>One shape for every env</>}>
      {/* provenance lockup */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, type: "spring", damping: 22 }}
        style={{
          position: "absolute",
          top: 244,
          left: 96,
          right: 96,
          display: "flex",
          alignItems: "center",
          gap: 18,
          fontFamily: MONO,
          fontSize: 22,
          color: T.textDim,
        }}
      >
        <PyTorchLogo size={34} />
        <MetaLogo size={30} color={T.text} />
        <span>started at Meta · PyTorch</span>
        <span style={{ color: T.lavender, fontSize: 26 }}>→</span>
        <HFMark size={30} />
        <span style={{ color: T.white }}>now maintained by Hugging Face</span>
      </motion.div>

      <div style={{ position: "absolute", top: 330, left: 96, right: 96 }}>
        <Stagger gap={0.1} delay={0.4} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <Rise>
            <Bullet>
              <Accent color="emerald">Gym-style API</Accent> — <code>reset()</code> /{" "}
              <code>step()</code>, just like OpenAI Gym
            </Bullet>
          </Rise>
          <Rise>
            <Bullet>
              <Accent color="emerald">First-class MCP</Accent> — any agent can talk to any env
            </Bullet>
          </Rise>
          <Rise>
            <Bullet>
              <Accent color="emerald">Built-in Rubric</Accent> — rewards live inside the env
            </Bullet>
          </Rise>
          <Rise>
            <Bullet>
              <Accent color="emerald">Task API</Accent> — serve your tasks / dataset
            </Bullet>
          </Rise>
          <Rise>
            <Bullet marker="★">
              <b style={{ color: T.white }}>1000+ environments</b> already on the Hub
            </Bullet>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
