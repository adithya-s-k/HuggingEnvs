import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

// The talk portion — topics may shift as we go.
const TOPICS = [
  "What RL environments are",
  "Why we need them",
  "OpenEnv & TRL",
  "Generating environments",
  "Reward hacking",
];

function Topic({ n, label, i }: { n: number; label: string; i: number }) {
  const { T } = useTheme();
  return (
    <motion.div
      initial={{ opacity: 0, x: 18 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ type: "spring", damping: 22, delay: 0.3 + i * 0.08 }}
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: 22,
        padding: "12px 0",
        borderBottom: `1px solid ${T.border}`,
      }}
    >
      <span
        style={{
          fontFamily: MONO,
          fontSize: 22,
          fontWeight: 700,
          color: T.textDim,
          width: 44,
          flex: "0 0 auto",
        }}
      >
        {String(n).padStart(2, "0")}
      </span>
      <span style={{ fontSize: 34, fontWeight: 600, color: T.text }}>{label}</span>
    </motion.div>
  );
}

export function AgendaSlide() {
  const { T } = useTheme();

  return (
    <SlideShell index={2} kicker="Roadmap" title={<>What we’ll cover</>}>
      <div style={{ position: "absolute", top: 236, left: 96, right: 96 }}>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          style={{
            fontFamily: MONO,
            fontSize: 18,
            letterSpacing: 2,
            color: T.textDim,
            textTransform: "uppercase",
            marginBottom: 6,
          }}
        >
          The talk
        </motion.div>

        {TOPICS.map((t, i) => (
          <Topic key={t} n={i + 1} label={t} i={i} />
        ))}

        {/* then → hands-on */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.85 }}
          style={{
            marginTop: 34,
            display: "flex",
            alignItems: "center",
            gap: 18,
            fontSize: 30,
          }}
        >
          <span style={{ fontFamily: MONO, fontSize: 24, color: T.textDim }}>
            then →
          </span>
          <Accent color="emerald">Q &amp; A</Accent>
        </motion.div>
      </div>
    </SlideShell>
  );
}
