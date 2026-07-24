import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { GitHubMark } from "./figures";

// ──────────────────────────────────────────────────────────────
// Repo2RLEnvIntro — a plain-React (framer-motion) port of the
// hf-motion Remotion "IntroScene" for repo2rlenv.
//
// Designed against the deck's fixed 1280×720 stage. Fills its parent
// (position:absolute inset:0). Entrance staggers use framer-motion
// springs; the continuous motion (pulse dot on the arrow, thinking
// dots, travelling token, tests filling) is driven by a single
// self-contained rAF clock. Fully theme-aware (light + dark) via
// useTheme() — no hard-coded near-black/near-white surfaces.
// ──────────────────────────────────────────────────────────────

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
// linear ramp: 0 before `a`, 1 after `b`
const seg = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));

// Layout anchor for the figure row (design coords, 1280×720 stage).
const FIG_Y = 300;

export function Repo2RLEnvIntro() {
  const { T, glow } = useTheme();

  // ── Single rAF clock. `t` is elapsed seconds; `frame` (~30fps) keeps
  //    the oscillation math identical in feel to the Remotion source. ──
  const [t, setT] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const loop = (now: number) => {
      setT((now - start) / 1000);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  const frame = t * 30;

  // Figure draw-on progress (staggered: repo → arrow → env loop).
  const repoP = seg(t, 1.1, 2.4);
  const arrowP = seg(t, 2.0, 2.7);
  const envP = seg(t, 2.4, 3.8);

  const spring = { type: "spring" as const, stiffness: 90, damping: 18 };

  return (
    <div style={{ position: "absolute", inset: 0, background: T.bg, overflow: "hidden" }}>
      {/* Faint grid backdrop — gives the frame structure, masked to centre */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            `linear-gradient(${T.border} 1px, transparent 1px),` +
            ` linear-gradient(90deg, ${T.border} 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
          opacity: 0.35,
          maskImage: "radial-gradient(ellipse at center, #000 25%, transparent 78%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at center, #000 25%, transparent 78%)",
          pointerEvents: "none",
        }}
      />
      {/* Soft lavender→emerald spotlight behind the figure row */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(60% 45% at 50% 58%, ${T.lavender}14, transparent 70%)`,
          pointerEvents: "none",
        }}
      />

      {/* Eyebrow */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring, delay: 0 }}
        style={{
          position: "absolute",
          top: 84,
          left: 0,
          right: 0,
          textAlign: "center",
          fontFamily: MONO,
          fontSize: 22,
          fontWeight: 700,
          color: T.lavender,
          letterSpacing: 10,
          textTransform: "uppercase",
        }}
      >
        Introducing
      </motion.div>

      {/* Title */}
      <motion.div
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ ...spring, delay: 0.18 }}
        style={{
          position: "absolute",
          top: 122,
          left: 0,
          right: 0,
          textAlign: "center",
          fontFamily: MONO,
          fontSize: 64,
          fontWeight: 800,
          color: T.white,
          letterSpacing: -2,
        }}
      >
        repo2
        <span style={{ color: T.emerald, textShadow: glow.emeraldText }}>rlenv</span>
      </motion.div>

      {/* Subtitle */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring, delay: 0.5 }}
        style={{
          position: "absolute",
          top: 214,
          left: 0,
          right: 0,
          textAlign: "center",
          fontFamily: MONO,
          fontSize: 20,
          fontWeight: 500,
          color: T.textMuted,
          letterSpacing: 0.2,
        }}
      >
        Convert{" "}
        <span style={{ color: T.lavender, fontWeight: 700 }}>any repository</span> into a
        verifiable{" "}
        <span style={{ color: T.emerald, fontWeight: 700 }}>RL environment</span>
      </motion.div>

      {/* ── Figure row: Repo → synthesize → RL env loop ── */}
      {/* Repo card (left) */}
      <div style={{ position: "absolute", left: 210, top: FIG_Y }}>
        <RepoCard progress={repoP} frame={frame} width={240} />
      </div>

      {/* Connector arrow (centre) */}
      <svg
        width="220"
        height="120"
        viewBox="0 0 220 120"
        style={{ position: "absolute", left: 490, top: FIG_Y + 80 }}
      >
        <defs>
          <marker
            id="introArrow"
            markerWidth="9"
            markerHeight="9"
            refX="5"
            refY="4.5"
            orient="auto"
          >
            <path d="M0 0 L9 4.5 L0 9 z" fill={T.text} />
          </marker>
        </defs>
        <DrawPath
          d="M10 60 L190 60"
          progress={arrowP}
          stroke={T.text}
          strokeWidth={2.5}
          markerEnd="url(#introArrow)"
        />
        <text
          x={100}
          y={44}
          textAnchor="middle"
          fill={T.textMuted}
          fontSize={12}
          fontWeight={700}
          fontFamily={MONO}
          opacity={arrowP}
          letterSpacing={1}
        >
          synthesize
        </text>
        {/* moving pulse dot once the line has drawn in */}
        {arrowP > 0.95 ? (
          <circle
            cx={10 + ((frame % 40) / 40) * 180}
            cy={60}
            r={4}
            fill={T.emerald}
            opacity={0.9}
          />
        ) : null}
      </svg>

      {/* RL env loop (right) */}
      <div style={{ position: "absolute", left: 730, top: FIG_Y - 30 }}>
        <RLEnvLoop progress={envP} frame={frame} width={300} reward={1.0} />
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// DrawPath — an SVG path that "draws on" as progress goes 0 → 1.
// markerEnd only attaches once the line is essentially complete.
// ──────────────────────────────────────────────────────────────
function DrawPath({
  d,
  progress,
  stroke,
  strokeWidth = 2,
  markerEnd,
}: {
  d: string;
  progress: number;
  stroke: string;
  strokeWidth?: number;
  markerEnd?: string;
}) {
  const p = clamp01(progress);
  return (
    <path
      d={d}
      fill="none"
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      pathLength={1}
      strokeDasharray={1}
      strokeDashoffset={1 - p}
      markerEnd={p > 0.9 ? markerEnd : undefined}
    />
  );
}

// ──────────────────────────────────────────────────────────────
// RepoCard — a repository window with an animated git commit-graph.
// The card fades in, then trunk/branch draw on, nodes pop, and
// changed-file lines settle. Intrinsic size 240 × 280.
// ──────────────────────────────────────────────────────────────
function RepoCard({
  progress,
  frame,
  width = 240,
}: {
  progress: number;
  frame: number;
  width?: number;
}) {
  const { T } = useTheme();
  const h = (width / 240) * 280;
  const appear = Math.min(1, progress / 0.12);

  const nodes = [
    { x: 60, y: 92, branch: 0 },
    { x: 60, y: 130, branch: 0 },
    { x: 120, y: 150, branch: 1 },
    { x: 60, y: 168, branch: 0 },
    { x: 120, y: 188, branch: 1 },
    { x: 60, y: 206, branch: 0 },
    { x: 60, y: 244, branch: 0 },
  ];

  return (
    <svg width={width} height={h} viewBox="0 0 240 280">
      <g opacity={appear}>
        {/* Card body */}
        <rect
          x={1}
          y={1}
          width={238}
          height={278}
          rx={14}
          fill={T.bgRaised}
          stroke={T.border}
          strokeWidth={1.5}
        />
        {/* Header bar (rounded top + square filler) */}
        <rect x={1} y={1} width={238} height={40} rx={14} fill={`${T.lavender}12`} />
        <rect x={1} y={28} width={238} height={13} fill={`${T.lavender}12`} />
        <line x1={1} y1={41} x2={239} y2={41} stroke={T.border} strokeWidth={1} />
        {/* header: GitHub mark + username / repo */}
        <g transform="translate(16 12)">
          <GitHubMark size={17} color={T.text} />
        </g>
        <text x={42} y={26} fontSize={13} fontFamily={MONO}>
          <tspan fill={T.textMuted}>username</tspan>
          <tspan fill={T.textDim}> / </tspan>
          <tspan fill={T.lavender} fontWeight={700}>
            repo
          </tspan>
        </text>

        {/* Git graph trunk */}
        <DrawPath d="M60 92 L60 244" progress={progress} stroke={T.lavender} strokeWidth={2.5} />
        {/* Branch out + merge */}
        <DrawPath
          d="M60 130 C 100 130, 120 134, 120 150 L120 188 C120 204, 100 206, 60 206"
          progress={Math.max(0, (progress - 0.2) / 0.8)}
          stroke={T.emerald}
          strokeWidth={2.5}
        />

        {/* Commit nodes (pop in along the graph) */}
        {nodes.map((n, i) => {
          const a = clamp01((progress - i * 0.1) / 0.2);
          return (
            <circle
              key={i}
              cx={n.x}
              cy={n.y}
              r={5.5 * a}
              fill={T.bg}
              stroke={n.branch === 1 ? T.emerald : T.lavender}
              strokeWidth={2.5}
            />
          );
        })}

        {/* Changed-file lines (diff hint) */}
        {[0, 1, 2, 3, 4].map((i) => {
          const a = clamp01((progress - 0.4 - i * 0.08) / 0.2);
          const w = [70, 52, 64, 44, 58][i];
          const isPlus = i % 2 === 0;
          return (
            <rect
              key={i}
              x={150}
              y={96 + i * 22}
              width={w}
              height={6}
              rx={3}
              fill={isPlus ? T.emerald : T.textDim}
              opacity={(isPlus ? 0.6 : 0.7) * a}
            />
          );
        })}

        {/* Pulsing ring on the trunk head */}
        <circle
          cx={60}
          cy={92}
          r={5.5}
          fill="none"
          stroke={T.lavender}
          strokeWidth={2}
          opacity={progress > 0.9 ? 0.4 + 0.4 * Math.sin(frame * 0.12) : 0}
        />
      </g>
    </svg>
  );
}

// ──────────────────────────────────────────────────────────────
// RLEnvLoop — the canonical agent ⇄ environment loop diagram, with
// action/reward arrows, a travelling token, thinking dots, a tests-
// passing strip, and a reward badge. Intrinsic size 300 × 300.
// ──────────────────────────────────────────────────────────────
function RLEnvLoop({
  progress,
  frame,
  width = 300,
  reward = 1.0,
}: {
  progress: number;
  frame: number;
  width?: number;
  reward?: number;
}) {
  const { T } = useTheme();
  const ease = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);
  const agentE = ease(progress / 0.5);
  const envE = ease((progress - 0.12) / 0.5);
  const arrowP = clamp01((progress - 0.42) / 0.5);
  const active = progress > 0.92;

  // Travelling token: down the left (action), up the right (reward).
  const tt = (frame % 90) / 90;
  const onRight = tt < 0.5;
  const localT = onRight ? tt / 0.5 : (tt - 0.5) / 0.5;
  let tokenX: number;
  let tokenY: number;
  let tokenColor: string;
  if (onRight) {
    tokenX = 210;
    tokenY = 192 - localT * 82;
    tokenColor = T.emerald;
  } else {
    tokenX = 90;
    tokenY = 108 + localT * 84;
    tokenColor = T.lavender;
  }

  // Environment "tests passing" — fills 0..5 squares on a loop.
  const TESTS = 5;
  const testFilled = active ? Math.floor((frame % 66) / 11) : 0;

  return (
    <svg width={width} height={width} viewBox="0 0 300 300">
      <defs>
        <marker id="arrowL" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0 0 L8 4 L0 8 z" fill={T.lavender} />
        </marker>
        <marker id="arrowR" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0 0 L8 4 L0 8 z" fill={T.emerald} />
        </marker>
      </defs>

      {/* Agent box */}
      <g
        opacity={agentE}
        transform={`translate(150 69) scale(${0.9 + 0.1 * agentE}) translate(-150 -69)`}
      >
        <rect
          x={70}
          y={32}
          width={160}
          height={74}
          rx={14}
          fill={T.bgRaised}
          stroke={T.lavender}
          strokeWidth={2}
        />
        <text
          x={150}
          y={60}
          textAnchor="middle"
          fill={T.text}
          fontSize={17}
          fontWeight={700}
          fontFamily={MONO}
        >
          Agent
        </text>
        <text
          x={150}
          y={78}
          textAnchor="middle"
          fill={T.textMuted}
          fontSize={11}
          fontFamily={MONO}
        >
          coding model
        </text>
        {active
          ? [0, 1, 2].map((i) => {
              const op = 0.25 + 0.6 * (0.5 + 0.5 * Math.sin(frame * 0.14 + i * 0.9));
              return (
                <circle key={i} cx={138 + i * 12} cy={94} r={2.6} fill={T.lavender} opacity={op} />
              );
            })
          : null}
      </g>

      {/* Environment box */}
      <g
        opacity={envE}
        transform={`translate(150 231) scale(${0.9 + 0.1 * envE}) translate(-150 -231)`}
      >
        <rect
          x={70}
          y={194}
          width={160}
          height={74}
          rx={14}
          fill={T.bgRaised}
          stroke={T.emerald}
          strokeWidth={2}
        />
        <text
          x={150}
          y={222}
          textAnchor="middle"
          fill={T.text}
          fontSize={17}
          fontWeight={700}
          fontFamily={MONO}
        >
          Environment
        </text>
        <text
          x={150}
          y={240}
          textAnchor="middle"
          fill={T.textMuted}
          fontSize={11}
          fontFamily={MONO}
        >
          repo + tests
        </text>
        {active
          ? Array.from({ length: TESTS }).map((_, i) => {
              const passed = i < testFilled;
              return (
                <rect
                  key={i}
                  x={124 + i * 12}
                  y={252}
                  width={8}
                  height={8}
                  rx={2}
                  fill={passed ? T.emerald : "none"}
                  stroke={T.emerald}
                  strokeWidth={1.2}
                  opacity={passed ? 1 : 0.4}
                />
              );
            })
          : null}
      </g>

      {/* Left arrow: agent → env (action) */}
      <DrawPath
        d="M90 106 L90 186"
        progress={arrowP}
        stroke={T.lavender}
        strokeWidth={2}
        markerEnd="url(#arrowL)"
      />
      {/* Right arrow: env → agent (reward / state) */}
      <DrawPath
        d="M210 194 L210 114"
        progress={arrowP}
        stroke={T.emerald}
        strokeWidth={2}
        markerEnd="url(#arrowR)"
      />

      {/* Arrow labels */}
      <text
        x={62}
        y={150}
        textAnchor="middle"
        fill={T.lavender}
        fontSize={12}
        fontWeight={700}
        fontFamily={MONO}
        opacity={arrowP}
        transform="rotate(-90 62 150)"
      >
        action
      </text>
      <text
        x={238}
        y={150}
        textAnchor="middle"
        fill={T.emerald}
        fontSize={12}
        fontWeight={700}
        fontFamily={MONO}
        opacity={arrowP}
        transform="rotate(90 238 150)"
      >
        reward
      </text>

      {/* Travelling token */}
      {active ? <circle cx={tokenX} cy={tokenY} r={5} fill={tokenColor} /> : null}

      {/* Reward badge */}
      <g opacity={active ? 1 : 0}>
        <rect
          x={104}
          y={137}
          width={92}
          height={27}
          rx={13.5}
          fill={`${T.emerald}22`}
          stroke={T.emerald}
          strokeWidth={1}
        />
        <text
          x={150}
          y={155}
          textAnchor="middle"
          fill={T.emerald}
          fontSize={13}
          fontWeight={700}
          fontFamily={MONO}
        >
          r = {reward.toFixed(3)}
        </text>
      </g>
    </svg>
  );
}
