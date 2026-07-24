import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO, STAGE_W, STAGE_H } from "../theme";
import { Backdrop } from "./Backdrop";
import type { Slide } from "../slides";

export const DRAWER_W = 380;

// ── Gear icon ──────────────────────────────────────────────────
function Gear({ size = 20, color }: { size?: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

// Fixed gear button (top-right). Toggles the drawer.
export function GearButton({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  const { T } = useTheme();
  return (
    <button
      onClick={onToggle}
      aria-label="Settings"
      title="Settings"
      style={{
        position: "fixed",
        top: 18,
        right: 20,
        width: 42,
        height: 42,
        display: "grid",
        placeItems: "center",
        borderRadius: 11,
        border: `1.5px solid ${T.border}`,
        background: T.bgRaised,
        zIndex: 60,
        opacity: open ? 1 : 0.55,
        transition: "opacity .2s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
      onMouseLeave={(e) => (e.currentTarget.style.opacity = open ? "1" : "0.55")}
    >
      <motion.span
        animate={{ rotate: open ? 90 : 0 }}
        transition={{ type: "spring", damping: 16 }}
        style={{ display: "grid", placeItems: "center" }}
      >
        <Gear color={T.textMuted} />
      </motion.span>
    </button>
  );
}

// ── A tiny, non-interactive render of a slide, scaled into a card ──
const THUMB_W = 300;
const THUMB_H = (THUMB_W * STAGE_H) / STAGE_W;

function Thumb({ slide }: { slide: Slide }) {
  const { T } = useTheme();
  const Comp = slide.component;
  return (
    <div
      style={{
        width: THUMB_W,
        height: THUMB_H,
        position: "relative",
        overflow: "hidden",
        background: T.bg,
        borderRadius: 8,
      }}
    >
      <div
        style={{
          width: STAGE_W,
          height: STAGE_H,
          transform: `scale(${THUMB_W / STAGE_W})`,
          transformOrigin: "top left",
          position: "absolute",
          top: 0,
          left: 0,
          pointerEvents: "none",
        }}
      >
        <Backdrop />
        <Comp />
      </div>
    </div>
  );
}

// Drawer content — rendered inline as a real layout child (no fixed overlay),
// so opening it pushes the stage rather than covering it.
export function SettingsDrawer({
  slides,
  index,
  goto,
  showArrows,
  setShowArrows,
  onClose,
}: {
  slides: Slide[];
  index: number;
  goto: (i: number) => void;
  showArrows: boolean;
  setShowArrows: (v: boolean) => void;
  onClose: () => void;
}) {
  const { T, mode, setMode } = useTheme();

  return (
    <div
      style={{
        width: DRAWER_W,
        height: "100%",
        background: T.bg,
        borderRight: `1.5px solid ${T.border}`,
        display: "flex",
        flexDirection: "column",
        fontFamily: MONO,
      }}
    >
      {/* header */}
      <div style={{ padding: "22px 24px 18px", borderBottom: `1px solid ${T.border}` }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 18,
          }}
        >
          <span
            style={{
              fontSize: 12,
              letterSpacing: 3,
              color: T.textDim,
              textTransform: "uppercase",
            }}
          >
            Settings
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              border: "none",
              background: "transparent",
              color: T.textDim,
              fontSize: 20,
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {/* concise icon toggles */}
        <div style={{ display: "flex", gap: 12 }}>
          <IconToggle
            label={mode === "dark" ? "Dark" : "Light"}
            active
            onClick={() => setMode(mode === "dark" ? "light" : "dark")}
            T={T}
          >
            {mode === "dark" ? <MoonIcon color={T.text} /> : <SunIcon color={T.text} />}
          </IconToggle>
          <IconToggle
            label="Arrows"
            active={showArrows}
            onClick={() => setShowArrows(!showArrows)}
            T={T}
          >
            <ArrowsIcon color={showArrows ? T.text : T.textDim} />
          </IconToggle>
        </div>
      </div>

      {/* slide list */}
      <div style={{ padding: "16px 24px 24px", overflowY: "auto", flex: 1 }}>
        <div
          style={{
            fontSize: 12,
            letterSpacing: 3,
            color: T.textDim,
            textTransform: "uppercase",
            marginBottom: 14,
          }}
        >
          Slides · {slides.length}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {slides.map((s, i) => {
            const current = i === index;
            return (
              <button
                key={s.id}
                onClick={() => goto(i)}
                style={{ padding: 0, border: "none", background: "transparent", textAlign: "left" }}
              >
                <div
                  style={{
                    border: `2px solid ${current ? T.borderStrong : T.border}`,
                    borderRadius: 10,
                    overflow: "hidden",
                    outline: current ? `2px solid ${T.text}` : "none",
                    outlineOffset: -1,
                    transition: "border-color .15s",
                  }}
                >
                  <Thumb slide={s} />
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "baseline" }}>
                  <span
                    style={{
                      color: current ? T.text : T.textDim,
                      fontSize: 13,
                      fontWeight: 700,
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span style={{ color: current ? T.text : T.textMuted, fontSize: 14 }}>
                    {s.title}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Compact icon toggle: an icon + short label in a pill.
function IconToggle({
  label,
  active,
  onClick,
  children,
  T,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  T: { border: string; bgRaised: string; text: string; textDim: string };
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-pressed={active}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 9,
        padding: "9px 14px",
        borderRadius: 10,
        border: `1.5px solid ${active ? T.text : T.border}`,
        background: active ? T.bgRaised : "transparent",
        color: active ? T.text : T.textDim,
        fontSize: 13,
        fontWeight: 600,
        fontFamily: MONO,
      }}
    >
      {children}
      <span>{label}</span>
    </button>
  );
}

function MoonIcon({ color }: { color: string }) {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SunIcon({ color }: { color: string }) {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  );
}

function ArrowsIcon({ color }: { color: string }) {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 18l-6-6 6-6" />
      <path d="M9 6l6 6-6 6" opacity={0.55} />
    </svg>
  );
}
