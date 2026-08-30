import { motion } from "framer-motion";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import { Accent } from "../../components/primitives";

export function RH2SegueSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.28, delayChildren: 0.2 } } }}
        style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 130px" }}
      >
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontSize: 44, color: T.textMuted, lineHeight: 1.3 }}>
          That was a <b style={{ color: T.white }}>0.5B</b> model.
        </motion.div>
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ marginTop: 24, fontSize: 58, fontWeight: 800, color: T.white, lineHeight: 1.15 }}>
          Now watch a <Accent color="emerald">frontier agent</Accent>.
        </motion.div>
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ marginTop: 26, fontFamily: MONO, fontSize: 24, color: T.textDim }}>
          Claude Code · Opus
        </motion.div>
      </motion.div>
    </div>
  );
}
