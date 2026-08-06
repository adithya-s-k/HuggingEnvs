import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

export function GenSegueSlide() {
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
          style={{ fontSize: 58, fontWeight: 800, color: T.white, lineHeight: 1.18, maxWidth: 1080 }}
        >
          Training is the <span style={{ color: T.textMuted }}>easy</span> part now.
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ marginTop: 30, fontSize: 40, fontWeight: 700, lineHeight: 1.3, maxWidth: 1000 }}
        >
          You still need the <Accent color="emerald">environments</Accent> — thousands of them.
        </motion.div>
      </motion.div>
    </div>
  );
}
