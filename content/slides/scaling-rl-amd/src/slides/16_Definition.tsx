import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

const PARTS = ["tasks", "state", "tools", "reward", "episode control"];

export function DefinitionSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0 } };

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.14, delayChildren: 0.15 } } }}
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
            fontSize: 22,
            letterSpacing: 6,
            color: T.textDim,
            textTransform: "uppercase",
            marginBottom: 36,
          }}
        >
          So — what is an RL environment?
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ fontSize: 52, fontWeight: 800, color: T.white, lineHeight: 1.25, maxWidth: 1080 }}
        >
          A place a model <Accent color="emerald">practises</Accent>, gets{" "}
          <Accent color="emerald">graded</Accent>, and learns —
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            marginTop: 34,
            display: "flex",
            gap: 14,
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          {PARTS.map((p) => (
            <span
              key={p}
              style={{
                fontFamily: MONO,
                fontSize: 26,
                color: T.text,
                padding: "12px 22px",
                border: `1.5px solid ${T.lavender}`,
                borderRadius: 999,
              }}
            >
              {p}
            </span>
          ))}
        </motion.div>
      </motion.div>
    </div>
  );
}
