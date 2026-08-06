import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import { GitHubMark } from "./figures";

// A GitHub-style repo card. Theme-inverted: white card on the dark deck,
// dark card on the light deck (like the real github.com preview).
export function GitHubCard({
  owner,
  name,
  description,
  stars,
  forks,
  issues = 0,
  contributors = 1,
  width = 560,
  compact = false,
  starPulse = false,
}: {
  owner: string;
  name: string;
  description: string;
  stars: number;
  forks: number;
  issues?: number;
  contributors?: number;
  width?: number;
  compact?: boolean;
  starPulse?: boolean; // highlight the star stat (e.g. while it's climbing)
}) {
  const { mode } = useTheme();
  const dark = mode === "dark";
  // invert relative to the deck
  const bg = dark ? "#ffffff" : "#0d1117";
  const ink = dark ? "#1f2328" : "#e6edf3";
  const muted = dark ? "#59636e" : "#8b949e";
  const border = dark ? "#d1d9e0" : "#30363d";

  const s = compact
    ? { pad: "20px 22px", owner: 20, name: 34, desc: 17, statN: 20, statI: 15, label: 12, gh: 30, gap: 30, mt1: 12, mt2: 18 }
    : { pad: "30px 32px", owner: 30, name: 52, desc: 24, statN: 26, statI: 20, label: 15, gh: 44, gap: 44, mt1: 18, mt2: 26 };

  const Stat = ({ icon, n, label, hot }: { icon: string; n: number; label: string; hot?: boolean }) => (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: s.statN,
          fontWeight: 700,
          color: hot ? "#e3a008" : ink,
        }}
      >
        <span style={{ fontSize: s.statI, color: hot ? "#e3a008" : muted }}>{icon}</span>
        {n}
      </span>
      <span style={{ fontFamily: MONO, fontSize: s.label, color: muted }}>{label}</span>
    </div>
  );

  return (
    <div
      style={{
        width,
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: 16,
        padding: s.pad,
        boxShadow: "0 16px 50px rgba(0,0,0,0.4)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: s.owner, color: muted, fontWeight: 500, lineHeight: 1.1 }}>{owner}/</div>
          <div style={{ fontSize: s.name, fontWeight: 800, color: ink, letterSpacing: -1, lineHeight: 1.05 }}>
            {name}
          </div>
        </div>
        <GitHubMark size={s.gh} color={ink} />
      </div>

      <div style={{ fontSize: s.desc, color: muted, marginTop: s.mt1, lineHeight: 1.35 }}>{description}</div>

      <div style={{ display: "flex", gap: s.gap, marginTop: s.mt2 }}>
        <Stat icon="👥" n={contributors} label="Contributors" />
        <Stat icon="⊙" n={issues} label="Issues" />
        <Stat icon="★" n={stars} label="Stars" hot={starPulse} />
        <Stat icon="⑂" n={forks} label="Forks" />
      </div>
    </div>
  );
}
