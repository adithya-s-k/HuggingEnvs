import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";

/**
 * A code panel sized for a projector. Deliberately minimal highlighting — no
 * syntax-highlighting dependency, just comments / strings / numbers / keywords,
 * which is all that reads at 10 metres. `highlight` dims every line except the
 * given 1-based line numbers, so you can point at the line you're discussing.
 */
const KEYWORDS =
  /\b(def|return|import|from|class|if|else|elif|for|while|with|as|in|not|and|or|None|True|False|await|async|const|let|var|function|export|type|interface|new)\b/g;

export function CodeBlock({
  code,
  language = "python",
  highlight,
  fontSize = 22,
  showLineNumbers = true,
}: {
  code: string;
  language?: string;
  highlight?: number[];
  fontSize?: number;
  showLineNumbers?: boolean;
}) {
  const { T } = useTheme();
  const lines = code.replace(/\n$/, "").split("\n");
  const focus = highlight && highlight.length > 0 ? new Set(highlight) : null;

  return (
    <div
      style={{
        background: T.bgRaised,
        border: `1.5px solid ${T.border}`,
        borderRadius: 16,
        padding: "26px 30px",
        fontFamily: MONO,
        fontSize,
        lineHeight: 1.6,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          fontSize: fontSize * 0.6,
          color: T.textDim,
          letterSpacing: 2,
          textTransform: "uppercase",
          marginBottom: 14,
        }}
      >
        {language}
      </div>
      {lines.map((line, i) => {
        const dim = focus ? !focus.has(i + 1) : false;
        return (
          <div key={i} style={{ display: "flex", gap: 18, opacity: dim ? 0.38 : 1 }}>
            {showLineNumbers && (
              <span style={{ color: T.textDim, minWidth: fontSize * 1.4, textAlign: "right" }}>
                {i + 1}
              </span>
            )}
            <span style={{ whiteSpace: "pre", color: T.text }}>{tokenize(line, T)}</span>
          </div>
        );
      })}
    </div>
  );
}

type Colors = { textDim: string; accent: string; accent2: string; text: string };

function tokenize(line: string, T: Colors): React.ReactNode {
  // Comment wins outright — the rest of the line is prose.
  const hash = line.search(/(^|\s)(#|\/\/)/);
  if (hash >= 0) {
    return (
      <>
        {tokenize(line.slice(0, hash), T)}
        <span style={{ color: T.textDim, fontStyle: "italic" }}>{line.slice(hash)}</span>
      </>
    );
  }

  const out: React.ReactNode[] = [];
  let last = 0;
  const re = new RegExp(`${KEYWORDS.source}|("[^"]*"|'[^']*')|\\b(\\d+\\.?\\d*)\\b`, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(line))) {
    if (m.index > last) out.push(line.slice(last, m.index));
    const color = m[2] ? T.accent2 : m[3] ? T.accent2 : T.accent;
    out.push(
      <span key={m.index} style={{ color, fontWeight: m[1] ? 700 : 400 }}>
        {m[0]}
      </span>,
    );
    last = m.index + m[0].length;
  }
  if (last < line.length) out.push(line.slice(last));
  return <>{out}</>;
}
