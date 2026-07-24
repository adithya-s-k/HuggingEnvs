import { useTheme } from "../ThemeContext";

// Faint grid + vignette — gives the frame structure. Ported from the
// forge theme's gridBackdrop / vignette.
export function Backdrop() {
  const { T, mode } = useTheme();
  const gridOpacity = mode === "dark" ? 0.18 : 0.5;
  const vignette =
    mode === "dark"
      ? "radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.55) 100%)"
      : "radial-gradient(ellipse at center, transparent 45%, rgba(15,23,42,0.05) 100%)";

  return (
    <>
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            `linear-gradient(${T.border} 1px, transparent 1px),` +
            ` linear-gradient(90deg, ${T.border} 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
          opacity: gridOpacity,
          maskImage:
            "radial-gradient(ellipse at center, #000 30%, transparent 80%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at center, #000 30%, transparent 80%)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: vignette,
          pointerEvents: "none",
        }}
      />
    </>
  );
}
