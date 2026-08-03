/**
 * Export the deck to PPTX + PDF.
 *
 *   npm run export                       # both, config theme  -> export/
 *   npm run export -- --mode light
 *   npm run export -- --scale 3          # 3840x2160 frames
 *   npm run export -- --pptx-only        # or --pdf-only
 *
 * Serves dist/, drives the real deck in headless Chromium through the
 * window.__DECK__ hook, waits for each slide's entrance animation to finish,
 * and screenshots the 1280x720 [data-stage] element. The frames become a 16:9
 * PPTX (one full-bleed image per slide, slide title as a speaker note) and a
 * same-size PDF.
 *
 * Slides export as IMAGES, not editable shapes. React + framer-motion has
 * nothing to map onto PowerPoint text boxes; what you get instead is a file
 * that opens anywhere and projects identically.
 */
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import PptxGenJS from "pptxgenjs";
import { preview } from "vite";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "export");
const FRAMES = path.join(OUT, "slides");
const PORT = 4319;

const argv = process.argv.slice(2);
const arg = (flag, fallback) => {
  const i = argv.indexOf(flag);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback;
};

const config = JSON.parse(await readFile(path.join(ROOT, "presentation.config.json"), "utf8"));
const NAME = config.export?.fileName || "presentation";
const MODE = arg("--mode", config.defaultMode || "dark");
const THEME = arg("--theme", config.theme || "forge");
const SCALE = Number(arg("--scale", "2"));
const ONLY = argv.includes("--pptx-only") ? "pptx" : argv.includes("--pdf-only") ? "pdf" : "both";

/**
 * Entrance animations run ~1.2s at the slowest. Slides carrying continuous
 * motion (a live simulation, a looping figure) never settle at all, so give
 * them a longer dwell here and they'll be captured on a representative frame
 * instead of an empty first one. Key by slide id.
 */
const SETTLE_MS = 1500;
const DWELL = {
  // "my-simulation-slide": 4000,
};

/** Wait until no finite animation is still running; springs are covered by the floor. */
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
    .catch(() => {}); // rAF-driven springs never report finished — the dwell covers them
  await page.waitForTimeout(ms);
}

async function main() {
  if (!existsSync(path.join(ROOT, "dist", "index.html"))) {
    throw new Error("dist/ is missing — run `npm run build` first (or just `npm run export`).");
  }

  await rm(OUT, { recursive: true, force: true });
  await mkdir(FRAMES, { recursive: true });

  const server = await preview({
    root: ROOT,
    preview: { port: PORT, host: "127.0.0.1", open: false },
  });

  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 720 }, // stage renders 1:1 — no rescaling blur
    deviceScaleFactor: SCALE,
    reducedMotion: "no-preference",
  });
  // The deck restores slide/theme/mode from localStorage; pin all three.
  await ctx.addInitScript(
    ([mode, theme]) => {
      localStorage.setItem("rpt-index", "0");
      localStorage.setItem("rpt-mode", mode);
      localStorage.setItem("rpt-theme", theme);
    },
    [MODE, THEME],
  );

  const page = await ctx.newPage();
  await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: "networkidle" });
  // Playwright's element screenshot is a viewport clip, not an element render,
  // so anything overlaying the stage would land in every frame.
  await page.addStyleTag({ content: "[data-chrome]{display:none !important}" });
  await page.waitForSelector("[data-stage]");
  await page.evaluate(() => document.fonts.ready);

  const { total, ids, titles } = await page.evaluate(() => {
    const d = window.__DECK__;
    return { total: d.total, ids: d.ids, titles: d.titles };
  });
  console.log(`▶ ${total} slides · ${THEME}/${MODE} · ${1280 * SCALE}×${720 * SCALE}`);

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
  pptx.author = (config.authors || []).join(", ");
  pptx.title = config.title;
  pptx.subject = config.subtitle || "";

  for (const { file, title } of frames) {
    const slide = pptx.addSlide();
    slide.addImage({ path: file, x: 0, y: 0, w: 13.333, h: 7.5 });
    if (title) slide.addNotes(title);
  }
  const out = path.join(OUT, `${NAME}.pptx`);
  await pptx.writeFile({ fileName: out });
  console.log(`  pptx → ${path.basename(out)}`);
}

async function buildPdf(page, frames) {
  // Print from a throwaway page: one 1280x720 image per page, no margins.
  const imgs = frames
    .map((f) => `<img src="slides/${path.basename(f.file)}">`)
    .join("");
  const html = `<!doctype html><meta charset="utf-8"><style>
    @page { size: 1280px 720px; margin: 0 }
    html,body { margin:0; padding:0; background:#000 }
    img { display:block; width:1280px; height:720px; break-after:page }
    img:last-child { break-after:auto }
  </style>${imgs}`;

  const printable = path.join(OUT, "_print.html");
  await writeFile(printable, html);
  await page.goto(`file://${printable}`, { waitUntil: "load" });
  await page.evaluate(async () => {
    await Promise.all(
      [...document.images]
        .filter((i) => !i.complete)
        .map((i) => new Promise((r) => (i.onload = i.onerror = r))),
    );
  });
  const out = path.join(OUT, `${NAME}.pdf`);
  await page.pdf({
    path: out,
    width: "1280px",
    height: "720px",
    printBackground: true,
    pageRanges: `1-${frames.length}`,
  });
  await rm(printable, { force: true });
  console.log(`  pdf  → ${path.basename(out)}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
