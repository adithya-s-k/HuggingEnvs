import { motion } from "framer-motion";
import { SlideShell } from "../../components/SlideShell";
import { Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import curves from "../../assets/reward-hack-curves.png";

export function RHCurvesSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The run" title={<>Training Qwen-0.5B…</>}>
      <div style={{ position: "absolute", top: 190, left: 80, right: 80 }}>
        {/* the real W&B curves, with the code-execution panel called out */}
        <div style={{ position: "relative", borderRadius: 12, overflow: "hidden", border: `1.5px solid ${T.border}`, background: "#fff" }}>
          <img src={curves} alt="reward curves" style={{ width: "100%", display: "block" }} />
          {/* highlight over code_execution_reward (row 2, col 1) */}
          <motion.div
            initial={{ opacity: 0, scale: 1.06 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.6, type: "spring", damping: 18 }}
            style={{
              position: "absolute",
              left: "1.5%",
              top: "35%",
              width: "31%",
              height: "28%",
              border: `3px solid ${T.emerald}`,
              borderRadius: 8,
              boxShadow: `0 0 24px ${T.emerald}`,
            }}
          />
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.9 }}
            style={{ position: "absolute", left: "1.5%", top: "27%", fontFamily: MONO, fontSize: 15, fontWeight: 800, color: T.emerald, background: "#0d1117", padding: "3px 8px", borderRadius: 6 }}
          >
            code_execution_reward 📈
          </motion.div>
        </div>
      </div>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.1, type: "spring", damping: 22 }}
        style={{ position: "absolute", bottom: 52, left: 80, right: 80, fontSize: 24, color: T.textMuted, textAlign: "center" }}
      >
        Format improving, correctness on-and-off… then the{" "}
        <Accent color="emerald">code-execution reward shoots up</Accent> and stays high. I got excited.
      </motion.div>
    </SlideShell>
  );
}
