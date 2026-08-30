import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";
import qwen from "../assets/qwen-scaling.png";

const STATS = [
  { n: "~20", who: "Qwen3", what: "general-domain tasks" },
  { n: "20K", who: "Qwen3-Coder", what: "parallel environments" },
  { n: "100K+", who: "MiniMax Forge", what: "real-world environments" },
  { n: "1M+", who: "Qwen3.5", what: "agent environments" },
];

export function ScaleSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={8} kicker="Why now" title={<>More environments → better models</>}>
      <div
        style={{
          position: "absolute",
          top: 190,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1.35fr 1fr",
          gap: 48,
          alignItems: "center",
        }}
      >
        {/* Qwen chart */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.25 }}
          style={{ background: "#fff", borderRadius: 14, padding: 14, border: `1.5px solid ${T.border}` }}
        >
          <img src={qwen} alt="Qwen3.5 environment scaling" style={{ width: "100%", display: "block", borderRadius: 6 }} />
          <div style={{ fontFamily: MONO, fontSize: 14, color: "#555", marginTop: 6, textAlign: "center" }}>
            Qwen3.5 · average ranking vs. # training environments
          </div>
        </motion.div>

        {/* the numbers, with what each is */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {STATS.map((s, i) => (
            <motion.div
              key={s.who}
              initial={{ opacity: 0, x: 18 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: "spring", damping: 22, delay: 0.4 + i * 0.12 }}
              style={{ display: "flex", alignItems: "baseline", gap: 18 }}
            >
              <span
                style={{
                  fontFamily: MONO,
                  fontSize: 40,
                  fontWeight: 800,
                  color: T.emerald,
                  width: 118,
                  flex: "0 0 auto",
                  whiteSpace: "nowrap",
                }}
              >
                {s.n}
              </span>
              <span style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 24, color: T.white, fontWeight: 600 }}>{s.who}</span>
                <span style={{ fontFamily: MONO, fontSize: 17, color: T.textDim }}>{s.what}</span>
              </span>
            </motion.div>
          ))}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.0 }}
            style={{ fontSize: 21, color: T.textMuted, lineHeight: 1.4, marginTop: 8 }}
          >
            Each model was trained on that many environments — from a handful to{" "}
            <Accent color="emerald">millions</Accent>.
          </motion.div>
        </div>
      </div>
    </SlideShell>
  );
}
