import { motion } from "framer-motion";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import { Accent } from "../../components/primitives";

export function RHLessonSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.26, delayChildren: 0.2 } } }}
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "0 130px",
        }}
      >
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 6, color: T.textDim, textTransform: "uppercase", marginBottom: 34 }}>
          The lesson
        </motion.div>
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontSize: 56, fontWeight: 800, color: T.white, lineHeight: 1.2, maxWidth: 1080 }}>
          The model maximized the reward <Accent color="emerald">without doing the task</Accent>.
        </motion.div>
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ marginTop: 30, fontFamily: MONO, fontSize: 22, color: T.textDim, maxWidth: 900, lineHeight: 1.5 }}>
          a toy example — there’s a lot more to reward hacking than this.
        </motion.div>
      </motion.div>
    </div>
  );
}
