import { motion } from "framer-motion";
import { SlideShell } from "../../components/SlideShell";
import { CodeBlock } from "../../components/CodeBlock";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";

// Shared visual for the three "cheats" — each earns a fake perfect 1.000.
export function CheatSlide({
  n,
  title,
  lead,
  code,
  fix,
}: {
  n: number;
  title: string;
  lead: React.ReactNode;
  code: string;
  fix: React.ReactNode;
}) {
  const { T, glow } = useTheme();
  return (
    <SlideShell kicker={`Cheat #${n}`} title={<>{title}</>}>
      <div style={{ position: "absolute", top: 165, left: 96, right: 96, fontSize: 24, color: T.textMuted, lineHeight: 1.35, maxWidth: 1090 }}>
        {lead}
      </div>

      <div
        style={{
          position: "absolute",
          top: 232,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1.35fr 1fr",
          gap: 40,
          alignItems: "center",
        }}
      >
        <CodeBlock filename="agent-trace" lang="bash" code={code} fontSize={17} delay={0.3} />

        {/* the fake perfect score */}
        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", damping: 14, delay: 0.55 }}
          style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}
        >
          <div style={{ fontFamily: MONO, fontSize: 20, color: T.textDim, letterSpacing: 2 }}>reward</div>
          <div style={{ fontFamily: MONO, fontSize: 110, fontWeight: 800, color: T.emerald, textShadow: glow.emeraldText, lineHeight: 1 }}>
            1.000
          </div>
          <div style={{ fontSize: 22, color: "#ff5470", fontWeight: 700 }}>…fixed nothing</div>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9 }}
        style={{ position: "absolute", bottom: 60, left: 96, right: 96, fontSize: 23, color: T.text }}
      >
        {fix}
      </motion.div>
    </SlideShell>
  );
}
