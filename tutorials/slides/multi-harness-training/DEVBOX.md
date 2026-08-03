# Running this deck on the cluster

The template expects Node and a working headless Chromium. Neither is present on a login node, and
there is no root, so both live under `~/.local/opt`. This file records what was installed and why,
so the next person does not rediscover it.

## One line to get a working shell

```bash
source tutorials/slides/multi-harness-training/env.sh
```

Then the usual template commands work:

```bash
npm run dev       # http://localhost:5173
npm run build     # static site into dist/
npm run export    # PPTX + PDF into export/
```

## What is installed, and why

**Node v22.14.0** at `~/.local/opt/node-v22.14.0-linux-x64`. The official tarball, unpacked. Nothing
system-wide changed; `~/.bashrc` gained a single PATH line.

**Chromium's shared libraries** at `~/.local/opt/chromium-deps/root`. `npx playwright install
chromium` fetches the browser but not the system libraries it links against, and on this image
fifteen of them are missing, so the binary dies with exit code 127 before printing anything. Playwright's
own `install-deps` needs root.

The fix is to download the Ubuntu packages and unpack them into a prefix, then point
`LD_LIBRARY_PATH` at it:

```bash
apt-get download libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libasound2 \
                 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libgbm1 \
                 libxkbcommon0 libxkbcommon-x11-0 libwayland-server0 \
                 libwayland-client0 libxi6 libxcb-randr0
for d in *.deb; do dpkg-deb -x "$d" ~/.local/opt/chromium-deps/root; done
```

`apt-get download` only fetches, it does not install, so it needs no privileges.

Verify with:

```bash
"$(find ~/.cache/ms-playwright -name chrome-headless-shell | head -1)" --version
```

If that prints a version, `npm run export` will work. If it prints nothing and exits 127, a library
is still missing: run `ldd` on the same binary and look for `not found`.

## Export output

`npm run export` drives the built deck in headless Chromium at 2560×1440 and writes both formats to
`export/`. Slide titles become PowerPoint speaker notes.
