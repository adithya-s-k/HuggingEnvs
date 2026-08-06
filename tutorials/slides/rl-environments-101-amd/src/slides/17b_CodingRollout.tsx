import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent, spring } from "../components/primitives";

type Line =
  | { k: "think"; t: string }
  | { k: "cmd"; t: string }
  | { k: "out"; t: string }
  | { k: "ans"; t: string };

// Trimmed to six lines each: the type is large enough to read from the back of
// a hall, which costs a line of transcript per rollout.
const WIN: Line[] = [
  { k: "think", t: "List the Python files." },
  { k: "cmd", t: "ls *.py" },
  { k: "out", t: "data.py  model.py  train.py" },
  { k: "cmd", t: "wc -l *.py" },
  { k: "out", t: "40 data.py  85 model.py  120 train.py" },
  { k: "ans", t: "train.py" },
];

const LOSE: Line[] = [
  { k: "think", t: "I’ll guess from the names." },
  { k: "cmd", t: "ls" },
  { k: "out", t: "data.py  model.py  train.py  readme" },
  { k: "cmd", t: "head model.py" },
  { k: "out", t: "import torch ..." },
  { k: "ans", t: "model.py" },
];

// A terminal reads as a terminal in both themes, so these stay fixed rather
// than going through the palette — but the greys are lifted well above GitHub's
// defaults, which are tuned for reading at arm's length, not from row 20.
const TERM = {
  bg: "#0d1117",
  chrome: "#161b22",
  border: "#30363d",
  label: "#a9b4c2",
  think: "#aeb9c7",
  out: "#9aa5b3",
  cmd: "#e6e2a8",
};

function Sandbox({ n, lines, pass, delay }: { n: number; lines: Line[]; pass: boolean; delay: number }) {
  const { T } = useTheme();
  const accent = pass ? T.emerald : "#ff5470";
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 24, delay }}
      style={{
        background: TERM.bg,
        border: `1px solid ${TERM.border}`,
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
          background: TERM.chrome,
          borderBottom: `1px solid ${TERM.border}`,
          fontFamily: MONO,
          fontSize: 17,
          color: TERM.label,
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f56" }} />
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ffbd2e" }} />
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#27c93f" }} />
          <span style={{ marginLeft: 8 }}>rollout {n}</span>
        </span>
      </div>

      {/* body */}
      <div style={{ padding: "14px 20px 16px", fontFamily: MONO, fontSize: 21, lineHeight: 1.42 }}>
        {lines.map((l, i) => {
          if (l.k === "think")
            return (
              <div key={i} style={{ color: TERM.think, fontStyle: "italic", margin: "6px 0 6px" }}>
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
                  paddingLeft: 11,
                  margin: "6px 0 2px",
                }}
              >
                <span
                  style={{
                    fontSize: 13,
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
                <span style={{ color: TERM.cmd }}>{l.t}</span>
              </div>
            );
          if (l.k === "out")
            return (
              <div key={i} style={{ color: TERM.out, paddingLeft: 14 }}>
                {l.t}
              </div>
            );
          return (
            <div key={i} style={{ color: accent, fontWeight: 700, marginTop: 12, fontSize: 25 }}>
              {pass ? "✓" : "✗"} answer: {l.t}
            </div>
          );
        })}
      </div>

      {/* The reward the environment hands back — the punchline of the box, so it
          lands at the end of the transcript rather than up in the title bar. */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "13px 20px",
          background: TERM.chrome,
          borderTop: `1px solid ${TERM.border}`,
          fontFamily: MONO,
        }}
      >
        <span style={{ fontSize: 18, color: TERM.label, letterSpacing: 2 }}>REWARD</span>
        <span style={{ fontSize: 30, fontWeight: 800, color: accent, letterSpacing: -0.5 }}>
          {pass ? "+1" : "0"}
        </span>
      </div>
    </motion.div>
  );
}

export function CodingRolloutSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Rollouts" title={<>Same task, many attempts</>}>
      <div
        style={{
          position: "absolute",
          top: 168,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 36,
        }}
      >
        <Sandbox n={1} lines={WIN} pass delay={0.3} />
        <Sandbox n={2} lines={LOSE} pass={false} delay={0.45} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring, delay: 0.95 }}
        style={{
          position: "absolute",
          bottom: 92,
          left: 96,
          right: 96,
          fontSize: 30,
          color: T.textMuted,
          lineHeight: 1.35,
        }}
      >
        The environment scores every attempt — GRPO nudges the model toward{" "}
        <Accent color="emerald">the ones that pay</Accent>.
      </motion.div>
    </SlideShell>
  );
}
