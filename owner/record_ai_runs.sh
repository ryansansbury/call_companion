#!/bin/bash
# The owner's machine only. Records the AI steps the page replays. Claude runs through claude -p, and GPT-6 Luna uses
# the key saved with owner/keys.sh. Safe to stop and run again, since anything already recorded
# for today's prompts is skipped.
# Run from the build folder:
#   bash owner/record_ai_runs.sh --split dev                     the development round, a few minutes
#   bash owner/record_ai_runs.sh --split test                    the scored round, after the prompts are frozen
#   bash owner/record_ai_runs.sh --split deal                    the three deal calls
#   bash owner/record_ai_runs.sh --split all --stand-in          a dry run with no model and no network
set -euo pipefail
cd "$(dirname "$0")/.."
case " $* " in
  *" --stand-in "*) ;;
  *) command -v claude >/dev/null || { echo "The claude command isn't on your PATH. Open Claude Code once, then run this again."; exit 1; } ;;
esac
python3 owner/record_ai_runs.py "$@"
