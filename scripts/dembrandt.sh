#!/bin/bash
# Runs dembrandt against the pre-installed Chromium over CDP, since dembrandt's
# own browser download (cdn.playwright.dev) may be blocked by the network policy.
# Usage: scripts/dembrandt.sh <url> [dembrandt options...]
set -euo pipefail

PORT="${CDP_PORT:-9222}"

if ! curl -s "localhost:$PORT/json/version" >/dev/null 2>&1; then
  CHROME="$(find "${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}" -maxdepth 4 -type f -path '*chrome-linux/chrome' 2>/dev/null | head -1)"
  if [ -z "$CHROME" ]; then
    echo "Chromium not found; falling back to dembrandt's own browser." >&2
    exec dembrandt "$@"
  fi
  nohup "$CHROME" --headless=new --no-sandbox --remote-debugging-port="$PORT" about:blank >/dev/null 2>&1 &
  for _ in $(seq 1 40); do
    curl -s "localhost:$PORT/json/version" >/dev/null 2>&1 && break
    sleep 0.25
  done
fi

BROWSER_CDP_ENDPOINT="http://localhost:$PORT" exec dembrandt "$@"
