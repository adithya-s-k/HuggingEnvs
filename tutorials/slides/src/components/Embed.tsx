import { useMemo } from "react";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";
import classicalRl from "../embeds/d3-classical-rl.html?raw";
import anatomyHero from "../embeds/d3-anatomy-hero.html?raw";
import llmRlCoding from "../embeds/d3-llm-rl-coding.html?raw";

// The self-contained D3/SVG fragments from the RL guide, keyed by name.
const FRAGMENTS: Record<string, string> = {
  "classical-rl": classicalRl,
  anatomy: anatomyHero,
  "llm-rl-coding": llmRlCoding,
};

// Render a blog embed inside a themed iframe: the fragment reads CSS vars,
// so we map our palette onto them (purple lines, white text, etc.).
export function Embed({
  name,
  height = 560,
  width = "100%",
}: {
  name: keyof typeof FRAGMENTS | string;
  height?: number;
  width?: number | string;
}) {
  const { T, mode } = useTheme();
  const fragment = FRAGMENTS[name] ?? "";

  const srcDoc = useMemo(
    () => `<!doctype html><html><head><meta charset="utf-8"/>
<style>
  :root{
    color-scheme: ${mode};
    --border-color:${T.border};
    --muted-color:${T.textDim};
    --primary-color:${T.lavender};
    --surface-bg:transparent;
    --text-color:${T.text};
    --bg:transparent;
    --accent:${T.emerald};
  }
  html,body{margin:0;padding:0;background:transparent;color:${T.text};
    font-family:${MONO};font-size:15px;overflow:hidden;}
  *{box-sizing:border-box;}
</style></head><body>${fragment}</body></html>`,
    [fragment, mode, T.border, T.textDim, T.lavender, T.text, T.emerald],
  );

  return (
    <iframe
      // remount on theme change so the embed re-reads colors
      key={mode}
      title={String(name)}
      srcDoc={srcDoc}
      scrolling="no"
      style={{
        width: typeof width === "number" ? `${width}px` : width,
        height,
        border: "none",
        background: "transparent",
        display: "block",
      }}
    />
  );
}
