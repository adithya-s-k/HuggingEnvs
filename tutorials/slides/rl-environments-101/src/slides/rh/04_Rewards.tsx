import { motion } from "framer-motion";
import { SlideShell } from "../../components/SlideShell";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";

const REWARDS = [
  { name: "format", detail: "right structure / XML", hot: false },
  { name: "correctness", detail: "final answer matches", hot: false },
  { name: "code_execution", detail: "runs cleanly → 0–2 bonus", hot: true },
];

function Row({ name, detail, hot, i }: { name: string; detail: string; hot: boolean; i: number }) {
  const { T } = useTheme();
  const accent = hot ? T.emerald : T.textMuted;
  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ type: "spring", damping: 22, delay: 0.3 + i * 0.14 }}
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: 22,
        padding: "18px 24px",
        border: `1.5px solid ${hot ? T.emerald : T.border}`,
        borderRadius: 12,
      }}
    >
      <span style={{ fontFamily: MONO, fontSize: 30, fontWeight: 700, color: accent, width: 320, flex: "0 0 auto" }}>
        {name}
      </span>
      <span style={{ fontSize: 26, color: T.text }}>{detail}</span>
    </motion.div>
  );
}

export function RHRewardsSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The rewards" title={<>What I rewarded</>}>
      <div style={{ position: "absolute", top: 250, left: 96, right: 96, display: "flex", flexDirection: "column", gap: 18 }}>
        {REWARDS.map((r, i) => (
          <Row key={r.name} {...r} i={i} />
        ))}
      </div>
      <div style={{ position: "absolute", bottom: 96, left: 96, right: 96, fontSize: 24, color: T.textDim }}>
        The last one felt harmless — reward code that just <b style={{ color: T.textMuted }}>runs</b>.
      </div>
    </SlideShell>
  );
}
