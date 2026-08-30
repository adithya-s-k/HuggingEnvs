import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

// The pivot into generation. The whole beat is one asymmetry: one side of the
// RL loop scales by spending money, the other doesn't scale at all.
export function GenSegueSlide() {
  const { T, glow } = useTheme();
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
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            fontFamily: MONO,
            fontSize: 22,
            letterSpacing: 6,
            color: T.textDim,
            textTransform: "uppercase",
            marginBottom: 34,
          }}
        >
          The catch
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ fontSize: 56, fontWeight: 800, color: T.white, lineHeight: 1.16, maxWidth: 1060 }}
        >
          Scaling training is <span style={{ color: T.textMuted }}>easy</span>.
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            marginTop: 16,
            fontFamily: MONO,
            fontSize: 28,
            color: T.textDim,
            letterSpacing: 0.5,
          }}
        >
          you just add GPUs.
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            marginTop: 52,
            fontSize: 62,
            fontWeight: 800,
            color: T.white,
            lineHeight: 1.14,
            maxWidth: 1100,
          }}
        >
          Scaling <Accent color="emerald" glow>RL environments</Accent> is{" "}
          <span style={{ color: T.emerald, textShadow: glow.emeraldText }}>hard</span>.
        </motion.div>
      </motion.div>
    </div>
  );
}
