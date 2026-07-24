import { useEffect, useRef, useState, type ReactNode } from "react";
import { STAGE_W, STAGE_H } from "../theme";

// DEV-ONLY: after a slide's animations settle, measure the bounding box of
// every descendant against the 1280×720 canvas and flag anything that spills
// past the edges (which the stage's overflow:hidden would silently clip).
// Renders a red badge + outline so overflow is impossible to miss while authoring.
export function OverflowGuard({ id, children }: { id: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [over, setOver] = useState<{ dx: number; dy: number } | null>(null);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const el = ref.current;
    if (!el) return;
    setOver(null);
    const check = () => {
      const base = el.getBoundingClientRect();
      if (base.width === 0) return;
      const sx = base.width / STAGE_W;
      const sy = base.height / STAGE_H;
      let maxR = 0;
      let maxB = 0;
      el.querySelectorAll<HTMLElement>("*").forEach((n) => {
        if (n.dataset.ovBadge) return;
        const r = n.getBoundingClientRect();
        maxR = Math.max(maxR, r.right - base.left);
        maxB = Math.max(maxB, r.bottom - base.top);
      });
      const dx = Math.round(maxR / sx - STAGE_W);
      const dy = Math.round(maxB / sy - STAGE_H);
      if (dx > 2 || dy > 2) {
        setOver({ dx: Math.max(0, dx), dy: Math.max(0, dy) });
        // eslint-disable-next-line no-console
        console.warn(
          `[overflow] slide "${id}" spills ${dx > 0 ? `→ ${dx}px` : ""} ${dy > 0 ? `↓ ${dy}px` : ""}`.trim(),
        );
      } else {
        setOver(null);
      }
    };
    // wait for staggered entrance animations to settle before measuring
    const t = window.setTimeout(check, 1700);
    return () => window.clearTimeout(t);
  }, [id]);

  return (
    <div ref={ref} style={{ position: "absolute", inset: 0 }}>
      {children}
      {over && (
        <>
          <div
            data-ov-badge="1"
            style={{
              position: "absolute",
              inset: 0,
              border: "3px solid #ff4d6d",
              boxShadow: "inset 0 0 0 3px rgba(255,77,109,0.25)",
              pointerEvents: "none",
              zIndex: 999,
            }}
          />
          <div
            data-ov-badge="1"
            style={{
              position: "absolute",
              top: 8,
              left: "50%",
              transform: "translateX(-50%)",
              background: "#ff4d6d",
              color: "#fff",
              fontFamily: "ui-monospace, monospace",
              fontSize: 15,
              fontWeight: 800,
              padding: "5px 12px",
              borderRadius: 8,
              letterSpacing: 0.5,
              zIndex: 1000,
              pointerEvents: "none",
            }}
          >
            ⚠ OVERFLOW {over.dx > 0 ? `→${over.dx}px` : ""} {over.dy > 0 ? `↓${over.dy}px` : ""}
          </div>
        </>
      )}
    </div>
  );
}
