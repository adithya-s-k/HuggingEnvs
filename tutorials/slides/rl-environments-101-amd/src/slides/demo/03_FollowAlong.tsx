import { motion } from "framer-motion";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import { Accent } from "../../components/primitives";
import { GitHubMark } from "../../components/figures";
import qr from "../../assets/qr-tutorials.png";

export function DemoFollowAlongSlide() {
  const { T } = useTheme();
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: 80, padding: "0 90px" }}>
      <motion.div
        initial={{ opacity: 0, x: -18 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ type: "spring", damping: 22, delay: 0.25 }}
        style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 620 }}
      >
        <div style={{ fontFamily: MONO, fontSize: 22, letterSpacing: 5, color: T.textDim, textTransform: "uppercase" }}>
          Follow along
        </div>
        <div style={{ fontSize: 58, fontWeight: 800, color: T.white, lineHeight: 1.12 }}>
          Do it <Accent color="emerald">yourself</Accent> →
        </div>
        <div style={{ fontSize: 28, color: T.textMuted, lineHeight: 1.4 }}>
          The full tutorial — env, TRL, GRPO — runs on a free GPU. Scan and follow along.
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontFamily: MONO, fontSize: 21, color: T.text, marginTop: 6 }}>
          <GitHubMark size={26} color={T.text} />
          <span>github.com/adithya-s-k/RL_Envs_101 › tutorials</span>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", damping: 18, delay: 0.4 }}
        style={{ background: "#fff", borderRadius: 24, padding: 24, flex: "0 0 auto" }}
      >
        <img src={qr} alt="Tutorial QR" style={{ width: 380, height: 380, display: "block", imageRendering: "pixelated" }} />
      </motion.div>
    </div>
  );
}
