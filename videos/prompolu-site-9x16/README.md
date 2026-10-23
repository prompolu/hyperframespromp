# PROMPOLU — « La qualité, notre meilleur profil. » (vidéo 9:16 pour prompolu.com)

A vertical video for the website, in the style of the motion reel. It uses puffy bronze materials, moves from the dark studio to the cream paper world and has fine grain. It tells the site's own story:

1. The slogan.
2. The four ranges.
3. Why PROMPOLU.
4. Fès & Sefrou.
5. The logo.

- **Files:**
  - [out.mp4](out.mp4): master, 1080 × 1920, 60 fps, 15 s (900 frames), H.264 CRF 16, AAC 192 kb/s.
  - [out-web.mp4](out-web.mp4): lighter encode of the same frames for the website, CRF 24, AAC 128 kb/s, `+faststart`.
  - [poster.jpg](poster.jpg): the last frame, for the `poster` attribute.
- **Source:** `index.html` is one deterministic page with a paused GSAP timeline and `window.seek(t)`.
- **Assets:** `assets/` holds the site's own `logo-prompolu.png`, `logo-strugal.png` and range photos, taken from prompolu.com.
- **Scripts:** `render.mjs` renders the frames and `sfx.mjs` builds the soundtrack. `cues.txt` and `evidence/` hold the cue list and the checks.

## Put it on the website

```html
<video class="prompolu-film" src="/assets/video/prompolu-9x16.mp4" poster="/assets/video/prompolu-9x16-poster.jpg"
       autoplay muted loop playsinline preload="metadata" width="1080" height="1920"
       aria-label="PROMPOLU ALUMINIUM — La qualité, notre meilleur profil."></video>
<style>
  .prompolu-film { display: block; width: 100%; max-width: 420px; height: auto; aspect-ratio: 9 / 16; border-radius: 24px; background: #F1F0EC; }
</style>
```

- Copy `out-web.mp4` to `/assets/video/prompolu-9x16.mp4` and `poster.jpg` to `/assets/video/prompolu-9x16-poster.jpg`.
- Browsers only autoplay video that is `muted`. To offer the sound, add a small button that sets `video.muted = false`.

## Storyboard (seconds)

| Time | Beat |
| --- | --- |
| 0.00–2.10 | **Dark studio.** "La qualité," and "notre meilleur" blur in word by word. **PROFIL.** tumbles in letter by letter in puffy aluminium type (Archivo wide 800, bronze rim). Then a flip ripple with onion-skin outlines, and the letters spring upright. |
| 2.10–2.95 | **The camera punches into the O, which turns bronze.** It becomes an aluminium profile section, then grows into the bronze window frame. The first photo appears through it and the cream paper world opens. |
| 2.95–8.90 | **"À chaque projet, son profil." · 01–04.** Each change is animated like the product itself: <br>– **Coulissants** (S70P → S140RP Infinity): the pane slides away on its track. <br>– **Battants** (S53RP+ · S46 · portes ALUDOORS): the sash swings on its hinge. <br>– **Agencement** (cuisines & dressings): pulled out like a drawer. <br>– **Extérieur** (pergolas · garde-corps · bardage): the pergola louvres close, slat by slat. |
| 9.00–11.40 | **The page scrolls to "Pourquoi PROMPOLU".** An odometer lands on **+18**, followed by "ans d'expérience". Then "Distributeur officiel" with the STRUGAL logo, and **EN 12207 · EN 12208 · EN 12210** typing on. |
| 11.40–12.85 | **The page scrolls to "Fès & Sefrou".** Two bronze pins drop on Fès (magasin historique) and Sefrou (showroom STRUGAL), the route draws between them, then "Livraison partout au Maroc." |
| 13.00–15.00 | **The PROMPOLU ALUMINIUM logo is revealed** letter window by letter window, with **prompolu.com** underneath. The edges close to ink around a clean cream centre. |

## Sound (`sfx.mjs`, procedural, no samples)

**Groove**
- 89 BPM. Bar 1 lands on the bronze O (2.22 s) and the logo on bar 5 (12.99 s).
- Chords: Fmaj9 → Dm9 → Bbmaj9 → Gm9 → C9sus4 → Fmaj9. The music is low-passed under the logo and silent by 14.7 s.

**Effects**
- Every transition has its own sound, shaped by the on-screen motion:
  - the sliding pane rolls on its track and ends with a clack;
  - a latch clicks before the swing;
  - the drawer runs on its runners;
  - one tick per closing louvre;
  - scroll whooshes, one odometer tick per digit, a clunk on the bronze 8, and the pin drops.
- `cues.txt` lists every cue.

**Master**
- −15 LUFS integrated, true peak ≤ −1 dBTP.
- Rendered from the same timeline, so it is in sync by construction.

## Rebuild

```sh
npm install
node sfx.mjs                 # sfx.wav + cues.txt (samples window.motionAt at 500 Hz)
node render.mjs              # out.mp4 + out-web.mp4 + poster.jpg (4 sub-frames per frame, tmix motion blur)
node render.mjs --stills 3.4,9.6,15   # review stills → stills/
npm run preview              # http://127.0.0.1:4173/?play
```

## Choices

**Photos**
- The four range photos are the site's own visuals: `window-original`, `battants`, `agencement` and `bardage-villa` from prompolu.com/assets. They are shown untouched inside the frame, with a slow push-in.

**Logo**
- The supplied `logo-prompolu.png` (the same file the site uses) is shown untouched at exactly 1.5× (903 × 124.5) so it fits the 1080 px width. It has no effects, and the grain is kept out of its box.

**STRUGAL**
- `logo-strugal.png` has an opaque white background, so it sits on a white rounded badge rather than directly on the cream.

**Texts**
- All texts come from prompolu.com, and the range specs are shortened from the range descriptions.

**Style**
- The style follows the motion reel brief:
  - Inter, Archivo (wdth 125) and JetBrains Mono, from Google Fonts;
  - the PROMPOLU palette only;
  - the shared puffy material on heavy type, the frame, the pins and the digits;
  - per-frame feTurbulence grain;
  - motion blur from 4 averaged sub-frames, plus velocity blur on the fast moves.
