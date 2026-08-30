import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

const FRAMEWORKS = [
  { name: "OpenEnv", who: "Meta", line: "HTTP + MCP · Rubric rewards" },
  { name: "Verifiers", who: "Prime Intellect", line: "in-process · dataset+tools+rubric" },
  { name: "OpenReward", who: "ORS", line: "per-tool-call rewards" },
  { name: "Harbor", who: "Laude Institute", line: "agent harnesses in containers" },
];

export function FrameworksSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={12} kicker="The unifiers" title={<>Frameworks step in</>}>
      <div
        style={{
          position: "absolute",
          top: 236,
          left: 96,
          right: 96,
          fontSize: 28,
          color: T.textMuted,
          maxWidth: 1080,
        }}
      >
        Frameworks stepped in to <Accent color="emerald">standardize all these different
        components</Accent>.
      </div>

      <div
        style={{
          position: "absolute",
          top: 322,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 24,
        }}
      >
        {FRAMEWORKS.map((f, i) => (
          <motion.div
            key={f.name}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", damping: 22, delay: 0.3 + i * 0.12 }}
            style={{
              border: `1.5px solid ${T.border}`,
              borderLeft: `3px solid ${T.lavender}`,
              borderRadius: 12,
              padding: "22px 26px",
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
              <span style={{ fontSize: 34, fontWeight: 700, color: T.white }}>{f.name}</span>
              <span style={{ fontFamily: MONO, fontSize: 20, color: T.emerald }}>{f.who}</span>
            </div>
            <div style={{ fontFamily: MONO, fontSize: 20, color: T.textDim }}>{f.line}</div>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.0 }}
        style={{
          position: "absolute",
          bottom: 96,
          left: 96,
          right: 96,
          fontFamily: MONO,
          fontSize: 20,
          color: T.textDim,
        }}
      >
        …plus NeMo Gym (NVIDIA) · SkyRL Gym (Berkeley) · GEM — same concept, different dialects.
      </motion.div>
    </SlideShell>
  );
}
