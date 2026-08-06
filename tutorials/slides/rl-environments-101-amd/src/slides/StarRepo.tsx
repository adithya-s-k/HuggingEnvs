import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { GitHubCard } from "../components/GitHubCard";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import qr from "../assets/qr-repo2rlenv.png";

const STARS = 450;

export function StarRepoSlide() {
  const { T } = useTheme();

  return (
    <SlideShell kicker="Your turn" title={<>Star the repo ⭐</>}>
      <div
        style={{
          position: "absolute",
          top: 172,
          left: 80,
          right: 80,
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
          <div style={{ background: "#fff", borderRadius: 22, padding: 20 }}>
            <img src={qr} alt="Star Repo2RLEnv" style={{ width: 360, height: 360, display: "block", imageRendering: "pixelated" }} />
          </div>
        </motion.div>

        {/* repo card + where to point the camera */}
        <motion.div
          initial={{ opacity: 0, x: 18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.45 }}
          style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24 }}
        >
          <GitHubCard
            owner="huggingface"
            name="Repo2RLEnv"
            description="Convert any repo into an RL environment."
            stars={STARS}
            forks={71}
            contributors={6}
            width={440}
            compact
          />
          <div style={{ fontFamily: MONO, fontSize: 22, color: T.textDim, letterSpacing: 1 }}>
            github.com/huggingface/Repo2RLEnv
          </div>
        </motion.div>
      </div>
    </SlideShell>
  );
}
