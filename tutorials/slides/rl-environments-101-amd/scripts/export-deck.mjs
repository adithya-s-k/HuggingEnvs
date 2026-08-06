/**
 * Export the deck to PPTX + PDF.
 *
 *   npm run export            # both, dark theme  -> export/
 *   npm run export -- --theme light --scale 3
 *
 * How it works: serve dist/, drive the real deck in headless Chromium via the
 * window.__DECK__ hook, let each slide's entrance animation finish, screenshot
 * the 1280x720 [data-stage] element, then assemble the PNGs into a 16:9 PPTX
 * (one full-bleed image per slide) and a same-size PDF.
 *
 * Slides are images, not editable shapes — the deck is React + framer-motion,
 * so there is nothing to map onto PowerPoint text boxes. What you get is a file
 * that opens anywhere and projects identically.
 */
import { mkdir, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import PptxGenJS from "pptxgenjs";
import { preview } from "vite";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "export");
const FRAMES = path.join(OUT, "slides");
const NAME = "RL-Environments-101-AMD";

const argv = process.argv.slice(2);
const arg = (flag, fallback) => {
  const i = argv.indexOf(flag);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback;
};
const THEME = arg("--theme", "dark");
const SCALE = Number(arg("--scale", "2")); // 2 -> 2560x1440 frames
const ONLY = argv.includes("--pptx-only") ? "pptx" : argv.includes("--pdf-only") ? "pdf" : "both";

// Entrance animations are ~1.2s at the slowest. Slides carrying a live
// simulation or a D3 embed never truly settle, so they get a longer dwell that
// lands them on a representative frame instead of an empty first one.
const SETTLE_MS = 1500;
const DWELL = {
  traditional: 4200, // CartPole — a running sim; catch it mid-swing
  anatomy: 3200, // D3 embed in an iframe
  "coding-example": 2600, // D3 embed
  "repo2rlenv-intro": 3600, // typewriter + staged reveal
};

/** Wait until no finite CSS/WAAPI animation is still running (springs get the floor below). */
async function settle(page, ms) {
  await page
    .waitForFunction(
      () =>
        document
          .getAnimations()
          .filter((a) => a.effect?.getTiming().iterations !== Infinity)
          .every((a) => a.playState === "finished" || a.playState === "idle"),
      null,
      { timeout: 4000 },
    )
    .catch(() => {}); // infinite/rAF-driven motion never reports finished — the dwell covers it
  await page.waitForTimeout(ms);
}

async function main() {
  if (!existsSync(path.join(ROOT, "dist", "index.html"))) {
    throw new Error("dist/ is missing — run `npm run build` first (or use `npm run export`).");
  }

  await rm(OUT, { recursive: true, force: true });
  await mkdir(FRAMES, { recursive: true });

  const server = await preview({
    root: ROOT,
    preview: { port: 4319, host: "127.0.0.1", open: false },
  });
  const url = `http://127.0.0.1:4319/`;

  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 720 }, // stage renders 1:1 — no rescaling blur
    deviceScaleFactor: SCALE,
    reducedMotion: "no-preference",
  });
  // The deck restores its last slide and theme from localStorage; pin both.
  await ctx.addInitScript(
    ([theme]) => {
      localStorage.setItem("rlenv-slides-index", "0");
      localStorage.setItem("rlenv-slides-theme", theme);
    },
    [THEME],
  );

  const page = await ctx.newPage();
  // Playwright's element screenshot is a viewport clip, so the deck's own
  // chrome (progress bar, arrows, gear) would otherwise sit on top of every
  // frame. Everything overlaying the stage is tagged data-chrome.
  await page.goto(url, { waitUntil: "networkidle" });
  await page.addStyleTag({ content: "[data-chrome]{display:none !important}" });
  await page.waitForSelector("[data-stage]");
  await page.evaluate(() => document.fonts.ready);

  const { total, ids, titles } = await page.evaluate(() => {
    const d = window.__DECK__;
    return { total: d.total, ids: d.ids, titles: d.titles };
  });
  console.log(`▶ ${total} slides · ${THEME} · ${1280 * SCALE}×${720 * SCALE}`);

  const stage = page.locator("[data-stage]");
  const frames = [];
  for (let i = 0; i < total; i++) {
    await page.evaluate((n) => window.__DECK__.goto(n), i);
    await page.waitForFunction((n) => window.__DECK__.index === n, i);
    await settle(page, DWELL[ids[i]] ?? SETTLE_MS);

    const file = path.join(FRAMES, `${String(i + 1).padStart(2, "0")}-${ids[i]}.png`);
    await stage.screenshot({ path: file });
    frames.push({ file, title: titles[i] });
    process.stdout.write(`\r  captured ${i + 1}/${total}  ${ids[i]}`.padEnd(60));
  }
  console.log("");

  if (ONLY !== "pdf") await buildPptx(frames);
  if (ONLY !== "pptx") await buildPdf(page, frames);

  await browser.close();
  await server.close();
  console.log(`✅ ${path.relative(process.cwd(), OUT)}/`);
}

async function buildPptx(frames) {
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: "STAGE", width: 13.333, height: 7.5 }); // 16:9
  pptx.layout = "STAGE";
  pptx.author = "Adithya S Kolavi";
  pptx.title = "RL Environments 101";
  pptx.subject = "From “What Is an Env?” to Training Your Own";

  for (const { file, title } of frames) {
    const slide = pptx.addSlide();
    slide.background = { color: "07090F" };
    slide.addImage({ path: file, x: 0, y: 0, w: 13.333, h: 7.5 });
    if (title) slide.addNotes(title); // slide title as a speaker note
  }
  const out = path.join(OUT, `${NAME}.pptx`);
  await pptx.writeFile({ fileName: out });
  console.log(`  pptx → ${path.basename(out)}`);
}

async function buildPdf(page, frames) {
  // Print the frames from a throwaway page: one 1280x720 image per page, no margins.
  const html = `<!doctype html><meta charset="utf-8"><style>
    @page { size: 1280px 720px; margin: 0 }
    html,body { margin:0; padding:0; background:#07090f }
    img { display:block; width:1280px; height:720px; break-after:page }
    img:last-child { break-after:auto }
  </style>${frames.map((f) => `<img src="${path.basename(path.dirname(f.file))}/${path.basename(f.file)}">`).join("")}`;

  const printable = path.join(OUT, "_print.html");
  await writeFile(printable, html);
  await page.goto(`file://${printable}`, { waitUntil: "load" });
  await page.evaluate(async () => {
    await Promise.all(
      [...document.images].filter((i) => !i.complete).map((i) => new Promise((r) => (i.onload = i.onerror = r))),
    );
  });
  const out = path.join(OUT, `${NAME}.pdf`);
  await page.pdf({ path: out, width: "1280px", height: "720px", printBackground: true, pageRanges: `1-${frames.length}` });
  await rm(printable, { force: true });
  console.log(`  pdf  → ${path.basename(out)}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
