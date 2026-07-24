// ──────────────────────────────────────────────────────────────
// The "forge" palette — ported from hf-motion / AdithyaSK.
// 3 colors only:  bg (near-black / white) · lavender (synthesis) · emerald (verified)
// Everything else is muted greys for text. Dark + light mirror each other
// so slide code is identical; only the values change.
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
  lavender: string;
  lavenderDim: string;
  emerald: string;
  emeraldDim: string;
  diffPlus: string;
  diffMinus: string;
};

export type Glow = {
  emerald: string;
  lavender: string;
  emeraldText: string;
  lavenderText: string;
};

export const dark: Palette = {
  bg: "#07090f",
  bgRaised: "#0e1422",
  border: "#283149",
  borderStrong: "#3a4560",
  white: "#ffffff",
  text: "#f8fafd", // primary — near-white
  textMuted: "#d0d8e6", // secondary — brightened for readability on dark
  textDim: "#97a1b5", // tertiary / structural — brightened
  lavender: "#b06bff",
  lavenderDim: "#7d3ff0",
  emerald: "#10f0a4",
  emeraldDim: "#0bc586",
  diffPlus: "#10f0a4",
  diffMinus: "#ff5470",
};

export const light: Palette = {
  bg: "#fbfcfe",
  bgRaised: "#ffffff",
  border: "#e3e8f1",
  borderStrong: "#cbd3e1",
  white: "#0b1020",
  text: "#161d2b",
  textMuted: "#3d4657", // darkened for readability on white
  textDim: "#616c80", // darkened

  lavender: "#7c3aed",
  lavenderDim: "#9d6bff",
  emerald: "#059669",
  emeraldDim: "#0a9d6e",
  diffPlus: "#059669",
  diffMinus: "#e11d48",
};

export const darkGlow: Glow = {
  emerald: "0 0 18px rgba(16,240,164,0.45)",
  lavender: "0 0 18px rgba(176,107,255,0.45)",
  emeraldText: "0 0 22px rgba(16,240,164,0.55)",
  lavenderText: "0 0 22px rgba(176,107,255,0.5)",
};

export const lightGlow: Glow = {
  emerald: "0 8px 24px rgba(5,150,105,0.18)",
  lavender: "0 8px 24px rgba(124,58,237,0.16)",
  emeraldText: "none",
  lavenderText: "none",
};

export const MONO =
  'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Monaco, Consolas, monospace';

export type Mode = "dark" | "light";

export type Theme = {
  mode: Mode;
  T: Palette;
  glow: Glow;
};

export const themeFor = (mode: Mode): Theme =>
  mode === "dark"
    ? { mode, T: dark, glow: darkGlow }
    : { mode, T: light, glow: lightGlow };

// ── Design canvas ──────────────────────────────────────────────
// Every slide is authored against this fixed 16:9 canvas and then
// uniformly scaled to fit the viewport. Guarantees an identical
// layout on any projector / screen.
export const STAGE_W = 1280;
export const STAGE_H = 720;
