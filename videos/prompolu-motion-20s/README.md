# PROMPOLU — film motion 20 s (FR)

A 20-second French promotional motion film for PROMPOLU, a supplier of aluminium profiles and systems. It is built as an editable HyperFrames composition: one HTML file, one master GSAP timeline, real DM Sans text layers, and the original logo asset. The soundtrack is original and synthesised.

- **Video:** `renders/PROMPOLU_Motion_20s_FR.mp4`
- **Final frame:** `renders/PROMPOLU_Motion_20s_FR_final-frame.png`
- **Asset and music sources:** [`assets/sources.json`](assets/sources.json) and the summary below

## Storyboard (as built)

| Time | Beat | Mechanism |
| --- | --- | --- |
| 00.00–02.00 | "Le bon profil pour chaque projet." | Kerned character cascade on shallow curved paths with a bronze echo trail; bronze accent dot appears after the full stop and travels to the centre while the words exit left with a short horizontal blur |
| 02.00–03.50 | Brand reveal | The dot expands into a bronze field. An off-white 1400 × 330 panel (94 → 100 %) carries the original logo at 1100 px; "Profilés & systèmes aluminium" sits beneath |
| 03.25–04.10 | Sphere wipe | An off-white sphere appears at the left, then travels to the centre and grows past the frame edges |
| 04.10–06.60 | Product families | Small logo, then four cards with caption bands (Coulissants / Fenêtres & portes / Agencement / Extérieur): 90 ms stagger, 50 px rise, 0.96 → 1 |
| 06.60–08.30 | Selection | Editorial category rail with a bronze highlight on "Coulissants"; the selected card moves forward with a 2 px bronze border; "Explorez nos solutions." |
| 08.30–10.40 | Masonry | Category cards morph into the tops of four 310 px columns. Scroll: 0.35 s acceleration, 0.45 s fast, 0.50 s deceleration, with vertical blur only near peak speed. The sliding-window card detaches |
| 10.40–13.10 | Hero | The selected card travels to 1100 × 680 at (860, 520), from −6° Z / 8° Y to frontal by 11.00. "Systèmes coulissants" and three information chips appear |
| 13.10–15.50 | Visualisation | The hero frame expands into a presentation panel. Its moving edge wipes across the photo to reveal the 3D teaser; "Visualisation 3D", "Visualisez votre projet." |
| 15.50–17.00 | Call to action | The panel contracts into a bronze capsule (560 × 120, radius 60) reading "Demander un devis", with a vector arrow and a bronze glow |
| 16.70–20.00 | Final frame | The capsule's bronze expands past the frame. An off-white circle follows from the centre and reveals the logo, slogan, "Fès • Sefrou" and prompolu.com. Everything settles by 17.80 and holds unchanged to 20.00 |

## Editing

All timings, coordinates and image choices are in the `CFG`, `IMG`, `CATEGORIES` and `COLUMNS` blocks at the top of the script in `index.html`. Text strings live in the HTML.

```sh
npm run check      # HyperFrames lint + runtime + layout + contrast gate
npm run snapshot -- --at 7.8,12.8,19.9
npm run audio      # recompose and remaster the soundtrack (numpy + scipy + ffmpeg)
npm run render     # 1920x1080, 30 fps, H.264 + AAC -> renders/PROMPOLU_Motion_20s_FR.mp4
```

`scripts/hyperframes.sh` pins `hyperframes@0.8.186` and uses the preinstalled Chromium when one is present.

The composition is deliberately a single file with one GSAP timeline. Lint warns that it could be split into sub-compositions, but the hero card, panel and capsule are one continuous object across beats, and a split would fragment that timeline.

## Brand rules applied

- The logo is the unmodified `https://prompolu.com/assets/logo-prompolu.png`. It is never redrawn, cropped, filtered, given a shadow or recoloured. It is animated only by translation, uniform scale and opacity, and always sits on an off-white surface.
- The source logo is 602 × 83 px. At the requested ~1100 px width it is upscaled about 1.83×, which reads cleanly but slightly soft. No vector or larger version is published on the site; supplying an SVG would make the brand frames sharper.
- Colours: charcoal #15171A, off-white #F1F0EC and bronze #8C6A45, with the supporting shades used only for light, shadow and depth.
- Website images are shown as illustrations. No model numbers, specifications, prices, performance figures, claims of a configurator or AR interaction, or claims of submitted quotations appear on screen.

## Sources

| Asset | Source | Use |
| --- | --- | --- |
| Logo | prompolu.com/assets/logo-prompolu.png | Brand panel, gallery header, final frame |
| Sliding bay photo | prompolu.com/assets/window-original.webp | "Coulissants" card, masonry, hero |
| Opening window, interior fit-out, villa | battants.webp, agencement.webp, products/bardage-villa.webp | Category cards, masonry |
| 3D teaser (pergola) | visualisation-3d-teaser.jpg | Visualisation panel |
| Other product images | coulissant/battant/garde-corps teasers; products/pergola, garde-corps, volets-roulants, porte-a400k, dressing-profil | Masonry |
| Profile cutouts | products/cutouts/s110p, s125rp, s140rp, s70p, s86rp, s88r, s88rp, s90rp, s53rp-plus | Masonry (contain fit, no labels) |
| Fonts | prompolu.com/assets/font-1.woff2 (DM Sans 400) and font-2.woff2 (500) | All new text; SIL OFL 1.1 |
| Music and sound effects | Original — `scripts/compose-soundtrack.py` | Soundtrack (no samples or third-party audio) |

The following were deliberately not used: og-image.jpg (baked-in text), porte-a200-4fh2.jpg and accessoires-cuisine-starax.jpg (visible third-party marks), and cuisine-profil-ouvrant.jpg (excluded at the client's request). Full URLs, page origins, alt texts and checksums are in `assets/sources.json`.

## Soundtrack

The score is 120 BPM in F major (Fmaj9 – Dm9 – B♭maj9 – C6/9). It combines a warm sine bass with octave off-beats, a soft four-on-the-floor kick, quiet hats, claps and shaker, FM plucks with a ping-pong echo, a detuned pad and a light reverb. No vocals.

Sound effects are placed on the film's cue times:

| Time | Effect |
| --- | --- |
| 00.10–00.90 | Letter flutters |
| 01.65 | Dot tick |
| 02.00 | Bronze whoosh |
| 03.50 | Sphere sweep |
| 04.10–05.20 | Card arrivals |
| 06.60 | Navigation tick |
| 08.30–10.10 | Air movement, filtered by scroll speed, with a filter dip on the groove |
| 10.40 | Low selection impact |
| 13.10 | Frame-expansion sweep |
| 15.50 | Capsule formation |
| 17.00 | Final whoosh |
| 17.80 | Fmaj9 resolution |

A cosine fade reaches exact silence at 20.000 s. Stems are in `assets/audio/stems/`.

## Validation (measured on the delivered file)

`scripts/verify-render.py` decodes the MP4 and writes `evidence/render-verification.json`:

- **Video:** H.264 High, yuv420p, 1920 × 1080, 30/1 fps, **600 frames decoded**, 20.000 s.
- **Audio:** AAC stereo at 48 kHz, 20.000 s, **−16.1 LUFS integrated** and **−2.2 dBTP true peak** (EBU R128 meter on the MP4 itself).
- **Blank or black frames:** none in 600.
- **Final hold:** from 17.8 s to 20.0 s the maximum pixel change is 1/255 (encoder noise), so the brand frame is stable.
- **HyperFrames gate:** `check` returned 0 errors and 0 runtime warnings, and 44/44 contrast samples passed (`evidence/check-final.json`). The one layout warning is the deliberate overlap of the bronze trail echoes during the 0.5 s letter cascade.
- **Visual inspection:** frames from every beat were reviewed (`evidence/contact-sheet.jpg`, `evidence/frames/`). The logo is never distorted, and products stay fully recognisable.

The render took 1 min 41 s on this cloud machine. It used the software-GL screenshot capture path, because BeginFrame is unavailable with the preinstalled Chromium. Output is identical, only slower.
