#!/usr/bin/env bash
# Scaffold a new film project from the motion-promo-film template.
#   bash <skill>/scripts/new_film.sh <target-dir> [package-name]
# Copies the runtime page, render/preview/motion-export scripts and the sound engine, installs Playwright,
# and copies Inter Display (OFL) from the system fonts when available.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:?usage: new_film.sh <target-dir> [package-name]}"
NAME="${2:-$(basename "$DEST")}"

if [ -e "$DEST/index.html" ]; then
  echo "refusing to overwrite $DEST/index.html" >&2
  exit 1
fi
mkdir -p "$DEST"
cp -R "$SKILL_DIR/assets/template/." "$DEST/"
mv "$DEST/gitignore" "$DEST/.gitignore"
mkdir -p "$DEST/assets/fonts" "$DEST/assets/audio" "$DEST/renders" "$DEST/evidence"
node -e '
  const fs = require("fs"), p = process.argv[1] + "/package.json";
  const j = JSON.parse(fs.readFileSync(p, "utf8"));
  j.name = process.argv[2].toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "") || "motion-film";
  fs.writeFileSync(p, JSON.stringify(j, null, 2) + "\n");
' "$DEST" "$NAME"

for f in InterDisplay-Regular InterDisplay-Medium InterDisplay-SemiBold Inter-Regular; do
  for dir in /usr/share/fonts/opentype/inter "$HOME/Library/Fonts" /Library/Fonts; do
    if [ -f "$dir/$f.otf" ]; then cp "$dir/$f.otf" "$DEST/assets/fonts/"; break; fi
  done
done
ls "$DEST/assets/fonts"/*.otf >/dev/null 2>&1 || echo "note: no Inter Display found — add the brand fonts to $DEST/assets/fonts and FONT_FACES"

(cd "$DEST" && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="${PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:-1}" npm install --no-audit --no-fund --silent) \
  || echo "note: npm install failed — run it in $DEST before rendering"

cat <<EOF
Film project ready: $DEST
  npm run preview      # http://127.0.0.1:4173/ (loops; ?t=1.2 freezes a time)
  npm run stills       # review PNGs → renders/stills/
  npm run soundtrack   # assets/audio/soundtrack.wav + cues.txt (python3 -m pip install numpy scipy)
  npm run render       # renders/<name>-WxH.mp4, soundtrack muxed when present
The demo film in index.html (4 s) and scripts/compose-soundtrack.py shows the patterns — replace both.
EOF
