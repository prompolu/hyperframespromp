# Proposed PROMPOLU film — 60 seconds

Design direction derived from the observed Tubik reference. **This is a proposed edit, not a newly rendered video.** Output remains 1080 × 1920, 30 FPS, French voiceover and music, real photography, and the actual PROMPOLU website palette. Existing video outputs remain available separately.

## Frame rules

- Dominant paper `#F1F0EC`; ink `#15171A`; sparse bronze `#8C6A45`; small bronze text `#765333`; rules `#D8D5CE`.
- Keep Anton hero typography and DM Sans body/subheads, locally available in the current project. Do not claim these are the reference's unidentified fonts.
- 108 px horizontal title margins; 192 px top/bottom title-safe area. Photos may bleed. Keep essential content out of the final 192 px at the bottom.
- Hero type roughly 112–152 px, editorial subheads 72–96 px, supporting copy 36–44 px, labels at least 28 px. Fit actual French line lengths before finalizing sizes.
- Square image crops, thin rules, natural photographic color. Let image shapes and typography supply the composition; avoid added decorative effects.

## Sequence

| Time | French on-screen message | Photography and layout | Motion derived from reference |
| --- | --- | --- | --- |
| 0–6 s | **L’ALUMINIUM.** / La précision au service de l’habitat. | Authentic black logo above a large title; three uneven-height architectural photo crops below | Hero photo frieze, then coordinated upward travel |
| 6–13 s | **Lumière. / Lignes. / Confort.** | Centered statement on ivory; one large interior photo enters at the lower edge | Line-by-line masked reveal; reading hold; incoming panel |
| 13–22 s | **Entre l’extérieur / et l’intérieur.** | Offset exterior photo upper-right and interior photo lower-left; concise copy between | Asymmetric spread, staggered captions, smooth panel push |
| 22–34 s | **Rupture de / pont thermique.** / Une liaison isolante en polyamide. | Prefer a genuine documented thermal-break product close-up. Otherwise use an interior photograph with a separate explanatory text panel, making no visual identification of internal parts | Fixed technical label; image/text pair advances vertically in a clipped stack |
| 34–44 s | **Séparer les sections. / Limiter la conduction.** | Photograph plus short conceptual statements; no numeric performance claims or fabricated profile labels | Shift between two photo/text arrangements with the title anchored |
| 44–53 s | **Des lignes maîtrisées. / Une matière durable.** | Two tall architectural crops with open ivory space; short copy rather than awards or client logos | Horizontal photo-row travel and fixed heading |
| 53–60 s | **PROMPOLU** / Parlons de votre projet. / prompolu.com | Authentic logo, one final exterior crop, bronze rule, ivory end frame | Restrained upward reveal; minimum three-second readable closing hold |

## Draft voiceover

Approximately 116 words. Final read must be timed to the composition; leave pauses between ideas and a clean closing hold. This text is a new draft, not extracted audio: the reference is silent.

> L’aluminium donne une ligne à l’architecture. Des ouvertures précises, des espaces baignés de lumière, une matière au service de l’habitat.
>
> Entre l’extérieur et l’intérieur, chaque détail compte. L’aluminium conduit la chaleur. Pour limiter cette transmission à travers les profilés, la rupture de pont thermique sépare les parties métalliques par une liaison isolante en polyamide.
>
> Le principe est simple : interrompre la continuité du métal pour réduire la conduction. Le résultat dépend aussi du vitrage, de la conception de la menuiserie et de la qualité de la pose.
>
> Avec PROMPOLU, donnons à votre projet des lignes maîtrisées et une place pour la lumière. Parlons de vos envies, de vos contraintes et de votre habitat. Retrouvez-nous sur prompolu.com.

## Asset and render readiness

Existing credited architecture photos, local fonts, authentic logo, French narration workflow and original music are reusable from `videos/prompolu-thermal-break-60s/`. Source and validate a genuine product close-up before using one as technical evidence; otherwise use the explicitly described photo-plus-text treatment. Do not imply stock architecture is a PROMPOLU installation.

The cloud environment previously rendered a complete 60-second HyperFrames film successfully. This extraction itself does not validate a new composition. Next implementation should build an editable composition in a new version directory, preserve the previous film, run the pinned engine's checks, render a low-resolution MP4, inspect actual frames and sound, then render the final resolution. The original browser audio-processing limitation and baked music-stem workaround remain documented in the existing project.
