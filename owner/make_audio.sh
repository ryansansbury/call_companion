#!/bin/bash
# The owner's machine only. Voices, mixes and encodes the calls.
#   bash owner/make_audio.sh --samples              each deal role in three candidate voices, to pick from
#   bash owner/make_audio.sh                        every call: voice each line, mix the tracks, the phone line,
#                                                   the web encode (several minutes the first time)
#   bash owner/make_audio.sh --calls deal-1,deal-2  only those calls
# Safe to stop and run again, since lines already voiced are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x .venv/bin/python3 ] || { echo "Run bash owner/bootstrap.sh first."; exit 1; }
if [ "${1:-}" = "--samples" ]; then
  .venv/bin/python3 audio/tts.py --samples
  echo "Listen with: open owner/out/samples   Then reply with one voice per role (AE, SE, OPS, IT, CFO)."
  exit 0
fi
.venv/bin/python3 audio/tts.py "$@"
.venv/bin/python3 audio/mix.py "$@"
.venv/bin/python3 engine/vad.py "$@"
.venv/bin/python3 engine/peaks.py "$@"
echo "Done. Next: bash owner/transcribe.sh"
