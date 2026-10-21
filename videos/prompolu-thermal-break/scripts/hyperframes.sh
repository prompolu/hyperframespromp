#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Keep the complete project skills pinned; no global installs or telemetry.
export HYPERFRAMES_SKIP_SKILLS=1
export HYPERFRAMES_NO_TELEMETRY=1
export NODE_USE_ENV_PROXY=1
export HYPERFRAMES_RUN_ID=prompolu-thermal-break-test
export HYPERFRAMES_HISTORY_ROOT="$PWD/.hyperframes/history"
export XDG_STATE_HOME="${XDG_STATE_HOME:-$PWD/.hyperframes/state}"
if [[ -z "${HYPERFRAMES_BROWSER_PATH:-}" ]] && command -v chromium >/dev/null 2>&1; then
  export HYPERFRAMES_BROWSER_PATH="$(command -v chromium)"
fi
if [[ -d /workspace/.npm-cache ]]; then
  export npm_config_cache=/workspace/.npm-cache
fi
exec npx --yes hyperframes@0.8.183 "$@"
