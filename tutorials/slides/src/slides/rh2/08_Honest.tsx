import { motion } from "framer-motion";
import { SlideShell } from "../../components/SlideShell";
import { Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";

export function RH2HonestSlide() {
  const { T, glow } = useTheme();
  return (
    <SlideShell kicker="What honest looks like" title={<>So I cut the egress</>}>
      <div
        style={{
          position: "absolute",
          top: 240,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1.15fr 1fr",
          gap: 48,
          alignItems: "center",
        }}
      >
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
          style={{ fontSize: 34, color: T.text, lineHeight: 1.4 }}
        >
          An <Accent color="emerald">allowlist</Accent>, not a block. And for the first time, Opus{" "}
          <b style={{ color: T.white }}>actually worked the bug</b>.
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", damping: 14, delay: 0.5 }}
          style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}
        >
          <div style={{ fontFamily: MONO, fontSize: 20, color: T.textDim, letterSpacing: 2 }}>reward</div>
          <div style={{ fontFamily: MONO, fontSize: 120, fontWeight: 800, color: T.emerald, textShadow: glow.emeraldText, lineHeight: 1 }}>
            0.000
          </div>
          <div style={{ fontSize: 22, color: T.emerald, fontWeight: 700 }}>the number I wanted</div>
        </motion.div>
      </div>

      <div style={{ position: "absolute", bottom: 70, left: 96, right: 96, fontSize: 25, color: T.textMuted }}>
        Every green before was <b style={{ color: "#ff5470" }}>contamination</b>. Real solve ≈ 0.
      </div>
    </SlideShell>
  );
}
