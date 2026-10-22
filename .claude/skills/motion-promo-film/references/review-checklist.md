# Review checklist: you can't watch it, so look at frames and numbers

Run these from the film project. `<skill>` is this skill's folder.

## Picture

1. **Stills at every beat boundary.** Pick times at the start, middle and end of each beat, plus the frames just after each handoff.
   ```sh
   node scripts/render.mjs --stills 0.1,0.5,0.8,1.0,1.3,1.6,2.0,2.45 --dir renders/stills/a
   python3 <skill>/scripts/contact_sheet.py renders/review-a.jpg renders/stills/a/*.png
   ```
   Read the sheet, then crop at full resolution anything that looks odd. A downscaled sheet can make a vertical blur look horizontal, so check before "fixing" it.
   ```sh
   python3 -c "from PIL import Image; Image.open('renders/stills/a/t02.000.png').crop((520,60,1220,560)).save('renders/crop.png')"
   ```
2. **What to look for, beat by beat:**
   - Positions and sizes match the brief's numbers.
   - Eases feel right: overshoots visible, settles complete.
   - Blur only on fast moves, in the direction of motion, not smearing text meant to be read.
   - Nothing visible that should be hidden. Helper SVGs and parked elements leak most often.
   - Elements on same-colour surfaces are still visible.
   - Composition and safe margins.
3. **Handoff continuity.** For every morph-chain swap at time t, render the two frames either side and crop the region. Shapes, colours and positions must match exactly.
   ```sh
   node scripts/render.mjs --stills 3.0,3.0333333,4.8666667,4.9 --dir renders/stills/swaps
   ```
4. **Whole-film overview.** After a full render, check every 10th frame:
   ```sh
   mkdir -p renders/frames
   ffmpeg -v error -i renders/film.mp4 -vf "select='not(mod(n\,10))',scale=384:-1" -vsync 0 renders/frames/f%03d.png
   python3 <skill>/scripts/contact_sheet.py evidence/contact-sheet.jpg --cols 5 --width 384 renders/frames/*.png
   ```
5. **Determinism.** The same t must give identical bytes, whatever was seeked before:
   ```sh
   node scripts/render.mjs --stills 5.5,2.9 --dir renders/det1
   node scripts/render.mjs --stills 9.9,0.2,2.9,5.5 --dir renders/det2
   sha256sum renders/det1/t05.500.png renders/det2/t05.500.png
   ```
   Also grep the page: `Math.random`, `Date.now` and `performance.now` may appear only in preview code.
6. **Brand colours.** Sample flat areas, which must be exact tokens:
   ```sh
   python3 -c "from PIL import Image; im=Image.open('renders/stills/a/t00.500.png').convert('RGB'); print('#%02X%02X%02X' % im.getpixel((100,100)))"
   ```
7. **Last frame vs the logo file.** First check the DOM state of the end logo at the last frame (`t = (frames − 1) / fps`): every path at opacity 1, identity transform, final fill, `filter: none`; wrapper offset 0. Then build a reference page with the logo file as an `<img>` at the exact box over the same backdrop (same scale if the backdrop is pushed), screenshot it with the same Chromium, and compare:
   ```sh
   node scripts/render.mjs --stills 9.9666667 --dir renders/last        # frame 299 of 300 → renders/last/t09.967.png
   python3 <skill>/scripts/compare_images.py renders/last/t09.967.png renders/reference.png --box 520,470,1400,612
   ```
   Pass means identical ink bounding boxes and an ink pixel count within about 0.1 %. The rest is anti-aliasing: inline SVG and `<img>` snap sub-pixels differently.

## Sound

8. **Stems and plot:**
   ```sh
   npm run soundtrack -- --stems
   python3 <skill>/scripts/analyze_audio.py --master assets/audio/soundtrack.wav --music renders/work-audio/music.wav \
       --sfx renders/work-audio/sfx.wav --cues cues.txt --out evidence/soundtrack-analysis.png
   ```
   Every cue should be a red peak 6–12 dB over the blue bed. Look for clipped samples (0), the octave balance, and L/R correlation (0.8–0.9).
9. **Cue times vs picture.** Read `cues.txt` against the beat table: pops on appearances, swooshes peaking at the fastest frame, hits on world changes.
10. **Reproducible.** `rm -rf renders/work-audio && npm run soundtrack`, then compare the WAV hash with the previous one.

## Final file

11. **Render and verify:**
    ```sh
    npm run render
    python3 <skill>/scripts/verify_render.py renders/<name>-1920x1080.mp4 --wav assets/audio/soundtrack.wav --fps 30 --duration 10 \
        --out evidence/verification.json
    ```
    Expect: exact frame count, `yuv420p`, BT.709 tags, clean decode, AAC 48 kHz stereo of the same duration, about −15 LUFS, true peak at or below −1 dBTP, audio offset 0 samples.
12. **Evidence to ship:** `evidence/contact-sheet.jpg`, the last frame PNG, `verification.json`, `soundtrack-analysis.png`, and `cues.txt`. Also a README section listing the choices and deviations from the brief, with the reason for each.
