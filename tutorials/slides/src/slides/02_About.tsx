import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { Stagger, Rise, Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { HFMark } from "../components/figures";
import {
  AppleLogo,
  MetaLogo,
  MicrosoftLogo,
  GitHubLogo,
  CognitiveLabLogo,
} from "../components/logos";
import photo from "../assets/adithyask.jpeg";

function Row({
  label,
  children,
}: {
  label?: string;
  children: React.ReactNode;
}) {
  const { T } = useTheme();
  return (
    <Rise>
      {label && (
        <div
          style={{
            fontFamily: MONO,
            fontSize: 15,
            letterSpacing: 3,
            color: T.textDim,
            textTransform: "uppercase",
            marginBottom: 12,
          }}
        >
          {label}
        </div>
      )}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 18,
          fontSize: 30,
          color: T.text,
        }}
      >
        {children}
      </div>
    </Rise>
  );
}

export function AboutSlide() {
  const { T, glow } = useTheme();

  return (
    <SlideShell index={1} kicker="whoami" title={<>Adithya S Kolavi</>}>
      <div
        style={{
          position: "absolute",
          top: 200,
          left: 96,
          right: 96,
          display: "flex",
          gap: 72,
          alignItems: "center",
        }}
      >
        {/* Photo */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", damping: 18, delay: 0.2 }}
          style={{ flex: "0 0 auto" }}
        >
          <div
            style={{
              width: 300,
              height: 300,
              borderRadius: 26,
              padding: 3,
              background: `linear-gradient(140deg, ${T.lavender}, ${T.emerald})`,
              boxShadow: glow.lavender,
            }}
          >
            <img
              src={photo}
              alt="Adithya S Kolavi"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                borderRadius: 23,
                display: "block",
              }}
            />
          </div>
        </motion.div>

        {/* Bio — generously spaced, logo-forward */}
        <div style={{ flex: 1 }}>
          <Stagger gap={0.13} delay={0.35} style={{ display: "flex", flexDirection: "column", gap: 26 }}>
            <Row label="Now">
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
                  <HFMark size={40} />
                  <span>
                    <b style={{ color: T.white }}>Hugging Face</b> · post-training
                  </span>
                </div>
                <div style={{ fontSize: 24, color: T.emerald }}>
                  🚀 making RL go brrrrr
                </div>
              </div>
            </Row>

            <Row label="Previously">
              <AppleLogo size={38} color={T.text} />
              <span style={{ marginRight: 8 }}>Apple</span>
              <MicrosoftLogo size={34} />
              <span>Microsoft Research</span>
            </Row>

            <Row label="Founded — grant from Meta">
              <CognitiveLabLogo size={44} />
              <span>
                <b style={{ color: T.white }}>CognitiveLab</b>
              </span>
              <span style={{ color: T.textDim, fontSize: 26 }}>·</span>
              <MetaLogo size={34} color={T.text} />
              <span style={{ fontSize: 26, color: T.textMuted }}>Meta</span>
            </Row>

            <Row>
              <GitHubLogo size={38} color={T.text} />
              <span>
                I <span style={{ color: "#ff5470" }}>❤</span> open source ·{" "}
                <Accent color="emerald">12k+ stars</Accent> across my repos
              </span>
            </Row>
          </Stagger>
        </div>
      </div>
    </SlideShell>
  );
}
