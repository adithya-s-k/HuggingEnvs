import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { SlideShell } from "../components/SlideShell";
import { Rise, Stagger, spring } from "../components/primitives";
import { HFMark } from "../components/figures";

// Sits right after whoami: at a non-HF venue a chunk of the room knows the
// libraries but not that they come from one place. Two halves, weighted the
// same — the Hub you push to, and the packages you already import.
const PLATFORM = [
  { what: "Models", tail: "weights, in a git repo" },
  { what: "Datasets", tail: "versioned, streamable" },
  { what: "Spaces", tail: "a demo behind a URL" },
];

// Hugging Face's own homepage tagline. The two halves below cover what it does,
// so this line is spent on what it is. Swap in one string to change it.
const SUBTITLE = "The AI community building the future.";

// The last two are what this talk is actually built on, so they carry the accent.
const LIBS = [
  { name: "transformers" },
  { name: "diffusers" },
  { name: "datasets" },
  { name: "accelerate" },
  { name: "TRL", hot: true },
  { name: "OpenEnv", hot: true },
];

/** Small mono section label, so the two halves read as peers. */
function GroupLabel({ children }: { children: React.ReactNode }) {
  const { T } = useTheme();
  return (
    <div
      style={{
        fontFamily: MONO,
        fontSize: 17,
        fontWeight: 700,
        letterSpacing: 4,
        color: T.lavender,
        textTransform: "uppercase",
        marginBottom: 18,
      }}
    >
      {children}
    </div>
  );
}

export function HuggingFaceSlide() {
  const { T, glow, mode } = useTheme();

  // Soft halo behind the mark — the logo is already saturated, so this is
  // warmth rather than colour, and it stays out of the theme tokens.
  const halo =
    mode === "dark"
      ? "radial-gradient(circle, rgba(255,210,30,0.20) 0%, rgba(255,157,11,0.08) 45%, rgba(0,0,0,0) 70%)"
      : "radial-gradient(circle, rgba(255,190,30,0.30) 0%, rgba(255,157,11,0.10) 45%, rgba(0,0,0,0) 70%)";

  return (
    <SlideShell kicker="The platform" title={<>Hugging Face</>}>
      {/* Sits directly under the shell's title, above the two halves. */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring, delay: 0.2 }}
        style={{
          position: "absolute",
          top: 138,
          left: 96,
          right: 96,
          fontSize: 27,
          color: T.textMuted,
          letterSpacing: -0.2,
        }}
      >
        {SUBTITLE}
      </motion.div>

      <div
        style={{
          position: "absolute",
          top: 196,
          left: 96,
          right: 96,
          bottom: 66,
          display: "flex",
          alignItems: "center",
          gap: 68,
        }}
      >
        {/* Hero mark, captioned with the thing that makes it matter */}
        <motion.div
          initial={{ opacity: 0, scale: 0.82 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", damping: 16, stiffness: 140, delay: 0.15 }}
          style={{
            flex: "0 0 auto",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 18,
          }}
        >
          <div
            style={{
              width: 300,
              height: 300,
              display: "grid",
              placeItems: "center",
              position: "relative",
            }}
          >
            <div style={{ position: "absolute", inset: -28, background: halo }} />
            <HFMark size={244} />
          </div>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: 6,
              color: T.emerald,
              textShadow: glow.emeraldText,
              textTransform: "uppercase",
            }}
          >
            Open source
          </div>
        </motion.div>

        {/* Two halves: the Hub, then the packages */}
        <div style={{ flex: 1 }}>
          <Stagger gap={0.12} delay={0.4} style={{ display: "flex", flexDirection: "column", gap: 40 }}>
            <Rise>
              <div>
                <GroupLabel>The platform</GroupLabel>
                <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                  {PLATFORM.map((p) => (
                    <div key={p.what} style={{ display: "flex", alignItems: "center", gap: 20 }}>
                      <div
                        style={{
                          width: 5,
                          height: 38,
                          borderRadius: 3,
                          background: T.emerald,
                          boxShadow: glow.emerald,
                        }}
                      />
                      <span
                        style={{
                          fontSize: 44,
                          fontWeight: 800,
                          color: T.white,
                          letterSpacing: -1.2,
                          lineHeight: 1,
                        }}
                      >
                        {p.what}
                      </span>
                      <span style={{ fontSize: 24, color: T.textDim, letterSpacing: -0.2 }}>
                        {p.tail}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </Rise>

            <Rise>
              <div>
                <GroupLabel>The libraries</GroupLabel>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
                  {LIBS.map((l) => (
                    <span
                      key={l.name}
                      style={{
                        padding: "10px 20px",
                        borderRadius: 999,
                        border: `1.5px solid ${l.hot ? T.emerald : T.border}`,
                        background: T.bgRaised,
                        boxShadow: l.hot ? glow.emerald : "none",
                        fontFamily: MONO,
                        fontSize: 22,
                        fontWeight: 700,
                        color: l.hot ? T.emerald : T.white,
                        letterSpacing: 0.3,
                      }}
                    >
                      {l.name}
                    </span>
                  ))}
                </div>
              </div>
            </Rise>
          </Stagger>
        </div>
      </div>
    </SlideShell>
  );
}
