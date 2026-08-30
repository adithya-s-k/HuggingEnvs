// ──────────────────────────────────────────────────────────────
// Themes are token sets, not CSS. A theme is a dark + light pair so slide
// code never branches on mode — only the values change.
//
// Three tokens carry the identity: bg, accent (structure / chrome) and
// accent2 (in-text emphasis, "the verified thing"). Everything else is muted
// greys. Add a theme by adding an entry to THEMES; nothing else changes.
// ──────────────────────────────────────────────────────────────

export type Palette = {
  bg: string;
  bgRaised: string;
  border: string;
  borderStrong: string;
  white: string; // max-contrast foreground (near-white on dark, ink on light)
  text: string;
  textMuted: string;
  textDim: string;
  accent: string;
  accentDim: string;
  accent2: string;
  accent2Dim: string;
  diffPlus: string;
  diffMinus: string;
};

export type Glow = {
  accent: string;
  accent2: string;
  accentText: string;
  accent2Text: string;
};

export type Mode = "dark" | "light";
export type Theme = { mode: Mode; T: Palette; glow: Glow };

const greysDark = {
  white: "#ffffff",
  text: "#f8fafd",
  textMuted: "#d0d8e6",
  textDim: "#97a1b5",
};
const greysLight = {
  white: "#0b1020",
  text: "#161d2b",
  textMuted: "#3d4657",
  textDim: "#616c80",
};

// rgba() from a hex, for glows
const rgba = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

const glowFor = (mode: Mode, accent: string, accent2: string): Glow =>
  mode === "dark"
    ? {
        accent: `0 0 18px ${rgba(accent, 0.45)}`,
        accent2: `0 0 18px ${rgba(accent2, 0.45)}`,
        accentText: `0 0 22px ${rgba(accent, 0.5)}`,
        accent2Text: `0 0 22px ${rgba(accent2, 0.55)}`,
      }
    : {
        accent: `0 8px 24px ${rgba(accent, 0.16)}`,
        accent2: `0 8px 24px ${rgba(accent2, 0.18)}`,
        accentText: "none",
        accent2Text: "none",
      };

export const THEMES = {
  // Near-black · violet · mint. High contrast, reads well on bad projectors.
  forge: {
    dark: {
      bg: "#07090f",
      bgRaised: "#0e1422",
      border: "#283149",
      borderStrong: "#3a4560",
      accent: "#b06bff",
      accentDim: "#7d3ff0",
      accent2: "#10f0a4",
      accent2Dim: "#0bc586",
      diffPlus: "#10f0a4",
      diffMinus: "#ff5470",
      ...greysDark,
    },
    light: {
      bg: "#fbfcfe",
      bgRaised: "#ffffff",
      border: "#c4cddb",
      borderStrong: "#9fabc0",
      accent: "#7c3aed",
      accentDim: "#9d6bff",
      accent2: "#059669",
      accent2Dim: "#0a9d6e",
      diffPlus: "#059669",
      diffMinus: "#e11d48",
      ...greysLight,
    },
  },
  // Off-white · navy · brick. Quiet and paper-like; light mode is the default look.
  paper: {
    dark: {
      bg: "#12141a",
      bgRaised: "#1b1e26",
      border: "#333844",
      borderStrong: "#495062",
      accent: "#7ea2ff",
      accentDim: "#5b83e8",
      accent2: "#ff8f6b",
      accent2Dim: "#e2724f",
      diffPlus: "#7fd6a2",
      diffMinus: "#ff8f6b",
      ...greysDark,
    },
    light: {
      bg: "#fdfcf9",
      bgRaised: "#ffffff",
      border: "#d8d3c8",
      borderStrong: "#b3ab9b",
      accent: "#1d3b8b",
      accentDim: "#3f5ba8",
      accent2: "#b23a20",
      accent2Dim: "#c95a3d",
      diffPlus: "#1d7a4f",
      diffMinus: "#b23a20",
      ...greysLight,
    },
  },
  // Charcoal · cyan · amber. Cool/technical, good for systems talks.
  carbon: {
    dark: {
      bg: "#0b0f12",
      bgRaised: "#141a1f",
      border: "#26313a",
      borderStrong: "#3a4854",
      accent: "#38bdf8",
      accentDim: "#0f8fc7",
      accent2: "#fbbf24",
      accent2Dim: "#d99b0d",
      diffPlus: "#4ade80",
      diffMinus: "#fb7185",
      ...greysDark,
    },
    light: {
      bg: "#f8fafb",
      bgRaised: "#ffffff",
      border: "#ccd6dd",
      borderStrong: "#9fb0bc",
      accent: "#0369a1",
      accentDim: "#0284c7",
      accent2: "#b45309",
      accent2Dim: "#d97706",
      diffPlus: "#15803d",
      diffMinus: "#be123c",
      ...greysLight,
    },
  },
} satisfies Record<string, { dark: Palette; light: Palette }>;

export type ThemeName = keyof typeof THEMES;

export const themeFor = (name: ThemeName, mode: Mode): Theme => {
  const T = THEMES[name][mode];
  return { mode, T, glow: glowFor(mode, T.accent, T.accent2) };
};

export const MONO =
  'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Monaco, Consolas, monospace';

// ── Design canvas ──────────────────────────────────────────────
// Every slide is authored against this fixed 16:9 canvas and uniformly scaled
// to fit the viewport, so the layout is identical on any projector.
export const STAGE_W = 1280;
export const STAGE_H = 720;
