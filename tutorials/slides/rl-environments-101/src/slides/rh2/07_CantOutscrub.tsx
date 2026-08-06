import { motion } from "framer-motion";
import { useTheme } from "../../ThemeContext";
import { Accent } from "../../components/primitives";

export function RH2CantOutscrubSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.3, delayChildren: 0.2 } } }}
        style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 130px" }}
      >
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ fontSize: 62, fontWeight: 800, color: T.white, lineHeight: 1.18, maxWidth: 1080 }}>
          You can’t <Accent color="emerald">out-scrub</Accent> the internet.
        </motion.div>
        <motion.div variants={fade} transition={{ type: "spring", damping: 20 }} style={{ marginTop: 30, fontSize: 30, color: T.textMuted, lineHeight: 1.4, maxWidth: 980 }}>
          The published fix is the single most useful thing online for the task you just handed it.
        </motion.div>
      </motion.div>
    </div>
  );
}
