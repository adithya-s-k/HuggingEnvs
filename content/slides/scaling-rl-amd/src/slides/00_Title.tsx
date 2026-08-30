import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";
import { HFMark } from "../components/figures";

// The two halves of the talk. "Infra" is deliberately absent — the plates name
// what the audience will actually see built.
const PILLARS = ["RL Environments", "RL Training"];

// The background is the title: a hockey-stick growth curve rising to the right,
// sitting in the band below the type so nothing crosses a letterform. Sampled
// rather than hand-authored beziers so the exponent is the only knob.
const AXIS_Y = 646;

function curvePath(exponent: number, height: number) {
  const pts: string[] = [];
  for (let i = 0; i <= 56; i++) {
    const t = i / 56;
    const x = t * 1280;
    const y = AXIS_Y - Math.pow(t, exponent) * height;
    pts.push(`${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  return pts.join(" ");
}

const MAIN = curvePath(2.4, 258);
const TRAIL = curvePath(3.3, 168);
const MAIN_AREA = `${MAIN} L1280 ${AXIS_Y} L0 ${AXIS_Y} Z`;

// Sampled at the same exponent as MAIN so the dots sit exactly on the line.
const DOTS = [0.42, 0.66, 0.84, 0.97].map((t) => ({
  t,
  x: t * 1280,
  y: AXIS_Y - Math.pow(t, 2.4) * 258,
}));

// Faint order-of-magnitude ticks — the one place the field says "scale" in words.
const TICKS = [
  { x: 330, label: "10×" },
  { x: 700, label: "100×" },
  { x: 1055, label: "1,000×" },
];

function ScalingCurve() {
  const { T, mode } = useTheme();
  const dim = mode === "dark" ? 0.5 : 0.6;
  const areaTop = mode === "dark" ? 0.3 : 0.22;

  return (
    <svg width="1280" height="720" viewBox="0 0 1280 720" style={{ position: "absolute", inset: 0 }}>
      <defs>
        <linearGradient id="scale-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={T.emerald} stopOpacity={areaTop} />
          <stop offset="100%" stopColor={T.emerald} stopOpacity={0} />
        </linearGradient>
      </defs>

      {/* plot furniture — verticals only, so it reads as a chart without becoming one */}
      {TICKS.concat([{ x: 1240, label: "" }]).map((g, i) => (
        <motion.line
          key={i}
          x1={g.x}
          y1={300}
          x2={g.x}
          y2={AXIS_Y}
          stroke={T.border}
          strokeWidth={1}
          initial={{ opacity: 0 }}
          animate={{ opacity: dim * 0.55 }}
          transition={{ delay: 0.3 + i * 0.1, duration: 0.5 }}
        />
      ))}
      <motion.line
        x1={0}
        y1={AXIS_Y}
        x2={1280}
        y2={AXIS_Y}
        stroke={T.border}
        strokeWidth={1.5}
        initial={{ opacity: 0 }}
        animate={{ opacity: dim }}
        transition={{ delay: 0.25, duration: 0.5 }}
      />

      {/* the slower curve behind — training scales, just not as steeply */}
      <motion.path
        d={TRAIL}
        fill="none"
        stroke={T.lavender}
        strokeWidth={2}
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 0.5 }}
        transition={{ pathLength: { delay: 0.5, duration: 1.7, ease: "easeInOut" }, opacity: { delay: 0.5, duration: 0.4 } }}
      />

      {/* the hero curve */}
      <motion.path
        d={MAIN_AREA}
        fill="url(#scale-area)"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5, duration: 0.9 }}
      />
      <motion.path
        d={MAIN}
        fill="none"
        stroke={T.emerald}
        strokeWidth={10}
        strokeLinecap="round"
        opacity={0.2}
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ delay: 0.55, duration: 1.8, ease: "easeInOut" }}
      />
      <motion.path
        d={MAIN}
        fill="none"
        stroke={T.emerald}
        strokeWidth={3.2}
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ delay: 0.55, duration: 1.8, ease: "easeInOut" }}
      />

      {/* nodes land as the line passes them */}
      {DOTS.map((d) => (
        <motion.circle
          key={d.t}
          cx={d.x}
          cy={d.y}
          r={5}
          fill={T.emerald}
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 0.9, scale: 1 }}
          transition={{ delay: 0.55 + d.t * 1.8, type: "spring", damping: 14, stiffness: 220 }}
          style={{ transformOrigin: `${d.x}px ${d.y}px` }}
        />
      ))}

      {TICKS.map((t, i) => (
        <motion.text
          key={t.label}
          x={t.x}
          y={AXIS_Y + 26}
          textAnchor="middle"
          fill={T.textDim}
          fontFamily={MONO}
          fontSize={17}
          letterSpacing={1}
          initial={{ opacity: 0 }}
          animate={{ opacity: dim * 0.9 }}
          transition={{ delay: 1.1 + i * 0.14, duration: 0.5 }}
        >
          {t.label}
        </motion.text>
      ))}
    </svg>
  );
}

export function TitleSlide() {
  const { T, glow, mode } = useTheme();
  const fade = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } };
  const scrim =
    mode === "dark"
      ? "radial-gradient(ellipse at center, rgba(7,9,15,0.5) 30%, rgba(7,9,15,0.94) 78%)"
      : "radial-gradient(ellipse at center, rgba(251,252,254,0.55) 30%, rgba(251,252,254,0.92) 78%)";

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", inset: 0, background: scrim }} />
      <ScalingCurve />

      {/* Venue badge. Top-right is the one corner the curve never reaches, and
          it keeps the eyebrow slot above the title empty. */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", damping: 22, delay: 0.5 }}
        style={{
          position: "absolute",
          top: 46,
          right: 96,
          textAlign: "right",
          fontFamily: MONO,
          lineHeight: 1.5,
        }}
      >
        <div style={{ fontSize: 20, fontWeight: 700, color: T.textMuted, letterSpacing: 2 }}>
          AMD AI Dev Day
        </div>
        <div style={{ fontSize: 16, color: T.textDim, letterSpacing: 0.6 }}>
          amd.indiadevday.com
        </div>
      </motion.div>

      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.16, delayChildren: 0.15 } } }}
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "0 80px",
        }}
      >
        {/* Title */}
        <motion.h1
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            margin: 0,
            fontSize: 88,
            fontWeight: 800,
            color: T.white,
            letterSpacing: -3,
            lineHeight: 1.02,
            maxWidth: 1120,
          }}
        >
          <Accent color="emerald" glow>Scaling RL</Accent> for LLMs
        </motion.h1>

        {/* The two halves of the talk, as plates rather than a line of text —
            the same "pairing is the visual" idea as the multi-harness title.
            Both are accented: neither one is the supporting act. */}
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{ marginTop: 42, display: "flex", alignItems: "stretch", gap: 20 }}
        >
          {PILLARS.map((p) => (
            <div
              key={p}
              style={{
                minWidth: 300,
                padding: "22px 34px",
                background: T.bgRaised,
                border: `1.5px solid ${T.emerald}`,
                borderRadius: 16,
                boxShadow: glow.emerald,
                fontSize: 34,
                fontWeight: 700,
                color: T.emerald,
                textShadow: glow.emeraldText,
                letterSpacing: -0.4,
                whiteSpace: "nowrap",
              }}
            >
              {p}
            </div>
          ))}
        </motion.div>

        {/* Byline */}
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            marginTop: 54,
            display: "flex",
            alignItems: "center",
            gap: 14,
            fontFamily: MONO,
            fontSize: 24,
            color: T.textDim,
            letterSpacing: 1,
          }}
        >
          <HFMark size={30} />
          <span>Adithya S Kolavi</span>
          <span style={{ opacity: 0.5 }}>·</span>
          <span>@AdithyaSK</span>
        </motion.div>
      </motion.div>
    </div>
  );
}
