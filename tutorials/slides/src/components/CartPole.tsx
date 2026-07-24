import { useEffect, useRef } from "react";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

// A self-contained, auto-playing CartPole. Exact Gymnasium CartPole-v1
// dynamics + a tuned LQR-style linear controller that genuinely balances
// the pole (small graceful corrections, recovers from nudges, rarely
// resets). Rendered to a canvas via requestAnimationFrame, fixed-timestep
// physics with sub-stepping, slowed to a cinematic ~half real-time so it
// reads cleanly on a projector.
type S = { x: number; xd: number; th: number; thd: number };

// Gymnasium CartPole-v1 constants.
const G = 9.8;
const MC = 1.0; // mass of cart
const MP = 0.1; // mass of pole
const L = 0.5; // half-length of pole
const PML = MP * L; // polemass * length
const TOTAL = MC + MP;
const FMAG = 10; // force magnitude
const TAU = 0.02; // seconds between physics steps
const XLIM = 2.4; // track half-width (world units)

// One fixed-timestep integration step. `action` is a continuous command in
// [-1, 1]; force = FMAG * action (matches Gym's ±FMAG at the extremes).
function physics(s: S, action: number): S {
  const force = FMAG * action;
  const ct = Math.cos(s.th);
  const st = Math.sin(s.th);
  const temp = (force + PML * s.thd * s.thd * st) / TOTAL;
  const thacc = (G * st - ct * temp) / (L * (4 / 3 - (MP * ct * ct) / TOTAL));
  const xacc = temp - (PML * thacc * ct) / TOTAL;
  return {
    x: s.x + TAU * s.xd,
    xd: s.xd + TAU * xacc,
    th: s.th + TAU * s.thd,
    thd: s.thd + TAU * thacc,
  };
}

// Tuned linear feedback (LQR-style). Positive-definite, stable: keeps the
// pole vertical while gently pulling the cart back to centre. Output is
// clamped to the ±force action range.
const KX = 0.5;
const KXD = 1.5;
const KTH = 25;
const KTHD = 5;
const controller = (s: S) =>
  Math.max(-1, Math.min(1, KX * s.x + KXD * s.xd + KTH * s.th + KTHD * s.thd));

const fresh = (): S => ({
  x: 0,
  xd: 0,
  th: (Math.random() - 0.5) * 0.08,
  thd: 0,
});

export function CartPole({
  width = 560,
  height = 380,
  speed = 0.5,
}: {
  width?: number;
  height?: number;
  speed?: number;
}) {
  const { T } = useTheme();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // ── Layout (all derived from canvas size, robust to any width/height) ──
    const margin = Math.max(36, width * 0.09);
    const groundY = Math.round(height * 0.66);
    const cw = Math.max(56, Math.min(110, width * 0.17)); // cart width
    const ch = Math.max(26, cw * 0.42); // cart height
    const scale = (width / 2 - margin) / XLIM; // world→px
    const poleLen = L * 2 * scale;
    const pivotY = groundY - ch / 2;
    const cxOf = (wx: number) => width / 2 + wx * scale;

    // ── Simulation state ──
    let s = fresh();
    let action = controller(s);
    let reward = 0;
    let last = performance.now();
    let acc = 0; // physics-time accumulator (seconds)
    let kickTimer = 1.6 + Math.random() * 1.8; // time until next nudge
    let raf = 0;
    let alive = true;

    // Motion trail for the pole tip (world-independent screen coords).
    const trail: { x: number; y: number }[] = [];
    const TRAIL_MAX = 16;

    const step = () => {
      action = controller(s);
      s = physics(s, action);
      // reward: +1 per step while upright & on-track (Gym-style)
      if (Math.abs(s.th) < 0.2095 && Math.abs(s.x) < XLIM) reward += 1;
      // fell over / ran off the track → gentle reset
      if (Math.abs(s.th) > 0.7 || Math.abs(s.x) > XLIM) {
        s = fresh();
        reward = 0;
        trail.length = 0;
      }
    };

    const drawArrow = (baseX: number, baseY: number, dir: number, mag: number) => {
      const len = 14 + mag * 30;
      const tipX = baseX + dir * len;
      const y = baseY;
      ctx.strokeStyle = T.lavenderDim;
      ctx.fillStyle = T.lavenderDim;
      ctx.lineWidth = 2.5;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(baseX, y);
      ctx.lineTo(tipX, y);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(tipX, y);
      ctx.lineTo(tipX - dir * 7, y - 4);
      ctx.lineTo(tipX - dir * 7, y + 4);
      ctx.closePath();
      ctx.fill();
    };

    const render = () => {
      const cx = cxOf(s.x);
      const tipX = cx + poleLen * Math.sin(s.th);
      const tipY = pivotY - poleLen * Math.cos(s.th);

      ctx.clearRect(0, 0, width, height);

      // ── Track ──
      ctx.strokeStyle = T.border;
      ctx.lineWidth = 2;
      ctx.lineCap = "butt";
      ctx.beginPath();
      ctx.moveTo(margin, groundY);
      ctx.lineTo(width - margin, groundY);
      ctx.stroke();
      // ticks (subtle) at each world unit
      ctx.fillStyle = T.border;
      for (let t = -2; t <= 2; t++) {
        const isCentre = t === 0;
        ctx.fillRect(cxOf(t) - 1, groundY + 4, isCentre ? 2 : 1.5, isCentre ? 11 : 7);
      }

      // ── Pole-tip motion trail ──
      for (let i = 0; i < trail.length; i++) {
        const p = trail[i];
        const a = (i / trail.length) * 0.5;
        ctx.globalAlpha = a;
        ctx.fillStyle = T.emerald;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 2.5 + a * 3, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      // ── Push-direction indicator (below the cart) ──
      if (Math.abs(action) > 0.02) {
        drawArrow(cx, groundY + ch / 2 + 20, Math.sign(action), Math.abs(action));
      }

      // ── Cart ──
      ctx.fillStyle = T.bgRaised;
      ctx.strokeStyle = T.text;
      ctx.lineWidth = 2.5;
      roundRect(ctx, cx - cw / 2, groundY - ch / 2, cw, ch, Math.min(10, ch / 3));
      ctx.fill();
      ctx.stroke();
      // wheels
      const wr = Math.max(5, ch * 0.18);
      ctx.fillStyle = T.textDim;
      ctx.strokeStyle = T.text;
      ctx.lineWidth = 2;
      for (const wx of [cx - cw / 3, cx + cw / 3]) {
        ctx.beginPath();
        ctx.arc(wx, groundY + ch / 2, wr, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }

      // ── Pole ──
      ctx.strokeStyle = T.lavender;
      ctx.lineWidth = Math.max(8, cw * 0.11);
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(cx, pivotY);
      ctx.lineTo(tipX, tipY);
      ctx.stroke();
      // pivot hub
      ctx.fillStyle = T.text;
      ctx.beginPath();
      ctx.arc(cx, pivotY, Math.max(3, cw * 0.035), 0, Math.PI * 2);
      ctx.fill();
      // glowing emerald tip
      ctx.shadowColor = T.emerald;
      ctx.shadowBlur = 18;
      ctx.fillStyle = T.emerald;
      ctx.beginPath();
      ctx.arc(tipX, tipY, Math.max(7, cw * 0.09), 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // ── HUD (minimal, monospace) ──
      ctx.font = `13px ${MONO}`;
      ctx.textBaseline = "top";
      ctx.fillStyle = T.textDim;
      ctx.textAlign = "left";
      ctx.fillText(`reward +${reward}`, margin, 8);
      ctx.textAlign = "right";
      const deg = (s.th * 180) / Math.PI;
      ctx.fillText(`θ ${deg >= 0 ? "+" : "−"}${Math.abs(deg).toFixed(1)}°`, width - margin, 8);
      ctx.textAlign = "left";
    };

    const frame = (now: number) => {
      if (!alive) return;
      let dtReal = (now - last) / 1000;
      last = now;
      if (dtReal > 0.1) dtReal = 0.1; // avoid spiral-of-death after a stall
      acc += dtReal * speed;

      // occasional gentle nudge so the balance looks alive & intelligent
      kickTimer -= dtReal * speed;
      if (kickTimer <= 0) {
        s = { ...s, thd: s.thd + (Math.random() < 0.5 ? -1 : 1) * (0.9 + Math.random() * 0.6) };
        kickTimer = 2.2 + Math.random() * 2.4;
      }

      let steps = 0;
      while (acc >= TAU && steps < 240) {
        step();
        acc -= TAU;
        steps++;
      }

      // sample tip position into the trail after stepping
      const cx = cxOf(s.x);
      trail.push({ x: cx + poleLen * Math.sin(s.th), y: pivotY - poleLen * Math.cos(s.th) });
      if (trail.length > TRAIL_MAX) trail.shift();

      render();
      raf = requestAnimationFrame(frame);
    };

    raf = requestAnimationFrame(frame);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
    };
  }, [width, height, speed, T]);

  return (
    <div
      style={{
        background: T.bgRaised,
        border: `1.5px solid ${T.border}`,
        borderRadius: 18,
        padding: 18,
      }}
    >
      <div
        style={{
          fontFamily: MONO,
          fontSize: 15,
          letterSpacing: 2,
          color: T.textDim,
          textTransform: "uppercase",
          marginBottom: 6,
        }}
      >
        CartPole
      </div>
      <canvas ref={canvasRef} style={{ width, height, display: "block" }} />
    </div>
  );
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
