import { motion } from "framer-motion";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import { Accent } from "../../components/primitives";
import photo from "../../assets/adithyask.jpeg";

export function RH2QuoteSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.24, delayChildren: 0.2 } } }}
        style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 140px" }}
      >
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ fontFamily: "Georgia, serif", fontSize: 120, lineHeight: 0.6, color: T.lavender, marginBottom: 20, height: 60 }}
        >
          &ldquo;
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ fontSize: 46, fontWeight: 700, color: T.white, lineHeight: 1.32, maxWidth: 1080 }}
        >
          Reward hacking isn’t an edge case — it happens{" "}
          <Accent color="emerald">at scale</Accent>. Reward modeling is{" "}
          <Accent color="emerald">trial and error</Accent>, every single time.
        </motion.div>

        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ marginTop: 44, display: "flex", alignItems: "center", gap: 16 }}
        >
          <img src={photo} alt="Adithya S Kolavi" style={{ width: 56, height: 56, borderRadius: "50%", objectFit: "cover" }} />
          <span style={{ fontFamily: MONO, fontSize: 24, color: T.textMuted }}>— Adithya S Kolavi</span>
        </motion.div>
      </motion.div>
    </div>
  );
}
