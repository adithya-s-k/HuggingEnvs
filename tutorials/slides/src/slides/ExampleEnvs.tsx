import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { HFMark } from "../components/figures";

export function ExampleEnvsSlide() {
  const { T, glow } = useTheme();
  return (
    <SlideShell kicker="Try it" title={<>Already generated — go play</>}>
      <div style={{ position: "absolute", top: 260, left: 96, right: 96, display: "flex", flexDirection: "column", gap: 30 }}>
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
          style={{ display: "flex", alignItems: "baseline", gap: 24 }}
        >
          <span style={{ fontFamily: MONO, fontSize: 110, fontWeight: 800, color: T.emerald, textShadow: glow.emeraldText, lineHeight: 1 }}>
            ~1,000
          </span>
          <span style={{ fontSize: 36, color: T.white, fontWeight: 600 }}>verifiable RL environments</span>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.45 }}
          style={{ fontSize: 32, color: T.textMuted, lineHeight: 1.4, maxWidth: 1080 }}
        >
          Generated with <Accent color="emerald">Repo2RLEnv</Accent> and live on Hugging Face — and
          we’re scaling further. <Accent color="emerald">Contributions welcome.</Accent>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
          style={{ display: "flex", alignItems: "center", gap: 12, fontFamily: MONO, fontSize: 24, color: T.textDim, marginTop: 4 }}
        >
          <HFMark size={28} />
          <span>hf.co/collections/AdithyaSK/repo2rlenv…</span>
        </motion.div>
      </div>
    </SlideShell>
  );
}
