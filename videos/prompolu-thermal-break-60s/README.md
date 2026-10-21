# PROMPOLU — Rupture de pont thermique, film photographique de 60 secondes

Editable 1080 × 1920, 30 FPS HyperFrames film. Six real photographic scenes, French synthetic narration, and original electric-piano music. The original five-second schematic test is preserved in the neighboring project, not reused in this film.

## Brand and imagery

The live website's current `/styles.css` and `/assets/fonts.css` are the references: warm ivory `#F1F0EC` is dominant; dark ink `#15171A` is the text color; bronze `#8C6A45` is an accent. Small bronze text uses the site's darker `#765333`. Anton and DM Sans are local. The original black logo is not inverted.

Only the four photographs listed in `assets/selected-photos.json` are used. No schematic drawing, manufacturer-profile rendering or generated architectural image is used. These are credited stock photographs illustrating the subject, not documented PROMPOLU installations. Technical claims remain qualitative; no fictional profile geometry, U-values, savings percentages or product ratings are asserted. Full source and license information is in [CREDITS.md](CREDITS.md).

## Edit and render

Run from this project directory:

```sh
npm ci
npm run check
npm run dev
npm run render
```

HyperFrames CLI and helper packages are pinned to `0.8.183`. `scripts/hyperframes.sh` selects the available Chromium and writable history/state paths in this managed cloud environment. The real HyperFrames browser capture, audio graph and FFmpeg pipeline produce the output; no replacement rasterizer is used.

- `index.html`: six timed scene hosts plus separate narration and music tracks.
- `compositions/scenes/`: independently editable 10-second scene files.
- `index.motion.json`: full-film visibility, frame-boundary and liveness assertions.
- `SCRIPT.md`, `narration.json`, `audio-meta.json`: French script and voice timing.
- `design.md`, `STORYBOARD.md`: brand rules and scene plan.
- `scripts/build-film.py`: editable source generator (rerunning it rewrites index.html, so reapply the audio carve afterward).
- `scripts/generate-voice.py`: speech regeneration using edge-tts 7.3.1, a trusted CA bundle and the inherited HTTPS proxy.
- `scripts/compose-music.py`: original instrumental composition, requiring numpy and FFmpeg.
- `scripts/prepare-preview.mjs`: a separate half-scale project under the ignored `.hyperframes/preview-project/` folder, leaving the full-size source intact.

Voice is `fr-FR-DeniseNeural`. The cloud TTS connection initially needed the existing environment CA added to its standard trust context; TLS verification stayed enabled. The music track has HyperFrames' frequency-aware voiceover carve and volume automation, so voice and music remain separately editable.

## Checks and limitations

Runtime, layout, font and contrast checks are executed in Chromium; motion assertions use stable composition attributes because the assembler namespaces scene IDs. Stock-photo provenance is explicit. This is architectural photo-based communication of the thermal-break principle; no cut-away photograph of a particular manufacturer's polyamide bar is claimed. System Chromium uses slower software screenshot capture in this environment.


### Cloud audio-effects workaround

The browser's managed policy rejects the local file navigation used by HyperFrames' offline effects renderer. A strict first preview therefore stopped instead of silently dropping audio. The generated carve is preserved in `audio-mix.json`. `scripts/bake-music-fx.py` applies its five time-varying peaking filters and gain envelope to a separate `music-carved.wav` stem with standard RBJ filters at 10 ms blocks. The source music is retained. HyperFrames still performs the final voice/music mixing, live volume fades, browser frame capture and video encoding. No audio-processing warning was suppressed. Run `python scripts/bake-music-fx.py` after regenerating the original music; it needs numpy and scipy. This is an offline approximation of the saved Web Audio filter automation, not a claim of bit-identical browser audio processing.

The animation-map helper was installed and pinned to the same 0.8.183 core/producer versions. It reports a 60-second timeline with 108 mapped tweens. Full-film motion assertions use stable `data-composition-id` selectors to survive the assembler's ID namespacing.


## Current validation

The complete 540 × 960 preview renders with actual HyperFrames: 60.000 seconds, 30 FPS, 1,800 H.264 video frames and a 60-second AAC stereo audio stream at 48 kHz. Full decoding passes. Audio mean level is -18.1 dB and peak -1.8 dB (no clipping). `evidence/preview-verification.json` records the measured output. Final source checks in `evidence/check-ready.json` pass with zero errors or warnings, 300 motion samples and all 40 sampled contrast checks passing. Each scene's midpoint was visually inspected in `evidence/proof-frames/contact-sheet.jpg`.

The downloadable editable ZIP contains source, assets, scripts, licenses and validation evidence; MP4 outputs are linked separately to avoid duplicating large files. Install Python dependencies for optional audio regeneration with `python -m pip install edge-tts==7.3.1 numpy scipy`; finished audio stems are already included for ordinary re-rendering.

The full-resolution HyperFrames export also passes: 1080 × 1920, 60.000 seconds, 30 FPS, 1,800 H.264 frames, 60-second AAC stereo audio at 48 kHz, full decoding successful. Audio mean/peak are -18.1/-1.8 dB. The full render took 2m35.4s on this cloud machine, using the software screenshot capture path. See `evidence/full-verification.json`.
