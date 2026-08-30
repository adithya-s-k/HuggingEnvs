import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

const SUPERVISED = ["Dataset", "Model", "Trainer"];
const RL_PARTS = [
  "Tasks", "Prompt template", "Initial state", "Tools / harness",
  "Observation", "Execution backend", "State", "Reward / rubric",
  "Done", "Episode control", "Transport",
];

export function ContrastSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={11} kicker="Why it’s harder" title={<>A lot more to wire up</>}>
      <div
        style={{
          position: "absolute",
          top: 210,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 1.4fr",
          gap: 40,
          alignItems: "start",
        }}
      >
        {/* supervised */}
        <div
          style={{
            border: `1.5px solid ${T.border}`,
            borderRadius: 16,
            padding: "28px 30px",
          }}
        >
          <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 2, color: T.textDim, textTransform: "uppercase", marginBottom: 22 }}>
            Supervised
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {SUPERVISED.map((s, i) => (
              <motion.div
                key={s}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + i * 0.1, type: "spring", damping: 22 }}
                style={{
                  fontSize: 30,
                  color: T.white,
                  padding: "16px 22px",
                  border: `1.5px solid ${T.border}`,
                  borderRadius: 12,
                }}
              >
                {s}
              </motion.div>
            ))}
            <div style={{ fontSize: 22, color: T.textDim, marginTop: 6 }}>swap freely · done</div>
          </div>
        </div>

        {/* RL */}
        <div
          style={{
            border: `1.5px solid ${T.borderStrong}`,
            borderRadius: 16,
            padding: "28px 30px",
          }}
        >
          <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 2, color: T.textDim, textTransform: "uppercase", marginBottom: 22 }}>
            Reinforcement learning
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            {RL_PARTS.map((p, i) => (
              <motion.span
                key={p}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.5 + i * 0.05, type: "spring", damping: 20 }}
                style={{
                  fontFamily: MONO,
                  fontSize: 22,
                  color: T.text,
                  padding: "10px 16px",
                  border: `1.5px solid ${T.borderStrong}`,
                  borderRadius: 999,
                }}
              >
                {p}
              </motion.span>
            ))}
          </div>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2 }}
            style={{ fontSize: 26, color: T.textMuted, marginTop: 26 }}
          >
            same goal — <Accent color="emerald">many more moving parts</Accent>.
          </motion.div>
        </div>
      </div>
    </SlideShell>
  );
}
