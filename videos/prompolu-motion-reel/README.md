# PROMPOLU — Motion reel (10 s, 16:9, 60 fps)

A tactile, keynote-style motion-design reel for PROMPOLU. It opens in a dark warm-ink studio, flips to the cream paper world, and ends on the supplied logo. There are no hard cuts: one polished-bronze hero object morphs from beat to beat.

1. "MOTION" in puffy aluminium type.
2. The bronze O becomes a ball for the squash-and-stretch beat.
3. The camera dollies out into a motion editor, where an easing curve becomes a spring.
4. The ball flies at the camera and becomes a toggle, then a glass disc, then a bronze flood.
5. A 3D bento of six motion techniques.
6. A "600 frames." odometer.
7. The PROMPOLU ALUMINIUM logo, revealed window by window.

- **Film:** [out.mp4](out.mp4). 1920 × 1080, 60 fps, exactly 600 frames, H.264 yuv420p (BT.709), AAC 192 kb/s.
- **Source:** `index.html` is one self-contained page. It holds all the CSS, JS and SVG, plus `assets/logo-prompolu.png`.
- **Renderer:** `render.mjs` uses Playwright and FFmpeg.
- **Soundtrack:** `sfx.mjs` uses procedural PCM synthesis and writes `sfx.wav`.
- **Evidence:** `evidence/` and `cues.txt`.

## Run it

```sh
npm install                 # Playwright 1.56.1 (uses the machine's Chromium); FFmpeg must be on PATH
npm run stills              # the 11 review stills from the brief → stills/
node sfx.mjs                # sfx.wav + cues.txt (samples the page's motion at 500 Hz)
node render.mjs             # out.mp4: 4 sub-frames per frame, tmix, x264 CRF 16, AAC 192k
node render.mjs --mux       # re-encode the frames in work/frames with a new sfx.wav
npm run preview             # http://127.0.0.1:4173/?play  (real time, loops)  ·  ?t=4.55 freezes a moment
```

## How it is built

**Deterministic page**
- One paused GSAP 3.12.5 master timeline drives `draw(t)`.
- Every element's state is a pure function of `t`: cameras, ball path, spring curves, odometer reels and logo windows.
- `window.DURATION = 10` and `window.seek(t)` render the exact state for `t`. `seek` returns a promise once that frame's grain is drawn.
- There is no `Date.now`, no `Math.random` and no free-running `requestAnimationFrame` outside `?play`.
- Dust, embers and grain seeds come from a seeded mulberry32 PRNG.

**Fonts and GSAP**
- The page loads Inter (variable 100–900), Archivo (wdth 125, wght 800) and JetBrains Mono 400/600 from Google Fonts, and GSAP from cdnjs, exactly as written in the brief.
- The renderer serves these requests from `.cache/net/`, which curl fills on the first run. Every render therefore uses the same bytes and works offline.

**Puffy material**
- The brief's filter chain is shared by every heavy glyph, the ball, the toggle, the Springs card, the digits and the data bars, and is never used on the logo:
  1. blur of SourceAlpha (7);
  2. specular lighting at (−400, −600, 500);
  3. composite "in";
  4. arithmetic add (k2 1, k3 .8);
  5. drop shadow 0 10 18.
- "MOTION" adds a second specular pass, lit from below in #D9A86C at 50 %, for its bronze rim.

**Motion blur**
- `render.mjs` captures 4 sub-frames per frame at `t + k/240`.
- FFmpeg averages them with `tmix=frames=4` and keeps one frame in four. This gives 2,400 captures for 600 frames.
- Four samples alone leave visible copies on the fastest moves. Those elements also get a velocity-scaled blur that fills the gap between sub-frames: the shrinking sphere, the ball, the toggle knob, the cursor, and the bento camera (capped at 6 px, as the brief allows).
- The brief's own blurs are kept on top of that: the 14 px tumble blur, the reel smear, the depth blur of the flying ball and the logo-window blur.

**Encode**
- The capture → `tmix` → `f_%04d.png` → `ffmpeg -framerate 60 -i f_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 16 -movflags +faststart` chain follows the brief.
- The encode also adds a BT.709 matrix, BT.709 tags and `-preset slow`.
- Three headless Chromium workers capture in parallel: about 6 minutes for the 2,400 sub-frames, plus about 4 minutes of averaging and encoding.

## Soundtrack (`sfx.mjs`, original, no samples)

**Groove**
- 93 BPM. Bar 1 lands on the sub-bass drop at 1.05 s, and the "600" clunk at 8.15 s falls on a beat.
- Chords: Dm9 → Bbmaj9 → Gm9 → C9sus4 → Fmaj9. The Fmaj9 arrives under the logo, low-passed and silent by 9.70 s.
- Parts: kick, rim, hats, a pumped bass, a stereo pad and a plucked arpeggio.

**Effects** (cue by cue in `cues.txt`)
- 0.15–0.45: glassy ticks tuned to Dm9 as each letter lands, with an airy filtered intro.
- 1.05: zoom whoosh, then the sub-bass drop as the O turns bronze.
- 1.50, 1.86, 2.18 and 2.34: rubbery thumps, 30 % softer each time.
- 2.65: air whoosh on the dolly-out.
- 3.20: UI tick when the cursor grabs the handle.
- 4.00: big whoosh on the fly-through.
- 4.50: crisp mouse click.
- 4.82: glassy chime as the disc splits.
- 5.00: bass swell into the bronze flood.
- 5.55–6.35: swishes on the camera swoop.
- 7.45–8.15: one mechanical tick per digit passing on each reel, then a clunk on the bronze 0.
- 8.60: bright shimmer as the logo rises.

Every whoosh is driven by the page's own motion: `window.motionAt(t)` is sampled at 500 Hz, so level, brightness and pan follow the real on-screen speed.

**Master**
- −15 LUFS integrated, true peak −1.0 dBTP after AAC, limiter at most 2.4 dB.
- AAC sync offset is 0 samples.
- Regeneration is byte-identical.

## Checks (`evidence/`)

- **`verification.json`:**
  - exactly 600 frames, 1920 × 1080, yuv420p, BT.709;
  - clean full decode;
  - AAC 48 kHz stereo of the same length;
  - −15.2 LUFS and −1.0 dBTP after AAC;
  - 0-sample audio offset.
- **`logo-check.json`:** the logo area of the 10.00 still against `logo-prompolu.png`, composited on #F1F0EC and scaled exactly 2×.
  - Against the same PNG drawn by the same Chromium as an `<img>`, the frame is pixel-identical (max difference 0).
  - Against a PIL composite with bilinear 2× scaling, the max difference is 2 levels, within the brief's tolerance.
  - Bicubic or Lanczos scaling differ more at the edges because they are different resampling filters, not because the logo changed.
- **`last-frame-599.png`:** the real last frame of the film (the average of its 4 sub-frames). Its logo box is also pixel-identical to the reference.
- **Determinism:** `window.seek` gives byte-identical PNGs for the same `t` whatever was seeked before. This was checked on 5 times in two different seek orders.
- **`colour-samples.json`:**
  - Flat areas match the brand tokens within 1–2 levels; the difference is the grain.
  - The final-frame corners are pure #17120D.
  - The Springs card reads lighter than #765333 at its centre because of the puffy filter's specular lighting.
- **`brief-stills.jpg`:** the 11 stills the brief asks for (0.40 → 10.00), reviewed against the beat descriptions before the full render.
- **`contact-sheet.jpg`:** every 20th frame of `out.mp4`.
- **`final-frame-10.00.png`** and **`soundtrack-analysis.png`:** the last frame, and music-vs-effects loudness with cue markers.

## Choices and deviations from the brief

**Logo file**
- The supplied `logo-prompolu.png` (602 × 83, sha256 `2e23815c…`) is used untouched: 1204 × 166 at (358, 457), revealed through the brief's nine windows and swapped to one `<img>` at 9.10 s.
- The SVG logo from the earlier "Nos gammes" brief is not used. Its framing is different (aspect 7.11 vs 7.25) and it is coloured #15171A, and the brief's pixel check is defined against the PNG.

**Grain and the logo**
- The grain is never drawn inside the logo rectangle (24 px feathered margin), and the logo layer sits above the grain and both vignettes.
- The lighter #F8F7F4 centre used during the reveal fades out between 9.10 and 9.30 s, so the settled logo sits on exact #F1F0EC, as the final-frame spec and the pixel check require.

**How the grain is rendered**
- It is still `feTurbulence` (baseFrequency .9), re-seeded every frame from mulberry32.
- It is rendered once per frame into a canvas instead of as a live overlay. The 4 sub-frames share it, so averaging does not wash it out, and it keeps the capture fast.
- Its mean follows the world colour (#4F4740 in the dark world, #F1F0EC on paper), so flat brand colours do not shift.

**"MOTION" width**
- With the brief's cap height of 200 px, Archivo at wdth 125 and +2 % tracking, the word measures about 1,560 px, not "about 1,300".
- The explicit typographic values were kept, which puts the second O at about 68 % of the width instead of 64 %. The camera punches in on the O wherever it is.

**Spring overshoot**
- The curve, the playhead, the Position X readout and the ball all follow the same spring: `spring(180, 12)`, about a 22 % overshoot, flat from 60 % of the width.
- The ball therefore overshoots to about 20 % of the frame rather than the 27 % the brief also mentions. The two numbers cannot both hold while the curve and the ball stay in sync.

**Tempo**
- 93 BPM instead of exactly 94, so that bar 1 lands on the 1.05 s sub drop and the 8.15 s clunk falls on a beat.

**Effects-tail fade**
- The music fades to silence by 9.70 s. The tail of the logo shimmer and its reverb fades out by 9.95 s, so the last frames are silent.

**Cursor timing**
- The cursor's 50 ms rise at 4.45–4.50 s is kept as written. It reads as a quick, motion-blurred swipe.
