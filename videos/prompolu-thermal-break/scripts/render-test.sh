#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
node scripts/prepare-test.mjs
bash scripts/hyperframes.sh render .hyperframes/test-project --fps 30 --quality draft --workers 2 --strict --no-best-effort --output "$PWD/renders/prompolu-thermal-break-test-540x960.mp4"
