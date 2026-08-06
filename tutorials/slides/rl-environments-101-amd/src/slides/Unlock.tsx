import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

// The pivot between "DeepSeek made rewards verifiable" and "so everyone raced
// to build more environments." A big, quiet, important beat.
export function UnlockSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.28, delayChildren: 0.2 } } }}
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
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            fontFamily: MONO,
            fontSize: 20,
            letterSpacing: 6,
            color: T.textDim,
            textTransform: "uppercase",
            marginBottom: 36,
          }}
        >
          The unlock
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ fontSize: 60, fontWeight: 800, color: T.white, lineHeight: 1.18, maxWidth: 1080 }}
        >
          If a program can <Accent color="emerald">grade it</Accent>, a model can{" "}
          <Accent color="emerald">learn it</Accent>.
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ marginTop: 40, fontSize: 34, color: T.textMuted, lineHeight: 1.4, maxWidth: 960 }}
        >
          So the race became simple: build <b style={{ color: T.white }}>more environments</b>.
        </motion.div>
      </motion.div>
    </div>
  );
}
