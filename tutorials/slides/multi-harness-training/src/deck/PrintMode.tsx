import { MotionConfig } from "framer-motion";
import { useEffect } from "react";
import { useTheme } from "../ThemeContext";
import { STAGE_W, STAGE_H } from "../themes";
import { SectionNumberContext } from "./SlideShell";
import type { Slide } from "../slides";

/**
 * Every slide stacked, one per printed page, for the browser's own
 * "Save as PDF". No headless Chromium needed — and because it's the real
 * renderer, glows, SVG and iframes come out right.
 *
 * Animations are the catch: entrance transitions would print mid-flight. A
 * zero-duration MotionConfig plus reducedMotion="always" makes every animated
 * element render at its FINAL state immediately, which is what you want on
 * paper. Continuously animating figures (a running simulation) print at
 * whatever frame they're on — same caveat as the PPTX export.
 */
export function PrintMode({ slides, onDone }: { slides: Slide[]; onDone: () => void }) {
  const { T } = useTheme();

  useEffect(() => {
    // let the stacked slides mount + fonts settle, then hand off to the browser
    const t = window.setTimeout(() => {
      window.print();
      onDone();
    }, 700);
    const after = () => onDone();
    window.addEventListener("afterprint", after);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("afterprint", after);
    };
  }, [onDone]);

  return (
    <MotionConfig transition={{ duration: 0 }} reducedMotion="always">
      <style>{`
        @page { size: ${STAGE_W}px ${STAGE_H}px; margin: 0 }
        @media print {
          html, body, #root { overflow: visible !important; height: auto !important }
          [data-chrome] { display: none !important }
        }
      `}</style>
      <div style={{ position: "fixed", inset: 0, overflow: "auto", background: T.bg, zIndex: 200 }}>
        {slides.map((s, i) => {
          const Slide = s.component;
          return (
            <div
              key={s.id}
              style={{
                position: "relative",
                width: STAGE_W,
                height: STAGE_H,
                overflow: "hidden",
                background: T.bg,
                color: T.text,
                breakAfter: i === slides.length - 1 ? "auto" : "page",
              }}
            >
              <SectionNumberContext.Provider value={s.section ?? null}>
                <Slide />
              </SectionNumberContext.Provider>
            </div>
          );
        })}
      </div>
    </MotionConfig>
  );
}
