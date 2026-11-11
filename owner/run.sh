#!/bin/bash
# The owner's machine only. The whole pipeline in three runs, with a review between each. Each run is safe to start
# again, since voiced lines and recorded AI steps are skipped and the mix and its noise are seeded.
#
#   bash owner/run.sh 1   Setup, the OpenAI key, the voice samples, and all twelve calls voiced with the provisional
#                         voices (about 25 minutes). The samples are ready after a few minutes, so listen and read the
#                         scripts while the rest is voiced. Then pick the voices, approve or edit the scripts, and
#                         choose a local model or "skip".
#   bash owner/run.sh 2   After the voices are set in calls/cast.json and the key is frozen. Any line whose voice or
#                         words changed is voiced again, then transcription, a check that every key fact lines up with
#                         the transcripts (it stops for a review if one doesn't), and the tuning round of AI runs
#                         (about 20 minutes).
#   bash owner/run.sh 3   After the prompts are frozen. Every model on every call, the local model if one is
#                         set, the real build, and the screenshots (about half an hour, or an hour with a local model).
#
# Run from the build folder:   bash owner/run.sh 1
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n== %s\n' "$*"; }
ready() {
  python3 -c "import sys; sys.path.insert(0, '.'); from evals import freeze; sys.exit(0 if freeze.ready('$1') else 1)"
}
local_on() {
  python3 -c "import json, sys; m = [x for x in json.load(open('config/models.json'))['models'] if x['id'] == 'local']; sys.exit(0 if m and m[0].get('enabled') else 1)"
}
luna_on() {
  python3 -c "import json, sys; c = json.load(open('config/models.json')); m = [x for x in c['models'] if x['id'] == 'openai-luna']; sys.exit(0 if 'openai-luna' in c['compare'] and m and m[0].get('enabled', True) else 1)"
}

one() {
  say "Setup"
  bash owner/bootstrap.sh
  say "The OpenAI key"
  if security find-generic-password -s call-companion-openai >/dev/null 2>&1; then
    echo "Already saved as call-companion-openai."
  elif security find-generic-password -s policy-reconciler-openai >/dev/null 2>&1; then
    bash owner/keys.sh openai --from policy-reconciler-openai
  else
    echo "No OpenAI key in the Keychain. Take GPT-6 Luna out of the comparison in config/models.json."
  fi
  say "The voice samples"
  bash owner/make_audio.sh --samples
  echo "Listen now with: open owner/out/samples"
  echo "The scripts are in calls/scripts/. The rest of this run voices all twelve calls."
  say "All twelve calls, with the provisional voices"
  bash owner/make_audio.sh
  say "Local models"
  if command -v ollama >/dev/null 2>&1; then
    ollama list || echo "Ollama is installed but isn't running."
  else
    echo "Ollama isn't installed, so the local model sits out unless you add one."
  fi
  cat <<'EOF'

Run 1 is done. Hear a whole call with: open site/audio/deal-1.v1.m4a
Then settle three things before run 2:
  the voices, like AE am_michael, SE af_nicole, OPS af_heart, IT am_liam, CFO af_kore
  the three deal scripts, approved or edited
  a local model name from the list above, or "skip"
EOF
}

two() {
  if ! ready key; then
    echo "The answer key isn't frozen yet. Set the voices, approve the scripts, and freeze the key, then run this again."
    exit 1
  fi
  say "Voicing anything that changed"
  bash owner/make_audio.sh
  say "Transcription"
  bash owner/transcribe.sh
  say "Lining the key up with the transcripts"
  if ! python3 engine/align.py; then
    echo "Some key facts can't be placed in the transcripts. Look at them before any model runs."
    exit 1
  fi
  python3 evals/wer.py
  python3 evals/timing.py
  if ! python3 -c "import json, sys; sys.exit(0 if json.load(open('evals/timing.json'))['worst_points_off'] <= 5 else 1)"; then
    echo "Talk time from the audio is more than five points off the mix on some call, so the voice activity step"
    echo "looks broken. Fix it before any model runs."
    exit 1
  fi
  python3 - <<'PY'
import sys
sys.path.insert(0, ".")
from evals import freeze
changed = freeze.changed("aligned")
if changed is None:
    freeze.freeze("aligned")
    print("Froze the aligned key.")
elif changed:
    sys.exit("The aligned key differs from the one frozen earlier. Decide whether to refreeze before any model runs.")
else:
    print("The aligned key is frozen and unchanged.")
PY
  say "The tuning round"
  bash owner/record_ai_runs.sh --split dev
  say "Local models"
  if command -v ollama >/dev/null 2>&1; then
    ollama list || echo "Ollama is installed but isn't running."
  else
    echo "Ollama isn't installed, so the local model sits out."
  fi
  echo
  echo "Run 2 is done. The tuning round is recorded, with the local models listed above."
}

three() {
  if ! ready prompts; then
    say "The tuning round again, on the revised prompts"
    bash owner/record_ai_runs.sh --split dev
    python3 evals/score.py
    python3 - <<'PY'
import json
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, ".")
from agents import inputs
from evals import freeze
default = json.loads(Path("config/models.json").read_text())["default"]
path = Path("evals/tuning_rounds.json")
log = json.loads(path.read_text())
best = max(r["f1"] for r in log["rounds"])
s = json.loads(Path("evals/scores.json").read_text())["models"][default]["dev"]
log["rounds"].append({"round": len(log["rounds"]) + 1, "date": date.today().isoformat(),
                      "extract_prompt": inputs.prompt_hash("extract"), "precision": s["precision"],
                      "recall": s["recall"], "f1": s["f1"], "tp": s["tp"], "fp": s["fp"], "fn": s["fn"]})
path.write_text(json.dumps(log, indent=1) + "\n")
print(f"Tuning calls: F1 {s['f1']} (precision {s['precision']}, recall {s['recall']}), and {best} before the revision.")
if s["f1"] < best:
    sys.exit("The revised prompts scored lower on the tuning calls. Decide what to freeze before running this again.")
freeze.freeze("prompts")
print("Froze the prompts and the scoring code.")
PY
  fi
  if local_on && ! curl -sf -o /dev/null http://localhost:11434/api/tags; then
    echo "The local model is switched on but Ollama isn't running. Start Ollama, then run this again."
    exit 1
  fi
  if luna_on && ! security find-generic-password -s call-companion-openai >/dev/null 2>&1; then
    echo "GPT-6 Luna is in the comparison but there's no OpenAI key. Save the key or take Luna out of the comparison."
    exit 1
  fi
  say "Every model on every call"
  bash owner/record_ai_runs.sh --split all --models compare
  if local_on; then
    say "The local model, with its thinking off"
    if python3 owner/local_check.py; then
      echo "About three minutes a call on this Mac, and a line prints as each call finishes."
      bash owner/record_ai_runs.sh --split all --models local
    else
      echo "The local model sits out of this build for the reason above."
    fi
  fi
  say "The real page and its screenshots"
  bash owner/screenshots.sh
  echo
  echo "Run 3 is done. The runs and the screenshots are in."
}

case "${1:-}" in
  1) one ;;
  2) two ;;
  3) three ;;
  *) echo "Usage: bash owner/run.sh 1|2|3   (see the top of this file)"; exit 1 ;;
esac
