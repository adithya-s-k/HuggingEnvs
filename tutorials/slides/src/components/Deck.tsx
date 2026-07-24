import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type TouchEvent as ReactTouchEvent,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO, STAGE_W, STAGE_H } from "../theme";
import { Backdrop } from "./Backdrop";
import { GearButton, SettingsDrawer, DRAWER_W } from "./Settings";
import { OverflowGuard } from "./OverflowGuard";
import { SectionNumberContext } from "./SlideShell";
import { sectionOf, type Slide } from "../slides";

// Uniformly scale the fixed 1280×720 canvas to fit whatever space the
// stage container currently has. Measuring the container (not the window)
// means the slide re-scales smoothly as the drawer pushes it narrower.
function useFitScale(ref: React.RefObject<HTMLElement>) {
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const compute = () => {
      const { width, height } = el.getBoundingClientRect();
      setScale(Math.min(width / STAGE_W, height / STAGE_H));
    };
    compute();
    const ro = new ResizeObserver(compute);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return scale;
}

const SLIDE_KEY = "rlenv-slides-index";

export function Deck({ slides }: { slides: Slide[] }) {
  const { T, toggle } = useTheme();
  const total = slides.length;
  const [[index, dir], setState] = useState<[number, number]>(() => {
    const saved = Number(
      typeof window !== "undefined" ? window.localStorage.getItem(SLIDE_KEY) : NaN,
    );
    const start = Number.isInteger(saved) && saved >= 0 && saved < total ? saved : 0;
    return [start, 0];
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showArrows, setShowArrows] = useState(true);

  // remember which slide we're on across refreshes
  useEffect(() => {
    try {
      window.localStorage.setItem(SLIDE_KEY, String(index));
    } catch {
      /* ignore */
    }
  }, [index]);

  const stageAreaRef = useRef<HTMLDivElement>(null);
  const scale = useFitScale(stageAreaRef);

  const go = useCallback(
    (next: number, direction: number) => {
      const clamped = Math.max(0, Math.min(total - 1, next));
      setState(([cur]) => (cur === clamped ? [cur, 0] : [clamped, direction]));
    },
    [total],
  );

  const next = useCallback(() => go(index + 1, 1), [go, index]);
  const prev = useCallback(() => go(index - 1, -1), [go, index]);
  const goto = useCallback((i: number) => go(i, i >= index ? 1 : -1), [go, index]);

  // touch swipe (mobile): horizontal drag → prev/next
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const onTouchStart = useCallback((e: ReactTouchEvent) => {
    const t = e.touches[0];
    touchStart.current = { x: t.clientX, y: t.clientY };
  }, []);
  const onTouchEnd = useCallback(
    (e: ReactTouchEvent) => {
      const s = touchStart.current;
      touchStart.current = null;
      if (!s) return;
      const t = e.changedTouches[0];
      const dx = t.clientX - s.x;
      const dy = t.clientY - s.y;
      // mostly-horizontal swipe past a threshold
      if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.4) {
        if (dx < 0) next();
        else prev();
      }
    },
    [next, prev],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      switch (e.key) {
        case "ArrowRight":
        case "PageDown":
        case " ":
          e.preventDefault();
          next();
          break;
        case "ArrowLeft":
        case "PageUp":
          e.preventDefault();
          prev();
          break;
        case "Home":
          e.preventDefault();
          go(0, -1);
          break;
        case "End":
          e.preventDefault();
          go(total - 1, 1);
          break;
        case "t":
        case "T":
          toggle();
          break;
        case "f":
        case "F":
          if (document.fullscreenElement) document.exitFullscreen();
          else document.documentElement.requestFullscreen?.();
          break;
        case "Escape":
          setDrawerOpen(false);
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, go, total, toggle]);

  const Current = slides[index].component;

  const variants = {
    enter: (d: number) => ({ opacity: 0, x: d >= 0 ? 80 : -80 }),
    center: { opacity: 1, x: 0 },
    exit: (d: number) => ({ opacity: 0, x: d >= 0 ? -80 : 80 }),
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: T.bg,
        display: "flex",
        overflow: "hidden",
      }}
    >
      {/* Left drawer — a real layout child that animates its width, so it
          pushes the stage instead of overlaying it. */}
      <motion.div
        animate={{ width: drawerOpen ? DRAWER_W : 0 }}
        transition={{ type: "spring", damping: 30, stiffness: 260 }}
        style={{ height: "100%", overflow: "hidden", flex: "0 0 auto" }}
      >
        <SettingsDrawer
          slides={slides}
          index={index}
          goto={goto}
          showArrows={showArrows}
          setShowArrows={setShowArrows}
          onClose={() => setDrawerOpen(false)}
        />
      </motion.div>

      {/* Stage area — takes the remaining space; slide scales to fit it. */}
      <div
        ref={stageAreaRef}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
        style={{
          flex: 1,
          minWidth: 0,
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
          touchAction: "pan-y",
        }}
      >
        <div
          style={{
            width: STAGE_W,
            height: STAGE_H,
            transform: `scale(${scale})`,
            transformOrigin: "center center",
            position: "relative",
            background: T.bg,
            color: T.text,
            fontFamily: MONO,
            overflow: "hidden",
            flex: "0 0 auto",
          }}
        >
          <Backdrop />
          <AnimatePresence mode="wait" custom={dir}>
            <motion.div
              key={index}
              custom={dir}
              variants={variants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.34, ease: [0.22, 0.61, 0.36, 1] }}
              style={{ position: "absolute", inset: 0 }}
            >
              <SectionNumberContext.Provider value={sectionOf[slides[index].id] ?? null}>
                <OverflowGuard id={slides[index].id}>
                  <Current />
                </OverflowGuard>
              </SectionNumberContext.Provider>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Hidable on-screen arrows (within the stage area). */}
        <AnimatePresence>
          {showArrows && (
            <>
              <Arrow side="left" disabled={index === 0} onClick={prev} />
              <Arrow side="right" disabled={index === total - 1} onClick={next} />
            </>
          )}
        </AnimatePresence>

        <ProgressBar index={index} total={total} />
      </div>

      <GearButton open={drawerOpen} onToggle={() => setDrawerOpen((o) => !o)} />
    </div>
  );
}

function Arrow({
  side,
  onClick,
  disabled,
}: {
  side: "left" | "right";
  onClick: () => void;
  disabled: boolean;
}) {
  const { T } = useTheme();
  return (
    <motion.button
      initial={{ opacity: 0, x: side === "left" ? -12 : 12 }}
      animate={{ opacity: disabled ? 0.25 : 0.8, x: 0 }}
      exit={{ opacity: 0, x: side === "left" ? -12 : 12 }}
      whileHover={disabled ? {} : { opacity: 1, scale: 1.06 }}
      onClick={disabled ? undefined : onClick}
      aria-label={side === "left" ? "Previous" : "Next"}
      style={{
        position: "absolute",
        top: "50%",
        [side]: 14,
        transform: "translateY(-50%)",
        width: 40,
        height: 40,
        display: "grid",
        placeItems: "center",
        borderRadius: "50%",
        border: `1.5px solid ${T.border}`,
        background: T.bgRaised,
        color: T.textMuted,
        fontSize: 20,
        lineHeight: 1,
        cursor: disabled ? "default" : "pointer",
        zIndex: 40,
      }}
    >
      {side === "left" ? "‹" : "›"}
    </motion.button>
  );
}

function ProgressBar({ index, total }: { index: number; total: number }) {
  const { T, glow } = useTheme();
  const pct = total <= 1 ? 100 : (index / (total - 1)) * 100;
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: 3,
        background: "transparent",
        zIndex: 50,
      }}
    >
      <motion.div
        animate={{ width: `${pct}%` }}
        transition={{ type: "spring", damping: 26, stiffness: 200 }}
        style={{ height: "100%", background: T.lavender, boxShadow: glow.lavender }}
      />
    </div>
  );
}
