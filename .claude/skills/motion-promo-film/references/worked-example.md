# Worked example: PROMPOLU — Nos gammes

A 10 s, 1920×1080, 30 fps (300 frames) cut-free morph-chain website promo for an aluminium joinery distributor. All on-screen text is in French. The palette has three brand colours (INK #15171A, PAPER #F1F0EC, BRONZE #8C6A45) plus listed mixes, and nothing else. The source lives in the repository at `videos/prompolu-nos-gammes/`; if you have it, read its `index.html` and `scripts/compose-soundtrack.py` as the full reference implementation.

## Brief → build, beat by beat

| Time | Beat in the brief | How it was built |
| --- | --- | --- |
| 0.00–0.64 | P mark rises from y=1050, −35° → 0, expo.out; a giant PAPER-2 echo collapses into it | `#markWrap` y tween with a motion-blur tracker. The echo is a wrapper with CSS `blur(10px)` (constant apparent blur) around a scaled clone of the P |
| 0.64–1.15 | Squircle tile springs in (to 310 px, settles at 290); P overshoots to 240 then 160 px | `spring(0.115)` on the tile scale; P scale keyframes 0.8 → 1.5 → 1.0. `corner-shape: squircle` at 34 % |
| 1.15–2.48 | Background PAPER → GRAY-M → INK; icon glides to the column; page builds: logo letters settle, button pops, stats roll up, page scrolls 160 px | Two colour tweens on `#bg`. Camera 1.05 → 0.82 (top-centred focal) → 1.00. Inverse logo inline with `inv-` ids, `settleSvg` on L1–L8. Rolling digits are strips of numbers in clipped boxes. Kerned `split` + `settle` on the text. `#pageScroll` power3.out |
| 2.48–3.02 | Push to 1.35× on icon + button; share arrow detaches into a pointer that taps the button | Camera `T = −s(F − C)`, F=(860,330), which leaves the button above centre so the bar can later slide down. MotionPath for the pointer. The pointer and tick got a PAPER outline (bronze on bronze was invisible) |
| 3.02–3.68 | Button detaches, stretches into a 1100×165 pill at −4°; INK-2 wipes in, PAPER collapses into the go circle; URL types in; reload draws on | Swap button → `#pill` at identical coordinates. Width/height tweens, not scaleX. `#pillPaper` anchored right, shrinking to the 128.7 px circle, with `--soft` mask edge. Camera eases home meanwhile |
| 3.68–4.88 | Damped pendulum rocking; GRAY-L circle swings in and lands left of the pill; × rotates into + | Rotation and y keyframes with sine.inOut. The circle hangs from a 700 px arm pivoting at (395, −160): positive rotation = upper left |
| 4.88–5.25 | Circle → PROMPOLU squircle tile; go circle arcs into the BRONZE "3" badge; INK → blurred wallpaper; grid fades in radially | `--r/--k` superellipse morph. Badge swap at 4.88. The wallpaper is gradient-only (discs, crescent, rim). Tile delays proportional to distance |
| 5.25–6.07 | Grid flings up 780 px (power3.out), blur peaks "0 16", badge stays sticky | `#grid` tracker with max 16; the badge lives outside the grid |
| 6.07–6.44 | Haze: Pergola photo shrinks into a frosted tile; neighbours desaturate; milky bloom; badge → pill → first card | `backdrop-filter` (tile filter set to none first), screen-blend bloom, badge width/height morph, swap to `#card1` at 6.44 |
| 6.44–8.56 | Three range cards (Coulissants, Battants, Extérieur), letters settle, chips pop, cards tip back and stack | Stagger = window ÷ (letters − 1). Tip-back `rotationX −70°` about the bottom edge; the new card drops in 40 ms later so the tip is visible |
| 8.56–8.72 | Underlying cards fan down, camera tilts 4° and pans, flash to PAPER | Card and camera trackers (max 18); flash overlay; camera hidden and reset under the flash |
| 8.72–9.06 | P drops (2.4×), overshoots, springs back, slides into L1's exact position | `#dropP`: a clone of `#L1` in an SVG with the logo's own viewBox and box; transform-origin at L1's centre; lands at identity, then the real L1 is shown |
| 9.06–10.00 | Letters reveal, fill to INK, ALUMINIUM fades up, bronze sheen sweeps, logo drifts to optical centre, hold | Per-letter SVG blur filters removed at the end; sheen as a clipPath of `<use>` elements; hold push-in on the vignette only, so the logo ends at exactly 860 px |

## Choices worth copying

- **Contradictions resolved openly.** "Push-in 1.000 → 1.015 during the hold" against "final frame exactly 860 px": the vignette is pushed and the logo is not.
- **Brief numbers over stock eases.** The 310 px overshoot needed a custom spring instead of `elastic.out(1, 0.45)`.
- **No third-party marks.** A supplier watermark in one product photo was cropped by `object-position`.
- **Verified final frame.** The DOM state is clean at the last frame, and a pixel comparison with the SVG rendered as an `<img>` gives the same ink bounding box (531–1388 px).

## Problems found in review, and the fixes

| Found | Fix |
| --- | --- |
| Faint "U M" visible from t=0 | The sheen band was parked over the logo; it now starts past the edge and its SVG is hidden outside 9.45–9.71 s |
| Page unreadable during the 160 px scroll | Blur gain 0.3 → 0.18, cap 10 for the page |
| Tick and pointer invisible on the button | PAPER outline |
| Tip-back hidden behind the new card | New card's drop delayed 40 ms, with a 0.04 s fade |
| Pendulum circle entering from the right | Sign of the arm rotation |

## Soundtrack

- **Bed:** 125 BPM, Dm9 → Bbmaj9 → Fmaj9 → C6/9 → Fmaj9, with downbeats at 1.20, 3.12, 5.04 and 8.88 s.
  - Dm9 is the cut to the dark page, Bbmaj9 the button becoming the address bar, Fmaj9 the grid reveal.
  - The last Fmaj9 lands as the P slides into the logo.
  - The bed is muffled in the haze, high-passed and cut into the flash, blooms on the logo and fades from 9.10 s.
- **Effects:** about 50 cues:
  - motion-driven swooshes for every travel;
  - pops and bubbles for every appearance;
  - a deep hit at 1.20 s and a flash hit at 8.71 s;
  - a zip, a tap and a lock click;
  - blips for the logo letters, the URL and each range word, in the bar's harmony;
  - a ding for the badge, flicks for the card swaps, and a sheen shimmer panned right to left.
- **First mix:** the bed was 10–15 dB over the effects on the analysis plot. The fix was `BED_DB` −12.5 and raising the effects.
- **Final numbers:** −15.2 LUFS, −1.1 dBTP after AAC, limiter at most 1.9 dB, 0-sample AAC offset, byte-identical regeneration.
