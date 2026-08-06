import { motion } from "framer-motion";
import { SlideShell } from "../../components/SlideShell";
import { Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import { HFMark } from "../../components/figures";

export function DemoTaskSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The task" title={<>LaTeX OCR</>}>
      <div style={{ position: "absolute", top: 200, left: 96, right: 96, fontSize: 27, color: T.textMuted, lineHeight: 1.35, maxWidth: 1090 }}>
        A <Accent color="emerald">VLM</Accent> sees an image of a formula → writes the LaTeX. The
        reward: does it <b style={{ color: T.white }}>render back to the same math?</b>
      </div>

      <div style={{ position: "absolute", top: 300, left: 96, right: 96, display: "flex", alignItems: "center", gap: 40 }}>
        {/* the "image" */}
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
          style={{ flex: "0 0 auto", width: 460, height: 180, background: "#fff", borderRadius: 12, display: "grid", placeItems: "center", boxShadow: "0 12px 40px rgba(0,0,0,0.4)" }}
        >
          <span style={{ fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 46, color: "#111", fontStyle: "italic" }}>
            x = ( −b ± √(b²−4ac) ) / 2a
          </span>
        </motion.div>

        <div style={{ fontSize: 40, color: T.lavender }}>→</div>

        {/* the LaTeX */}
        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.45 }}
          style={{ flex: 1, background: "#0d1117", border: "1px solid #30363d", borderRadius: 12, padding: "22px 24px", fontFamily: MONO, fontSize: 24, color: "#dcdcaa", lineHeight: 1.5 }}
        >
          x = \frac&#123;-b \pm \sqrt&#123;b^2 - 4ac&#125;&#125;&#123;2a&#125;
        </motion.div>
      </div>

      <div style={{ position: "absolute", bottom: 90, left: 96, right: 96, display: "flex", alignItems: "center", gap: 12, fontFamily: MONO, fontSize: 20, color: T.textDim }}>
        <HFMark size={24} />
        <span>dataset · hf.co/datasets/unsloth/LaTeX_OCR</span>
      </div>
    </SlideShell>
  );
}
