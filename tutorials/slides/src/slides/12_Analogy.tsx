import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

const MAP = [
  { from: "Agent", to: "the LLM", sub: "policy · token gen" },
  { from: "Environment", to: "a sandbox", sub: "tools · code · state" },
  { from: "Reward", to: "a verifier", sub: "rubric · check" },
];

export function AnalogySlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={10} kicker="The bridge" title={<>Same idea — for LLMs</>}>
      <div
        style={{
          position: "absolute",
          top: 250,
          left: 96,
          right: 96,
          display: "flex",
          flexDirection: "column",
          gap: 26,
        }}
      >
        {MAP.map((m, i) => (
          <motion.div
            key={m.from}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ type: "spring", damping: 22, delay: 0.3 + i * 0.16 }}
            style={{ display: "flex", alignItems: "center", gap: 28 }}
          >
            {/* classical side box */}
            <div
              style={{
                width: 300,
                padding: "18px 26px",
                border: `1.5px solid ${T.border}`,
                borderRadius: 12,
                fontFamily: MONO,
                fontSize: 30,
                color: T.textMuted,
                textAlign: "center",
              }}
            >
              {m.from}
            </div>

            <div style={{ fontSize: 36, color: T.lavender }}>→</div>

            {/* LLM side box (highlighted) */}
            <div
              style={{
                flex: 1,
                padding: "16px 28px",
                border: `1.5px solid ${T.border}`,
                borderLeft: `3px solid ${T.emerald}`,
                borderRadius: 12,
                display: "flex",
                alignItems: "baseline",
                gap: 18,
              }}
            >
              <span style={{ fontSize: 36, fontWeight: 700, color: T.emerald }}>{m.to}</span>
              <span style={{ fontFamily: MONO, fontSize: 22, color: T.textDim }}>{m.sub}</span>
            </div>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.0 }}
        style={{ position: "absolute", bottom: 90, left: 96, right: 96, fontSize: 26, color: T.textMuted }}
      >
        Same skeleton — what changes is the{" "}
        <b style={{ color: T.white }}>tools, observations, and reward rule</b>.
      </motion.div>
    </SlideShell>
  );
}
