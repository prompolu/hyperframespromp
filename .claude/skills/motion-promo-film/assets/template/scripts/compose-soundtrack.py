#!/usr/bin/env python3
"""Soundtrack for this film. The engine is soundlib.py (same folder); this file is the score: one block per
beat of the picture, written against the cue plan. Everything is synthesised and seeded (reproducible).

    python3 scripts/compose-soundtrack.py            → assets/audio/soundtrack.wav + cues.txt
    python3 scripts/compose-soundtrack.py --stems    → also renders/work-audio/{music,sfx}.wav
Needs numpy + scipy, Node + Playwright (motion export), FFmpeg (loudness).
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import soundlib as sl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BEAT = 60.0 / 125.0            # 125 BPM
BAR1 = 0.60                    # put a downbeat on the biggest picture moment (here: the tile pop)


def music():
    """Bed: sustained sub, soft pad, offbeat shaker, sidechain pump. Fmaj9 → Bbmaj9."""
    bars = [(0.60, 2.52, [57, 60, 64, 67], 41), (2.52, 4.00, [53, 57, 60, 62, 65], 34)]
    sl.bed('music', sl.pad([69, 72, 76, 79], 0.05, 0.62, attack=0.4, release=0.3, cutoff=5200, tag='intro'), 0.05, -13.0, hall=0.25)
    for i, (t0, t1, notes, _) in enumerate(bars):
        sl.bed('music', sl.pad(notes, t0, t1, attack=0.05 if i == 0 else 0.1, release=0.35, cutoff=2300, tag=f'pad{i}'), t0, -10.0, hall=0.18)
    t, k = BAR1, 0
    while t < 3.9:
        if k % 2:                                            # offbeat 8ths
            sl.bed('music', sl.shaker(f'sh{k}'), t, -22.0, pan=0.15)
        t += BEAT / 2
        k += 1
    sl.MIX.bus['music'] += sl.db(-12.5 + sl.BED_DB) * sl.sub_bass([(t0, t1, root) for t0, t1, _, root in bars], 0.60, 4.0)
    sl.pump([BAR1 + i * BEAT for i in range(8)], depth=0.3)


def effects(M):
    # 0.00–0.60 the mark rises: a swoosh on its expo.out speed + an airy riser into the pop
    v = M.speed(M['mark.y'])
    sl.sfx(sl.swoosh('rise', 0.0, 0.58, v, lo=500, hi=7500, air=0.5, attack=0.02, release=0.09), 0.0, -15.5, hall=0.2,
           cue='upward swoosh — mark rises')
    sl.sfx(sl.air_riser('riser', 0.55), 0.04, -21.0, hall=0.3, cue='airy riser')
    # 0.60 the tile pops: pop + soft thump + glass ping tuned to the chord (D7 over Fmaj9)
    sl.sfx(sl.kick('thump', f0=110, f1=50, tau=0.17), 0.595, -14.0, cue='soft bass thump')
    sl.sfx(sl.pop('tilepop', 1250, 360, tau=0.032), 0.60, -12.5, room=0.25, cue='pop — tile springs in')
    sl.sfx(sl.glass(sl.midi(98)), 0.608, -20.0, room=0.15, hall=0.25, cue='glass ping')
    # 1.00–1.40 glide: swoosh follows the icon's on-screen speed and position (camera included)
    ix, iy = M.screen(M['icon.x'], M['icon.y'])
    v = M.speed(ix, iy)
    sl.sfx(sl.swoosh('glide', 0.98, 1.45, v, ix, lo=180, hi=3500, air=0.25), 0.98, -16.0, cue='swoosh — icon glides',
           cue_t=M.peak(0.98, 1.45, v))
    # 1.25 title letters: blips on the F major pentatonic, panned with the letters (skip spaces)
    notes = [72, 74, 77, 79, 81, 84, 86, 84, 86, 89, 91, 93]
    letters = 'Votre marque'
    for i, ch in enumerate(letters):
        if ch != ' ':
            sl.sfx(sl.blip(f'title{i}', sl.midi(notes[i % len(notes)]), tau=0.04, bright=0.3, click=0.15),
                   1.25 + 0.035 * i + 0.02, -24.0, pan=-0.1 + 0.03 * i, room=0.2,
                   cue='blips — title letters' if i == 0 else None)
    # 2.20 card slides in from the right: swoosh panned right → centre, pop as it appears
    cx, cy = M.screen(M['card.x'], M['card.y'])
    v = M.speed(cx, cy)
    sl.sfx(sl.swoosh('card', 2.18, 2.7, v, cx, lo=300, hi=6500, air=0.45, attack=0.005), 2.18, -14.5,
           cue='swoosh — card slides in', cue_t=M.peak(2.18, 2.7, v))
    sl.sfx(sl.pop('cardpop', 900, 300, tau=0.03), 2.26, -18.0, pan=0.45, room=0.2, cue='pop — card lands')
    # 3.00 release: a soft bell chord as the camera eases back
    for i, m in enumerate([81, 84, 88]):
        sl.sfx(sl.bell(sl.midi(m), dur=1.0, bright=0.6, tau=0.5), 3.0 + 0.07 * i, -24.0, pan=-0.3 + 0.3 * i, hall=0.35,
               cue='bell chord — settle' if i == 0 else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--motion', default='renders/work-audio/motion.json')
    ap.add_argument('--no-export', action='store_true', help='reuse an existing motion export')
    ap.add_argument('--stems', action='store_true')
    ap.add_argument('--out', default='assets/audio/soundtrack.wav')
    args = ap.parse_args()
    motion = ROOT / args.motion
    if not (args.no_export and motion.exists()):
        subprocess.run(['node', str(ROOT / 'scripts/export-motion.mjs'), str(motion)], check=True, cwd=ROOT)
    M = sl.load_motion(motion)
    sl.configure(duration=M.duration)
    music()
    effects(M)
    sl.cue(3.2, 'music fades out (silence at the end)')
    sl.finish(ROOT / args.out, cues_path=ROOT / 'cues.txt', music_fade=(3.2, M.duration), end_fade=0.25,
              stems_dir=ROOT / 'renders/work-audio' if args.stems else None,
              cue_header=['# Soundtrack cue sheet (generated by scripts/compose-soundtrack.py). Original synthesis, no samples.',
                          '# Bed: 125 BPM, Fmaj9 → Bbmaj9, downbeat on the tile pop (0.60 s).'])


if __name__ == '__main__':
    main()
