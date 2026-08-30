import { spawn } from "node:child_process";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import config from "./presentation.config.json";

/**
 * Which deck to serve. Defaults to src/slides; DECK=<dir> serves
 * examples/<dir>/slides instead, so the bundled example talks run with the same
 * framework, build and export pipeline as your own deck:
 *
 *   DECK=rl-environments-101 npm run dev
 *   DECK=rl-environments-101 npm run export
 */
const DECK = process.env.DECK
  ? path.resolve(__dirname, "examples", process.env.DECK, "slides")
  : path.resolve(__dirname, "src/slides");

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/**
 * presentation.config.json is the single source of truth, so the <head> is
 * generated from it rather than hand-edited. Anything that changes per talk —
 * title, description, social card — lives in the config.
 */
function headFromConfig(): Plugin {
  return {
    name: "head-from-config",
    transformIndexHtml(html) {
      const { title, subtitle, authors, meta } = config;
      const who = authors.join(", ");
      const fullTitle = `${title} — ${who}`;
      const desc = meta.description || subtitle;
      const ogImage = meta.url ? new URL(meta.ogImage, meta.url).toString() : meta.ogImage;
      const tags = [
        `<title>${esc(fullTitle)}</title>`,
        `<meta name="description" content="${esc(desc)}" />`,
        `<meta property="og:type" content="website" />`,
        `<meta property="og:title" content="${esc(fullTitle)}" />`,
        `<meta property="og:description" content="${esc(desc)}" />`,
        meta.url ? `<meta property="og:url" content="${esc(meta.url)}" />` : "",
        `<meta property="og:image" content="${esc(ogImage)}" />`,
        `<meta property="og:image:width" content="1200" />`,
        `<meta property="og:image:height" content="630" />`,
        `<meta name="twitter:card" content="summary_large_image" />`,
        `<meta name="twitter:title" content="${esc(fullTitle)}" />`,
        `<meta name="twitter:description" content="${esc(desc)}" />`,
        `<meta name="twitter:image" content="${esc(ogImage)}" />`,
      ].filter(Boolean);
      return html.replace("<!--@head-->", tags.join("\n    "));
    },
  };
}

/**
 * Dev-only export endpoints, so the Settings drawer's PPTX / PDF buttons
 * actually run the real capture (headless Chromium) instead of only offering a
 * command to copy. On a deployed build these routes don't exist and the UI
 * falls back to browser print (PDF) or the command (PPTX).
 */
function exportEndpoints(): Plugin {
  return {
    name: "export-endpoints",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const match = req.url?.match(/^\/__export\/(pptx|pdf|both)$/);
        if (!match) return next();
        const flag = match[1] === "both" ? [] : [`--${match[1]}-only`];
        const child = spawn("npm", ["run", "export", "--", ...flag], {
          cwd: process.cwd(),
          env: process.env,
        });
        let log = "";
        const collect = (b: Buffer) => (log += b.toString());
        child.stdout.on("data", collect);
        child.stderr.on("data", collect);
        child.on("close", (code) => {
          res.setHeader("content-type", "application/json");
          res.end(JSON.stringify({ ok: code === 0, code, log: log.slice(-4000) }));
        });
      });
    },
  };
}

// base "./" so the build works from any sub-path (e.g. an HF Space root).
export default defineConfig({
  plugins: [react(), headFromConfig(), exportEndpoints()],
  resolve: { alias: { "@deck": DECK } },
  base: "./",
  server: { host: true, port: 5173 },
});
