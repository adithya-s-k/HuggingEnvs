import { motion } from "framer-motion";
import { SlideShell } from "../../components/SlideShell";
import { useTheme } from "../../ThemeContext";
import { MONO } from "../../theme";

type Row = { name: string; from: string; to: string; color: string };

export function CurvesSlide({
  title,
  img,
  rows,
}: {
  title: string;
  img: string;
  rows: Row[];
}) {
  const { T } = useTheme();
  return (
    <SlideShell kicker="Results" title={<>{title}</>}>
      <div
        style={{
          position: "absolute",
          top: 190,
          left: 90,
          right: 90,
          bottom: 50,
          display: "grid",
          gridTemplateColumns: "1fr 360px",
          gap: 44,
          alignItems: "center",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", damping: 22, delay: 0.3 }}
          style={{ background: "#fff", borderRadius: 12, padding: 12, border: `1.5px solid ${T.border}`, display: "grid", placeItems: "center", height: "100%" }}
        >
          <img src={img} alt={title} style={{ maxWidth: "100%", maxHeight: "100%", display: "block", borderRadius: 6 }} />
        </motion.div>

        <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
          <div style={{ fontFamily: MONO, fontSize: 16, letterSpacing: 2, color: T.textDim, textTransform: "uppercase" }}>
            eval reward
          </div>
          {rows.map((r, i) => (
            <motion.div
              key={r.name}
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: "spring", damping: 22, delay: 0.45 + i * 0.15 }}
              style={{ display: "flex", flexDirection: "column", gap: 6 }}
            >
              <span style={{ fontSize: 24, fontWeight: 700, color: T.white }}>{r.name}</span>
              <span style={{ fontFamily: MONO, fontSize: 30, fontWeight: 800, display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ color: T.textDim }}>{r.from}</span>
                <span style={{ color: r.color }}>→ {r.to} ↑</span>
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </SlideShell>
  );
}
