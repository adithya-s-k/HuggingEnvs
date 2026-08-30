import { motion } from "framer-motion";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import { Accent } from "../../components/primitives";
import thumb from "../../assets/cheating-agents.jpeg";
import qr from "../../assets/qr-rh2-thread.png";

export function RH2TitleSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0 } };
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.2, delayChildren: 0.15 } } }}
        style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 90px" }}
      >
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontFamily: MONO, fontSize: 18, letterSpacing: 5, color: T.textDim, textTransform: "uppercase", marginBottom: 22 }}>
          Reward hacking · example 2
        </motion.div>

        {/* Thumbnail plus a way out: if this section gets cut for time, the QR
            is the whole story and the room can read it later. */}
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ display: "flex", alignItems: "center", gap: 30, marginBottom: 30 }}
        >
          <div
            style={{
              borderRadius: 16,
              overflow: "hidden",
              border: `1.5px solid ${T.border}`,
              boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
            }}
          >
            <img src={thumb} alt="cheating agents" style={{ width: 486, display: "block" }} />
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
            <div style={{ background: "#fff", borderRadius: 16, padding: 14 }}>
              <img
                src={qr}
                alt="Read the full thread on X"
                style={{ width: 254, height: 254, display: "block", imageRendering: "pixelated" }}
              />
            </div>
            <div
              style={{
                fontFamily: MONO,
                fontSize: 19,
                color: T.textDim,
                letterSpacing: 1,
                textAlign: "center",
                lineHeight: 1.35,
              }}
            >
              scan for the full thread
            </div>
          </div>
        </motion.div>

        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontSize: 54, fontWeight: 800, color: T.white, lineHeight: 1.12 }}>
          A perfect score for <Accent color="emerald">fixing nothing</Accent>
        </motion.div>
      </motion.div>
    </div>
  );
}
