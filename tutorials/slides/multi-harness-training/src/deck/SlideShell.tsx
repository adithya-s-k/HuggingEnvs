import { motion } from "framer-motion";
import { createContext, useContext, type ReactNode } from "react";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { spring } from "../primitives";

// Deck sets this to the current slide's auto-derived section number, so slides
// never hard-code their kicker index — insert a slide anywhere and the numbers
// fix themselves.
export const SectionNumberContext = createContext<number | null>(null);

/**
 * Standard chrome for a content slide: kicker (NN / SECTION), big title, and a
 * page index in the corner. Slides position their own content underneath.
 */
export function SlideShell({
  index,
  kicker,
  title,
  children,
  titleSize = 46,
}: {
  index?: number; // manual override; normally auto-numbered
  kicker: string; // e.g. "METHOD"
  title: ReactNode;
  children?: ReactNode;
  titleSize?: number;
}) {
  const { T } = useTheme();
  const ctxNo = useContext(SectionNumberContext);
  const idx = String(ctxNo ?? index ?? 0).padStart(2, "0");

  return (
    <div style={{ position: "absolute", inset: 0 }}>
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
          <span style={{ color: T.accent2 }}>{idx}</span>
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
      </div>

      {children}

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
