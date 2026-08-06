import { motion } from "framer-motion";
import { SlideShell } from "../../components/SlideShell";
import { Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";
import fireship from "../../assets/openai-ss1.png";
import nyt from "../../assets/openai-ss2-crop.png";
import decrypt from "../../assets/openai-ss3-crop.png";

function Shot({
  src,
  left,
  top,
  rot,
  z,
  delay,
  w,
  h,
  label,
}: {
  src: string;
  left: number;
  top: number;
  rot: number;
  z: number;
  delay: number;
  w?: number;
  h?: number;
  label?: string;
}) {
  const { T } = useTheme();
  return (
    <motion.div
      initial={{ opacity: 0, y: 28, rotate: rot * 1.7, scale: 0.94 }}
      animate={{ opacity: 1, y: 0, rotate: rot, scale: 1 }}
      transition={{ type: "spring", damping: 20, delay }}
      style={{ position: "absolute", left, top, zIndex: z }}
    >
      <img
        src={src}
        alt={label ?? ""}
        style={{
          width: w ?? "auto",
          height: h ?? "auto",
          display: "block",
          background: "#fff",
          borderRadius: 12,
          border: `3px solid ${T.white}`,
          boxShadow: "0 24px 64px rgba(0,0,0,0.6)",
        }}
      />
      {label && (
        <div style={{ fontFamily: MONO, fontSize: 15, color: T.textDim, marginTop: 8, textAlign: "center" }}>
          {label}
        </div>
      )}
    </motion.div>
  );
}

export function RHOpenAINewsSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Last week" title={<>It actually happened</>}>
      <div style={{ position: "absolute", top: 152, left: 96, right: 96, fontSize: 25, color: T.textMuted, lineHeight: 1.35 }}>
        OpenAI’s models <Accent color="emerald">hacked Hugging Face</Accent> to cheat a benchmark —
        last week.
      </div>

      {/* scattered press wall (tilted) */}
      <div style={{ position: "absolute", top: 206, left: 60, right: 60, bottom: 24 }}>
        {/* NYT headline banner */}
        <Shot src={nyt} left={470} top={6} rot={4} z={1} w={470} delay={0.35} label="The New York Times" />
        {/* Decrypt headline banner */}
        <Shot src={decrypt} left={495} top={188} rot={-3} z={2} w={470} delay={0.55} label="Decrypt" />
        {/* Fireship video — the star, on top */}
        <Shot src={fireship} left={225} top={70} rot={-5} z={3} h={232} delay={0.75} label="YouTube · Fireship" />
      </div>
    </SlideShell>
  );
}
