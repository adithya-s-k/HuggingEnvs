import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { GitHubCard } from "../components/GitHubCard";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import qr from "../assets/qr-repo2rlenv.png";

const USES = ["evaluation", "training", "benchmarks", "and more"];

// Absorbed the old "Star the repo" slide: same content, with the QR sitting
// next to the pitch so the room can scan while it's being talked about,
// instead of on a slide of its own.
export function Repo2RLEnvSlide() {
  const { T, glow } = useTheme();
  return (
    <SlideShell kicker="Repo2RLEnv" title={<>Coding envs, at scale</>}>
      <div
        style={{
          position: "absolute",
          top: 196,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 48,
          alignItems: "center",
        }}
      >
        <motion.div
          initial={{ opacity: 0, x: -18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
        >
          <GitHubCard
            owner="huggingface"
            name="Repo2RLEnv"
            description="Convert any repo into an RL environment."
            stars={450}
            forks={71}
            issues={0}
            contributors={6}
            width={540}
            starPulse
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.42 }}
          style={{ display: "flex", flexDirection: "column", gap: 22 }}
        >
          <div style={{ fontSize: 32, color: T.text, lineHeight: 1.4 }}>
            Standardizing the <Accent color="emerald">generation of coding RL environments</Accent>{" "}
            — at scale.
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            {USES.map((u) => (
              <span
                key={u}
                style={{
                  fontFamily: MONO,
                  fontSize: 20,
                  color: T.textMuted,
                  border: `1.5px solid ${T.border}`,
                  borderRadius: 999,
                  padding: "8px 18px",
                }}
              >
                {u}
              </span>
            ))}
          </div>

          {/* All that's left of the old slide 32 — the code, no call to action. */}
          <div
            style={{
              background: "#fff",
              borderRadius: 16,
              padding: 14,
              boxShadow: glow.emerald,
              alignSelf: "flex-start",
              marginTop: 6,
            }}
          >
            <img
              src={qr}
              alt="Repo2RLEnv on GitHub"
              style={{ width: 186, height: 186, display: "block", imageRendering: "pixelated" }}
            />
          </div>
        </motion.div>
      </div>
    </SlideShell>
  );
}
