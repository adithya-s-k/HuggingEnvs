import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { CodeBlock } from "../components/CodeBlock";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

const CODE = `import gymnasium as gym

env = gym.make("CartPole-v1")
obs, info = env.reset()

done = False
while not done:
    action = policy(obs)            # agent decides
    obs, reward, done, _, _ = env.step(action)`;

const POINTS = [
  <>
    <code>reset()</code> → first observation
  </>,
  <>
    <code>step(action)</code> → <Accent color="emerald">obs, reward, done</Accent>
  </>,
  <>
    <code>action_space</code> · <code>observation_space</code>
  </>,
  <>
    any agent ↔ any env · <b>reproducible</b>
  </>,
];

export function GymAPISlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="OpenAI Gym" title={<>One API for every environment</>}>
      <div
        style={{
          position: "absolute",
          top: 205,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "0.85fr 1.15fr",
          gap: 44,
          alignItems: "center",
        }}
      >
        {/* left — compact points */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
          style={{ display: "flex", flexDirection: "column", gap: 16 }}
        >
          <div style={{ fontSize: 23, color: T.textMuted, lineHeight: 1.4, marginBottom: 6 }}>
            Before Gym, every env had its own interface. Gym{" "}
            <span style={{ color: T.textDim }}>(2016 → Gymnasium)</span> gave RL{" "}
            <Accent color="emerald">one contract</Accent>.
          </div>
          {POINTS.map((p, i) => (
            <div key={i} style={{ display: "flex", gap: 14, alignItems: "baseline", fontSize: 24, color: T.text }}>
              <span style={{ color: T.emerald, fontWeight: 800 }}>▸</span>
              <span>{p}</span>
            </div>
          ))}
        </motion.div>

        {/* right — the canonical loop */}
        <div>
          <CodeBlock filename="cartpole.py" code={CODE} fontSize={16} delay={0.45} />
          <div style={{ fontSize: 19, color: T.textDim, marginTop: 14, textAlign: "center" }}>
            <Accent color="emerald">CartPole-v1</Accent> — the “hello world” you just saw.
          </div>
        </div>
      </div>
    </SlideShell>
  );
}
