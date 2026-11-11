#!/bin/bash
# The local model run: the same frozen prompts on a model Ollama serves on this Mac, so nothing leaves the machine.
# Give it the model's name exactly as `ollama list` shows it.
# Run from the build folder:   bash owner/run_local.sh qwen3:14b
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
[ -x "$PY" ] || PY=python3
MODEL="${1:?Give the model name as ollama list shows it}"
if ! curl -sf -o /dev/null http://localhost:11434/api/tags; then
  echo "Ollama isn't running. Start it, then run this again."
  exit 1
fi
"$PY" owner/set_local_model.py "$MODEL"
bash owner/record_ai_runs.sh --split all --models local
"$PY" build.py
echo "Done. The local run is recorded."
