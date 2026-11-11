#!/bin/bash
# The owner's machine only. Transcribes every person's track on this Mac with mlx-whisper (a few minutes).
#   bash owner/transcribe.sh                 every call with a VAD file in data/vad/
#   bash owner/transcribe.sh --calls deal-1  only that call
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x .venv/bin/python3 ] || { echo "Run bash owner/bootstrap.sh first."; exit 1; }
if [ ! -d data/vad ]; then
  echo "There's no data/vad/ yet. Run bash owner/make_audio.sh first, which finds the speech on each track."
  exit 1
fi
.venv/bin/python3 transcribe/stt.py "$@"
echo "Done. Next, engine/align.py lines the transcripts up with the answer key."
