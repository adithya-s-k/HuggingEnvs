import { useState } from "react";
import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO, THEMES, type ThemeName } from "../themes";
import { config } from "../config";
import type { Slide } from "../slides";

export const DRAWER_W = 320;

/** Gear in the corner. Tagged data-chrome so exports don't capture it. */
export function GearButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const { T } = useTheme();
  return (
    <button
      onClick={onToggle}
      aria-label="Settings"
      title="Settings"
      data-chrome
      style={{
        position: "fixed",
        top: 18,
        right: 20,
        width: 42,
        height: 42,
        display: "grid",
        placeItems: "center",
        borderRadius: 12,
        border: `1.5px solid ${T.border}`,
        background: T.bgRaised,
        color: T.textMuted,
        fontSize: 19,
        opacity: open ? 1 : 0.75,
        zIndex: 60,
      }}
    >
      ⚙
    </button>
  );
}

type ExportKind = "pdf" | "pptx";
type Status = { kind: ExportKind; state: "running" | "done" | "failed" | "manual"; note?: string };

/**
 * Settings drawer: slide list, theme controls, and the export buttons.
 *
 * Export has two paths on purpose:
 *  - PDF always works in the browser (print mode → "Save as PDF").
 *  - PPTX needs the headless-Chromium capture in scripts/export-deck.mjs,
 *    because a real image per slide is the only way to keep glows, SVG filters
 *    and iframes faithful. In `npm run dev` the button runs it through a dev
 *    endpoint; on a deployed build there's no server, so we hand over the
 *    one-line command instead of pretending.
 */
export function SettingsDrawer({
  slides,
  index,
  goto,
  showArrows,
  setShowArrows,
  onPrint,
  onClose,
}: {
  slides: Slide[];
  index: number;
  goto: (i: number) => void;
  showArrows: boolean;
  setShowArrows: (v: boolean) => void;
  onPrint: () => void;
  onClose: () => void;
}) {
  const { T, mode, toggle, name, setName } = useTheme();
  const [status, setStatus] = useState<Status | null>(null);
  const canRunScripts = import.meta.env.DEV;
  const command = "npm run export";

  const runExport = async (kind: ExportKind) => {
    if (kind === "pdf" && !canRunScripts) {
      onPrint(); // browser print — the honest client-side path
      return;
    }
    if (!canRunScripts) {
      try {
        await navigator.clipboard.writeText(command);
        setStatus({ kind, state: "manual", note: "command copied — run it in the repo" });
      } catch {
        setStatus({ kind, state: "manual", note: `run: ${command}` });
      }
      return;
    }
    setStatus({ kind, state: "running", note: "capturing slides…" });
    try {
      const res = await fetch(`/__export/${kind}`);
      const data = (await res.json()) as { ok: boolean; log?: string };
      setStatus({
        kind,
        state: data.ok ? "done" : "failed",
        note: data.ok ? "written to export/" : (data.log ?? "").split("\n").slice(-1)[0],
      });
    } catch (e) {
      setStatus({ kind, state: "failed", note: String(e) });
    }
  };

  const label = (kind: ExportKind) => {
    const busy = status?.kind === kind && status.state === "running";
    if (busy) return "working…";
    return kind === "pdf" ? "Export PDF" : "Export PPTX";
  };

  return (
    <div
      style={{
        width: DRAWER_W,
        height: "100%",
        background: T.bgRaised,
        borderRight: `1px solid ${T.border}`,
        display: "flex",
        flexDirection: "column",
        fontFamily: MONO,
      }}
    >
      <div
        style={{
          padding: "16px 18px",
          borderBottom: `1px solid ${T.border}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span style={{ color: T.textMuted, fontSize: 13, letterSpacing: 2 }}>
          {config.title.toUpperCase()}
        </span>
        <button
          onClick={onClose}
          aria-label="Close"
          style={{
            background: "none",
            border: "none",
            color: T.textDim,
            fontSize: 18,
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      {/* slide list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "10px 8px" }}>
        {slides.map((s, i) => (
          <button
            key={s.id}
            onClick={() => goto(i)}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "7px 10px",
              marginBottom: 2,
              borderRadius: 8,
              border: "none",
              background: i === index ? T.bg : "transparent",
              color: i === index ? T.accent2 : T.textDim,
              fontSize: 13,
              fontFamily: MONO,
            }}
          >
            <span style={{ opacity: 0.6, marginRight: 8 }}>
              {String(i + 1).padStart(2, "0")}
            </span>
            {s.title}
          </button>
        ))}
      </div>

      {/* controls */}
      <div
        style={{
          borderTop: `1px solid ${T.border}`,
          padding: 14,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <Row label="Theme">
          <select
            value={name}
            onChange={(e) => setName(e.target.value as ThemeName)}
            style={selectStyle(T.bg, T.text, T.border)}
          >
            {Object.keys(THEMES).map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </Row>

        <Row label="Mode">
          <button onClick={toggle} style={btnStyle(T.bg, T.text, T.border)}>
            {mode === "dark" ? "🌙 dark" : "☀ light"}
          </button>
        </Row>

        <Row label="Arrows">
          <button
            onClick={() => setShowArrows(!showArrows)}
            style={btnStyle(T.bg, T.text, T.border)}
          >
            {showArrows ? "shown" : "hidden"}
          </button>
        </Row>

        <div style={{ height: 1, background: T.border, margin: "2px 0" }} />

        <div style={{ display: "flex", gap: 8 }}>
          {(["pdf", "pptx"] as ExportKind[]).map((kind) => (
            <button
              key={kind}
              onClick={() => runExport(kind)}
              disabled={status?.state === "running"}
              style={{
                ...btnStyle(T.bg, T.text, T.border),
                flex: 1,
                padding: "10px 8px",
                borderColor: T.accent,
                color: T.text,
              }}
            >
              {label(kind)}
            </button>
          ))}
        </div>

        {status && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              fontSize: 11,
              lineHeight: 1.5,
              color: status.state === "failed" ? T.diffMinus : T.textDim,
              wordBreak: "break-word",
            }}
          >
            {status.note}
          </motion.div>
        )}

        <div style={{ fontSize: 10.5, color: T.textDim, lineHeight: 1.5 }}>
          {canRunScripts
            ? "Runs the real capture and writes export/."
            : "PDF prints from this page; PPTX needs `npm run export` in the repo."}
        </div>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  const { T } = useTheme();
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <span style={{ fontSize: 12, color: T.textDim, letterSpacing: 1 }}>{label}</span>
      {children}
    </div>
  );
}

const btnStyle = (bg: string, fg: string, border: string) => ({
  background: bg,
  color: fg,
  border: `1.5px solid ${border}`,
  borderRadius: 9,
  padding: "6px 12px",
  fontSize: 12,
  fontFamily: MONO,
});

const selectStyle = (bg: string, fg: string, border: string) => ({
  ...btnStyle(bg, fg, border),
  padding: "6px 8px",
});
