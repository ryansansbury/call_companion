#!/bin/bash
# The owner's machine only. A few minutes the first time. It creates .venv with Python 3.12 (the voice model's
# libraries don't support newer Pythons yet), installs the voice and transcription tools, installs ffmpeg and
# espeak-ng with Homebrew if they're missing, fetches the two fonts' license files, and warms up both models so their
# downloads happen now instead of in the middle of a run. The build itself needs only the standard library.
# Run from the build folder:   bash owner/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=""
for cand in /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 python3.12 /opt/homebrew/bin/python3.11 python3.11; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$(command -v "$cand")"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Installing Python 3.12 with Homebrew..."
  brew install python@3.12
  PY="$(brew --prefix)/bin/python3.12"
fi
echo "Using $PY ($("$PY" --version))"

for tool in ffmpeg espeak-ng; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Installing $tool with Homebrew..."
    brew install "$tool"
  fi
done

if [ ! -x .venv/bin/python3 ]; then
  "$PY" -m venv .venv
fi
.venv/bin/python3 -m pip install --quiet --upgrade pip
.venv/bin/python3 -m pip install --quiet "kokoro>=0.9.4" "misaki[en]>=0.9.4" soundfile numpy mlx-whisper

mkdir -p site/fonts
curl -fsSL https://raw.githubusercontent.com/rsms/inter/master/LICENSE.txt -o site/fonts/Inter-LICENSE.txt
curl -fsSL https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/OFL.txt -o site/fonts/JetBrainsMono-OFL.txt
cp reference/fonts/inter-latin.woff2 reference/fonts/jetbrains-mono-latin.woff2 site/fonts/

echo "Warming up the voice model (it downloads once)..."
.venv/bin/python3 audio/tts.py --warmup
echo "Warming up the transcription model (it downloads once, about 1.6 GB)..."
.venv/bin/python3 transcribe/stt.py --warmup

.venv/bin/python3 -c 'import sys, kokoro, mlx_whisper, numpy, soundfile; print("Ready: Python", sys.version.split()[0], "with kokoro, mlx-whisper, numpy and soundfile")'
echo "Next: bash owner/keys.sh openai --from policy-reconciler-openai"
