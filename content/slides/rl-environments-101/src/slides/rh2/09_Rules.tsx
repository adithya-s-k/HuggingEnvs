import { motion } from "framer-motion";
import { SlideShell } from "../../components/SlideShell";
import { Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";

const RULES = [
  "Make the verifier trustworthy first — gold 1.0, no-op 0.0, only targeted tests",
  "Strip the answer from the prompt",
  "Scrub the repo to the base commit",
  "Pre-bake dependencies, run offline by default",
  "If network is needed — allowlist, never a full block",
  "Keep the gold patch & hidden tests out of the container",
];

export function RH2RulesSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The takeaway" title={<>Trust lives in the environment</>}>
      <div style={{ position: "absolute", top: 210, left: 96, right: 96, fontSize: 25, color: T.textMuted }}>
        The environment <b style={{ color: T.white }}>enforces</b> it — the prompt never asks for it.
      </div>

      <div style={{ position: "absolute", top: 268, left: 96, right: 96, display: "flex", flexDirection: "column", gap: 13 }}>
        {RULES.map((r, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ type: "spring", damping: 22, delay: 0.3 + i * 0.08 }}
            style={{ display: "flex", gap: 16, alignItems: "baseline", fontSize: 23, color: T.text }}
          >
            <span style={{ fontFamily: MONO, fontSize: 18, color: T.emerald, fontWeight: 800, width: 30, flex: "0 0 auto" }}>
              {String(i + 1).padStart(2, "0")}
            </span>
            <span>{r}</span>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.0 }}
        style={{ position: "absolute", bottom: 56, left: 96, right: 96, fontSize: 22, color: T.textDim }}
      >
        All of it is baked into <Accent color="emerald">Repo2RLEnv</Accent> — the trust lives in the box by default.
      </motion.div>
    </SlideShell>
  );
}
