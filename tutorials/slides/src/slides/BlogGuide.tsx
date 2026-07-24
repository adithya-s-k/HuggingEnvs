import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import hero from "../assets/blog-hero.png";
import qr from "../assets/qr-blog.png";

export function BlogGuideSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Go deeper" title={<>The ultimate guide to RL environments</>}>
      <div
        style={{
          position: "absolute",
          top: 210,
          left: 96,
          right: 96,
          bottom: 60,
          display: "grid",
          gridTemplateColumns: "1fr 300px",
          gap: 48,
          alignItems: "center",
        }}
      >
        {/* blog hero image */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
          style={{
            border: `1.5px solid ${T.border}`,
            borderRadius: 14,
            overflow: "hidden",
            boxShadow: "0 16px 50px rgba(0,0,0,0.45)",
          }}
        >
          <img src={hero} alt="The ultimate guide to RL environments" style={{ width: "100%", display: "block" }} />
        </motion.div>

        {/* QR */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", damping: 18, delay: 0.45 }}
          style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}
        >
          <div style={{ background: "#fff", borderRadius: 18, padding: 16 }}>
            <img src={qr} alt="Scan for the guide" style={{ width: 260, height: 260, display: "block", imageRendering: "pixelated" }} />
          </div>
          <div style={{ fontFamily: MONO, fontSize: 22, color: T.emerald, letterSpacing: 1 }}>
            scan to read →
          </div>
        </motion.div>
      </div>
    </SlideShell>
  );
}
