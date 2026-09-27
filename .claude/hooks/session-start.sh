#!/bin/bash
# Installs the dembrandt CLI (design-token extractor) for Claude Code on the web sessions.
set -euo pipefail

# Only run in remote (Claude Code on the web) environments.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if ! command -v dembrandt >/dev/null 2>&1; then
  npm install -g dembrandt >/dev/null 2>&1
fi

echo "dembrandt $(dembrandt --version) ready — run via scripts/dembrandt.sh <url>"
