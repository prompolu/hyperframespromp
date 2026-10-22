# FORMA — 20-second product film (work in progress, superseded)

**Status: unfinished, not rendered.** This project was paused when the request changed to the PROMPOLU film (`../prompolu-motion-20s/`). It is kept for reference only.

What exists:

- `index.html` — the complete visual timeline (00.00–20.00) on one master GSAP timeline. It covers the opening question and answer cascades, red circle → sparkle reveal, white sphere wipe, discovery board, search focus, masonry scroll, hero photo card with action discs, save → "Saved" capsule, and the closing gradient with the FORMA wordmark. Lint passes with 0 errors, and snapshots were inspected for every beat.
- `assets/` — Inter (OFL), GSAP, and photos from prompolu.com supplied at the client's request. The hero uses a crop of `window-original.webp`: `assets/photos/hero-medina-portrait.jpg`.

What is missing:

- **No score or sound design.** `assets/audio/forma-score.wav` is a git-ignored silent placeholder; recreate it with `ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 20 -c:a pcm_s16le assets/audio/forma-score.wav`.
- **No MP4 render and no final validation.**
