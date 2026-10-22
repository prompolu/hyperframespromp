#!/usr/bin/env bash
# Pinned HyperFrames CLI wrapper for this project (no global installs, no telemetry).
set -euo pipefail
cd "$(dirname "$0")/.."
export HYPERFRAMES_SKIP_SKILLS=1
export HYPERFRAMES_NO_TELEMETRY=1
export NODE_USE_ENV_PROXY=1
export HYPERFRAMES_RUN_ID="${HYPERFRAMES_RUN_ID:-prompolu-motion-20s}"
export HYPERFRAMES_HISTORY_ROOT="$PWD/.hyperframes/history"
export XDG_STATE_HOME="${XDG_STATE_HOME:-$PWD/.hyperframes/state}"
# Use the system or preinstalled Chromium when present.
if [[ -z "${HYPERFRAMES_BROWSER_PATH:-}" ]]; then
  for c in "$(command -v chromium 2>/dev/null || true)" /opt/pw-browsers/chromium; do
    if [[ -n "$c" && -x "$c" ]]; then export HYPERFRAMES_BROWSER_PATH="$c"; break; fi
  done
fi
exec npx --yes hyperframes@0.8.186 "$@"
