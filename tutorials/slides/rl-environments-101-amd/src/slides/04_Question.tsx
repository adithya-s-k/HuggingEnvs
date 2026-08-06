import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";

export function QuestionSlide() {
  const { T } = useTheme();
  const fade = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0 } };

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.2, delayChildren: 0.15 } } }}
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
        {/* show of hands — big yellow hand emoji up top */}
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 22,
            marginBottom: 54,
          }}
        >
          <motion.span
            style={{ fontSize: 96, lineHeight: 1, transformOrigin: "70% 90%" }}
            animate={{ rotate: [0, 14, -8, 14, -4, 0] }}
            transition={{ duration: 1.6, delay: 0.6, ease: "easeInOut" }}
          >
            ✋
          </motion.span>
          <span
            style={{
              fontFamily: MONO,
              fontSize: 22,
              fontWeight: 700,
              color: T.white,
              letterSpacing: 6,
              textTransform: "uppercase",
            }}
          >
            Show of hands
          </span>
        </motion.div>

        {/* the question */}
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            fontSize: 72,
            fontWeight: 800,
            color: T.white,
            letterSpacing: -2,
            lineHeight: 1.16,
            maxWidth: 1040,
          }}
        >
          How many of you have heard{" "}
          <Accent color="emerald">“RL environments”</Accent>?
        </motion.div>
      </motion.div>
    </div>
  );
}
