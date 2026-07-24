import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

function Box({
  label,
  sub,
  tone = "plain",
  i,
}: {
  label: string;
  sub?: string;
  tone?: "plain" | "key";
  i: number;
}) {
  const { T } = useTheme();
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 24, delay: 0.25 + i * 0.05 }}
      style={{
        width: 300,
        background: T.bgRaised,
        border: `1.5px solid ${tone === "key" ? T.emerald : T.border}`,
        borderRadius: 10,
        padding: "8px 16px",
        textAlign: "center",
      }}
    >
      <span style={{ fontSize: 23, fontWeight: 600, color: tone === "key" ? T.emerald : T.text }}>
        {label}
      </span>
      {sub && <span style={{ fontFamily: MONO, fontSize: 14, color: T.textDim, marginLeft: 8 }}>{sub}</span>}
    </motion.div>
  );
}

function Arrow() {
  const { T } = useTheme();
  return <span style={{ color: T.lavender, fontSize: 18, lineHeight: 1 }}>↓</span>;
}

export function EnvTypesSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Env types" title={<>Not all environments are equal</>}>
      <div
        style={{
          position: "absolute",
          top: 150,
          left: 130,
          right: 130,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          columnGap: 150,
        }}
      >
        {/* one-shot RLVR */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 7 }}>
          <div style={{ fontSize: 25, fontWeight: 700, color: T.white }}>One-shot · RLVR</div>
          <div style={{ fontFamily: MONO, fontSize: 15, color: T.textDim, marginBottom: 6 }}>
            math · code · logic
          </div>
          <Box label="Prompt" i={0} />
          <Arrow />
          <Box label="LLM" i={1} />
          <Arrow />
          <Box label="Answer" i={2} />
          <Arrow />
          <Box label="Verifier" sub="binary reward" tone="key" i={3} />
          <div style={{ fontFamily: MONO, fontSize: 16, color: T.textMuted, marginTop: 12, textAlign: "center" }}>
            1 turn · stateless · reward every rollout
          </div>
        </div>

        {/* multi-turn Agent RL */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 7 }}>
          <div style={{ fontSize: 25, fontWeight: 700, color: T.white }}>Multi-turn · Agent RL</div>
          <div style={{ fontFamily: MONO, fontSize: 15, color: T.textDim, marginBottom: 6 }}>
            SWE-bench · OSWorld · AppWorld
          </div>
          <Box label="Task" i={0} />
          <Arrow />
          {/* loop zone: agent → action → environment → observation, with ×T back-arrow */}
          <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", gap: 7 }}>
            <Box label="LLM agent" i={1} />
            <Arrow />
            <Box label="Action" i={2} />
            <Arrow />
            <Box label="Environment" sub="stateful" tone="key" i={3} />
            <Arrow />
            <Box label="Observation" i={4} />
            <LoopArrow />
          </div>
          <Arrow />
          <Box label="Reward" sub="sparse · delayed" tone="key" i={5} />
          <div style={{ fontFamily: MONO, fontSize: 16, color: T.textMuted, marginTop: 12, textAlign: "center" }}>
            10–100+ turns · reward at the end
          </div>
        </div>
      </div>
    </SlideShell>
  );
}

// A bracket hugging the right edge of the loop zone, with an arrowhead at the
// top pointing back into the LLM agent — the observation → agent feedback loop.
function LoopArrow() {
  const { T } = useTheme();
  return (
    <div
      style={{
        position: "absolute",
        top: 14,
        bottom: 14,
        right: -52,
        width: 34,
        border: `2px solid ${T.lavender}`,
        borderLeft: "none",
        borderTopRightRadius: 10,
        borderBottomRightRadius: 10,
      }}
    >
      {/* arrowhead at top, pointing left toward the LLM agent */}
      <div
        style={{
          position: "absolute",
          top: -6,
          left: -6,
          width: 0,
          height: 0,
          borderTop: "6px solid transparent",
          borderBottom: "6px solid transparent",
          borderRight: `9px solid ${T.lavender}`,
        }}
      />
      <span
        style={{
          position: "absolute",
          top: "50%",
          right: -34,
          transform: "translateY(-50%)",
          fontFamily: MONO,
          fontSize: 18,
          fontWeight: 700,
          color: T.emerald,
        }}
      >
        ×T
      </span>
    </div>
  );
}
