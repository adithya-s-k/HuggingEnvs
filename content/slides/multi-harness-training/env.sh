#!/usr/bin/env bash
# Put Node and Chromium's libraries on the path for this deck. See DEVBOX.md for why these are
# needed and how they were installed. Source it, do not execute it:
#
#   source content/slides/multi-harness-training/env.sh

_node="$HOME/.local/opt/node-v22.14.0-linux-x64/bin"
_chromium_libs="$HOME/.local/opt/chromium-deps/root/usr/lib/x86_64-linux-gnu"

[ -d "$_node" ] && export PATH="$_node:$PATH" || echo "warning: node not found at $_node"
# Playwright ships the browser but not the system libraries it links against; without this the
# headless binary exits 127 before printing anything.
[ -d "$_chromium_libs" ] && export LD_LIBRARY_PATH="$_chromium_libs:$LD_LIBRARY_PATH" \
  || echo "warning: chromium libs not found at $_chromium_libs"

cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null || true
echo "node $(node --version 2>/dev/null || echo MISSING)  ·  deck $(pwd)"
