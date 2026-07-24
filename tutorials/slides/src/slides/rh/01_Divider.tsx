import { motion } from "framer-motion";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import { Accent } from "../../components/primitives";

export function RHDividerSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.24, delayChildren: 0.2 } } }}
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "0 120px",
        }}
      >
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontFamily: MONO, fontSize: 22, letterSpacing: 6, color: T.textDim, textTransform: "uppercase", marginBottom: 32 }}>
          Pitfalls · a story
        </motion.div>
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontSize: 74, fontWeight: 800, color: T.white, lineHeight: 1.1 }}>
          Reward <Accent color="emerald">hacking</Accent>
        </motion.div>
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ marginTop: 28, fontSize: 32, color: T.textMuted, maxWidth: 900, lineHeight: 1.4 }}>
          When the model games the <b style={{ color: T.white }}>reward</b> — not the task.
        </motion.div>
      </motion.div>
    </div>
  );
}
