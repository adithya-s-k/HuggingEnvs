import type { CSSProperties, ReactNode } from "react";
import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { rise, spring, stagger } from "./index";

/**
 * Diagram vocabulary for this deck.
 *
 * Every shape here is drawn with divs and inline SVG rather than an image, so it
 * inherits the theme, scales with the 1280x720 canvas, and stays legible in the
 * 2560x1440 export. One primitive per idea the talk needs to show, reused across
 * slides so the audience learns the visual language once.
 */

// ---------------------------------------------------------------- flow (A -> B -> C)

export type FlowNode = {
  label: string;
  sub?: string;
  accent?: boolean;
  dim?: boolean;
};

/** Horizontal pipeline. The accented node is the one the slide is about. */
export function Flow({
  nodes,
  gap = 12,
  width,
  style,
}: {
  nodes: FlowNode[];
  gap?: number;
  width?: number;
  style?: CSSProperties;
}) {
  const { T } = useTheme();
  return (
    <motion.div
      variants={stagger(0.12, 0.1)}
      initial="hidden"
      animate="show"
      style={{ display: "flex", alignItems: "stretch", gap, ...style }}
    >
      {nodes.map((n, i) => (
        <motion.div
          key={n.label + i}
          variants={rise}
          transition={spring}
          style={{ display: "flex", alignItems: "center", gap }}
        >
          <div
            style={{
              minWidth: width ?? 232,
              padding: "24px 28px",
              borderRadius: 12,
              border: `1px solid ${n.accent ? T.accent : T.border}`,
              background: n.accent ? `${T.accent}14` : T.bgRaised,
              boxShadow: n.accent ? `0 0 32px ${T.accent}33` : "none",
              opacity: n.dim ? 0.55 : 1,
            }}
          >
            <div
              style={{
                fontFamily: MONO,
                fontSize: 27,
                color: n.accent ? T.accent : T.text,
              }}
            >
              {n.label}
            </div>
            {n.sub ? (
              <div style={{ fontSize: 20, color: T.textDim, marginTop: 7 }}>{n.sub}</div>
            ) : null}
          </div>
          {i < nodes.length - 1 ? (
            <span style={{ fontSize: 32, color: T.textDim }}>&rarr;</span>
          ) : null}
        </motion.div>
      ))}
    </motion.div>
  );
}

// ---------------------------------------------------------------- cycle (A <-> B)

/** A two-node loop, for "the trainer drives and the env answers". */
export function Cycle({
  left,
  right,
  outLabel,
  backLabel,
  style,
}: {
  left: { label: string; sub?: string };
  right: { label: string; sub?: string };
  outLabel: string;
  backLabel: string;
  style?: CSSProperties;
}) {
  const { T } = useTheme();
  const box = (n: { label: string; sub?: string }, accent: boolean) => (
    <div
      style={{
        width: 288,
        padding: "28px 30px",
        borderRadius: 12,
        border: `1px solid ${accent ? T.accent2 : T.border}`,
        background: accent ? `${T.accent2}14` : T.bgRaised,
        textAlign: "center",
      }}
    >
      <div style={{ fontFamily: MONO, fontSize: 28, color: accent ? T.accent2 : T.text }}>
        {n.label}
      </div>
      {n.sub ? <div style={{ fontSize: 20, color: T.textDim, marginTop: 7 }}>{n.sub}</div> : null}
    </div>
  );

  return (
    <motion.div
      variants={rise}
      initial="hidden"
      animate="show"
      transition={spring}
      style={{ display: "flex", alignItems: "center", gap: 0, ...style }}
    >
      {box(left, true)}
      <svg width="300" height="120" viewBox="0 0 300 120" style={{ flexShrink: 0 }}>
        <defs>
          <marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="3"
                  orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L8,3 z" fill={T.accent2} />
          </marker>
          <marker id="ah2" markerWidth="9" markerHeight="9" refX="7" refY="3"
                  orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L8,3 z" fill={T.textDim} />
          </marker>
        </defs>
        <path d="M10,38 C110,10 190,10 288,38" fill="none" stroke={T.accent2}
              strokeWidth="2" markerEnd="url(#ah)" />
        <path d="M288,82 C190,110 110,110 12,82" fill="none" stroke={T.textDim}
              strokeWidth="2" strokeDasharray="5 5" markerEnd="url(#ah2)" />
        <text x="150" y="18" textAnchor="middle" fill={T.accent2}
              fontFamily={MONO} fontSize="19">{outLabel}</text>
        <text x="150" y="112" textAnchor="middle" fill={T.textDim}
              fontFamily={MONO} fontSize="19">{backLabel}</text>
      </svg>
      {box(right, false)}
    </motion.div>
  );
}

// ---------------------------------------------------------------- layered stack

/** Architecture bands, bottom layer first in the array. */
export function Layers({
  bands,
  style,
}: {
  bands: { label: string; items: string; accent?: string }[];
  style?: CSSProperties;
}) {
  const { T } = useTheme();
  return (
    <motion.div
      variants={stagger(0.1, 0.1)}
      initial="hidden"
      animate="show"
      style={{ display: "flex", flexDirection: "column-reverse", gap: 12, ...style }}
    >
      {bands.map((b) => {
        const accent = b.accent ?? T.border;
        return (
          <motion.div key={b.label} variants={rise} transition={spring}>
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 30,
                padding: "26px 30px",
                borderRadius: 12,
                border: `1px solid ${accent}`,
                borderLeft: `4px solid ${accent}`,
                background: T.bgRaised,
              }}
            >
              <span
                style={{
                  fontFamily: MONO,
                  fontSize: 27,
                  color: accent === T.border ? T.text : accent,
                  minWidth: 250,
                }}
              >
                {b.label}
              </span>
              <span style={{ fontSize: 23, color: T.textDim }}>{b.items}</span>
            </div>
          </motion.div>
        );
      })}
    </motion.div>
  );
}

// ---------------------------------------------------------------- token bar

export type Seg = { n: number; kind: "prompt" | "completion" | "discarded" };

/** One rollout turn as a bar: grey context, green trainable, red abandoned.
 *
 * Context and completion are scaled SEPARATELY and on purpose. A real first turn is ~8k prompt
 * tokens against ~80 sampled, so a single shared scale renders every completion as one pixel and
 * hides the thing the slide is about. Context therefore gets a capped bar that says "large", and
 * completions get the full width so their differences are readable.
 */
export function TokenBar({
  segments,
  scale,
  label,
  height = 27,
}: {
  segments: Seg[];
  scale: number;
  label?: ReactNode;
  height?: number;
}) {
  const { T } = useTheme();
  const colour = { prompt: "#94a3b8", completion: T.accent2, discarded: "#ef4444" };
  const CTX_MAX = 150;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
        {segments.map((s, i) => {
          const isCtx = s.kind === "prompt";
          const w = isCtx
            ? Math.min(CTX_MAX, 26 + Math.log2(Math.max(2, s.n)) * 10)
            : Math.max(4, (s.n / scale) * 470);
          return (
            <div
              key={i}
              style={{
                width: w,
                height,
                borderRadius: 3,
                background: colour[s.kind],
                opacity: s.kind === "discarded" ? 0.6 : isCtx ? 0.5 : 1,
                // a soft right edge on a capped context bar reads as "continues"
                maskImage: isCtx && w >= CTX_MAX
                  ? "linear-gradient(90deg, #000 78%, transparent)"
                  : undefined,
                WebkitMaskImage: isCtx && w >= CTX_MAX
                  ? "linear-gradient(90deg, #000 78%, transparent)"
                  : undefined,
              }}
            />
          );
        })}
      </div>
      {label ? (
        <span style={{ fontFamily: MONO, fontSize: 21, color: T.textDim }}>{label}</span>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- rollout tree

export type TreeNode = {
  label: string;
  note?: string;
  depth: number;
  kind?: "root" | "turn" | "discarded" | "aux";
};

/** The rollout graph: nodes, connector lines, and branches that went nowhere. */
export function Tree({ nodes, style }: { nodes: TreeNode[]; style?: CSSProperties }) {
  const { T } = useTheme();
  const tone = (k?: string) =>
    k === "discarded" ? "#ef4444" : k === "aux" ? T.textDim : k === "root" ? T.accent : T.text;

  return (
    <motion.div
      variants={stagger(0.08, 0.1)}
      initial="hidden"
      animate="show"
      style={{ ...style }}
    >
      {nodes.map((n, i) => (
        <motion.div
          key={n.label + i}
          variants={rise}
          transition={spring}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginLeft: n.depth * 58,
            marginBottom: 17,
          }}
        >
          {n.depth > 0 ? (
            <svg width="26" height="26" style={{ marginLeft: -26, flexShrink: 0 }}>
              <path
                d="M4,0 L4,13 L24,13"
                fill="none"
                stroke={n.kind === "discarded" ? "#ef4444" : T.border}
                strokeWidth="1.5"
                strokeDasharray={n.kind === "discarded" ? "4 3" : undefined}
              />
            </svg>
          ) : null}
          <span
            style={{
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: tone(n.kind),
              flexShrink: 0,
              opacity: n.kind === "discarded" ? 0.7 : 1,
            }}
          />
          <span
            style={{
              fontFamily: MONO,
              fontSize: 26,
              color: tone(n.kind),
              opacity: n.kind === "discarded" ? 0.75 : 1,
            }}
          >
            {n.label}
          </span>
          {n.note ? (
            <span style={{ fontSize: 22, color: T.textDim }}>{n.note}</span>
          ) : null}
        </motion.div>
      ))}
    </motion.div>
  );
}

// ---------------------------------------------------------------- funnel (many -> one -> many)

/** Four dialects converging on one upstream shape, then replayed back out. */
export function Funnel({
  inputs,
  hub,
  out,
  style,
}: {
  inputs: string[];
  hub: string;
  out: string;
  style?: CSSProperties;
}) {
  const { T } = useTheme();
  const H = 348;
  const step = H / (inputs.length + 1);

  return (
    <motion.div
      variants={rise}
      initial="hidden"
      animate="show"
      transition={spring}
      style={{ display: "flex", alignItems: "center", gap: 0, ...style }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {inputs.map((n) => (
          <div
            key={n}
            style={{
              fontFamily: MONO,
              fontSize: 23,
              color: T.text,
              padding: "15px 20px",
              borderRadius: 9,
              border: `1px solid ${T.border}`,
              background: T.bgRaised,
              width: 372,
            }}
          >
            {n}
          </div>
        ))}
      </div>

      <svg width="150" height={H} viewBox={`0 0 150 ${H}`} style={{ flexShrink: 0 }}>
        <defs>
          <marker id="fh" markerWidth="8" markerHeight="8" refX="6" refY="3"
                  orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L7,3 z" fill={T.accent} />
          </marker>
        </defs>
        {inputs.map((_, i) => (
          <path
            key={i}
            d={`M0,${step * (i + 1)} C70,${step * (i + 1)} 70,${H / 2} 140,${H / 2}`}
            fill="none"
            stroke={T.accent}
            strokeWidth="1.6"
            opacity="0.75"
            markerEnd={i === 0 ? "url(#fh)" : undefined}
          />
        ))}
      </svg>

      <div
        style={{
          padding: "20px 24px",
          borderRadius: 12,
          border: `1px solid ${T.accent}`,
          background: `${T.accent}14`,
          boxShadow: `0 0 34px ${T.accent}33`,
          textAlign: "center",
          minWidth: 190,
        }}
      >
        <div style={{ fontFamily: MONO, fontSize: 27, color: T.accent }}>{hub}</div>
        <div style={{ fontSize: 20, color: T.textDim, marginTop: 8 }}>{out}</div>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------- pipeline (numbered steps)

/** Vertical numbered steps joined by a rail, for "what happens when you run X". */
export function Pipeline({
  steps,
  style,
}: {
  steps: { head: string; sub?: string }[];
  style?: CSSProperties;
}) {
  const { T } = useTheme();
  return (
    <motion.div
      variants={stagger(0.09, 0.1)}
      initial="hidden"
      animate="show"
      style={{ position: "relative", ...style }}
    >
      <div
        style={{
          position: "absolute",
          left: 21,
          top: 14,
          bottom: 20,
          width: 2,
          background: `linear-gradient(${T.accent}, ${T.border})`,
        }}
      />
      {steps.map((s, i) => (
        <motion.div
          key={s.head}
          variants={rise}
          transition={spring}
          style={{ display: "flex", alignItems: "baseline", gap: 22, marginBottom: 24 }}
        >
          <span
            style={{
              width: 44,
              height: 44,
              flexShrink: 0,
              borderRadius: "50%",
              border: `1px solid ${T.accent}`,
              background: T.bg,
              color: T.accent,
              fontFamily: MONO,
              fontSize: 22,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1,
            }}
          >
            {i + 1}
          </span>
          <span style={{ fontSize: 30, color: T.text, minWidth: 372 }}>{s.head}</span>
          {s.sub ? (
            <span style={{ fontSize: 23, color: T.textDim }}>{s.sub}</span>
          ) : null}
        </motion.div>
      ))}
    </motion.div>
  );
}

// ---------------------------------------------------------------- combination matrix

/** Three axes multiplying out, for "one integration covers the whole matrix". */
export function Matrix({
  axes,
  style,
}: {
  axes: { count: string; label: string; sample: string }[];
  style?: CSSProperties;
}) {
  const { T } = useTheme();
  return (
    <motion.div
      variants={stagger(0.12, 0.1)}
      initial="hidden"
      animate="show"
      style={{ display: "flex", alignItems: "center", gap: 18, ...style }}
    >
      {axes.map((a, i) => (
        <motion.div
          key={a.label}
          variants={rise}
          transition={spring}
          style={{ display: "flex", alignItems: "center", gap: 18 }}
        >
          <div
            style={{
              padding: "28px 30px",
              borderRadius: 12,
              border: `1px solid ${T.border}`,
              background: T.bgRaised,
              textAlign: "center",
              minWidth: 288,
            }}
          >
            <div
              style={{
                fontSize: 62,
                fontWeight: 700,
                color: T.accent,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {a.count}
            </div>
            <div
              style={{
                fontFamily: MONO,
                fontSize: 20,
                letterSpacing: 2,
                textTransform: "uppercase",
                color: T.textDim,
                marginTop: 4,
              }}
            >
              {a.label}
            </div>
            <div style={{ fontSize: 19, color: T.textDim, marginTop: 12, opacity: 0.85 }}>
              {a.sample}
            </div>
          </div>
          {i < axes.length - 1 ? (
            <span style={{ fontSize: 38, color: T.textDim }}>&times;</span>
          ) : null}
        </motion.div>
      ))}
    </motion.div>
  );
}
