import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { Timeline } from "../components/Timeline";
import { useTheme } from "../ThemeContext";
import { Accent } from "../components/primitives";

export function ParadigmSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={3} kicker="The paradigm" title={<>How did we get here?</>}>
      <div style={{ position: "absolute", top: 340, left: 96, right: 96 }}>
        <Timeline active={3} />
      </div>
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.1, type: "spring", damping: 22 }}
        style={{
          position: "absolute",
          bottom: 120,
          left: 96,
          right: 96,
          textAlign: "center",
          fontSize: 30,
          color: T.textMuted,
          lineHeight: 1.4,
        }}
      >
        Every step made models better — until the next one had to{" "}
        <Accent color="emerald">change how we teach them</Accent>.
      </motion.div>
    </SlideShell>
  );
}
