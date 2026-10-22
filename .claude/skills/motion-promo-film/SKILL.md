---
name: motion-promo-film
description: Build short premium motion-graphics films as code and render them to MP4 with sound. Covers app or website promos, morph-chain and keynote-style transitions, logo stings and reveals, and product showcases. The film is one deterministic HTML page driven by a paused GSAP timeline (window.seek), with velocity motion blur, letter-by-letter typography and inline SVG logo animation. It is rendered frame-accurately with headless Chromium (Playwright) and FFmpeg, and gets an original synthesised soundtrack whose pops, swooshes and hits follow the motion on screen. Use this skill whenever the user asks for a motion-graphics video, promo or teaser film, an animated logo reveal, an HTML/GSAP animation rendered to video or a frame-by-frame Playwright render. Also use it when they want sound design, sound effects, pops and swooshes or a music bed added to an animation, even if they never name the skill. It suits detailed second-by-second briefs best.
compatibility: Node 18+ with Playwright (Chromium 139+ for CSS corner-shape), FFmpeg and ffprobe, Python 3 with numpy and scipy for the soundtrack, Pillow and matplotlib for the review tools.
---

# Motion promo film

A short film (5–20 s) built as code:

- **One HTML page is the film.** A paused GSAP timeline is its clock, and `window.seek(t)` draws any instant deterministically.
- **A renderer screenshots every frame** at `t = frame / fps` and pipes the frames to FFmpeg.
- **The soundtrack is synthesised against the same timeline.** The swooshes are driven by the real on-screen speeds, so sound and picture are in sync by construction.

This workflow produced *PROMPOLU — Nos gammes*: 10 s, 1920×1080, 300 frames, a cut-free morph-chain website promo with pops and swooshes. `references/worked-example.md` maps that brief to the build, beat by beat, with every problem found along the way.

Why build it this way:
- **Timing.** You can hit a written second-by-second brief to the frame.
- **Reproducibility.** Re-renders are byte-identical.
- **Brand fidelity.** Logos are the real SVG paths, and colours are only the brand tokens.
- **Sound.** It can be redone in seconds when the picture changes.

If the user explicitly wants a HyperFrames project (its CLI, studio or cloud), use the HyperFrames skills instead. This skill is the self-contained Playwright route.

## Workflow

1. **Turn the brief into a beat table**: time window, what moves, its ease, and what appears or changes. Look for contradictions now and pick a resolution you can explain in the README. One example: a "final frame exactly as the logo file" and a "push-in during the hold" cannot both apply to the logo, so push the backdrop instead.
2. **Scaffold the project**: `bash <skill-dir>/scripts/new_film.sh <project-dir> <name>`. This copies `assets/template/`: the runtime page with a 4-second demo, the render, preview and motion-export scripts, and the sound engine. It also runs `npm install`.
3. **Collect the assets.**
   - Logo SVGs, inlined verbatim later.
   - Fonts, bundled under `assets/fonts` with their licence.
   - Images downloaded into `assets/`.
   - The palette as CSS tokens.

   Open every image and look for third-party watermarks or logos, then crop them out with `object-position`.
4. **Probe the browser features you depend on** in the render Chromium before building on them: `corner-shape`, `backdrop-filter`, SVG filters on HTML elements and GSAP CSS-variable tweens. A ten-line test page and one screenshot settle it.
5. **Author the film** in `index.html`. Keep the runtime and replace the demo. `references/engine.md` covers structure, the camera, morph handoffs, motion blur, typography, logos and the pitfalls to avoid.
6. **Review the picture**, following `references/review-checklist.md`. You cannot watch the film, so look at frames.
   1. Render stills at every beat boundary and build a contact sheet.
   2. Fix what you see and repeat.
   3. Then check consecutive frames around every handoff, determinism, brand colours on flat areas, and the last frame against the logo file.
7. **Compose the soundtrack**, following `references/sound-design.md`.
   1. Plan one cue per beat and write the score in `scripts/compose-soundtrack.py`.
   2. Run `npm run soundtrack -- --stems`.
   3. Run `scripts/analyze_audio.py` and rebalance until the effects clearly ride over the bed.
8. **Render and verify**: run `npm run render`, then `python3 <skill-dir>/scripts/verify_render.py <mp4> --wav assets/audio/soundtrack.wav --fps 30 --duration <s> --out evidence/verification.json`.
9. **Deliver.** Write a README listing the choices and any deviations from the brief, with the reason for each. Add `evidence/`: contact sheet, last frame, `verification.json` and `soundtrack-analysis.png`. Add `cues.txt`, then send the MP4.

Keep the user posted with short progress notes between long steps. A full render takes about 1.5 min for 300 frames at 1080p.

## Starting from an existing animation

When the user already has an animation and wants it scored or rendered, keep their timing and look unchanged.

1. Scaffold as usual, then replace the template's `index.html` with their page and copy their files in.
2. Add the page contract at the end of their script without changing what it draws.
   - Pause the timeline (`paused: true` or `tl.pause()`).
   - Set `window.seek = t => { tl.seek(t, false); return t; }`. Seek must return a number, never the timeline: Playwright tries to serialise a returned GSAP object and hangs.
   - Set `__duration = tl.duration()`, `__fps`, `__width`, `__height` and `__timeline = tl`.
   - Set `__ready` to a promise that resolves once fonts and images are loaded.
   - In render mode, place the stage at the page's top left at its exact pixel size, with no centring or scale-to-fit. The renderer screenshots the region from (0, 0) to (`__width`, `__height`).
3. Declare `__motionChannels` for everything that travels, as `[name, selector, property]`. The property is a GSAP property (`x`, `y`, `scale`, `rotation`), or `cx` / `cy` for the element's on-screen centre in stage pixels. The swooshes read these channels.
4. Plan the cues from the page's own tween times. Read them from the code, or print the top-level ones with `__timeline.getChildren(false).map(c => [c.startTime(), c.duration()])`. A staggered tween is a single child, so add `i × stagger` for each of its targets.
5. If the animation isn't GSAP, make `seek` drive whatever is there:
   - CSS animations and Web Animations: `document.getAnimations().forEach(a => { a.pause(); a.currentTime = t * 1000; })`.
   - Lottie: `anim.goToAndStop(t * 1000)`.
   - With no GSAP timeline, the motion export calls `window.seek` and can only read `cx` / `cy` channels.

Then continue from step 6 of the workflow.

## Authoring rules, short version

- **Page contract.** Expose `window.seek(t)`, `__ready` (fonts loaded, images decoded, timeline built), `__duration`, `__fps`, `__width`, `__height`, `__timeline` and `__motionChannels`. Use `?render` for the renderer, `?t=1.2` to freeze a frame and no parameter for a looping preview. Never read a clock or `Math.random` in render mode.
- **Layers.** Put backgrounds outside `#camera`. Scenes go inside it. Overlays (flash, bloom, vignette) and an exact end frame go after it.
- **Placement.** Place elements by their centre (`.pc` with `xPercent/yPercent -50`) so x/y read like the brief's coordinates.
- **Camera.** To centre a focal point F at scale s: `x = -s·(Fx − W/2)`, `y = -s·(Fy − H/2)`. To zoom while keeping F where it is: `x = (1 − s)·(Fx − W/2)`.
- **Morph chain.** One element hands off to the next at a frame where both look identical (same box, colour and position in the same coordinate space). Prove each handoff with two consecutive frames.
- **Motion blur.** Use one SVG `feGaussianBlur` per fast mover, sized by displacement per frame (gain 0.18, about a 180° shutter) and only inside its time window. Never tween `filter` on a tracked element; animate a wrapper instead. Read `engine.md` before adding a tracker.
- **Text.** Split letters at their kerned positions before any transform. Settle with three separate tweens (transform, opacity, colour) so back-ease overshoot never pushes a colour off-palette. Shorten staggers so long lines finish inside their window.
- **Logos.** Inline the SVG verbatim and prefix the ids of any second copy. Animate letter paths in SVG user units (px ÷ scale). Build a gloss sweep as a gradient inside a `<clipPath>` of `<use>` elements with `clip-rule="evenodd"`. Hide helper SVGs outside their window.
- **Colours.** Use only the brief's tokens, and shadows only as rgba of those tokens. Keep any element that sits on a same-colour surface visible with an outline from the palette.
- **Determinism.** `gsap.config({force3D:false})` keeps text crisp. Set initial states with `gsap.set`, and use `immediateRender:false` on late `fromTo` tweens. Give width and height in explicit px when a `set` must revert. Set `transformOrigin` once at init.

## Sound rules, short version

- **Effects.** Every transition gets a sound shaped by the motion that causes it.
  - Things that move get a swoosh: level and brightness follow the speed, the pan follows screen x.
  - Things that appear get a pop or bubble.
  - Things that land or lock get a thud or click.
  - World changes get a hit with a reverse swell into it.
  - Dissolves get a shimmer riser, and text gets soft blips.
- **The bed.** Pick the tempo phase so downbeats land on the biggest picture moments. Thin it when the film is calm, muffle it in hazes and cut it into flashes. Then let the final chord bloom under the logo and fade it out by the last frame.
- **Balance.** The bed sits about 8–10 dB under the effect peaks. Check it on the plot; the first instinctive mix had the music 10–15 dB too loud.
- **Tuning.** Put pings, dings and blips on chord tones or the pentatonic of the bar they fall in.
- **Master.** Aim for −15 LUFS integrated and a true peak at or below −1 dBTP, with no more than about 3 dB of limiter reduction. Mux as AAC 256 kb/s at 48 kHz, then confirm a 0-sample offset against the WAV.

## Deliverables checklist

- [ ] MP4: exact frame count, H.264 yuv420p, BT.709-tagged, decodes cleanly, audio track the same length as the video.
- [ ] Last frame matches the brand file (`scripts/compare_images.py` on the same ink bounding box).
- [ ] `window.seek` is deterministic (same t gives the same PNG bytes, in any seek order).
- [ ] Brand colours exact on flat areas, and no third-party marks.
- [ ] Soundtrack at about −15 LUFS, true peak at or below −1 dBTP, 0-sample sync offset, and regenerates byte-identically.
- [ ] README with the choices and deviations, evidence images, `verification.json` and `cues.txt`.

## Files in this skill

| Path | Use |
| --- | --- |
| `scripts/new_film.sh` | Scaffold a project from `assets/template/` |
| `assets/template/index.html` | Runtime page (seek, motion blur, split/settle, spring ease, asset loading, preview) and a 4 s demo film |
| `assets/template/scripts/render.mjs` | Frame-accurate render, stills (`--stills`), partial ranges (`--frames`), soundtrack mux |
| `assets/template/scripts/export-motion.mjs` | Samples `window.__motionChannels` (GSAP properties or on-screen centres) at 500 Hz for the soundtrack |
| `assets/template/scripts/soundlib.py` | Sound engine: motion-driven swoosh, pops, hits, blips, bells, pads, sub, reverb, mixer, mastering |
| `assets/template/scripts/compose-soundtrack.py` | The score (demo); rewrite it per film |
| `scripts/contact_sheet.py` | Contact sheets of stills or extracted frames |
| `scripts/analyze_audio.py` | Music-vs-effects curves, spectrogram and cue markers: see the mix you can't hear |
| `scripts/compare_images.py` | Last-frame and logo comparison: pixel diffs, ink bounding box and count |
| `scripts/verify_render.py` | ffprobe facts, full decode, loudness after AAC, audio sync offset → JSON |
| `references/engine.md` | How to author the page, morph handoffs, motion blur, typography, logos, pitfalls |
| `references/sound-design.md` | Cue planning, swoosh mapping, the bed, levels, mastering, verifying without ears |
| `references/review-checklist.md` | The review loop with commands |
| `references/worked-example.md` | PROMPOLU — Nos gammes: brief → build, decisions, problems and fixes |
