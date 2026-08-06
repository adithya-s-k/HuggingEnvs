import { motion } from "framer-motion";
import type { CSSProperties, ReactNode } from "react";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

// ── Motion presets ─────────────────────────────────────────────
// Staggered "rise + fade" for content that enters when a slide mounts.
export const rise = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0 },
};

// container that staggers its rise() children
export const stagger = (stagger = 0.09, delay = 0.15) => ({
  hidden: {},
  show: {
    transition: { staggerChildren: stagger, delayChildren: delay },
  },
});

export const spring = { type: "spring" as const, damping: 22, stiffness: 180 };

// A drop-in <motion.div> that rises in; use inside a Stagger parent.
export function Rise({
  children,
  style,
  className,
}: {
  children?: ReactNode;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <motion.div
      variants={rise}
      transition={spring}
      style={style}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// Parent that orchestrates staggered children.
export function Stagger({
  children,
  style,
  gap,
  delay,
}: {
  children?: ReactNode;
  style?: CSSProperties;
  gap?: number;
  delay?: number;
}) {
  return (
    <motion.div
      variants={stagger(gap, delay)}
      initial="hidden"
      animate="show"
      style={style}
    >
      {children}
    </motion.div>
  );
}

// ── Panel — a raised rounded card with an optional accent edge ──
export function Panel({
  children,
  accent,
  style,
}: {
  children?: ReactNode;
  accent?: string;
  style?: CSSProperties;
}) {
  const { T, glow } = useTheme();
  return (
    <div
      style={{
        background: T.bgRaised,
        border: `1.5px solid ${accent ?? T.border}`,
        borderRadius: 18,
        boxShadow: accent === T.emerald ? glow.emerald : glow.lavender,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ── Chip — a small monospace pill ──
export function Chip({
  children,
  color,
}: {
  children?: ReactNode;
  color?: string;
}) {
  const { T } = useTheme();
  const c = color ?? T.textMuted;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "8px 16px",
        borderRadius: 999,
        border: `1.5px solid ${c}`,
        color: c,
        fontSize: 20,
        fontWeight: 700,
        fontFamily: MONO,
        letterSpacing: 0.4,
        background: "rgba(127,127,127,0.05)",
      }}
    >
      {children}
    </span>
  );
}

// ── Bullet — marker + text row ──
export function Bullet({
  children,
  marker = "▸",
  markerColor,
}: {
  children?: ReactNode;
  marker?: string;
  markerColor?: string;
}) {
  const { T } = useTheme();
  return (
    <div style={{ display: "flex", gap: 18, alignItems: "baseline" }}>
      <span
        style={{
          color: markerColor ?? T.emerald,
          fontWeight: 800,
          fontSize: 28,
        }}
      >
        {marker}
      </span>
      <span style={{ color: T.text, fontSize: 34, lineHeight: 1.4 }}>
        {children}
      </span>
    </div>
  );
}

// ── Accent — inline colored text span. Emerald by default (in-text
// emphasis); lavender is reserved for chrome, so it's opt-in. Glow off
// by default to keep body text calm. ──
export function Accent({
  children,
  color = "emerald",
  glow: withGlow = false,
}: {
  children?: ReactNode;
  color?: "lavender" | "emerald";
  glow?: boolean;
}) {
  const { T, glow } = useTheme();
  const c = color === "lavender" ? T.lavender : T.emerald;
  const g = withGlow
    ? color === "lavender"
      ? glow.lavenderText
      : glow.emeraldText
    : "none";
  return <span style={{ color: c, textShadow: g }}>{children}</span>;
}
