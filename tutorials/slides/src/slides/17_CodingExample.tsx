import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

function Block({ label, children, i }: { label: string; children: React.ReactNode; i: number }) {
  const { T } = useTheme();
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 22, delay: 0.3 + i * 0.15 }}
      style={{
        border: `1.5px solid ${T.border}`,
        borderLeft: `3px solid ${T.emerald}`,
        borderRadius: 14,
        padding: "22px 28px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <span style={{ fontFamily: MONO, fontSize: 17, letterSpacing: 2, color: T.textDim, textTransform: "uppercase" }}>
        {label}
      </span>
      <div style={{ fontSize: 30, color: T.text, lineHeight: 1.35 }}>{children}</div>
    </motion.div>
  );
}

export function CodingExampleSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="By example" title={<>A coding environment</>}>
      <div style={{ position: "absolute", top: 210, left: 96, right: 96, display: "flex", flexDirection: "column", gap: 22 }}>
        <Block label="Task" i={0}>
          Find the <code style={{ color: T.emerald }}>.py</code> file with the most lines.
        </Block>
        <Block label="Tool" i={1}>
          The model gets one tool: <code style={{ color: T.emerald }}>bash</code> — run any shell
          command in a sandbox.
        </Block>
        <Block label="Reward" i={2}>
          <span style={{ color: T.emerald }}>+1</span> if the final answer is correct, else{" "}
          <span style={{ color: T.textMuted }}>0</span>.
        </Block>
      </div>
    </SlideShell>
  );
}
