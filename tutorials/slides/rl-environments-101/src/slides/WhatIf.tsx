import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

export function WhatIfSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.3, delayChildren: 0.2 } } }}
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
            fontSize: 30,
            color: T.textDim,
            marginBottom: 30,
            letterSpacing: 2,
          }}
        >
          hmm 🤔
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ fontSize: 56, fontWeight: 800, color: T.white, lineHeight: 1.22, maxWidth: 1120 }}
        >
          That’s a lot of repos. Could we turn them into{" "}
          <Accent color="emerald">thousands of environments</Accent> — automatically,{" "}
          <Accent color="emerald">at scale</Accent>?
        </motion.div>
      </motion.div>
    </div>
  );
}
