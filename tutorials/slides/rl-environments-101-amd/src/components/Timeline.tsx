import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

export type Era = { key: string; label: string; sub?: string };

// The post-training paradigm, in order.
export const ERAS: Era[] = [
  { key: "pretrain", label: "Pretraining", sub: "the whole web" },
  { key: "sft", label: "SFT", sub: "curated data" },
  { key: "rlhf", label: "RLHF", sub: "humans judge" },
  { key: "rlvr", label: "RLVR · GRPO", sub: "verifiers judge" },
];

// Horizontal timeline. `active` highlights the current era in emerald;
// the connecting line is lavender (chrome). `compact` renders the small
// strip used at the top of each zoom-in slide.
export function Timeline({
  active,
  compact = false,
  animate = true,
}: {
  active: number;
  compact?: boolean;
  animate?: boolean;
}) {
  const { T, glow } = useTheme();
  const dot = compact ? 18 : 22;
  const labelSize = compact ? 26 : 32;
  const subSize = compact ? 0 : 18;

  return (
    <div style={{ position: "relative", width: "100%" }}>
      {/* line */}
      <div
        style={{
          position: "absolute",
          top: dot / 2,
          left: `${100 / (ERAS.length * 2)}%`,
          right: `${100 / (ERAS.length * 2)}%`,
          height: 2,
          background: T.textDim,
          opacity: 0.5,
        }}
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${ERAS.length}, 1fr)`,
        }}
      >
        {ERAS.map((era, i) => {
          const isActive = i === active;
          const isPast = i < active;
          const color = isActive ? T.emerald : isPast ? T.textMuted : T.textDim;
          return (
            <motion.div
              key={era.key}
              initial={animate ? { opacity: 0, y: 10 } : false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: "spring", damping: 22, delay: animate ? 0.2 + i * 0.18 : 0 }}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: compact ? 8 : 14,
                position: "relative",
              }}
            >
              <div
                style={{
                  width: dot,
                  height: dot,
                  borderRadius: "50%",
                  background: isActive ? T.emerald : T.bg,
                  border: `2px solid ${isActive ? T.emerald : isPast ? T.textMuted : T.borderStrong}`,
                  boxShadow: isActive ? glow.emerald : "none",
                }}
              />
              <div style={{ textAlign: "center" }}>
                <div
                  style={{
                    fontFamily: MONO,
                    fontSize: labelSize,
                    fontWeight: 700,
                    color,
                    letterSpacing: 0.5,
                  }}
                >
                  {era.label}
                </div>
                {!compact && era.sub && (
                  <div style={{ fontSize: subSize, color: T.textDim, marginTop: 6 }}>
                    {era.sub}
                  </div>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
