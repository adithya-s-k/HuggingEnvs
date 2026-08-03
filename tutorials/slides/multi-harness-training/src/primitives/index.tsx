import { motion } from "framer-motion";
import type { CSSProperties, ReactNode } from "react";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";

// ── Motion presets ─────────────────────────────────────────────
export const spring = { type: "spring" as const, damping: 22, stiffness: 180 };

export const rise = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0 } };

export const stagger = (gap = 0.09, delay = 0.15) => ({
  hidden: {},
  show: { transition: { staggerChildren: gap, delayChildren: delay } },
});

/** A block that rises in. Use inside <Stagger>. */
export function Rise({ children, style }: { children?: ReactNode; style?: CSSProperties }) {
  return (
    <motion.div variants={rise} transition={spring} style={style}>
      {children}
    </motion.div>
  );
}

/** Parent that orchestrates staggered <Rise> children. */
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
    <motion.div variants={stagger(gap, delay)} initial="hidden" animate="show" style={style}>
      {children}
    </motion.div>
  );
}

// ── Panel — raised card, optional accent edge ──────────────────
export function Panel({
  children,
  accent,
  glow: withGlow = true,
  style,
}: {
  children?: ReactNode;
  accent?: string;
  glow?: boolean;
  style?: CSSProperties;
}) {
  const { T, glow } = useTheme();
  return (
    <div
      style={{
        background: T.bgRaised,
        border: `1.5px solid ${accent ?? T.border}`,
        borderRadius: 18,
        boxShadow: withGlow ? (accent === T.accent2 ? glow.accent2 : glow.accent) : "none",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ── Chip — small monospace pill ────────────────────────────────
export function Chip({ children, color }: { children?: ReactNode; color?: string }) {
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

// ── Bullet — marker + text row ─────────────────────────────────
export function Bullet({
  children,
  marker = "▸",
  markerColor,
  size = 34,
}: {
  children?: ReactNode;
  marker?: string;
  markerColor?: string;
  size?: number;
}) {
  const { T } = useTheme();
  return (
    <div style={{ display: "flex", gap: 18, alignItems: "baseline" }}>
      <span style={{ color: markerColor ?? T.accent2, fontWeight: 800, fontSize: size * 0.82 }}>
        {marker}
      </span>
      <span style={{ color: T.text, fontSize: size, lineHeight: 1.4 }}>{children}</span>
    </div>
  );
}

// ── Accent — inline coloured emphasis ──────────────────────────
// accent2 by default (in-text emphasis); accent is the chrome colour, so it's
// opt-in. Glow off by default to keep body text calm.
export function Accent({
  children,
  color = "accent2",
  glow: withGlow = false,
}: {
  children?: ReactNode;
  color?: "accent" | "accent2";
  glow?: boolean;
}) {
  const { T, glow } = useTheme();
  const c = color === "accent" ? T.accent : T.accent2;
  const g = withGlow ? (color === "accent" ? glow.accentText : glow.accent2Text) : "none";
  return <span style={{ color: c, textShadow: g }}>{children}</span>;
}

// ── Stat — one big number with a label ─────────────────────────
export function Stat({
  value,
  label,
  color,
  size = 76,
}: {
  value: ReactNode;
  label: ReactNode;
  color?: string;
  size?: number;
}) {
  const { T } = useTheme();
  return (
    <div style={{ textAlign: "center" }}>
      <div
        style={{
          fontSize: size,
          fontWeight: 800,
          lineHeight: 1,
          color: color ?? T.accent2,
          fontFamily: MONO,
          letterSpacing: -2,
        }}
      >
        {value}
      </div>
      <div
        style={{
          marginTop: 12,
          fontSize: 19,
          color: T.textDim,
          letterSpacing: 1.5,
          textTransform: "uppercase",
          fontFamily: MONO,
        }}
      >
        {label}
      </div>
    </div>
  );
}

// ── Figure — image with an optional caption ────────────────────
export function Figure({
  src,
  alt,
  caption,
  height,
  width,
  style,
}: {
  src: string;
  alt: string;
  caption?: ReactNode;
  height?: number;
  width?: number | string;
  style?: CSSProperties;
}) {
  const { T } = useTheme();
  return (
    <figure style={{ margin: 0, display: "flex", flexDirection: "column", gap: 12, ...style }}>
      <img
        src={src}
        alt={alt}
        style={{
          height,
          width: width ?? "100%",
          objectFit: "contain",
          borderRadius: 14,
          border: `1px solid ${T.border}`,
          background: T.bgRaised,
        }}
      />
      {caption && (
        <figcaption style={{ fontSize: 18, color: T.textDim, fontFamily: MONO, lineHeight: 1.4 }}>
          {caption}
        </figcaption>
      )}
    </figure>
  );
}

// ── Quote — a pull quote with attribution ──────────────────────
export function Quote({ children, cite }: { children?: ReactNode; cite?: ReactNode }) {
  const { T } = useTheme();
  return (
    <div style={{ borderLeft: `4px solid ${T.accent}`, paddingLeft: 28 }}>
      <div style={{ fontSize: 40, lineHeight: 1.3, color: T.white, fontWeight: 500 }}>
        {children}
      </div>
      {cite && (
        <div style={{ marginTop: 18, fontSize: 21, color: T.textDim, fontFamily: MONO }}>
          — {cite}
        </div>
      )}
    </div>
  );
}
