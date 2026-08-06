import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

export function NowWhatSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0 } };

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.22, delayChildren: 0.15 } } }}
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
          style={{ fontSize: 62, fontWeight: 800, color: T.white, lineHeight: 1.15 }}
        >
          You have an environment.
        </motion.div>
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ fontSize: 62, fontWeight: 800, color: T.white, lineHeight: 1.15, marginTop: 6 }}
        >
          Now what?
        </motion.div>
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            marginTop: 42,
            fontFamily: MONO,
            fontSize: 30,
            color: T.textMuted,
            letterSpacing: 1,
          }}
        >
          → <Accent color="emerald">train a model with it</Accent>
        </motion.div>
      </motion.div>
    </div>
  );
}
