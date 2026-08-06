import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { Accent } from "../components/primitives";
import { HFMark } from "../components/figures";

// A quiet field of "environment" tiles accretes behind the title.
const COLS = 22;
const ROWS = 11;

function TileField() {
  const { T } = useTheme();
  return (
    <svg
      width="1280"
      height="720"
      viewBox="0 0 1280 720"
      style={{ position: "absolute", inset: 0, opacity: 0.55 }}
    >
      {Array.from({ length: COLS * ROWS }).map((_, i) => {
        const col = i % COLS;
        const row = Math.floor(i / COLS);
        const x = 40 + col * 56;
        const y = 30 + row * 62;
        return (
          <motion.g
            key={i}
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.12 }}
            transition={{
              delay: 0.3 + (i / (COLS * ROWS)) * 2.4,
              duration: 0.5,
            }}
          >
            <rect
              x={x}
              y={y}
              width={38}
              height={30}
              rx={5}
              fill="none"
              stroke={T.border}
              strokeWidth={1}
            />
            <rect x={x} y={y} width={38} height={5} rx={3} fill={T.lavender} opacity={0.5} />
          </motion.g>
        );
      })}
    </svg>
  );
}

export function TitleSlide() {
  const { T, mode } = useTheme();
  const fade = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } };
  const scrim =
    mode === "dark"
      ? "radial-gradient(ellipse at center, rgba(7,9,15,0.5) 30%, rgba(7,9,15,0.94) 78%)"
      : "radial-gradient(ellipse at center, rgba(251,252,254,0.55) 30%, rgba(251,252,254,0.92) 78%)";

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <TileField />
      <div style={{ position: "absolute", inset: 0, background: scrim }} />

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
        {/* Eyebrow */}
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            fontSize: 22,
            fontWeight: 700,
            color: T.lavender,
            letterSpacing: 8,
            textTransform: "uppercase",
            fontFamily: MONO,
            marginBottom: 30,
          }}
        >
          Hugging Face · RL Environments
        </motion.div>

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
          RL Environments <Accent color="emerald" glow>101</Accent>
        </motion.h1>

        {/* Subtitle */}
        <motion.div
          variants={fade}
          transition={{ type: "spring", damping: 20 }}
          style={{
            marginTop: 28,
            fontSize: 34,
            fontWeight: 500,
            color: T.textMuted,
            letterSpacing: -0.3,
            maxWidth: 980,
            lineHeight: 1.25,
          }}
        >
          From <Accent color="lavender" glow>“What Is an Env?”</Accent> to
          Training Your Own
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
