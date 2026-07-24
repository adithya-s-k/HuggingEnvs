import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { HFMark } from "../components/figures";
import qr from "../assets/qr-collection.png";

export function ExampleEnvsSlide() {
  const { T, glow } = useTheme();
  return (
    <SlideShell kicker="Try it" title={<>Already generated — go play</>}>
      <div
        style={{
          position: "absolute",
          top: 236,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 320px",
          gap: 56,
          alignItems: "center",
        }}
      >
        {/* left — the collection */}
        <motion.div
          initial={{ opacity: 0, x: -18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
          style={{ display: "flex", flexDirection: "column", gap: 22 }}
        >
          <div style={{ display: "flex", alignItems: "baseline", gap: 20 }}>
            <span style={{ fontFamily: MONO, fontSize: 92, fontWeight: 800, color: T.emerald, textShadow: glow.emeraldText, lineHeight: 1 }}>
              ~1,000
            </span>
            <span style={{ fontSize: 30, color: T.white, fontWeight: 600 }}>verifiable RL environments</span>
          </div>
          <div style={{ fontSize: 28, color: T.textMuted, lineHeight: 1.4, maxWidth: 720 }}>
            Already generated with <Accent color="emerald">Repo2RLEnv</Accent> and live on Hugging
            Face — and we’re scaling further.
          </div>
          <div style={{ fontSize: 26, color: T.text }}>
            <Accent color="emerald">Contributions welcome.</Accent>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, fontFamily: MONO, fontSize: 19, color: T.textDim }}>
            <HFMark size={24} />
            <span>hf.co/collections/AdithyaSK/repo2rlenv…</span>
          </div>
        </motion.div>

        {/* right — QR to the collection */}
        <motion.div
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", damping: 18, delay: 0.45 }}
          style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}
        >
          <div style={{ background: "#fff", borderRadius: 18, padding: 16 }}>
            <img src={qr} alt="RL environments collection" style={{ width: 260, height: 260, display: "block", imageRendering: "pixelated" }} />
          </div>
          <div style={{ fontFamily: MONO, fontSize: 20, color: T.emerald }}>scan → the collection</div>
        </motion.div>
      </div>
    </SlideShell>
  );
}
