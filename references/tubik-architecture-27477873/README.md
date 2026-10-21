# Architecture editorial reference → PROMPOLU

Analysis of Tubik's **About Page—Architecture & Interior Design Studio**, Dribbble shot 27477873. Inspected on 2026-10-21 from the exact publicly linked MP4, not inferred from the thumbnail. This is a reusable direction for a future PROMPOLU edit; no new film has been rendered as part of this analysis.

- [Original shot](https://dribbble.com/shots/27477873-About-Page-Architecture-Interior-Design-Studio)
- [Watch the original reference MP4](https://cdn.dribbble.com/userupload/48088161/file/806a846af8b46d9b8ec4ad568798827d.mp4)
- [Annotated overview](evidence/overview.jpg)
- [Observed motion map](motion-map.json)
- [Reference observations and PROMPOLU tokens](design-tokens.json)
- [Proposed French 60-second storyboard](PROMPOLU-STORYBOARD.md)

## What makes this design work

The composition behaves like an architectural editorial spread: enormous, tightly spaced sans-serif headlines; small section indexes; generous open areas; and photographs aligned to a precise grid. Its restraint comes from hierarchy and crop choices. The images provide nearly all the color.

The source video is **3200 × 2400, 60 FPS, 26.517 seconds, H.264, with no audio stream**. A landscape website viewport sits inside a dark presentation matte. That black surround is part of the Dribbble presentation, not the website's main background. Do not carry it into a full-frame vertical PROMPOLU film.

## Style extraction

| Element | Observed in the reference | Application to PROMPOLU |
| --- | --- | --- |
| Color | Near-white pages, warm stone-gray panels, black type; natural photographic colors | Use the actual site palette: paper `#F1F0EC`, ink `#15171A`, bronze `#8C6A45`, rule `#D8D5CE` |
| Typography | Large grotesque sans, mostly regular/medium weight, tight tracking and line spacing; sentence case | Keep the site's Anton display and DM Sans text. Use DM Sans Semibold for the larger editorial subheads; Anton for short French hero statements |
| Hierarchy | One enormous hero phrase, then medium statements and tiny metadata | One French message per beat; enlarge labels for phone viewing |
| Layout | Alternating centered statements and asymmetric text/photo spreads; a stable alignment system | Recompose for 9:16 with offset stacked images and short captions; retain consistent title anchors |
| Photography | Rectangular architecture, interiors, portraits; mixed portrait/landscape crops | Use real architectural and product photography with verified sources; preserve natural colors |
| Surfaces | Flat fills, square photo corners, fine horizontal rules; almost no decorative depth | Square crops, visible 2 px rules at 1080 px width, no ornamental cards or shadows |
| Scale | The opening title nearly spans the viewport width; footer has a huge cropped wordmark | Let “L’ALUMINIUM” occupy most of the usable width; finish with the authentic PROMPOLU logo |
| Rhythm | Fast travel between sections, brief pauses to read, longer pinned sequences | Alternate movement and reading holds; synchronize holds to the French voiceover |

Decoded dominant flat pixels are approximately `#F3F3F3` on the opening page and `#DDDBD7` on stone panels, with `#111111` in the outer matte and `#282828` in part of the footer. These are compressed-video samples, **not recovered CSS tokens**. The reference font family and exact weights cannot be established from the MP4. The source HTML, font files, easing curves and original animation code were not available.

## Motion extraction

Times below are approximate source-video positions, generally within 0.5 seconds. The evidence sheets sample every 0.5 seconds; labels on the detailed sheets use **absolute clip time**. These observations describe visible results, not a claim about the original implementation.

| Source time | Observed motion | Reusable technique |
| --- | --- | --- |
| 0–1.5 s | Oversized “The Studio” above an uneven-height strip of photos; the hero title contracts as the composition moves upward to reveal the next section | Large type plus a bottom-aligned photo frieze; one coherent vertical push |
| 1.5–4.3 s | A centered three-line statement enters and settles in open white space | Short typographic statement; travel followed by a reading hold |
| 4.3–6.5 s | A stone panel arrives from below; paragraph upper-left, large exterior photo upper-right, smaller interior crop lower-left; text becomes fully visible in stages | Panel push with staggered text visibility and asymmetric photo anchors |
| 6.5–12.6 s | The “Meet the founders” label remains anchored while four portraits, names and roles cycle vertically; neighboring items peek above/below and are clipped during travel | Pinned section label with a masked vertical content stack; coordinated photo/title travel |
| 12.6–16.6 s | Centered heading above three tall image columns; a short text block occupies a gap that changes position as the image arrangement shifts | Fixed heading, sliding photo row, changing whitespace; relative motion within a stable section |
| 16.6–19.5 s | Warm-gray awards panel rises; oversized multiline heading resolves, a horizontal divider leads into two aligned lists; a cursor moves across entries | Section push, staged line reveal and rule; preserve the grid while content changes |
| 19.5–22.2 s | A collaborators spread combines a small left image/text group and a larger right-hand list, then scrolls onward | Offset photo plus large, vertically arranged keywords |
| 22.2–24.6 s | Testimonial section moves into place: heading left, portrait/quote panel right, small navigation circles below | Offset heading with one restrained evidence panel; use only real attributed evidence |
| 24.6–25.2 s | Dark footer exposes a giant cropped “auren” wordmark | Typographic end frame with intentional edge cropping |
| 25.2–26.517 s | Pale reset frame and clipped opening elements restore the initial hero | Designed loop return; optional for a promotional film |

Detailed evidence: [opening](evidence/opening.jpg), [team stack](evidence/team.jpg), [image row and lists](evidence/middle.jpg), [ending](evidence/ending.jpg).

## Motion settings to use in our version

These are **proposed HyperFrames settings**, not extracted original values:

- Text reveal: 0.55–0.8 s, vertical travel 32–64 px inside an overflow-hidden line mask, `power3.out`, 0.08–0.12 s stagger.
- Panel travel: 0.85–1.1 s, `power2.inOut`; move the outgoing and incoming content together to suggest continuous scroll.
- Image/title stack: 0.75–0.95 s travel, then at least 1.6 s to read; move the image and its caption as one group.
- Photo-row shift: 1.0–1.3 s, `power2.inOut`, with the section title fixed. In vertical format use two visible crops and an edge preview rather than three unreadable desktop columns.
- Final brand hold: at least 3 s. A clean close is preferable to forcing the source's loop into a narrated 60-second film.

For HyperFrames, emulate scrolling with deterministic `x`/`y` transforms on a single paused timeline. Do not depend on live browser scrolling, wheel events or ScrollTrigger. Use inner clipping wrappers and fixed geometry; keep the engine in charge of clip lifecycles. Run `hyperframes lint`, `check`, seek samples, and a 540 × 960 MP4 before the 1080 × 1920 final render. Use the existing project's pinned engine and working audio workflow.

## Adaptation constraints

The site's ivory canvas remains dominant. Bronze is an accent, not a brown wash over photographs. Keep French accents, authentic PROMPOLU branding, French voiceover and music. Preserve the real-photo requirement: no drawn cross-section, synthetic building, or invented manufacturer geometry.

The current licensed photo set can support atmosphere and architecture. A close-up that identifies aluminium sections or a polyamide thermal break needs a genuine, documented product photograph; the existing room photos do not demonstrate that internal detail. Until such a photo is sourced, explain that mechanism with French typography alongside architectural photography, without arrows that pretend to identify an unseen component.

The reference's portraits, names, awards, client list and testimonial are content of the reference presentation. They are not evidence about PROMPOLU and must not be transferred. Its imagery and wordmark are not production assets for our video. Evidence thumbnails here are attributed study excerpts; no third-party source MP4 or source assets have been added to the production photo library.

## Inspection and reproduction

The direct shot page served a verification challenge. The accessible public [Tubik portfolio, page 3](https://dribbble.com/Tubik?page=3) contained the exact `screenshot-27477873` card with the original `data-animated-url` above. Ordinary HTTPS downloads with certificate verification succeeded; no browser security settings were changed.

`source.json` records the URL, file hash and FFprobe metadata. To reproduce evidence with FFmpeg and Pillow:

```sh
curl -fL 'https://cdn.dribbble.com/userupload/48088161/file/806a846af8b46d9b8ec4ad568798827d.mp4' -o /tmp/tubik-27477873.mp4
python references/tubik-architecture-27477873/extract-evidence.py /tmp/tubik-27477873.mp4
```

Analysis informed by the installed [HyperFrames Creative skill](../../.agents/skills/hyperframes-creative/SKILL.md) and [HyperFrames Animation skill](../../.agents/skills/hyperframes-animation/SKILL.md). Existing production files and website are unchanged.
