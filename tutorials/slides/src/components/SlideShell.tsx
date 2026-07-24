import { motion } from "framer-motion";
import { createContext, useContext, type ReactNode } from "react";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { spring } from "./primitives";

// Deck sets this to the current slide's auto-derived section number, so
// slides no longer hard-code their kicker index (insert freely, numbers fix
// themselves). Falls back to the `index` prop if no context is present.
export const SectionNumberContext = createContext<number | null>(null);

// Consistent deck chrome for content slides: kicker (NN / SECTION),
// big title, accent rule, and a small page index in the corner.
export function SlideShell({
  index,
  kicker,
  title,
  children,
  titleSize = 46,
}: {
  index?: number; // optional manual override; normally auto-numbered
  kicker: string; // e.g. "TRADITIONAL RL"
  title: ReactNode;
  children?: ReactNode;
  titleSize?: number; // override the (compact) default when a slide needs it
}) {
  const { T } = useTheme();
  const ctxNo = useContext(SectionNumberContext);
  const idx = String(ctxNo ?? index ?? 0).padStart(2, "0");

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {/* Header — kept compact so content gets the room */}
      <div style={{ position: "absolute", top: 52, left: 96, right: 96 }}>
        <motion.div
          initial={{ opacity: 0, x: -14 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ ...spring, delay: 0.05 }}
          style={{
            fontSize: 17,
            fontWeight: 700,
            letterSpacing: 5,
            textTransform: "uppercase",
            marginBottom: 10,
            fontFamily: MONO,
          }}
        >
          <span style={{ color: T.emerald }}>{idx}</span>
          <span style={{ color: T.textDim }}> &nbsp;/&nbsp; {kicker}</span>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...spring, delay: 0.12 }}
          style={{
            fontSize: titleSize,
            fontWeight: 800,
            color: T.white,
            letterSpacing: -1,
            lineHeight: 1.06,
            maxWidth: 1040,
          }}
        >
          {title}
        </motion.div>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: 260 }}
          transition={{ ...spring, delay: 0.24 }}
          style={{
            marginTop: 20,
            height: 7,
            background: T.white,
            opacity: 1,
            borderRadius: 4,
          }}
        />
      </div>

      {/* Content region — slides position their own content below the header */}
      {children}

      {/* Footer — just a small page index in the corner */}
      <div
        style={{
          position: "absolute",
          bottom: 44,
          right: 96,
          fontFamily: MONO,
          fontSize: 18,
          color: T.textDim,
          letterSpacing: 2,
        }}
      >
        {idx}
      </div>
    </div>
  );
}
