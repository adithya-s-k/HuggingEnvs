import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { CartPole } from "../components/CartPole";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

export function TraditionalRLSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Classical RL" title={<>RL environments already exist</>}>
      <div style={{ position: "absolute", top: 230, left: 96, right: 72, bottom: 70 }}>
        {/* the loop, laid out horizontally: agent → action → environment */}
        <div style={{ position: "relative", height: "100%" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
            {/* Agent */}
            <motion.div
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: "spring", damping: 22, delay: 0.25 }}
              style={{
                width: 230,
                flex: "0 0 auto",
                border: `1.5px solid ${T.border}`,
                borderLeft: `3px solid ${T.emerald}`,
                borderRadius: 14,
                padding: "26px 22px",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 34, fontWeight: 700, color: T.text }}>Agent</div>
              <div style={{ fontFamily: MONO, fontSize: 18, color: T.textDim, marginTop: 6 }}>
                a policy
              </div>
            </motion.div>

            {/* action arrow */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, flex: "0 0 auto" }}>
              <span style={{ fontFamily: MONO, fontSize: 18, color: T.emerald }}>action</span>
              <span style={{ color: T.lavender, fontSize: 32 }}>→</span>
            </div>

            {/* Environment = the live CartPole */}
            <motion.div
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: "spring", damping: 22, delay: 0.35 }}
              style={{ flex: 1 }}
            >
              <CartPole width={620} height={330} speed={0.5} />
            </motion.div>
          </div>

          {/* return path: state · reward, back to the agent */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.9 }}
            style={{
              position: "absolute",
              left: 40,
              right: 300,
              bottom: 4,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span style={{ color: T.lavender, fontSize: 26 }}>←</span>
            <div style={{ flex: 1, borderTop: `2px dashed ${T.lavender}`, opacity: 0.6 }} />
            <span style={{ fontFamily: MONO, fontSize: 20, color: T.emerald }}>state · reward</span>
            <div style={{ flex: 1, borderTop: `2px dashed ${T.lavender}`, opacity: 0.6 }} />
          </motion.div>
        </div>
      </div>
    </SlideShell>
  );
}
