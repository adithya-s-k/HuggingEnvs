import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { Stagger, Rise, spring } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

// What one good environment costs, as blocks — then the multiplier that makes
// hand-building it hopeless. The tile grid is the same visual language as the
// title slide, so "thousands" is seen rather than read.
const NEEDS = [
  { label: "Tasks", claim: "Mirror the real world", detail: "Not toy prompts." },
  { label: "Reward", claim: "Can’t be gamed", detail: "A grader that survives contact." },
  { label: "Sandbox", claim: "Reset, run in parallel", detail: "Isolated, thousands at once." },
];

const COLS = 26;
const ROWS = 4;

/** A field of env tiles — the visual for "and now do that a thousand times". */
function TileSwarm() {
  const { T } = useTheme();
  return (
    <svg width="100%" height="96" viewBox={`0 0 ${COLS * 22} ${ROWS * 24}`} preserveAspectRatio="none">
      {Array.from({ length: COLS * ROWS }).map((_, i) => {
        const col = i % COLS;
        const row = Math.floor(i / COLS);
        return (
          <motion.rect
            key={i}
            x={col * 22}
            y={row * 24}
            width={16}
            height={17}
            rx={3}
            fill="none"
            stroke={T.emerald}
            strokeWidth={1}
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.34 }}
            transition={{ delay: 0.7 + (i / (COLS * ROWS)) * 1.1, duration: 0.35 }}
          />
        );
      })}
    </svg>
  );
}

export function HardToGenerateSlide() {
  const { T, glow } = useTheme();

  return (
    <SlideShell kicker="Generation" title={<>Scaling environments is hard</>}>
      {/* What one environment costs */}
      <Stagger
        gap={0.13}
        delay={0.25}
        style={{
          position: "absolute",
          top: 190,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 20,
        }}
      >
        {NEEDS.map((n) => (
          <Rise key={n.label}>
            <div
              style={{
                height: "100%",
                padding: "22px 24px",
                background: T.bgRaised,
                border: `1.5px solid ${T.border}`,
                borderRadius: 16,
              }}
            >
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 16,
                  fontWeight: 700,
                  letterSpacing: 3,
                  color: T.lavender,
                  textTransform: "uppercase",
                  marginBottom: 12,
                }}
              >
                {n.label}
              </div>
              <div
                style={{
                  fontSize: 31,
                  fontWeight: 700,
                  color: T.white,
                  letterSpacing: -0.5,
                  lineHeight: 1.15,
                  marginBottom: 8,
                }}
              >
                {n.claim}
              </div>
              <div style={{ fontSize: 21, color: T.textDim, lineHeight: 1.3 }}>{n.detail}</div>
            </div>
          </Rise>
        ))}
      </Stagger>

      {/* …now multiply it */}
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring, delay: 0.62 }}
        style={{
          position: "absolute",
          top: 412,
          left: 96,
          right: 96,
          display: "flex",
          alignItems: "center",
          gap: 34,
        }}
      >
        <span
          style={{
            fontSize: 74,
            fontWeight: 800,
            color: T.emerald,
            textShadow: glow.emeraldText,
            letterSpacing: -2,
            whiteSpace: "nowrap",
          }}
        >
          × 1,000s
        </span>
        <div style={{ flex: 1, marginTop: 6 }}>
          <TileSwarm />
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ ...spring, delay: 1.5 }}
        style={{
          position: "absolute",
          top: 546,
          left: 96,
          right: 96,
          fontFamily: MONO,
          fontSize: 24,
          color: T.textDim,
          letterSpacing: 0.5,
        }}
      >
        hand-built, one at a time → <span style={{ color: T.white }}>doesn’t scale</span>
      </motion.div>
    </SlideShell>
  );
}
