import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { GitHubCard } from "../components/GitHubCard";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import qr from "../assets/qr-repo2rlenv.png";

const START = 15;
const BASE_STARS = 450;

function BigCountdown({ secs }: { secs: number }) {
  const { T, glow } = useTheme();
  const R = 138;
  const C = 2 * Math.PI * R;
  const frac = secs / START;
  const urgent = secs > 0 && secs <= 5;
  const panic = secs > 0 && secs <= 3;
  const done = secs === 0;
  const color = urgent ? "#ff3b5c" : T.emerald;

  return (
    <motion.div
      animate={panic ? { x: [0, -5, 5, -4, 4, 0] } : { x: 0 }}
      transition={panic ? { duration: 0.4, repeat: Infinity } : { duration: 0.2 }}
      style={{ position: "relative", width: 320, height: 320 }}
    >
      <svg width={320} height={320} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={160} cy={160} r={R} fill="none" stroke={T.border} strokeWidth={16} />
        <circle
          cx={160}
          cy={160}
          r={R}
          fill="none"
          stroke={done ? T.emerald : color}
          strokeWidth={16}
          strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={C * (1 - frac)}
          style={{ transition: "stroke-dashoffset 1s linear, stroke .3s", filter: `drop-shadow(0 0 18px ${done ? T.emerald : color})` }}
        />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>
        <AnimatePresence mode="popLayout">
          <motion.div
            key={secs}
            initial={{ scale: urgent ? 1.7 : 1.3, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.6, opacity: 0 }}
            transition={{ type: "spring", damping: 13, stiffness: 260 }}
            style={{
              fontFamily: MONO,
              fontSize: done ? 110 : 172,
              fontWeight: 800,
              lineHeight: 1,
              color: done ? T.emerald : color,
              textShadow: done ? glow.emeraldText : urgent ? "0 0 34px rgba(255,59,92,0.8)" : "none",
            }}
          >
            {done ? "⭐" : secs}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export function StarRepoSlide() {
  const [secs, setSecs] = useState(START);
  useEffect(() => {
    setSecs(START);
    const id = window.setInterval(() => setSecs((s) => (s <= 0 ? 0 : s - 1)), 1000);
    return () => window.clearInterval(id);
  }, []);

  // stars climb as the clock ticks — as if the room is starring live
  const stars = BASE_STARS + (START - secs) * 3;

  return (
    <SlideShell kicker="Your turn" title={<>Star the repo — now ⭐</>}>
      <div
        style={{
          position: "absolute",
          top: 200,
          left: 80,
          right: 80,
          bottom: 40,
          display: "grid",
          gridTemplateColumns: "1.05fr 1fr",
          gap: 48,
          alignItems: "center",
        }}
      >
        {/* big QR */}
        <motion.div
          initial={{ opacity: 0, x: -18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
          style={{ display: "flex", justifyContent: "center" }}
        >
          <div style={{ background: "#fff", borderRadius: 24, padding: 24 }}>
            <img src={qr} alt="Star Repo2RLEnv" style={{ width: 400, height: 400, display: "block", imageRendering: "pixelated" }} />
          </div>
        </motion.div>

        {/* timer + small live card */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 26 }}>
          <BigCountdown secs={secs} />
          <GitHubCard
            owner="huggingface"
            name="Repo2RLEnv"
            description="Convert any repo into an RL environment."
            stars={stars}
            forks={71}
            contributors={6}
            width={440}
            compact
            starPulse={secs > 0}
          />
        </div>
      </div>
    </SlideShell>
  );
}
