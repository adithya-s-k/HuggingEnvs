# SPDX-License-Identifier: BSD-3-Clause

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""Rate candidate paintings into tiers and pack the reference pool.

Narreddi rated 1,664 generations one at a time into love, okay and nope, and the
117 love-tier seeded the comparison pool. This is the same pass, and it is the
one step nobody can automate: the ratings *are* the reward function, so they have
to come from whoever the taste belongs to.

Serves a page on localhost with one painting at a time and three keys. Ratings
are written to disk after every keystroke, so closing the tab loses nothing and
the pass can be finished in several sittings.

**Both tiers ship.** The obvious move is to keep only the paintings you loved,
and it is what broke the first version of this pool: six uniformly good
references meant a small model lost every comparison and the reward was
identically zero on every rollout. The okay tier is what a policy beats first,
and without something to beat there is no gradient. Aim for a spread, not a
gallery.

    python examples/watercolour_pool_generate.py --per-model 20
    python examples/watercolour_pool_rate.py
    python examples/watercolour_pool_rate.py --pack
"""

from __future__ import annotations

import argparse
import http.server
import json
import pathlib
import shutil
import socketserver
import threading
import urllib.parse
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parents[1]
POOL = ROOT / "pool"
CANDIDATES = POOL / "candidates"
# `meh` is a rung, not a grade. Narreddi rated into love, okay and nope for a 35B
# policy; a 4B needs one more step below, because with two tiers everything that is
# not a flower goes to nope, nope is discarded, and the pool then has nothing the
# policy can beat by construction. Measured: 0 policy wins in 56 comparisons, and a
# candidate rated nope by eye turned out to have a 0.50 win rate, which is the most
# informative opponent there is. `meh` is that band, named.
#
# Its key is 4, not 3. Rating is muscle memory and 3 has meant nope for two
# sessions; remapping it mid-pass would silently turn intended nopes into rungs,
# which is the one mistake that puts garbage into the pool.
TIERS = ("love", "okay", "meh", "nope")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>rate the pool</title>
<style>
  :root { color-scheme: light dark }
  * { box-sizing: border-box }
  body { margin:0; font:15px/1.5 ui-sans-serif,system-ui,sans-serif;
         background:#faf8f4; color:#2a2723; padding:14px 18px 28px }
  header { display:flex; gap:14px; align-items:baseline; flex-wrap:wrap;
           justify-content:center; margin-bottom:10px }
  h1 { font-size:15px; font-weight:600; margin:0 }
  .muted { font-size:13px; color:#6a635b }
  .counts { font-variant-numeric:tabular-nums }
  button { font:inherit; padding:6px 14px; border-radius:4px; cursor:pointer;
           border:1px solid #cfc9c0; background:#fff; color:inherit }
  button:hover { background:#f2ede5 }
  button.love { border-color:#7a9a5e } button.okay { border-color:#b9a15e }
  button.meh { border-color:#b0a068 }
  button.nope { border-color:#b07068 }
  kbd { font:12px ui-monospace,monospace; background:#efeae2; padding:1px 5px;
        border-radius:3px; border:1px solid #ddd8d0 }
  /* one at a time */
  #single { display:flex; flex-direction:column; align-items:center; gap:10px }
  #shot { max-width:min(66vh,80vw); max-height:66vh; border:1px solid #ddd8d0;
          background:#fff; border-radius:3px }
  .bar { display:flex; gap:9px; flex-wrap:wrap; justify-content:center }
  /* grid */
  #grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
          gap:9px }
  .cell { position:relative; cursor:pointer; border:3px solid transparent;
          border-radius:4px; background:#fff; line-height:0 }
  .cell img { width:100%; aspect-ratio:1; object-fit:cover; border-radius:2px }
  .cell.love { border-color:#7a9a5e } .cell.okay { border-color:#b9a15e }
  .cell.meh { border-color:#b0a068; opacity:.7 }
  .cell.nope { border-color:#b07068; opacity:.45 }
  .cell .tag { position:absolute; bottom:3px; left:4px; font:11px ui-monospace,monospace;
               background:#000a; color:#fff; padding:0 4px; border-radius:2px; line-height:1.5 }
  /* An id selector beats a class, so `#single { display:flex }` wins over a
     bare `.hidden` and both views end up on screen at once. */
  #single.hidden, #grid.hidden { display:none }
</style></head><body>
<header>
  <h1>rate the reference pool</h1>
  <span class="muted" id="pos"></span>
  <button onclick="toggle()" id="mode">grid</button>
  <span class="muted counts" id="counts"></span>
</header>

<div id="single">
  <img id="shot" alt="">
  <div class="bar">
    <button class="love" onclick="rate('love')">love <kbd>1</kbd></button>
    <button class="okay" onclick="rate('okay')">okay <kbd>2</kbd></button>
    <button class="meh" onclick="rate('meh')">meh <kbd>4</kbd></button>
    <button class="nope" onclick="rate('nope')">nope <kbd>3</kbd></button>
    <button onclick="skip(-1)">back <kbd>&larr;</kbd></button>
    <button onclick="skip(1)">skip <kbd>&rarr;</kbd></button>
  </div>
  <div class="muted" id="info"></div>
</div>

<div id="grid" class="hidden"></div>

<script>
let items = [], i = 0, ratings = {}, gridMode = false;

async function load() {
  const s = await (await fetch("/state")).json();
  items = s.items; ratings = s.ratings;
  i = Math.max(0, items.findIndex(it => !(it.png in ratings)));
  buildGrid();
  render();
  setInterval(poll, 12000);
}

// Paintings appear on disk while the generator is still working, so the list
// grows under us. Appending without touching `i` means rating can start on the
// first one and carry on as the rest arrive, and the position never jumps out
// from under a keystroke.
async function poll() {
  const s = await (await fetch("/state")).json();
  const known = new Set(items.map(it => it.png));
  const added = s.items.filter(it => !known.has(it.png));
  const enriched = s.items.length === items.length &&
                   items.some(it => it.model === "?") &&
                   s.items.every(it => it.model !== "?");
  if (!added.length && !enriched) return;
  const current = items[i] && items[i].png;
  items = s.items;
  const at = items.findIndex(it => it.png === current);
  if (at >= 0) i = at;
  buildGrid();
  show();
}

// The grid exists so the whole range can be seen before rating any of it.
// Rating the first twenty against no reference and the last twenty against
// nineteen others produces two different scales in one pool.
function buildGrid() {
  const g = document.getElementById("grid");
  g.innerHTML = "";
  items.forEach((it, n) => {
    const d = document.createElement("div");
    d.className = "cell " + (ratings[it.png] || "");
    d.onclick = () => { i = n; gridMode = false; render() };
    d.innerHTML = `<img loading="lazy" src="/img/${it.png}">` +
                  `<span class="tag">${it.paint_fraction}</span>`;
    g.appendChild(d);
  });
}

function updateCounts() {
  const c = {love:0, okay:0, meh:0, nope:0};
  for (const k in ratings) c[ratings[k]]++;
  document.getElementById("counts").textContent =
    `love ${c.love} \u00b7 okay ${c.okay} \u00b7 meh ${c.meh} \u00b7 nope ${c.nope} ` +
    `\u00b7 ${Object.keys(ratings).length}/${items.length} rated` +
    (items.some(it => it.model === "?") ? " \u00b7 still generating" : "");
}

function show() {
  if (!items.length) { document.getElementById("pos").textContent = "no candidates"; return }
  const it = items[i];
  document.getElementById("shot").src = "/img/" + it.png;
  document.getElementById("pos").textContent =
    `${i + 1} / ${items.length}` + (ratings[it.png] ? ` \u00b7 ${ratings[it.png]}` : "");
  document.getElementById("info").textContent =
    `${it.model} \u00b7 ${it.subject} \u00b7 temp ${it.temperature} ` +
    `\u00b7 coverage ${it.paint_fraction} \u00b7 ${(it.elapsed_ms/1000).toFixed(1)}s` +
    (it.finished ? "" : " \u00b7 unfinished");
  updateCounts();
}

function render() {
  document.getElementById("single").classList.toggle("hidden", gridMode);
  document.getElementById("grid").classList.toggle("hidden", !gridMode);
  document.getElementById("mode").textContent = gridMode ? "one at a time" : "grid";
  show();
}
function toggle() { gridMode = !gridMode; render() }

async function rate(tier) {
  const it = items[i];
  ratings[it.png] = tier;
  const cell = document.getElementById("grid").children[i];
  if (cell) cell.className = "cell " + tier;
  await fetch("/rate?png=" + encodeURIComponent(it.png) + "&tier=" + tier, {method: "POST"});
  skip(1);
}
function skip(d) { i = Math.min(items.length - 1, Math.max(0, i + d)); show() }

document.addEventListener("keydown", e => {
  if (e.key === "1") rate("love");
  else if (e.key === "2") rate("okay");
  else if (e.key === "3") rate("nope");
  else if (e.key === "4") rate("meh");
  else if (e.key === "ArrowRight") skip(1);
  else if (e.key === "ArrowLeft") skip(-1);
  else if (e.key === "g") toggle();
});
load();
</script></body></html>"""


def load_items(directory: pathlib.Path) -> list[dict]:
    """Return the paintings on disk, with whatever metadata exists for them.

    Driven by the PNGs rather than by the manifest, because the generator writes
    each painting the moment it finishes rendering and only writes the manifest at
    the very end. Scanning means a rating pass can start on the first painting
    while the rest are still being generated, which matters when generating a
    hundred of them takes the better part of an hour.

    The manifest fills in model, subject and coverage once it lands. Until then
    the entries carry just the filename, which is all the page needs to show one.
    """
    manifest = directory / "candidates.json"
    metadata = {}
    if manifest.exists():
        metadata = {
            c["png"]: c for c in json.loads(manifest.read_text()) if c.get("kept")
        }
    items = []
    # Any PNG, not just `cand_*`. The authored pool is worth reviewing through the
    # same page: its tiers come from a parameterised ablation rather than from a
    # person, and rating them by hand is exactly the gap the dataset card names.
    for png in sorted(directory.glob("*.png")):
        items.append(
            metadata.get(png.name)
            or {
                "png": png.name,
                "model": png.stem.split("_")[0] if "_" in png.stem else "?",
                "subject": "?",
                "temperature": "?",
                "paint_fraction": "?",
                "elapsed_ms": 0,
                "finished": True,
            }
        )
    if not items:
        raise SystemExit(
            f"no paintings in {directory} yet. Run watercolour_pool_generate.py first."
        )
    return items


def serve(
    directory: pathlib.Path,
    ratings_path: pathlib.Path,
    port: int,
    open_browser: bool = True,
) -> None:
    """Serve the rating page until interrupted."""
    items = load_items(directory)
    ratings = json.loads(ratings_path.read_text()) if ratings_path.exists() else {}
    lock = threading.Lock()

    def rescan() -> list[dict]:
        """Re-read the directory so paintings finished since startup show up."""
        try:
            return load_items(directory)
        except SystemExit:
            return items

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the terminal readable
            pass

        def _send(self, body: bytes, kind: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self._send(PAGE.encode(), "text/html; charset=utf-8")
            elif path == "/state":
                fresh = rescan()
                with lock:
                    items[:] = fresh
                    body = json.dumps({"items": items, "ratings": ratings}).encode()
                self._send(body, "application/json")
            elif path.startswith("/img/"):
                name = pathlib.Path(urllib.parse.unquote(path[5:])).name
                png = directory / name
                if png.exists():
                    self._send(png.read_bytes(), "image/png")
                else:
                    self.send_error(404)
            else:
                self.send_error(404)

        def do_POST(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            png = (query.get("png") or [""])[0]
            tier = (query.get("tier") or [""])[0]
            if tier not in TIERS or not png:
                self.send_error(400)
                return
            with lock:
                ratings[png] = tier
                # Written on every keystroke rather than at the end, so a closed
                # tab or a stopped server costs nothing.
                ratings_path.write_text(json.dumps(ratings, indent=2))
                counts = {t: sum(1 for v in ratings.values() if v == t) for t in TIERS}
            print(
                f"\r{len(ratings)}/{len(items)} rated  "
                f"love {counts['love']}  okay {counts['okay']}  "
                f"meh {counts['meh']}  nope {counts['nope']}",
                end="",
                flush=True,
            )
            self._send(b"{}", "application/json")

    class Server(socketserver.TCPServer):
        # Without this, restarting inside the socket's TIME_WAIT window fails
        # with "Address already in use" and the server exits before printing a
        # URL, which looks like the page being broken rather than the port being
        # briefly held.
        allow_reuse_address = True

    with Server(("127.0.0.1", port), Handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print(f"rating {len(items)} candidates at {url}")
        print("keys: 1 love, 2 okay, 4 meh, 3 nope, arrows to move, g for the grid.")
        print("ratings save as you go. ctrl-c when done.\n")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped. ratings saved to", ratings_path)


def pack(
    directory: pathlib.Path, ratings_path: pathlib.Path, pool: pathlib.Path = POOL
) -> None:
    """Copy the rated paintings into the pool the environment reads.

    Every tier but `nope` ships. Keeping only the loved ones is what made the first
    pool a wall a small model could never climb, and `meh` is the step below `okay`
    that gives it somewhere to start.
    """
    if not ratings_path.exists():
        raise SystemExit(f"no ratings at {ratings_path}. Rate some first.")
    ratings = json.loads(ratings_path.read_text())
    items = {c["png"]: c for c in load_items(directory)}

    kept, counts, missing = [], {t: 0 for t in TIERS}, []
    for png, tier in sorted(ratings.items()):
        if not (directory / png).exists():
            # A rating whose painting is gone, which happens after regenerating
            # candidates with an older ratings file still on disk. Skipped rather
            # than raised: crashing halfway leaves a pool that is neither the old
            # one nor the new one.
            missing.append(png)
            continue
        counts[tier] += 1
        if tier == "nope":
            continue
        target = pool / f"{tier}_{png}"
        shutil.copyfile(directory / png, target)
        source = directory / png.replace(".png", ".js")
        if source.exists():
            shutil.copyfile(source, pool / "sources" / f"{tier}_{source.name}")
        kept.append({"file": target.name, "tier": tier, **items.get(png, {})})

    (pool / "tiers.json").write_text(json.dumps(kept, indent=2))
    print(
        f"packed {len(kept)} references into {pool}\n"
        f"  love {counts['love']}, okay {counts['okay']}, meh {counts['meh']}, "
        f"dropped {counts['nope']}"
    )
    if missing:
        print(f"  {len(missing)} rated paintings no longer on disk, skipped")
    if counts["okay"] == 0:
        print(
            "\nWarning: no okay-tier references. A pool of only loved paintings is\n"
            "a wall: a small policy loses every comparison, the judge term is\n"
            "constant, and there is no gradient. Rate some as okay."
        )


def main() -> None:
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--dir", default=str(CANDIDATES), help="Rendered candidates.")
    ap.add_argument("--ratings", default=None, help="Where ratings live.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument(
        "--pool",
        default=str(POOL),
        help="Where --pack writes the rated references. Defaults to the pool the "
        "environment reads.",
    )
    ap.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open a browser tab. Only useful when testing the server.",
    )
    ap.add_argument(
        "--pack",
        action="store_true",
        help="Skip rating and copy the already-rated paintings into the pool.",
    )
    args = ap.parse_args()

    directory = pathlib.Path(args.dir)
    ratings_path = pathlib.Path(args.ratings or directory / "ratings.json")
    pool = pathlib.Path(args.pool)
    (pool / "sources").mkdir(parents=True, exist_ok=True)

    if args.pack:
        pack(directory, ratings_path, pool)
    else:
        serve(directory, ratings_path, args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
