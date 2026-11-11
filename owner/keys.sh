#!/bin/bash
# Saves one vendor's API key in the macOS Keychain under this project's own service name. Keys never go in a file.
#
#   bash owner/keys.sh openai --from policy-reconciler-openai    copies the key the Policy Reconciler already saved
#   bash owner/keys.sh openai                                     after copying the OpenAI key to the clipboard
#   bash owner/keys.sh google                                     only if Gemini joins the comparison
#
# Claude runs through the Claude Code CLI, so it needs no key here. A typed Keychain prompt can cut a
# long key short, which is why a new key comes from the clipboard.
set -euo pipefail
vendor="${1:-}"
case "$vendor" in
  openai|google|anthropic) ;;
  *) echo "Usage: bash owner/keys.sh openai|google|anthropic [--from SERVICE]"; exit 1 ;;
esac
if [ "${2:-}" = "--from" ] && [ -n "${3:-}" ]; then
  key="$(security find-generic-password -s "$3" -w)"
else
  key="$(pbpaste)"
fi
if [ ${#key} -lt 20 ]; then
  echo "That doesn't look like a key. Copy it, or check the service name, and run this again."
  exit 1
fi
security add-generic-password -U -a "$USER" -s "call-companion-$vendor" -w "$key"
echo "Saved the $vendor key as call-companion-$vendor (${#key} characters)."
