import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

const ROLLOUTS = [
  { pass: true, note: "ls → wc → train.py" },
  { pass: false, note: "cat files → wrong guess" },
  { pass: true, note: "wc -l → train.py" },
  { pass: false, note: "gave up early" },
];

function RolloutCard({ pass, note, i }: { pass: boolean; note: string; i: number }) {
  const { T } = useTheme();
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 22, delay: 0.3 + i * 0.12 }}
      style={{
        border: `1.5px solid ${pass ? T.emerald : T.border}`,
        borderRadius: 14,
        padding: "22px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
        alignItems: "center",
        textAlign: "center",
      }}
    >
      <span style={{ fontFamily: MONO, fontSize: 15, letterSpacing: 1, color: T.textDim }}>
        rollout {i + 1}
      </span>
      <span style={{ fontSize: 44 }}>{pass ? "✅" : "❌"}</span>
      <span style={{ fontFamily: MONO, fontSize: 16, color: T.textMuted, lineHeight: 1.35 }}>{note}</span>
      <span style={{ fontFamily: MONO, fontSize: 20, fontWeight: 700, color: pass ? T.emerald : T.textDim }}>
        {pass ? "+1" : "0"}
      </span>
    </motion.div>
  );
}

export function CodingRolloutsSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Many rollouts" title={<>Try it many times, keep what works</>}>
      <div
        style={{
          position: "absolute",
          top: 250,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 22,
        }}
      >
        {ROLLOUTS.map((r, i) => (
          <RolloutCard key={i} {...r} i={i} />
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.9, type: "spring", damping: 22 }}
        style={{ position: "absolute", bottom: 110, left: 96, right: 96, fontSize: 30, color: T.textMuted, lineHeight: 1.4 }}
      >
        GRPO samples <Accent color="emerald">N rollouts per task</Accent> and nudges the model toward
        the ones that score.
      </motion.div>
    </SlideShell>
  );
}
