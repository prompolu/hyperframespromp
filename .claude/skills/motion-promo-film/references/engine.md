# Authoring the film page

How the runtime in `assets/template/index.html` works, and how to build scenes on it without hitting the bugs we already paid for.

## Contents
1. Page contract
2. Layers and coordinates
3. The camera
4. Building the timeline
5. Morph-chain handoffs
6. Velocity motion blur
7. Typography
8. Brand logos (inline SVG)
9. Shapes and materials
10. Images, fonts and fallbacks
11. Pitfalls: symptom → cause → fix

## 1. Page contract

| Global | Meaning |
| --- | --- |
| `window.seek(t)` | Render time t (seconds) synchronously, motion blur included. Same t → same pixels, whatever came before. |
| `window.__ready` | Promise: fonts loaded, every `<img>` decoded (or replaced by a fallback tile), timeline built. |
| `__duration`, `__fps`, `__width`, `__height` | Read by `render.mjs` (frame count = duration × fps; viewport = stage size). |
| `__timeline` | The paused GSAP timeline (used by `export-motion.mjs`). |
| `__motionChannels` | `[[name, selector, property], …]`: what the soundtrack follows. `property` is a GSAP property, or `cx` / `cy` for the element's on-screen centre in stage pixels, with every parent transform included. |

Query modes: `?render` (renderer: no preview loop), `?t=4.2` (freeze for inspection), none (looping preview scaled to the window). Fonts need http, because browsers block `@font-face` from `file://`. Preview with `npm run preview`.

The renderer: `page.evaluate(t => window.seek(t), f / fps)`, PNG screenshot, FFmpeg `image2pipe` → `libx264 -crf 16 -preset slow`, `scale=out_color_matrix=bt709:out_range=tv,format=yuv420p` plus BT.709 tags. Without the matrix, FFmpeg converts with BT.601 and brand colours shift.

## 2. Layers and coordinates

```
#stage (W×H, overflow hidden)
  #fx svg (filters defs: motion blur, letter blur) — width/height 0, never display:none
  backgrounds (solid colour, wallpaper, gradients) — outside the camera so zooms never reveal edges
  #camera (.layer, transform-origin W/2 H/2) — every scene lives here
  overlays: bloom (mix-blend-mode: screen), flash, vignette — outside the camera
  end scene (exact final logo) — outside the camera so nothing can scale it
```

- `.pc` elements are positioned by their centre: `gsap.set('.pc', {xPercent:-50, yPercent:-50})`, then `x/y` are the centre in the parent's space. Brief coordinates ("icon box x 520–750, y 250–480") translate directly to `x: 635, y: 365`.
- A scene that scrolls (a page, a grid) is a container you translate (`#pageScroll`, `#grid`). Anything that scrolls with it lives inside it.
- Give containers that carry filters a real box covering their content. An SVG filter's region on an HTML element is computed from its border box, and content outside the region is clipped.

## 3. The camera

`#camera` animates `x, y, scale, rotation` about the stage centre C. A point p lands at `C + T + s·(p − C)`.

- **Centre a focal point F on screen at scale s:** `T = −s·(F − C)`.
- **Zoom while F stays put:** `T = (1 − s)·(F − C)`, the "page small, top-centred" look when F is near the top.
- **Avoid hitches:** chain camera tweens so each starts where the last ended. A push that reverses direction makes a visible stop; use it only when the brief wants that beat.
- **Pull back before handing off to screen-space elements:** ease the camera home to identity while the old scene fades out. From then on, camera space equals screen space and later coordinates are exact.
- **Use the camera for the end only if the brief allows it.** A hold push-in on the camera makes the last frame larger than the logo file. Push the backdrop (vignette) instead.

## 4. Building the timeline

- Set every initial state with `gsap.set` in `build()` before adding tweens. Prefer `to` tweens; they record their start value when first rendered, in timeline order, so random-access seeks are deterministic.
- A late `fromTo` needs `immediateRender:false`, or it stamps its "from" state at time 0.
- Use one tween per property at a time: two overlapping tweens on the same property of the same element fight. Different transform components (rotation vs scale) are fine.
- Zero-duration `tl.set(…)` handles visibility swaps and reverts when seeking backwards. GSAP reverts to the value it recorded, so set explicit px sizes: a `set` from `100%` reverts to a computed px value.
- Set `transformOrigin` once at init. Changing it mid-film jumps unless the element is at identity at that moment.
- Ease vocabulary: entrances `expo.out`, pops `back.out(1.8–2)`, camera `sine.inOut`, scrolls `power3.out` (momentum: fastest at the start).
- When a brief gives an exact overshoot ("springs to 310 px, settles at 290"), use the template's `spring(overshoot)` instead of `elastic.out`. Stock `elastic.out(1, 0.45)` overshoots about 21 % of the move.
- End the timeline with `tl.set({}, {}, DUR)` so its duration is the film's.
- `gsap.config({force3D:false})`: 2D transforms re-rasterise every frame, so scaled text stays crisp.

## 5. Morph-chain handoffs

A morph chain is one form continuously becoming the next: a mark becomes a tile, which becomes a button, then an address bar, a badge, a card and finally a letter of the logo. Often it is really two elements swapped at an invisible moment.

1. Choose the swap time t. Make A and B identical then: same size, radius, colour, contents and position in the same coordinate space. Compute B's start from A's numbers. When A sits inside a scrolled container, subtract the scroll: B's y = A's page y + scroll y.
2. At t: `tl.set(A, {opacity:0}, t)` and `tl.set(B, {autoAlpha:1}, t)`, then B carries on.
3. Animate shape changes with `width/height` and a pill radius (`999px`), not `scaleX`, which stretches the rounded ends. Keep inner parts in explicit px and tween them in step.
4. Check two consecutive frames around t. Any jump shows immediately (see `review-checklist.md`).

Examples from the worked film: the button became the address bar at 3.02 s; the go-button circle became a badge at 4.88 s; the badge became the first card at 6.44 s. The dropping P is a clone of the logo's own `#L1` path in an SVG with the same viewBox and box as the logo. It lands at identity at 9.03 s, and the real `#L1` replaces it a frame later, so the final logo is the file itself.

## 6. Velocity motion blur

`mblur(el, {pos, windows, max, gain, scale, outer, rx, ry})`:

- `pos()` returns the element's x/y in its parent's space. `windows` lists the time ranges where it may blur. Outside them the filter is removed, which also stops teleports (sets) from producing a blur spike.
- Displacement over one frame × `gain` (0.18 ≈ 180° shutter) gives `stdDeviation "sx sy"` in screen px, capped at `max` (14 by default; 16 for a grid fling, 18 for a whip). It is then divided by the element's own scale and its ancestors' scale (`scale`, `outer`), because a filter runs in local coordinates.
- `rx/ry` are the filter region's margins as fractions of the box. Make them large enough for 3σ plus any overshoot, and small on huge containers (a 2000 px grid needs only about 0.05).
- One tracker per element. Never tween `filter` on a tracked element: the tracker overwrites it. Put the fade/blur on a wrapper layer instead.
- A filter on an ancestor makes it a backdrop root, which breaks `backdrop-filter` (frosted glass) inside it. That is one more reason trackers switch off when still.
- Blur beats that snap: rises, slides, scrolls, whips, drops, zooms. Leave reading moments sharp: text that has landed, slow drifts.
- Rotation-only motion (pendulums) blurs along the element's local x. Feed `pos()` the arc length (radius × angle).
- A whole-camera tracker blurs a zoom or whip of the entire scene. Use it for the fast camera moves only.

## 7. Typography

- `split(el)` measures each character with a DOM `Range` and rebuilds the line as absolutely placed spans, which preserves kerning. Inline-block spans would lose it. Call it before any transform touches the element or its ancestors, and after fonts load.
- `settle(chars, at, {final, from, stagger, dur, dy, dir, s0, wave})` is the letter "bronze-ink" settle. Each letter enters offset and small in an accent colour, then settles to its final colour with a slight wavy baseline. It uses three separate tweens so the back-ease overshoot never applies to colour; GSAP would otherwise push the colour past the target and off-palette.
- Typed text: `dir:-1, s0:1.2, from: paper` (drops from above at 120 %).
- A brief's 40 ms stagger cannot fit a 30-letter line into a 0.3 s window. Compute `stagger = window / (letters − 1)`, cap it at the brief's value, and note the change in the README.
- Every font in use: `@font-face` from `assets/fonts` plus an entry in `FONT_FACES`, which are awaited before measuring.

## 8. Brand logos (inline SVG)

- Inline the original SVG markup verbatim, never as an `<img>`, so that each letter path can animate. Keep the paths, kerning and `fill-rule` untouched. Add an `id` to the root `<svg>` and size it with CSS.
- A second copy in the same page (an inverse version on dark) must have its ids prefixed (`inv-L1`…). Duplicate ids break selectors and `<use>`.
- Letter paths animate in SVG user units: `k = rendered px / viewBox unit`. A 14 px rise is `y: 14 / k`. `transformOrigin: '50% 100%'` uses each path's bbox.
- Per-letter blur: one SVG filter per letter with `feGaussianBlur stdDeviation = px / k`, tweened with `{attr:{stdDeviation:0}}`. When done, `tl.set(paths, {filter:'none'})` so the last frame is unfiltered.
- Gloss or sheen: a second SVG with the same viewBox over the logo. Inside it, a `<clipPath clip-rule="evenodd">` of `<use href="#L1">`… elements, each with `clip-rule="evenodd"` too, otherwise letter counters fill in. In the clipped group, a gradient band with the skew baked into a path moves across. Hide that SVG (`autoAlpha`) outside its sweep window, or the band shows through the clip early.
- Final frame: compute the box from the brief. For 860 px wide centred at (960,540), height = 860 × vbH / vbW and top = 540 − h/2. Keep the logo outside the camera with every transform at identity on the last frame, and verify it with `compare_images.py` (`review-checklist.md`).
- Recolouring a logo for a label (PAPER on dark): clone its letter paths into a new SVG whose viewBox is cropped to the word, with the fill on the group.

## 9. Shapes and materials

- **Squircle / app-icon corners:** `border-radius: 34%; corner-shape: squircle` (Chromium 139+). This looks like an iOS 22.5 % continuous corner. Shadows and `overflow:hidden` follow the shape.
- **Circle → squircle morph:** `border-radius: var(--r); corner-shape: superellipse(var(--k))`, then tween `{'--r':'34%', '--k':2}` from `50% / 1`. GSAP tweens CSS variables.
- **Soft-edged wipe:** set `mask-image: linear-gradient(90deg, transparent 0, #000 var(--soft))` on the layer and tween `--soft` 0 → 40 px → 0.
- **Feathered disc (a "3 px soft edge"):** `radial-gradient(closest-side, colour calc(100% − 3px), transparent 100%)`.
- **Frosted glass:** `backdrop-filter: blur(12px)` plus a token at 35 % alpha. No filter or opacity below 1 may sit on any ancestor while it shows; set the tile's own filter to `none` first.
- **Extruded "chunky" card:** a face with a top-to-bottom gradient, plus an underside layer offset 14 px with an `inset 0 -3px 0` rim and the drop shadow. Tip-backs use `rotationX` with `perspective` on the parent, about `transformOrigin: 50% 100%`.
- **Phone wallpaper without filters:** large soft discs as radial gradients with about 80 px soft stops. A crescent is a disc masked by an offset radial gradient, and a rim light is a thin ring gradient masked to one region. This costs nothing per frame.

## 10. Images, fonts and fallbacks

- Download every image into `assets/`, mirroring the source paths. `loadAssets()` awaits `img.decode()` for each. A failed image becomes a `.fallback` tile showing its `data-name`.
- Look at every product photo before using it. Third-party watermarks such as "ALUDOORS" were cropped with `object-position`. Natural photo colours are allowed even with a strict palette.
- Cutouts (transparent PNGs) sit on light tiles with padding and `object-fit: contain`. Photos fill with `object-fit: cover`.

## 11. Pitfalls: symptom → cause → fix

| Symptom | Cause | Fix |
| --- | --- | --- |
| A faint copy of logo letters on screen from t=0 | Sheen band parked over the logo inside its clip | Start the band past the logo edge; hide the sheen SVG outside its window |
| Whole page unreadably smeared during a small scroll | Blur gain too high (360° shutter) | gain 0.18, lower `max` (10) for page scrolls |
| Pointer or tick invisible | BRONZE pointer on a BRONZE button | PAPER outline (`paint-order: stroke`) |
| Card tip-back never visible | New card appeared on top at the same instant | Start the drop-in 40 ms later with a 0.04 s fade |
| Pendulum circle came from the wrong side | Positive CSS rotation swings a hanging bob to the left | Start at +θ for upper-left |
| Element stuck at a wrong px size after seeking back | `set` reverted a `%` size to a recorded px value | Explicit px sizes throughout |
| Blur clipped at the element edges | Filter region too small for σ or overshoot | Raise `rx/ry`; give containers a real box |
| Frosted tile shows nothing | Ancestor filter or opacity made a backdrop root | Remove filters on ancestors while it shows |
| Colours slightly off in the MP4 | BT.601 conversion | `scale=out_color_matrix=bt709:out_range=tv` + BT.709 tags |
| Text loses kerning when animated | Inline-block letter spans | `split()` with Range measurement |
| Letter colour flashes off-palette | back.out applied to colour | Separate colour tween with a non-overshooting ease |
| Fonts differ between preview and render | `file://` blocked `@font-face` | Serve over http (`npm run preview`) |
| Last frame logo 1.5 % too big | Hold push-in applied to the camera | Push the backdrop only |
| Renderer or motion export hangs on the first seek | `page.evaluate(t => tl.seek(t))` returns the GSAP timeline, which Playwright tries to serialise | Return nothing or a number: `t => { tl.seek(t, false); return t; }` |
| Frames offset or cropped | Stage centred or scaled to fit the window | Put the stage at the top left at its exact pixel size in render mode |
