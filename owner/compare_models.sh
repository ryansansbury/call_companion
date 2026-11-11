#!/bin/bash
# The model comparison, after the prompts are frozen: every model in config/models.json's "compare" list runs
# all twelve calls, and then the page rebuilds with the comparison and the route.
# About 20 minutes. Run from the build folder:   bash owner/compare_models.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
[ -x "$PY" ] || PY=python3
bash owner/record_ai_runs.sh --split all --models compare
"$PY" build.py
echo "Done. The comparison is recorded."
