import { motion } from "framer-motion";
import { Fragment } from "react";
import { MONO } from "../theme";

// VS Code "Dark+" token palette. The code panel is always dark (like an
// embedded editor) so colors read the same in light or dark deck themes.
const C = {
  bg: "#0d1117",
  panelBorder: "#30363d",
  headerBg: "#161b22",
  text: "#d4d4d4",
  comment: "#6a9955",
  string: "#ce9178",
  number: "#b5cea8",
  keyword: "#c586c0", // control flow
  decl: "#569cd6", // def / class / None / True / False / self
  type: "#4ec9b0", // known types / classes
  func: "#dcdcaa", // function calls & decorators
  op: "#d4d4d4",
  dim: "#8b949e",
};

const CONTROL = new Set([
  "import", "from", "return", "if", "else", "elif", "for", "while", "in", "not",
  "and", "or", "with", "as", "try", "except", "finally", "raise", "lambda",
  "yield", "async", "await", "pass", "break", "continue", "is", "del", "global",
]);
const DECL = new Set(["def", "class", "None", "True", "False", "self", "super"]);
const TYPES = new Set([
  "str", "int", "float", "bool", "list", "dict", "tuple", "set", "bytes",
  "Observation", "State", "Action", "Rubric", "FastMCP", "MCPEnvironment",
  "GRPOConfig", "GRPOTrainer", "Sandbox", "CodingEnv", "TestsPassRubric",
]);

type Tok = { t: string; c: string };

// Tokenize one line of Python into colored spans.
function pyTokens(line: string): Tok[] {
  const out: Tok[] = [];
  let i = 0;
  const push = (t: string, c: string) => t && out.push({ t, c });
  while (i < line.length) {
    const ch = line[i];
    // comment
    if (ch === "#") {
      push(line.slice(i), C.comment);
      break;
    }
    // string
    if (ch === '"' || ch === "'") {
      let j = i + 1;
      while (j < line.length && line[j] !== ch) {
        if (line[j] === "\\") j++;
        j++;
      }
      push(line.slice(i, j + 1), C.string);
      i = j + 1;
      continue;
    }
    // decorator
    if (ch === "@") {
      let j = i + 1;
      while (j < line.length && /[\w.]/.test(line[j])) j++;
      push(line.slice(i, j), C.func);
      i = j;
      continue;
    }
    // number
    if (/[0-9]/.test(ch)) {
      let j = i;
      while (j < line.length && /[0-9._]/.test(line[j])) j++;
      push(line.slice(i, j), C.number);
      i = j;
      continue;
    }
    // identifier / keyword
    if (/[A-Za-z_]/.test(ch)) {
      let j = i;
      while (j < line.length && /[\w]/.test(line[j])) j++;
      const word = line.slice(i, j);
      const isCall = line[j] === "(";
      let color = C.text;
      if (CONTROL.has(word)) color = C.keyword;
      else if (DECL.has(word)) color = C.decl;
      else if (TYPES.has(word)) color = C.type;
      else if (isCall) color = C.func;
      push(word, color);
      i = j;
      continue;
    }
    // whitespace / punctuation run
    let j = i;
    while (j < line.length && !/[\w"'@#]/.test(line[j])) j++;
    push(line.slice(i, Math.max(j, i + 1)), C.op);
    i = Math.max(j, i + 1);
  }
  return out;
}

// Tokenize one line of a shell transcript.
function shTokens(line: string): Tok[] {
  const trimmed = line.trimStart();
  if (!trimmed.startsWith("$")) return [{ t: line, c: C.comment }];
  const out: Tok[] = [];
  const lead = line.slice(0, line.length - trimmed.length);
  out.push({ t: lead + "$", c: C.dim });
  const rest = trimmed.slice(1);
  const hash = rest.indexOf("#");
  const cmd = hash >= 0 ? rest.slice(0, hash) : rest;
  const comment = hash >= 0 ? rest.slice(hash) : "";
  cmd.split(/(\s+)/).forEach((tok, idx) => {
    if (/^\s+$/.test(tok) || tok === "") out.push({ t: tok, c: C.text });
    else if (tok.startsWith("--") || tok.startsWith("-")) out.push({ t: tok, c: C.decl });
    else if (idx === 1) out.push({ t: tok, c: C.func }); // command name
    else out.push({ t: tok, c: C.text });
  });
  if (comment) out.push({ t: comment, c: C.comment });
  return out;
}

function renderLine(line: string, lang: string) {
  // ⟪…⟫ marks an emphasized span (emerald tint background), tokens still colored
  const parts = line.split(/(⟪[^⟫]*⟫)/g).filter((s) => s.length > 0);
  return parts.map((part, pi) => {
    const hi = part.startsWith("⟪") && part.endsWith("⟫");
    const text = hi ? part.slice(1, -1) : part;
    const toks = lang === "bash" ? shTokens(text) : pyTokens(text);
    const inner = toks.map((tk, i) => (
      <span key={i} style={{ color: tk.c }}>
        {tk.t}
      </span>
    ));
    return hi ? (
      <span key={pi} style={{ background: "rgba(16,240,164,0.14)", borderRadius: 3 }}>
        {inner}
      </span>
    ) : (
      <Fragment key={pi}>{inner}</Fragment>
    );
  });
}

export function CodeBlock({
  filename,
  lang = "python",
  code,
  fontSize = 22,
  delay = 0.25,
}: {
  filename?: string;
  lang?: string;
  code: string;
  fontSize?: number;
  delay?: number;
}) {
  const lines = code.replace(/\n$/, "").split("\n");

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", damping: 24, delay }}
      style={{
        background: C.bg,
        border: `1px solid ${C.panelBorder}`,
        borderRadius: 14,
        overflow: "hidden",
        boxShadow: "0 12px 40px rgba(0,0,0,0.4)",
      }}
    >
      {filename && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "11px 20px",
            background: C.headerBg,
            borderBottom: `1px solid ${C.panelBorder}`,
            fontFamily: MONO,
            fontSize: 15,
            color: C.dim,
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#ff5f56" }} />
            <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#ffbd2e" }} />
            <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#27c93f" }} />
            <span style={{ marginLeft: 8 }}>{filename}</span>
          </span>
          <span style={{ letterSpacing: 2, textTransform: "uppercase" }}>{lang}</span>
        </div>
      )}
      <pre
        style={{
          margin: 0,
          padding: "20px 24px",
          fontFamily: MONO,
          fontSize,
          lineHeight: 1.55,
          whiteSpace: "pre",
          overflow: "hidden",
          color: C.text,
        }}
      >
        {lines.map((line, i) => (
          <div key={i}>{line ? renderLine(line, lang) : " "}</div>
        ))}
      </pre>
    </motion.div>
  );
}
