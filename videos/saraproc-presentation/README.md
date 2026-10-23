# SARAPROC MAROC — Présentation (16:9, French voiceover)

A premium presentation film for an international cleaning and hygiene meeting. It is Apple-keynote style in navy, blue, white and silver, with French on-screen text, a French voiceover and an original energetic corporate soundtrack.

It starts with SARAPROC and its history, then covers the sectors in the order of the brief:
- medical, with logo 1;
- industrial, with logo 2 (LAB);
- buildings and institutions, water treatment, industrial and livestock buildings, and professional kitchens;
- cosmetic raw materials and cosmetic bases;
- a second, light-themed water section;
- livestock feed supplements and plant nutrition;
- certifications.

It ends on the official SARAPROC MAROC logo and the web address.

## Files

| File | What it is |
|---|---|
| [out.mp4](out.mp4) | Master: 1920 × 1080, 30 fps, 3:48 (6,840 frames), H.264 CRF 16 with BT.709 tags, AAC 192 kb/s |
| [out-web.mp4](out-web.mp4) | Lighter encode of the same film (CRF 23, AAC 128 kb/s, `+faststart`) |
| [poster.jpg](poster.jpg) | The last frame |
| [STORYBOARD.md](STORYBOARD.md) · [evidence/storyboard.jpg](evidence/storyboard.jpg) | Storyboard: timing, logos, photos, voice and on-screen text |
| [evidence/contact-sheet.jpg](evidence/contact-sheet.jpg) | Frames from the final render |
| [evidence/soundtrack-analysis.png](evidence/soundtrack-analysis.png) · [cues.txt](cues.txt) | Loudness and spectrum of the soundtrack, plus the cue sheet |
| `index.html` | The film: one deterministic page with a paused GSAP timeline (`window.seek(t)`) |
| `score.json` | Bar map shared by the page and the music: 120 BPM, sections, stops, and when each voice line starts |
| `narration.json` · `voice.py` · `assets/voice/` | French narration (text, plus respellings for the voice), the generated lines (FLAC) and `voice.json`, which holds when each clause is spoken |
| `music.mjs` → `soundtrack.wav` | Music synthesis, voice processing, ducking, silences and mastering |
| `render.mjs` · `serve.mjs` | Playwright and FFmpeg renderer, and the local preview server |
| `assets/logos/` | `saraproc-medical.svg` and `saraproc-lab.svg` (the two supplied PDF pages, exported as exact vectors) and `saraproc-maroc.png` (the official logo from saraprocmaroc.com) |
| `assets/photos/` | Photos from saraprocmaroc.com; `SOURCES.json` lists the source URL and page of each one |

## How it is built

**Picture**
- `index.html` reads `score.json` and `assets/voice/voice.json`.
- Every section starts on a downbeat (one bar = 2 s).
- On-screen items appear on the 16th-note grid, just before the voice names them.
- Each frame averages 4 sub-frames, for motion blur.
- The renderer streams the PNGs straight into FFmpeg in 8 s chunks, so a re-run resumes where it stopped.

**Silences and the LAB card**
- Each section ends with a stop hit on beat 3 of its last bar.
- **0.71 s of silence** follows, measured on every one of the 13 stops.
- The LAB SARAPROC card fills that silence.
- The music comes back on the next downbeat.
- Between the medical and industrial sections, the card stays on screen and becomes the industrial sector's logo plate, then its corner badge.

**Music** (`music.mjs`)
- Original procedural synthesis, with no samples and no sound effects: kick, clap, hats, crash, pulsing bass, pads, a 16th-note pluck arpeggio with a dotted-eighth echo, and FM bells.
- The chords are Am–F–C–G, with variations per section. The last bar of each section goes to E, so the next section resolves back to A minor.
- The ending resolves on C major under the logo.

**Voice**
- French, generated locally with Kokoro v1.0 (`ff_siwis`, speed 0.94).
- Processing: high-pass, presence boost and a gentle compressor, with a touch of room reverb.

**Mix**
- The music ducks under the voice: bed −13 dB, drums −10 dB.
- In the speech band (300 Hz–4 kHz), the voice sits a median 22 dB above the music.
- Master: −15 LUFS integrated, true peak ≤ −1.3 dBTP.

## Logos

**Logo 1 (medical)** is PDF page 1.
- It appears on a white plate at the start of the medical section, then as the corner badge.

**Logo 2 (LAB)** is PDF page 2.
- It is the industrial sector's logo and the transition card between sections.

**Official logo** is `saraprocmaroc.com/images/logo.png`.
- It is the same eagle and arched-name artwork as the site header, without the badge background.
- It appears only at the end, at a uniform 1.4× scale.

**Handling**
- No logo is redrawn, recoloured, distorted or given effects. The two PDF logos are the original vectors.
- The blue logos sit on white or pearl backgrounds so they stay readable.

## Sources and accuracy

- All text comes from saraprocmaroc.com: the home page, À propos, the category pages and their subcategory pages, and Certifications.
- From your brief, not found on the site: the kitchen items *Fours* and *Trempage*, and the building items *Sanitaires* and *Écoles*.
- Certifications are text only (name and full name, as on the site), with the site's scope note: « Selon le périmètre couvert par chaque certification ».
- Some photos on the site (medical subcategories) carry the LAB badge in their corner. They are used as published.

## Rebuild

```sh
npm install
node music.mjs                       # soundtrack.wav + cues.txt (reads score.json and assets/voice)
node render.mjs                      # out.mp4 + out-web.mp4 + poster.jpg (resumable chunks in work/chunks)
node render.mjs --stills 3.3,63,227  # review stills → stills/
node serve.mjs                       # preview: http://127.0.0.1:4173/?play (click to start the sound)
```

**Regenerating the voice.** This needs `pip install kokoro-onnx soundfile` and the two model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) from the kokoro-onnx `model-files-v1.1` release. That export reports phoneme durations, which `voice.py` uses to time each clause.

```sh
python voice.py <model-dir> narration.json assets/voice 0.94
```
