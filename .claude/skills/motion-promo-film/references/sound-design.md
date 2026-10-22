# Sound design: motion-driven soundtrack

Everything is synthesised by `scripts/soundlib.py` (no samples, no licences to clear) and scored in `scripts/compose-soundtrack.py`. The result is a 48 kHz, 24-bit stereo WAV of exactly the film's length, plus a generated `cues.txt`.

## Contents
1. Pipeline
2. Plan the cues from the beat table
3. Motion-driven swooshes
4. Pops, blips, bells: tuned to the bar
5. Hits, risers, shimmers
6. The music bed
7. Levels that work
8. Master and mux
9. Verifying a mix you cannot hear
10. Pitfalls

## 1. Pipeline

```
index.html  →  export-motion.mjs  →  renders/work-audio/motion.json  (every channel in __motionChannels at 500 Hz)
                         ↓
compose-soundtrack.py (score) + soundlib.py (engine)
                         ↓
assets/audio/soundtrack.wav + cues.txt   →   render.mjs muxes AAC 256k   →   verify_render.py (sync, loudness)
```

`npm run soundtrack` re-exports the motion first, so the sound follows any picture change. Add `-- --no-export` to reuse the last export, and `-- --stems` to write `renders/work-audio/{music,sfx}.wav` for analysis. Noise is seeded per sound tag with `crc32`, never Python's per-process-random `hash()`, so two runs are byte-identical. Prove it with `sha256sum` before and after a clean rerun.

Declare in `__motionChannels` everything a sound should follow: the camera (`x`, `y`, `scale`), every element that travels, scrolls, rotates, scales or drops, and any containers. Name channels `element.prop`. A `cx` / `cy` channel gives the on-screen centre directly, camera and parents included, so a pan needs no `M.screen` conversion. It is the only kind that works on pages without GSAP.

## 2. Plan the cues from the beat table

For every beat, ask what happens in the picture, then pick the matching sound:

| On screen | Sound | soundlib |
| --- | --- | --- |
| Something travels (slide, glide, scroll, zoom, fling, whip, drop, swing) | Swoosh shaped by its speed and position | `swoosh(tag, t0, t1, speed, xpos, …)` |
| Something appears or pops in | Pop (pitch falls) or bubble (pitch climbs) | `pop(tag, f0, f1)`, `pop(…, rise=True)` |
| Something lands, presses or locks | Thud, knock, click, latch | `thup`, `kick`, `click(tag, tone, knock, latch)` |
| The world changes (cut to dark, flash) | Hit, with a reverse swell ending on it | `impact`, `rev_swell` placed at hit − dur |
| Haze, dissolve, bloom | Shimmer riser | `shimmer_riser` |
| Glossy sweep across a logo | Metallic shimmer, panned with the sweep | `metal_shimmer` + per-sample pan |
| Letters settle, a URL types | Soft blips, one per letter, on the bar's scale | `blip(tag, midi(n))` |
| Notification, badge | Bell "ding", optionally with a grace note | `bell(midi(n))` |
| Stretch (button → bar) | Rubbery zip | `rubber_zip` |
| Card or page swap | Paper flick | `flick` |
| Something blurs away | Airy puff | `whff` |

Put the cue time on the visual event. For swooshes, label the cue with the peak-speed time (`M.peak(t0, t1, v)`). Sound may trail the picture by up to about 40 ms but should not lead it by more than about 20 ms.

## 3. Motion-driven swooshes

`swoosh()` turns a speed curve into sound:
- level ∝ (speed / max)^shape;
- the low-pass cutoff sweeps from `lo` to `hi` Hz with speed, so it is brighter when faster;
- `air` adds band-passed hiss only near peak speed;
- the pan follows the element's screen x;
- `flutter` ripples the level at the rate items pass the eye (scroll speed ÷ row pitch);
- `tone=(f0, f1, level)` adds a pitched sweep for falls and doppler-like passes.

Compute screen positions with `M.screen(x, y)` (camera applied) and speeds with `M.speed(x, y)`. Settings that worked:

| Motion | Speed input | lo–hi (Hz) | air | attack / release (s) | Extra |
| --- | --- | --- | --- | --- | --- |
| Mark rising (expo.out, fastest at t=0) | \|dy/dt\| | 500–7500 | 0.5 | 0.02 / 0.09 | — |
| Icon glide + camera pull-back (deep) | screen speed | 120–2400 | 0.15 | 0.008 / 0.1 | pan from screen x |
| Page scroll (power3.out) | \|d scroll/dt\| × camera scale | 300–4200 | 0.25 | 0.01 / 0.12 | soft, −18.5 dB |
| Camera push-in | \|dT/dt\| + 900·\|d scale/dt\| | 200–6500 | 0.4 | — / 0.06 | — |
| Pointer flying to a button | screen speed | 900–9000 | 0.6 | — | light, high, panned |
| Pendulum rocking | \|dθ/dt\| (rad) × half-length | 600–3600 | 0.35 | — / 0.05 | shape 1.1, pan = 380·tanh(−ω/60) |
| Arc swing-in on a pivot | \|dθ/dt\| × arm length | 250–4200 | 0.3 | — | pan from the bob's x |
| Momentum fling of a grid | \|dy/dt\| | 300–9500 | 0.6 | 0.006 / 0.09 | flutter = speed / row pitch |
| Whip-down (power2.in, accelerating) | card + camera speed | 300–7500 | 0.6 | 0.004 / 0.05 | tone 1500 → 180 Hz, 0.6 |
| Drop (power2.in) | \|dy/dt\| | 400–5000 | 0.4 | 0.003 / 0.03 | tone 900 → 260 Hz, 0.4 |
| Slide into place (expo.inOut) | \|dx/dt\| | 300–6500 | 0.45 | 0.006 / 0.04 | lock click on landing |

Keep each swoosh's window tight around its motion. Before the motion the speed is zero, so the sound is silent anyway.

## 4. Pops, blips, bells: tuned to the bar

- `pop(f0, f1)`: icons and buttons 900–1300 → 300–400 Hz. A bubble (`rise=True`) for chips and grid icons, roughly 430–670 → 2.6× that, varied per item with `crc32(tag) % 5`.
- Blips for letters and typing follow the harmony of the bar they sit in: chord tones or the major pentatonic, rising through a word, panned across the word's width.
- Glass pings and dings on chord tones (D7 over Fmaj9, G7 over Bbmaj9; `midi(98)`, `midi(103)`). An untuned 3100 Hz ping sits 19 cents off and sounds sour.
- A grid appearing with a radial stagger becomes a cascade of soft bubbles rising through the pentatonic, timed to the stagger.

## 5. Hits, risers, shimmers

- **The strongest hit goes on the biggest world change** (0.3 s reverse swell, then `impact`). It carries its own kick, so don't stack a second "soft kick" on it.
- **A whip into a flash:** a short riser leads into it, the accelerating swoosh crescendos, and an `impact(bright=0.55)` lands just before the flash reaches full white.
- **Shimmer risers** use the chord's upper tones with tremolo, swelling into the next scene. Reverb (hall send 0.3–0.5) makes them dreamy.
- **Pan anything that crosses the frame:** a gloss sweep right to left, an arc in from the upper left, a card sliding in from the right.
- **Read landings and bounces from the motion instead of guessing them.** A `bounce.out` drop lands wherever the vertical velocity flips from falling to rising (screen y grows downwards):
  ```python
  dy = M.d(M['btn.y'])
  hits = [i for i in range(i0 + 1, i1) if dy[i - 1] > 0 >= dy[i]]
  ```
  Put a `thup` on each hit. Set its level from the impact speed, at `20·log10(v / v_first)` dB, and raise its pitch a little on each bounce.

## 6. The music bed

- **Tempo and phase.** About 125 BPM pop-house, with the grid phase chosen so downbeats hit the biggest moments. Search it:

```python
def dist_to_grid(t, phase, step):
    r = ((t - phase) / step) % 1.0
    return min(r, 1 - r) * step                       # seconds to the nearest grid line

moments = [(1.20, 3), (3.12, 1), (5.04, 2), (8.88, 2)]   # (time, weight): the biggest picture moments
cands = []
for bpm in np.arange(120, 130.5, 0.5):
    bar = 4 * 60 / bpm
    for phase in np.arange(0, bar, 0.01):
        err = sum(w * min(dist_to_grid(t, phase, bar), 0.1) for t, w in moments)
        cands.append((round(err, 3), float(bpm), round(float(phase), 2)))
print(sorted(cands)[:4])    # → (0.0, 125.0, 1.2): downbeats at 1.20, 3.12, 5.04, 6.96, 8.88
```

- **Harmony.** A simple bright progression, one chord per bar: vi–IV–I–V–I in F, i.e. Dm9 → Bbmaj9 → Fmaj9 → C6/9 → Fmaj9 on the logo. Voice-lead the pads (common tones, steps of 1–2 semitones). Put the root in a separate sustained sub (`sub_bass`), gliding 30 ms between roots.
- **Arrangement.** Follow the picture's energy:
  - airy intro pad, no bass;
  - pad, sub and offbeat shaker when the scene first builds;
  - plucks from the second bar;
  - full for the busy middle;
  - muffled during hazes (`automate_filter` low-pass down to about 650 Hz and back);
  - a rising high-pass then a cut just before a flash;
  - a fresh chord blooming under the logo, fading to silence on the last frame (`finish(music_fade=…)`).
- **Pump.** `pump(beats, 0.3)` ducks the bed about 3 dB on every beat for the house feel, deeper (0.5) under transition kicks.
- **Soft kicks on transitions**, not four-on-the-floor. Place them on beats near the visual transitions.

## 7. Levels that work

Gains are each sound's short-term level before mastering. All generators are normalised so the loudest 10 ms window has RMS 1.

| Sound | dB |
| --- | --- |
| Strongest hit (world change) | −9 |
| Flash hit | −10 |
| Fling / whip swooshes | −11.5 / −12 |
| Icon pop, soft bass thump | −12.5 / −14 |
| Lock click, zoom and slide-in swooshes | −13.5 to −15 |
| Glides, bar slide, morph swooshes | −15 to −17.5 |
| UI pops (button, chips, "+"), card flick | −15.5 to −19.5 |
| Notification ding | −17 |
| Pendulum and airy whooshes, shimmer riser | −18 to −21 |
| Blips (letters, typing) | −23.5 to −25 |
| Micro ticks (rolling counters, subline letters) | −33 to −39 |
| Bed parts (before `BED_DB` = −12.5): pad / sub / plucks / shaker | −10 / −12.5 / −16.5 / −21 |

The rule behind the table: effect peaks sit 6–12 dB above the bed's short-term level at every transition. The first mix of the worked film had the bed 10–15 dB too loud, which would have buried every pop. Only the plot showed it.

## 8. Master and mux

`finish()`:
- reverb returns (a 0.55 s room and a 2.2 s hall, synthetic stereo IRs);
- a 24 Hz high-pass and the music fade;
- an end fade into the last frame;
- loudness iterated to −15 LUFS integrated, with a 4× oversampled look-ahead limiter at −1.25 dBTP;
- a 24-bit WAV and the cue sheet.

It prints the limiter's largest reduction. Keep it under about 3 dB; if it is higher, lower the loudest effects rather than squash them.

`render.mjs` muxes `assets/audio/soundtrack.wav` as AAC-LC 256 kb/s, 48 kHz stereo. The MP4 edit list compensates the AAC priming, so the decoded audio lines up with the WAV to the sample. `verify_render.py` measures the offset by cross-correlation, and it must be 0. After AAC, expect −15.2 LUFS and a true peak about 0.1 dB higher than the WAV's.

## 9. Verifying a mix you cannot hear

1. **`analyze_audio.py --master … --music … --sfx … --cues cues.txt`.** The plot shows the effects (red) against the bed (blue). Every cue should be a red peak clearly above blue. It also shows the spectrogram (pitched lines where tones ring, broadband stripes for swooshes) and the waveform, where left/right asymmetry confirms the panning.
2. **Sound board.** Render each generator alone, then plot its waveform and spectrogram. Check that first and last samples are 0 (no clicks), there is no unexplained energy above 12 kHz, and pitch glides go the intended way.
3. **Octave balance** (printed by `analyze_audio.py`). In the worked film, 63 Hz ≈ 1 kHz with a gentle fall-off above 2 kHz. A sub band far above 1 kHz means boom.
4. **Numbers:** integrated loudness, true peak, LRA, clipped samples (0), DC (about 0), L/R correlation (0.8–0.9 means stereo but mono-safe).
5. **Reproducibility:** delete `renders/work-audio`, run `npm run soundtrack`, compare hashes.

## 10. Pitfalls

| Symptom | Cause | Fix |
| --- | --- | --- |
| Effects inaudible on the plot | Bed too loud | `BED_DB` about −12.5; re-check the plot |
| Two kicks flamming on the big hit | A "soft kick" stacked on `impact` | Drop the extra kick and keep a deeper pump dip |
| Non-reproducible audio | `hash()` used for a seed | `zlib.crc32(tag.encode())` |
| A ping sounds sour | Untuned frequency | `midi(n)` on a chord tone |
| Long ringing lines across later scenes | Long tau on pure tones plus hall reverb | Shorten tau (glass 0.48 s) and lower the hall send |
| Cue sheet out of order | Lines appended after sorting | Add every cue through `cue()` / `sfx(cue=…)` |
| Whoosh starts with a click | Motion is at full speed at t0 | `attack` 0.006–0.02 s, and the `fade()` edges stay |
