import { motion } from "framer-motion";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";

const RED = "#ff3b5c";

export function RHDividerSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.24, delayChildren: 0.2 } } }}
        style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 120px" }}
      >
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontFamily: MONO, fontSize: 22, letterSpacing: 6, color: T.textDim, textTransform: "uppercase", marginBottom: 32 }}>
          Pitfalls · a story
        </motion.div>

        {/* Reward  modeling(struck)  hacking(red) */}
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ fontSize: 82, fontWeight: 800, color: T.white, lineHeight: 1.1, display: "flex", alignItems: "baseline", gap: 24, flexWrap: "wrap", justifyContent: "center" }}
        >
          <span>Reward</span>

          {/* modeling — gets crossed out */}
          <span style={{ position: "relative", color: T.textMuted }}>
            modeling
            <motion.span
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: 0.9, duration: 0.4, ease: "easeInOut" }}
              style={{
                position: "absolute",
                left: -6,
                right: -6,
                top: "52%",
                height: 7,
                background: RED,
                borderRadius: 4,
                transformOrigin: "left center",
              }}
            />
          </span>

          {/* hacking — pops in red */}
          <motion.span
            initial={{ opacity: 0, y: 12, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 1.25, type: "spring", damping: 14 }}
            style={{ color: RED, textShadow: "0 0 30px rgba(255,59,92,0.5)" }}
          >
            hacking
          </motion.span>
        </motion.div>

        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ marginTop: 30, fontSize: 32, color: T.textMuted, maxWidth: 940, lineHeight: 1.4 }}>
          When the model games the <b style={{ color: T.white }}>reward</b> — not the task.
        </motion.div>
      </motion.div>
    </div>
  );
}
