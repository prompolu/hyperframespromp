# PROMPOLU — Technical Animation Test

An editable five-second French motion graphic explaining a thermal break with a generic schematic. Design canvas: 1080 × 1920, 30 FPS. The two simple aluminium bodies and two insulating polyamide bars are illustrative, not a manufacturer's extrusion geometry or a performance specification. Bronze is a diagram highlight, not a claim about the material's color.

## Sources

PROMPOLU's website was read for brand research only. The downloaded logo and Anton/DM Sans fonts are stored locally with source URLs and SHA-256 hashes in `assets/sources.json`. Fonts include their upstream OFL licenses. The color palette follows the user's supplied values and the site's current `/styles.css`: `#15171A`, `#F1F0EC`, `#8C6A45`. No website files were modified.

The title adapts the official HyperFrames `caption-clip-wipe` component. Its original source is retained in `references/`. All geometry and animation remain editable in `index.html` and the labeled GSAP timeline. `BRIEF.md` and `shot-plan.json` record the design and timing.

## Commands

Run from this project directory. Node 22+, Chromium, FFmpeg and FFprobe are needed. Commands pin the actual HyperFrames CLI to `0.8.183`; no substitute renderer is used.

```sh
npm run doctor
npm run check -- --snapshots
npm run snapshot -- --at 0.5,1.4,2.3,3.3,4.5
npm run render:test
npm run render
npm run dev
```

`render:test` generates a half-scale HTML entry from the unchanged 1080 × 1920 source, then renders that entry with HyperFrames at 540 × 960, 30 FPS. HyperFrames' resolution preset option supports upscaling, so the generated entry supplies the explicit test canvas. The derivative `.hyperframes/test-project/` is a separate disposable project ignored by Git. `render` exports the original full-size five-second composition.

`scripts/hyperframes.sh` keeps the installed project skill bundle pinned, disables telemetry, and enables Node's inherited proxy support for this cloud environment. Assets are local, so the composition itself makes no network requests during capture. A fresh machine may still need npm access to obtain the pinned CLI.

## Scope and limitations

This is a silent motion-design/rendering test. No narration, sound design, manufacturer-specific geometry, U-values or dimensions are implied. No complete 60-second video was started. Optional transcription, TTS and music-generation packages are not installed because this test does not use them. HyperFrames subscription usage cannot be read without a login; the requested local rendering workflow is tested independently.

Dependency, static, browser, motion and encoding evidence is saved in `evidence/`; outputs are in `renders/`.

## Verified result

The first 540 × 960 H.264 MP4 rendered successfully with HyperFrames 0.8.183: exactly 5.000 seconds, 30 FPS, 150 decoded frames, yuv420p. The entire stream decoded without errors. Rendered pixels were inspected against the proof snapshots. HyperFrames' browser check passed runtime, layout, all nine motion assertions (101 samples), and all 52 contrast checks. One nonblocking lint warning recommends splitting the single Studio timeline row into sub-compositions; the editable single-shot composition renders correctly.

The first render attempt failed before capture because managed-browser setup tried to create a cache under the read-only home directory. The tested wrapper fixes this by explicitly selecting the existing Chromium executable, placing project history in `.hyperframes/history`, and keeping preview state under a writable XDG state path. The temporary low-resolution entry is isolated in its own generated project to avoid duplicate-root lint errors.

The available browser is system Chromium 154.0.8037.57. Capture uses software graphics and the screenshot path, not the faster BeginFrame/headless-shell path. This affects speed and cross-browser pixel reproducibility. No substitute rasterizer is used. The 540 × 960 test's capture took about 8.3 seconds with two workers (plus setup/compile); the overlapping encode time must not be added again. Studio was started and its HTTP response verified locally; the cloud onboarding interface does not expose a usable localhost preview link, so review the MP4 files.

The original 1080 × 1920 composition also rendered successfully: 5.000 seconds, 30 FPS, 150 H.264/yuv420p frames. Full-stream decoding and rendered-final-frame inspection passed. `evidence/render-verification.json` records dimensions, frame counts, decoded-frame variation and SHA-256 hashes for both outputs.
