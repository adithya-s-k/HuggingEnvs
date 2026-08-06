import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

type Line =
  | { k: "think"; t: string }
  | { k: "cmd"; t: string }
  | { k: "out"; t: string }
  | { k: "ans"; t: string };

const WIN: Line[] = [
  { k: "think", t: "List the Python files first." },
  { k: "cmd", t: "ls *.py" },
  { k: "out", t: "data.py  model.py  train.py" },
  { k: "think", t: "Now count the lines." },
  { k: "cmd", t: "wc -l *.py" },
  { k: "out", t: "40 data.py  85 model.py  120 train.py" },
  { k: "ans", t: "train.py" },
];

const LOSE: Line[] = [
  { k: "think", t: "Quick peek at the directory." },
  { k: "cmd", t: "ls" },
  { k: "out", t: "data.py  model.py  train.py  readme" },
  { k: "think", t: "I'll guess from the names." },
  { k: "cmd", t: "head model.py" },
  { k: "out", t: "import torch ..." },
  { k: "ans", t: "model.py" },
];

function Sandbox({ n, lines, pass, delay }: { n: number; lines: Line[]; pass: boolean; delay: number }) {
  const { T } = useTheme();
  const accent = pass ? T.emerald : "#ff5470";
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 24, delay }}
      style={{
        background: "#0d1117",
        border: "1px solid #30363d",
        borderRadius: 14,
        overflow: "hidden",
        boxShadow: "0 14px 44px rgba(0,0,0,0.45)",
      }}
    >
      {/* header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "11px 18px",
          background: "#161b22",
          borderBottom: "1px solid #30363d",
          fontFamily: MONO,
          fontSize: 15,
          color: "#8b949e",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f56" }} />
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ffbd2e" }} />
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#27c93f" }} />
          <span style={{ marginLeft: 8 }}>sandbox · rollout {n}</span>
        </span>
        <span style={{ color: accent, fontWeight: 700 }}>{pass ? "reward +1" : "reward 0"}</span>
      </div>

      {/* body */}
      <div style={{ padding: "16px 20px", fontFamily: MONO, fontSize: 16.5, lineHeight: 1.5 }}>
        {lines.map((l, i) => {
          if (l.k === "think")
            return (
              <div key={i} style={{ color: "#8b949e", fontStyle: "italic", margin: "8px 0 4px" }}>
                🤖 {l.t}
              </div>
            );
          if (l.k === "cmd")
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  borderLeft: `3px solid ${accent}`,
                  paddingLeft: 10,
                  margin: "2px 0",
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    letterSpacing: 1,
                    color: accent,
                    border: `1px solid ${accent}`,
                    borderRadius: 5,
                    padding: "1px 6px",
                  }}
                >
                  BASH
                </span>
                <span style={{ color: "#dcdcaa" }}>{l.t}</span>
              </div>
            );
          if (l.k === "out")
            return (
              <div key={i} style={{ color: "#6e7681", paddingLeft: 13 }}>
                {l.t}
              </div>
            );
          return (
            <div key={i} style={{ color: accent, fontWeight: 700, marginTop: 10, fontSize: 19 }}>
              {pass ? "✓" : "✗"} answer: {l.t}
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

export function CodingRolloutSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="One rollout" title={<>Same task, two attempts</>}>
      <div
        style={{
          position: "absolute",
          top: 202,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 40,
        }}
      >
        <Sandbox n={1} lines={WIN} pass delay={0.3} />
        <Sandbox n={2} lines={LOSE} pass={false} delay={0.45} />
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9 }}
        style={{ position: "absolute", bottom: 74, left: 96, right: 96, textAlign: "center", fontSize: 25, color: T.textMuted }}
      >
        The environment runs the code and scores it — same task,{" "}
        <span style={{ color: T.emerald }}>different reward</span>.
      </motion.div>
    </SlideShell>
  );
}
