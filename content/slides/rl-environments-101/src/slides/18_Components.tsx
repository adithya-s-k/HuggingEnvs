import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

const CARDS = [
  { c: "Tasks", v: "“fix this failing test”", d: "the problems it practises on" },
  { c: "Prompt", v: "task → chat message", d: "how the task is shown to the model" },
  { c: "Tools", v: "bash · run_code", d: "what the model can do" },
  { c: "Observation", v: "stdout / stderr", d: "what it sees back after acting" },
  { c: "State", v: "repo + files", d: "the world it changes across turns" },
  { c: "Execution", v: "sandbox container", d: "where the code actually runs" },
  { c: "Reward", v: "tests pass? 0 / 1", d: "how we score the attempt" },
  { c: "Done", v: "answer submitted", d: "when the episode ends" },
];

function Card({ c, v, d, i }: { c: string; v: string; d: string; i: number }) {
  const { T } = useTheme();
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 22, delay: 0.25 + i * 0.06 }}
      style={{
        border: `1.5px solid ${T.border}`,
        borderLeft: `3px solid ${T.emerald}`,
        borderRadius: 12,
        padding: "16px 24px",
        display: "flex",
        alignItems: "baseline",
        gap: 18,
      }}
    >
      <span style={{ fontFamily: MONO, fontSize: 24, fontWeight: 700, color: T.emerald, width: 190, flex: "0 0 auto" }}>
        {c}
      </span>
      <span style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <span style={{ fontSize: 24, color: T.white }}>{v}</span>
        <span style={{ fontSize: 17, color: T.textDim }}>{d}</span>
      </span>
    </motion.div>
  );
}

export function ComponentsSlide() {
  return (
    <SlideShell kicker="Components" title={<>Each piece, in the example</>}>
      <div
        style={{
          position: "absolute",
          top: 200,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 18,
        }}
      >
        {CARDS.map((card, i) => (
          <Card key={card.c} {...card} i={i} />
        ))}
      </div>
    </SlideShell>
  );
}
