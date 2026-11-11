#!/bin/bash
# A few minutes. Builds the page, opens it in headless Chrome with a fresh profile from the file system and from a
# server on 127.0.0.1, takes every tab for two deal calls and every presenter step at 1440 and 1280 pixels, every tab
# at tablet and phone widths and the 1600 by 1000 card frame, checks the line rule, overlaps, console errors and
# network requests, and runs the seek test. Results land in owner/out/.
# Run from the build folder:   bash owner/screenshots.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
[ -x "$PY" ] || PY=python3
"$PY" build.py "$@"
"$PY" owner/browser_check.py
