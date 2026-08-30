import { motion } from "framer-motion";
import { SlideShell } from "../components/SlideShell";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

const REASONS = [
  { icon: "✓", title: "Easy to verify", body: "tests pass or they don’t" },
  { icon: "⟳", title: "Deterministic", body: "same input, same result" },
  { icon: "$", title: "High value", body: "we pay a lot for coding" },
];

function Card({ icon, title, body, i }: { icon: string; title: string; body: string; i: number }) {
  const { T } = useTheme();
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 22, delay: 0.3 + i * 0.14 }}
      style={{
        border: `1.5px solid ${T.border}`,
        borderTop: `3px solid ${T.emerald}`,
        borderRadius: 16,
        padding: "30px 28px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      <span
        style={{
          width: 60,
          height: 60,
          borderRadius: 14,
          display: "grid",
          placeItems: "center",
          fontSize: 30,
          color: T.emerald,
          border: `1.5px solid ${T.emerald}`,
        }}
      >
        {icon}
      </span>
      <span style={{ fontSize: 30, fontWeight: 700, color: T.white }}>{title}</span>
      <span style={{ fontFamily: MONO, fontSize: 20, color: T.textDim, lineHeight: 1.4 }}>{body}</span>
    </motion.div>
  );
}

export function WhyCodingSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Why code" title={<>Start with coding</>}>
      <div
        style={{
          position: "absolute",
          top: 250,
          left: 96,
          right: 96,
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 28,
        }}
      >
        {REASONS.map((r, i) => (
          <Card key={r.title} {...r} i={i} />
        ))}
      </div>
      <div style={{ position: "absolute", bottom: 100, left: 96, right: 96, fontSize: 24, color: T.textMuted }}>
        …and there’s a near-endless supply of real code — repos, issues, PRs.
      </div>
    </SlideShell>
  );
}
