import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { Timeline } from "../components/Timeline";
import { Stagger, Rise, Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { DeepSeekLogo } from "../components/logos";

export function GRPOSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={7} kicker="RLVR · GRPO" title={<>Then DeepSeek happened</>}>
      <div style={{ position: "absolute", top: 205, left: 96, right: 96 }}>
        <Timeline active={3} compact animate={false} />
      </div>

      {/* DeepSeek logo lockup */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", damping: 18, delay: 0.25 }}
        style={{ position: "absolute", top: 300, left: 96, display: "flex", alignItems: "center", gap: 18 }}
      >
        <DeepSeekLogo size={64} />
        <span style={{ fontSize: 40, fontWeight: 800, color: T.white }}>DeepSeek-R1</span>
      </motion.div>

      <div style={{ position: "absolute", top: 400, left: 96, right: 96 }}>
        <Stagger gap={0.13} delay={0.45} style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <Rise>
            <div style={{ fontSize: 34, color: T.text, lineHeight: 1.3, maxWidth: 1060 }}>
              Introduced <Accent color="emerald">GRPO</Accent> — reward the model only when its
              answer <b style={{ color: T.white }}>passes a check</b>. A program grades it, no human
              needed.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 30, color: T.textMuted, lineHeight: 1.35, maxWidth: 1040 }}>
              Cheap, hard to fake, endlessly scalable — and now{" "}
              <Accent color="emerald">every frontier model</Accent> trains this way.
            </div>
          </Rise>
          <Rise>
            <div
              style={{
                fontFamily: MONO,
                fontSize: 20,
                color: T.textMuted,
                borderLeft: `3px solid ${T.lavender}`,
                paddingLeft: 18,
                lineHeight: 1.5,
              }}
            >
              <span style={{ color: T.emerald, fontWeight: 700 }}>fun fact</span> — GRPO shipped a
              year earlier in <span style={{ color: T.text }}>DeepSeekMath</span> (Feb 2024), before
              R1 (Jan 2025).
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
