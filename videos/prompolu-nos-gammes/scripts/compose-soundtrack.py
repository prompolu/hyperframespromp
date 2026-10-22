#!/usr/bin/env python3
"""Original soundtrack for "PROMPOLU — Nos gammes" (10.00 s, 48 kHz, stereo, 24-bit WAV).

Everything is synthesised here: no samples and no third-party audio.
  · A 125 BPM pop-house bed: sustained sub-bass, a soft chord pad and plucks, an offbeat shaker and a
    sidechain pump. Its bars land on the picture's big moments (1.20 s cut to the dark page, 3.12 s
    button → address bar, 5.04 s product grid, 8.88 s P slides into the logo).
  · Pops, swooshes, hits and blips on every transition.

The swooshes follow the film's own motion. scripts/export-motion.mjs samples the GSAP timeline at 500 Hz,
and each swoosh's level, brightness and stereo position track the speed and screen position of the
element that moves. Noise is seeded, so the output is reproducible.

    python3 scripts/compose-soundtrack.py             → assets/audio/soundtrack.wav (+ cues.txt)
    python3 scripts/compose-soundtrack.py --stems     → also renders/work-audio/{music,sfx}.wav

Needs numpy and scipy, Node + Playwright for the motion export, and FFmpeg for the loudness measurement.
"""
import argparse
import json
import re
import subprocess
import wave
import zlib
from pathlib import Path

import numpy as np
from scipy import signal

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
DUR = 10.0
N = int(round(SR * DUR))
BEAT = 60.0 / 125.0                       # 0.48 s
BAR1 = 1.20                               # bar lines at 1.20, 3.12, 5.04, 6.96, 8.88
TARGET_LUFS = -15.0
MUSIC_DB = -12.5                          # the bed sits well under the transition effects
CEILING_DBTP = -1.0


# ──────────────────────────── basics ────────────────────────────
def rng(tag):
    return np.random.default_rng(zlib.crc32(tag.encode()))


def ns(seconds):
    return int(round(seconds * SR))


def tvec(n):
    return np.arange(n) / SR


def db(v):
    return 10.0 ** (v / 20.0)


def midi(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def fade(x, a=0.002, b=0.006):
    x = np.array(x, dtype=float, copy=True)
    na, nb = min(ns(a), x.shape[-1]), min(ns(b), x.shape[-1])
    if na > 0:
        x[..., :na] *= np.sin(np.linspace(0, np.pi / 2, na)) ** 2
    if nb > 0:
        x[..., -nb:] *= np.cos(np.linspace(0, np.pi / 2, nb)) ** 2
    return x


def level(x, win=0.010):
    """Scale so the loudest 10 ms window has an RMS of 1 (mono or stereo)."""
    sq = x ** 2 if x.ndim == 1 else np.mean(x ** 2, axis=0)
    k = max(1, ns(win))
    r = np.sqrt(np.convolve(sq, np.ones(k) / k, mode='same'))
    return x / (r.max() + 1e-12)


def pan2(x, p):
    a = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.vstack([x * np.cos(a), x * np.sin(a)])


# ──────────────────────────── filters ────────────────────────────
def biquad(kind, f0, q=0.707, gain_db=0.0):
    """RBJ cookbook biquad."""
    f0 = float(np.clip(f0, 12.0, SR * 0.45))
    w0 = 2 * np.pi * f0 / SR
    cw, sw = np.cos(w0), np.sin(w0)
    al = sw / (2 * q)
    A = 10 ** (gain_db / 40)
    if kind == 'lp':
        b, a = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2], [1 + al, -2 * cw, 1 - al]
    elif kind == 'hp':
        b, a = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2], [1 + al, -2 * cw, 1 - al]
    elif kind == 'bp':
        b, a = [al, 0.0, -al], [1 + al, -2 * cw, 1 - al]
    elif kind == 'peak':
        b, a = [1 + al * A, -2 * cw, 1 - al * A], [1 + al / A, -2 * cw, 1 - al / A]
    elif kind == 'hs':
        s = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - s)]
        a = [(A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - s]
    else:
        raise ValueError(kind)
    return np.asarray(b) / a[0], np.asarray(a) / a[0]


def filt(x, kind, f0, q=0.707, gain_db=0.0):
    b, a = biquad(kind, f0, q, gain_db)
    return signal.lfilter(b, a, x, axis=-1)


def tvfilt(x, kind, f, q=0.707, block=32):
    """Mono biquad whose frequency follows the per-sample curve f (updated every `block` samples)."""
    f = np.broadcast_to(np.asarray(f, float), x.shape)
    y = np.empty_like(x)
    zi = np.zeros(2)
    for i in range(0, len(x), block):
        b, a = biquad(kind, f[min(i + block // 2, len(x) - 1)], q)
        y[i:i + block], zi = signal.lfilter(b, a, x[i:i + block], zi=zi)
    return y


# ──────────────────────────── sources ────────────────────────────
def white(n, tag):
    return rng(tag).standard_normal(n)


def pink(n, tag):
    x = signal.lfilter([0.049922035, -0.095993537, 0.050612699, -0.004408786],
                       [1.0, -2.494956002, 2.017265875, -0.522189400], white(n, tag))
    return x / (np.std(x) + 1e-12)


def phase_of(freq):
    return 2 * np.pi * np.cumsum(freq) / SR


def saw(freq, harmonics=24, tilt=1.0, phase0=0.0):
    """Band-limited sawtooth by additive synthesis (freq may sweep)."""
    freq = np.asarray(freq, float)
    ph = phase_of(freq) + phase0
    out = np.zeros_like(freq)
    for k in range(1, harmonics + 1):
        out += (k * freq < SR * 0.45) * np.sin(k * ph) / k ** tilt
    return out


def perc(n, attack, tau):
    t = tvec(n)
    a = np.sin(np.clip(t / max(attack, 1e-5), 0, 1) * np.pi / 2) ** 2
    return a * np.exp(-np.maximum(t - attack, 0) / tau)


def follower(e, attack, release):
    """One-pole envelope follower with separate attack and release times (seconds)."""
    ga, gr = np.exp(-1 / (attack * SR)), np.exp(-1 / (release * SR))
    y = np.empty_like(e)
    s = 0.0
    for i, v in enumerate(e):
        g = ga if v > s else gr
        s = g * s + (1 - g) * v
        y[i] = s
    return y


# ──────────────────────────── motion ────────────────────────────
class Motion:
    """The film's GSAP timeline sampled at 500 Hz by scripts/export-motion.mjs."""

    def __init__(self, path):
        m = json.loads(Path(path).read_text())
        self.rate = m['rate']
        self.c = {k: np.asarray(v, float) for k, v in m['channels'].items()}
        self.t = np.arange(len(self.c['grid.y'])) / self.rate

    def __getitem__(self, k):
        return self.c[k]

    def d(self, arr):
        return np.gradient(arr, 1 / self.rate)

    def speed(self, x, y=None):
        return np.abs(self.d(x)) if y is None else np.hypot(self.d(x), self.d(y))

    def screen(self, x, y):
        """Camera space → stage pixels (the camera's own rotation is ignored)."""
        s, cx, cy = self.c['camera.scale'], self.c['camera.x'], self.c['camera.y']
        return 960 + cx + s * (x - 960), 540 + cy + s * (y - 540)


M = None


def swoosh(tag, t0, t1, speed, xpos=None, *, lo=250.0, hi=5500.0, air=0.35, whistle=0.0, tone=None,
           tail=0.16, shape=0.9, attack=0.008, release=0.07, width=0.85, flutter=None):
    """Noise whoosh between t0 and t1 driven by a motion speed curve: level ∝ speed**shape,
    brightness sweeps lo→hi with speed, the pan follows the element's screen x."""
    n = ns(t1 - t0 + tail)
    ta = t0 + tvec(n)
    v = np.interp(ta, M.t, speed)
    v[ta > t1] = 0.0
    e = np.clip(follower(np.clip(v / (v.max() + 1e-9), 0, 1), attack, release), 0, 1)
    cut = lo * (hi / lo) ** e
    x = filt(tvfilt(pink(n, tag), 'lp', cut, 0.75), 'hp', 80)
    if air:
        x = x + air * e * tvfilt(white(n, tag + '/air'), 'bp', np.minimum(cut * 1.7, 15000), 0.9)
    if whistle:
        x = x + whistle * tvfilt(white(n, tag + '/whistle'), 'bp', np.minimum(cut * 0.8, 12000), 6.0)
    if flutter is not None:                 # items passing the eye: a soft ripple at their rate
        fr = np.interp(ta, M.t, flutter)
        x = x * (1 - 0.3 * (0.5 + 0.5 * np.sin(phase_of(fr))))
    if tone is not None:                    # pitched component (f_start, f_end, relative level)
        f = tone[0] * (tone[1] / tone[0]) ** np.linspace(0, 1, n)
        x = x + tone[2] * np.sin(phase_of(f))
    sig = fade(x * e ** shape, 0.004, 0.02)
    if xpos is None:
        return level(sig)
    p = np.clip((np.interp(ta, M.t, xpos) - 960) / 960 * width, -width, width)
    return level(pan2(sig, p))


# ──────────────────────────── instruments & effects ────────────────────────────
def pop(tag, f0=1100.0, f1=330.0, glide=0.026, tau=0.030, body=0.45, click=0.25, rise=False):
    """Mouth-pop (pitch falls) or bubble (rise=True, pitch climbs)."""
    n = ns(0.18)
    t = tvec(n)
    k = np.clip(t / glide, 0, 1)
    f = f0 * (f1 / f0) ** (k ** 0.55) if rise else f1 + (f0 - f1) * (1 - k) ** 2
    x = np.sin(phase_of(f)) * perc(n, 0.0008, tau)
    x += body * np.sin(phase_of(f * 0.5)) * perc(n, 0.001, tau * 1.6)
    x += click * filt(white(n, tag), 'hp', 3000) * np.exp(-t / 0.0012)
    return level(fade(x, 0.0003, 0.01))


def glass(f=2349.3, dur=1.3):
    t = tvec(ns(dur))
    parts = [(1.0, 1.0, 0.48), (2.32, 0.42, 0.25), (4.25, 0.20, 0.12), (6.63, 0.09, 0.07)]
    x = sum(a * np.sin(2 * np.pi * f * r * t + r) * np.exp(-t / tau) for r, a, tau in parts)
    return level(fade(x * np.clip(t / 0.0015, 0, 1)))


def bell(f, dur=1.4, bright=1.0, tau=0.7):
    t = tvec(ns(dur))
    parts = [(1.0, 1.0, 1.0), (2.0, 0.30 * bright, 0.5), (3.0, 0.10 * bright, 0.28), (4.16, 0.07 * bright, 0.16), (5.43, 0.04 * bright, 0.09)]
    x = sum(a * np.sin(2 * np.pi * f * r * t + r) * np.exp(-t / (tau * k)) for r, a, k in parts)
    x += 0.25 * np.sin(2 * np.pi * f * 1.0018 * t) * np.exp(-t / tau)      # slow shimmer beat
    return level(fade(x * np.clip(t / 0.002, 0, 1)))


def blip(tag, f, tau=0.035, bright=0.3, click=0.12, dur=0.14):
    """Soft marimba-like blip (letters settling, typing)."""
    n = ns(dur)
    t = tvec(n)
    x = np.sin(2 * np.pi * f * t) * perc(n, 0.0015, tau)
    x += bright * np.sin(2 * np.pi * 3.93 * f * t + 0.3) * perc(n, 0.001, tau * 0.35)
    x += click * filt(white(n, tag), 'hp', 4000) * np.exp(-t / 0.0008)
    return level(fade(x, 0.0003, 0.01))


def kick(tag, f0=140.0, f1=47.0, drop=0.045, tau=0.20, dur=0.6, click=0.12, drive=1.4):
    n = ns(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / drop)
    x = np.tanh(drive * np.sin(phase_of(f)) * perc(n, 0.0015, tau)) / np.tanh(drive)
    x += click * filt(white(n, tag), 'lp', 2500) * np.exp(-t / 0.002)
    return level(fade(x))


def impact(tag, bright=0.2, boom=0.55, dur=1.8):
    """Deep hit: kick + low noise boom + pitched thwump + a little crack."""
    n = ns(dur)
    t = tvec(n)
    k = kick(tag + '/k', f0=125, f1=38, drop=0.06, tau=0.42, dur=dur, click=0.18, drive=1.8)
    b = filt(filt(pink(n, tag + '/b'), 'lp', 150, 0.8), 'lp', 150, 0.8) * perc(n, 0.004, 0.55)
    w = np.sin(phase_of(68 + 110 * np.exp(-t / 0.03))) * perc(n, 0.001, 0.12)
    c = filt(white(n, tag + '/c'), 'hp', 2500) * np.exp(-t / 0.012)
    return level(fade(level(k) + boom * level(b) + 0.5 * level(w) + bright * level(c)))


def rev_swell(tag, dur, lo=250.0, hi=7000.0, power=2.6):
    """Backwards-reverb style swell that ends exactly where it is placed + dur."""
    n = ns(dur)
    u = np.arange(n) / n
    x = tvfilt(pink(n, tag), 'lp', lo * (hi / lo) ** u, 0.7) * u ** power
    return level(fade(x, 0.01, 0.003))


def air_riser(tag, dur, lo=600.0, hi=6500.0, notes=(81, 84, 88)):
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    x = tvfilt(white(n, tag), 'bp', lo * (hi / lo) ** u, 1.1) * (0.2 + 0.8 * u) * np.sin(np.pi / 2 * np.clip(u * 1.4, 0, 1)) ** 2
    shim = sum(np.sin(2 * np.pi * midi(m) * t + i) * (1 + 0.3 * np.sin(2 * np.pi * (6.5 + 1.7 * i) * t)) for i, m in enumerate(notes))
    return level(fade(x + 0.35 * shim * u ** 2, 0.03, 0.01))


def rubber_zip(tag, dur=0.17, f0=150.0, f1=640.0):
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    f = f0 * (f1 / f0) ** (u ** 0.75) * (1 + 0.04 * np.sin(2 * np.pi * 26 * t))
    s = saw(f, harmonics=18)
    x = tvfilt(s, 'bp', np.minimum(f * 3.2, 9000), 2.6) + 0.5 * tvfilt(s, 'lp', 600 + 2500 * u, 0.9)
    env = np.minimum(np.clip(t / 0.012, 0, 1), np.clip((dur - t) / 0.035, 0, 1))
    return level(fade(x * env))


def flick(tag):
    """Paper flick: two quick noise transients + a little flap."""
    n = ns(0.16)
    t = tvec(n)
    nz = filt(filt(white(n, tag), 'bp', 2600, 0.8), 'hp', 700)
    e = np.exp(-t / 0.010) + 0.55 * np.exp(-np.maximum(t - 0.016, 0) / 0.026) * (t > 0.016)
    flap = 0.35 * np.sin(2 * np.pi * 210 * t) * np.exp(-t / 0.018)
    return level(fade(nz * e + flap))


def click(tag, tone=2900.0, knock=170.0, latch=0.0):
    n = ns(0.14)
    t = tvec(n)
    x = filt(white(n, tag), 'bp', 4200, 1.2) * np.exp(-t / 0.0025)
    x += 0.6 * np.sin(2 * np.pi * tone * t) * np.exp(-t / 0.010)
    x += 0.8 * np.sin(2 * np.pi * knock * t) * perc(n, 0.0005, 0.022)
    if latch:
        i = ns(latch)
        x[i:] += 0.5 * filt(white(n - i, tag + '/latch'), 'bp', 5200, 1.4) * np.exp(-t[:n - i] / 0.0018)
    return level(fade(x, 0.0003, 0.01))


def thup(tag, f=120.0):
    n = ns(0.2)
    t = tvec(n)
    x = np.sin(phase_of(70 + (f - 70) * np.exp(-t / 0.02))) * perc(n, 0.001, 0.05)
    x += 0.4 * filt(pink(n, tag), 'lp', 600) * perc(n, 0.001, 0.025)
    return level(fade(x))


def whff(tag, dur=0.16):
    n = ns(dur)
    t = tvec(n)
    x = tvfilt(pink(n, tag), 'lp', 3500 * np.exp(-t / 0.05) + 300, 0.7) * perc(n, 0.006, 0.05)
    return level(fade(x))


def shaker(tag, decay=0.032):
    n = ns(0.12)
    x = filt(filt(white(n, tag), 'hp', 6000, 0.7), 'lp', 12500, 0.7) * perc(n, 0.003, decay)
    return level(fade(x))


def shimmer_riser(tag, dur, notes=(84, 88, 91, 93)):
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    x = sum(np.sin(2 * np.pi * midi(m) * t + i) * (1 + 0.35 * np.sin(2 * np.pi * (7.5 + 1.3 * i) * t + i)) for i, m in enumerate(notes))
    x = x * u ** 1.8
    x += 0.35 * tvfilt(white(n, tag), 'bp', 4000 + 6000 * u, 2.0) * u ** 2
    return level(fade(x, 0.02, 0.01))


def metal_shimmer(tag, dur=0.7, f=1180.0):
    n = ns(dur)
    t = tvec(n)
    ratios = [1.0, 1.58, 2.24, 2.83, 3.51, 4.71, 5.93]
    x = sum((0.8 ** i) * np.sin(2 * np.pi * f * r * t + i) * (1 + 0.4 * np.sin(2 * np.pi * (9 + 2.3 * i) * t)) for i, r in enumerate(ratios))
    env = np.clip(t / 0.06, 0, 1) ** 1.5 * np.exp(-np.maximum(t - 0.06, 0) / 0.22)
    sparkle = 0.25 * filt(white(n, tag), 'bp', 9000, 1.5) * env
    return level(fade(x * env + sparkle, 0.005, 0.02))


def pad(notes, t0, t1, *, attack=0.12, release=0.45, cutoff=2200.0, detune=7.0, tag='pad'):
    """Warm detuned-saw pad, three voices per note spread across the stereo field."""
    n = ns(t1 - t0 + release)
    t = tvec(n)
    out = np.zeros((2, n))
    for m in notes:
        for v, (cents, p) in enumerate([(-detune, -0.6), (0.0, 0.0), (detune, 0.6)]):
            f = midi(m) * 2 ** (cents / 1200)
            ph0 = rng(f'{tag}:{m}:{v}').uniform(0, 2 * np.pi)
            out += pan2(saw(np.full(n, f), harmonics=max(3, int(min(28, 4200 / f))), tilt=1.25, phase0=ph0), p)
    out = filt(filt(out, 'lp', cutoff, 0.6), 'lp', cutoff, 0.6)
    env = np.sin(np.clip(t / attack, 0, 1) * np.pi / 2) ** 2
    hold = t1 - t0
    env *= np.where(t <= hold, 1.0, np.cos(np.clip((t - hold) / release, 0, 1) * np.pi / 2) ** 2)
    return level(out * env)


def pluck(notes, tag, decay=0.11):
    n = ns(0.45)
    t = tvec(n)
    x = sum(saw(np.full(n, midi(m) * 2 ** (c / 1200)), harmonics=16, phase0=rng(f'{tag}{m}{c}').uniform(0, 6.28))
            for m in notes for c in (-5, 5))
    x = tvfilt(x, 'lp', 650 + 3600 * np.exp(-t / 0.07), 0.9) * perc(n, 0.003, decay)
    return level(fade(x))


def make_ir(rt60, predelay, bright, dark, tag):
    n = ns(rt60 * 1.1)
    t = tvec(n)
    chans = []
    for ch in range(2):
        nz = white(n, f'{tag}{ch}') * np.exp(-t / (rt60 / 6.91))
        w = np.clip(t / (rt60 * 0.6), 0, 1)
        ir = filt(nz, 'lp', bright, 0.6) * (1 - w) + filt(nz, 'lp', dark, 0.6) * w
        ir *= np.clip(t / 0.006, 0, 1)
        chans.append(np.concatenate([np.zeros(ns(predelay)), ir]))
    ir = np.vstack(chans)
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


def reverb(x, ir):
    return np.vstack([signal.fftconvolve(x[c], ir[c])[:N] for c in range(2)])


# ──────────────────────────── mixer ────────────────────────────
class Mixer:
    def __init__(self):
        self.bus = {k: np.zeros((2, N)) for k in ('music', 'coda', 'sfx', 'room', 'hall')}
        self.cues = []

    def add(self, bus, sig, t0, gain_db=0.0, pan=0.0, room=0.0, hall=0.0, cue=None, cue_t=None):
        if sig.ndim == 1:
            sig = pan2(sig, pan)
        i0, n = ns(t0), sig.shape[1]
        a, b = max(0, i0), min(N, i0 + n)
        if b > a:
            seg = db(gain_db) * sig[:, a - i0:b - i0]
            self.bus[bus][:, a:b] += seg
            if room:
                self.bus['room'][:, a:b] += room * seg
            if hall:
                self.bus['hall'][:, a:b] += hall * seg
        if cue:
            self.cues.append((t0 if cue_t is None else cue_t, cue))


MIX = Mixer()


def sfx(sig, t0, gain_db, pan=0.0, room=0.0, hall=0.0, cue=None, cue_t=None):
    MIX.add('sfx', sig, t0, gain_db, pan, room, hall, cue, cue_t)


def peak_time(t0, t1, speed):
    i0, i1 = int(t0 * M.rate), int(t1 * M.rate)
    return (np.argmax(speed[i0:i1]) + i0) / M.rate


# ──────────────────────────── the music ────────────────────────────
INTRO = [69, 72, 76, 79]                                     # airy Fmaj9 upper structure
BARS = [  # start, end, pad (MIDI), sub root, pluck voicing
    (1.20, 3.12, [50, 57, 60, 64, 65], 38, None),            # Dm9 — the dark page
    (3.12, 5.04, [53, 57, 60, 62, 65], 34, [69, 72, 74]),    # Bbmaj9 — address bar
    (5.04, 6.96, [57, 60, 64, 67], 41, [72, 76, 79]),        # Fmaj9 — wallpaper and grid
    (6.96, 8.68, [55, 57, 62, 64, 67], 36, [74, 76, 79]),    # C6/9 — the range cards
]
CODA = (8.88, [53, 57, 60, 64, 67, 72], 41)                  # Fmaj9 under the logo
KICKS = [(5.04, -6.0), (6.48, -6.0), (7.20, -7.0), (7.92, -7.0)]   # soft kicks on transitions (1.20 has the big hit)


def bed(bus, sig, t0, gain_db, **kw):
    MIX.add(bus, sig, t0, gain_db + MUSIC_DB, **kw)


def compose_music():
    bus = MIX.bus['music']
    # intro: airy pad that blooms under the rising P
    bed('music', pad(INTRO, 0.10, 1.22, attack=0.5, release=0.35, cutoff=5200, tag='intro'), 0.10, -13.0, hall=0.25)
    for i, (t0, t1, notes, root, pl) in enumerate(BARS):
        bed('music', pad(notes, t0, t1, attack=0.04 if i == 0 else 0.10, release=0.35, cutoff=2100 + 300 * i, tag=f'pad{i}'),
                t0, -10.0, hall=0.18)
        if pl:
            for j in range(4):
                tt = t0 + BEAT / 2 + j * BEAT
                if tt < t1 - 0.05:
                    bed('music', pluck(pl, f'pl{i}{j}'), tt, -16.5 + (1.5 if j % 2 else 0), pan=0.22 if j % 2 else -0.22, hall=0.22)
    # shaker on 16ths, accented offbeats, light swing; thinner in bar 1
    vel = [0.32, 0.55, 1.0, 0.55]
    t, k = BAR1, 0
    while t < 8.56:
        bar = int((t - BAR1) / (4 * BEAT))
        if not (bar == 0 and k % 4 != 2):
            bed('music', shaker(f'sh{k}', 0.028 + 0.012 * (k % 4 == 2)), t + (0.008 if k % 2 else 0.0),
                    -21.0 + 20 * np.log10(vel[k % 4]), pan=0.18 if k % 2 else -0.12)
        t += BEAT / 4
        k += 1
    # sustained sub-bass: one oscillator gliding between bar roots, saturated a little for small speakers
    f = np.zeros(N)
    for t0, t1, _, root, _ in BARS:
        f[ns(t0):ns(t1)] = midi(root)
    f[:ns(BARS[0][0])] = midi(BARS[0][3])
    f[ns(BARS[-1][1]):] = midi(BARS[-1][3])
    f = signal.lfilter([1 - np.exp(-1 / (0.03 * SR))], [1, -np.exp(-1 / (0.03 * SR))], f, zi=[f[0] * np.exp(-1 / (0.03 * SR))])[0]
    ph = phase_of(f)
    sub = np.tanh(1.3 * (np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph))) / np.tanh(1.3)
    tt = tvec(N)
    amp = np.clip((tt - 1.20) / 0.02, 0, 1) * np.clip((8.68 - tt) / 0.06, 0, 1)
    bed('music', pan2(level(sub) * amp, 0.0)[:, :N], 0.0, -12.5)

    # sidechain pump on every beat, deeper under the transition kicks
    g = np.ones(N)
    beats = [BAR1 + i * BEAT for i in range(16)]
    for b, depth in [(b, 0.32) for b in beats] + [(k, 0.5) for k, _ in KICKS] + [(1.20, 0.6), (8.88, 0.0)]:
        i0, i1 = ns(b), min(N, ns(b + BEAT))
        u = tt[i0:i1] - b
        g[i0:i1] = np.minimum(g[i0:i1], 1 - depth * (1 - np.exp(-u / 0.004)) * np.exp(-u / 0.11))
    bus *= g
    for t0, gdb in KICKS:
        sfx(kick(f'kick{t0}', f0=135, f1=48, tau=0.16), t0, -16.0 + gdb, cue='soft kick')

    # haze (6.07–6.44): the bed goes dreamy-muffled, then opens on the first card
    cut = np.full(N, 18000.0)
    for (a, b, c0, c1) in [(6.04, 6.30, 18000, 650), (6.30, 6.38, 650, 650), (6.38, 6.58, 650, 18000)]:
        i0, i1 = ns(a), ns(b)
        cut[i0:i1] = c0 * (c1 / c0) ** np.linspace(0, 1, i1 - i0)
    # whip (8.40–8.68): rising high-pass into the flash, then the bed is gone
    hp = np.full(N, 20.0)
    i0, i1 = ns(8.40), ns(8.66)
    hp[i0:i1] = 20 * (1400 / 20) ** np.linspace(0, 1, i1 - i0) ** 2
    hp[i1:] = 1400
    for c in range(2):
        bus[c] = tvfilt(tvfilt(bus[c], 'lp', cut, 0.7, block=64), 'hp', hp, 0.7, block=64)
    bus *= np.clip((8.68 - tt) / 0.05, 0, 1)

    # coda: Fmaj9 blooms as the P slides into the logo, sub returns, three soft bell tones with the letters
    t0, notes, root = CODA
    bed('coda', pad(notes, t0, DUR, attack=0.22, release=0.05, cutoff=3200, tag='coda'), t0, -10.0, hall=0.3)
    n = N - ns(t0)
    sub2 = np.sin(phase_of(np.full(n, midi(root))))
    sub2 = sub2 * np.clip(tvec(n) / 0.25, 0, 1)
    bed('coda', pan2(level(sub2), 0.0), t0, -15.0)
    for i, m in enumerate([81, 84, 88]):
        bed('coda', bell(midi(m), dur=1.0, bright=0.6, tau=0.5), 9.08 + 0.07 * i, -18.5, pan=-0.3 + 0.3 * i, hall=0.35)


# ──────────────────────────── the sound effects ────────────────────────────
def compose_sfx():
    m = M
    # 0.00–0.64 MARK RISE: a swoosh on the P's expo.out rise + an airy riser toward the pop
    v = m.speed(m['mark.y'])
    sfx(swoosh('rise', 0.0, 0.62, v, lo=500, hi=7500, air=0.5, attack=0.02, release=0.09), 0.0, -15.5, hall=0.2, cue='upward swoosh — P rises')
    sfx(air_riser('riser', 0.58), 0.04, -21.0, hall=0.3, cue='airy riser')
    # 0.64 ICON POP: soft bass thump + pop + glass ping
    sfx(kick('thump', f0=110, f1=50, tau=0.17), 0.635, -14.0, cue='soft bass thump — icon pop')
    sfx(pop('iconpop', 1250, 360, tau=0.032), 0.64, -12.5, room=0.25, cue='pop — tile springs in')
    sfx(glass(midi(98)), 0.648, -20.0, room=0.15, hall=0.25, cue='glass ping')

    # 1.20 into the dark page: reverse swell, deep swoosh on the icon glide, the strongest hit
    sfx(rev_swell('preswell', 0.30, 200, 6000), 0.90, -18.5, hall=0.15, cue='reverse swell')
    ix, iy = m.screen(m['icon.x'], m['icon.y'])
    v = m.speed(ix, iy)
    sfx(swoosh('glide', 1.12, 1.44, v, ix, lo=120, hi=2400, air=0.15, release=0.1), 1.12, -15.0, hall=0.15,
        cue='deep swoosh — icon glides', cue_t=peak_time(1.12, 1.44, v))
    sfx(impact('hit1', bright=0.18), 1.20, -9.0, hall=0.4, cue='deep hit — cut to the dark page (strongest)')

    # 1.30–1.58 key-blips per logo letter (ascending through Dm9), ALUMINIUM ticks
    for i, note in enumerate([74, 76, 77, 81, 84, 86, 88, 89]):
        sfx(blip(f'key{i}', midi(note), tau=0.04, bright=0.25), 1.30 + 0.04 * i + 0.01, -24.0, pan=0.02 + 0.025 * i, room=0.2,
            cue='key-blips, one per logo letter' if i == 0 else None)
    for i in range(9):
        sfx(blip(f'alu{i}', 5200 + 90 * i, tau=0.012, bright=0.0, click=0.3, dur=0.05), 1.56 + 0.025 * i, -34.0, pan=0.15)
    sfx(pop('btnpop', 900, 300, tau=0.03), 1.47, -17.5, pan=0.0, room=0.2, cue='pop — "Explorer nos gammes" button')
    # 1.62–2.14 stat counters rolling up: tiny decelerating ticks
    for col, (start, counts) in enumerate([(1.62, [4]), (1.68, [11]), (1.74, [9, 19])]):
        for total in counts:
            for k in range(1, total + 1):
                tk = start + 0.52 * (1 - (1 - (k - 0.5) / total) ** (1 / 3))
                sfx(blip(f'tick{col}{total}{k}', 3400 + 40 * k, tau=0.006, bright=0.0, click=0.5, dur=0.03), tk,
                    -33.0 - 6 * k / total, pan=-0.2 + 0.2 * col)
    MIX.cues.append((1.62, 'stat counters roll up — soft ticks'))
    # 2.00 soft scroll swish
    v = m.speed(m['page.scroll']) * m['camera.scale']
    sfx(swoosh('scroll', 1.94, 2.42, v, lo=300, hi=4200, air=0.25, attack=0.01, release=0.12), 1.94, -18.5,
        cue='soft scroll swish', cue_t=peak_time(1.94, 2.42, v))

    # 2.48–2.68 push-in: short zoom whoosh
    v = m.speed(m['camera.x'], m['camera.y']) + 900 * np.abs(m.d(m['camera.scale']))
    sfx(swoosh('zoom', 2.46, 2.70, v, lo=200, hi=6500, air=0.4, release=0.06), 2.46, -14.5, pan=0.08, hall=0.15,
        cue='zoom whoosh — push-in', cue_t=peak_time(2.46, 2.70, v))
    # 2.62–2.92 the share arrow flies to the button
    py = m['pointer.y'] + m['page.scroll']
    px, py = m.screen(m['pointer.x'], py)
    v = m.speed(px, py)
    sfx(swoosh('pointer', 2.60, 2.93, v, px, lo=900, hi=9000, air=0.6, tail=0.08), 2.60, -21.5,
        cue='light swish — pointer flies to the button', cue_t=peak_time(2.60, 2.93, v))
    # 2.92 tap
    sfx(click('tap', 2900, 170), 2.92, -15.0, pan=0.12, room=0.2, cue='UI tap click')
    sfx(pop('tickflick', 1400, 2300, glide=0.02, tau=0.025, body=0.2, click=0.1, rise=True), 2.935, -24.0, pan=0.12, room=0.2, cue='tick flick')

    # 3.02–3.30 the button stretches into the address bar
    sfx(rubber_zip('zip', 0.17, 150, 640), 3.04, -15.0, pan=0.18, room=0.2, cue='rubbery stretch zip')
    sx, sy = m.screen(m['pill.x'], m['pill.y'])
    v = m.speed(sx, sy) + 3 * np.abs(m.d(m['pill.width']))
    sfx(swoosh('slide', 3.02, 3.32, v, sx, lo=250, hi=4500, air=0.3), 3.02, -17.5, cue='swoosh — bar slides to centre',
        cue_t=peak_time(3.02, 3.32, v))
    sfx(pop('gocircle', 420, 1100, glide=0.03, tau=0.035, rise=True), 3.285, -19.5, pan=0.5, room=0.25, cue='bubble pop — go button forms')
    # 3.30–3.69 "prompolu.com" typing blips
    typing = [81, 84, 86, 84, 81, 86, 89, 86, 84, 81, 84, 86]
    for i, note in enumerate(typing):
        sfx(blip(f'type{i}', midi(note), tau=0.022, bright=0.15, click=0.35, dur=0.08), 3.30 + 0.035 * i + 0.012, -24.5,
            pan=-0.38 + 0.033 * i, room=0.15, cue='typing blips — prompolu.com' if i == 0 else None)
    sfx(pop('arrowpop', 1600, 700, tau=0.02, body=0.3, click=0.1), 3.40, -25.5, pan=0.5)
    sfx(click('reload', 3600, 0.0), 3.645, -32.0, pan=0.36)

    # 3.68–4.50 pendulum: airy whooshes on every swing, panned with the direction of the swing
    w = m.d(m['pill.rotation'])
    v = np.abs(w) * np.pi / 180 * 550
    n0, n1 = int(3.66 * m.rate), int(4.56 * m.rate)
    pan_curve = np.full_like(v, 960.0)
    pan_curve[n0:n1] = 960 + 380 * np.tanh(-w[n0:n1] / 60)
    sfx(swoosh('pendulum', 3.66, 4.56, v, pan_curve, lo=600, hi=3600, air=0.35, release=0.05, tail=0.12, shape=1.1),
        3.66, -20.5, hall=0.15, cue='airy pendulum whooshes')
    # 4.02–4.40 the circle swings in from the upper left
    th = m['arm.rotation'] * np.pi / 180
    bx = 395 - 700 * np.sin(th)
    v = np.abs(m.d(m['arm.rotation'])) * np.pi / 180 * 700
    sfx(swoosh('swingin', 4.00, 4.42, v, m.screen(bx, 0 * bx)[0], lo=250, hi=4200, air=0.3), 4.00, -16.5,
        cue='swoosh — circle swings in from the upper left', cue_t=peak_time(4.00, 4.42, v))
    sfx(thup('land', 130), 4.395, -23.0, pan=-0.55)
    # 4.45 pop + bright ping for the "+"
    sfx(pop('plus', 1300, 400, tau=0.03), 4.43, -15.5, pan=-0.55, room=0.25, cue='pop + bright ping — the "+"')
    sfx(glass(midi(103), 1.1), 4.445, -21.0, pan=-0.5, room=0.15, hall=0.22)

    # 4.88–5.25 morph into the product grid
    sfx(rev_swell('premorph', 0.24, 400, 5000), 4.64, -23.5, hall=0.1)
    sfx(whff('pillout'), 4.88, -22.5, pan=0.1)
    tx, ty = m.screen(m['ptile.x'], m['ptile.y'])
    v = m.speed(tx, ty)
    sfx(swoosh('morph', 4.86, 5.20, v, tx, lo=250, hi=5200, air=0.35), 4.86, -15.5,
        cue='swoosh — circle becomes the PROMPOLU tile', cue_t=peak_time(4.86, 5.20, v))
    bx, by = m.screen(m['badge.x'], m['badge.y'])
    v = m.speed(bx, by)
    sfx(swoosh('badge', 4.88, 5.18, v, bx, lo=700, hi=8000, air=0.5), 4.88, -19.5,
        cue='light swoosh — go circle arcs into the badge', cue_t=peak_time(4.88, 5.18, v))
    sfx(bell(midi(84), dur=0.9, bright=0.7, tau=0.35), 5.075, -23.0, pan=0.15, hall=0.25)
    sfx(bell(midi(89), dur=1.4, bright=0.8, tau=0.6), 5.12, -17.0, pan=0.15, room=0.1, hall=0.3, cue='notification ding — badge "3"')
    cells = [(570, 150), (960, 150), (1350, 150), (570, 540), (1350, 540), (570, 930), (960, 930), (1350, 930)]
    notes = [77, 79, 81, 84, 86, 88, 89, 91]                     # F major pentatonic, rising with the stagger
    for i, (x, y) in enumerate(sorted(cells, key=lambda c: np.hypot(c[0] - 960, c[1] - 540))):
        d = np.hypot(x - 960, y - 540) / 390
        sfx(pop(f'cell{i}', midi(notes[i]) * 0.5, midi(notes[i]), glide=0.03, tau=0.03,
                body=0.2, click=0.05, rise=True), 4.97 + d * 0.07, -28.0, pan=(x - 960) / 960 * 0.7, room=0.2,
            cue='bubbly cascade — grid icons appear' if i == 0 else None)

    # 5.38 fling: a fast whoosh that decelerates with the scroll, rippling as the rows pass
    v = m.speed(m['grid.y']) * m['camera.scale']
    sfx(swoosh('fling', 5.36, 6.0, v, lo=300, hi=9500, air=0.6, attack=0.006, release=0.09, flutter=v / 390.0), 5.36, -11.5,
        hall=0.12, cue='fast scroll whoosh, decelerating with the fling', cue_t=peak_time(5.36, 6.0, v))

    # 6.07–6.44 dissolve to haze: dreamy shimmer riser, the badge drifts to centre
    sfx(shimmer_riser('haze', 0.42), 6.04, -18.0, hall=0.45, cue='dreamy shimmer riser — haze')
    bx, by = m.screen(m['badge.x'], m['badge.y'])
    v = m.speed(bx, by) + 2 * np.abs(m.d(m['badge.width']))
    sfx(swoosh('drift', 6.05, 6.46, v, bx, lo=400, hi=3500, air=0.3), 6.05, -22.0, hall=0.2)

    # 6.44–8.56 range cards: typing blips per word (in the bar's harmony), bubbly chip pops, paper flicks
    words = [(6.48, 0.030, [72, 74, 77, 79, 81, 84, 86, 84, 86, 89, 91], 'Coulissants'),
             (7.23, 0.27 / 7, [67, 69, 72, 74, 76, 79, 81, 84], 'Battants'),
             (8.00, 0.30 / 8, [69, 72, 74, 76, 79, 81, 84, 86, 88], 'Extérieur')]
    for t0, st, seq, word in words:
        for i, note in enumerate(seq):
            sfx(blip(f'{word}{i}', midi(note), tau=0.04, bright=0.3, click=0.15), t0 + st * i + 0.02, -23.5,
                pan=(i / (len(seq) - 1) - 0.5) * 0.55, room=0.2, cue=f'typing blips — "{word}"' if i == 0 else None)
    for t0, p, tag in [(6.52, 0.55, 's140rp'), (6.60, -0.55, 'window'), (7.27, -0.55, 's53rp'),
                       (7.34, 0.55, 'a400k'), (8.04, -0.6, 'pergola'), (8.11, 0.55, 'garde-corps')]:
        f0 = 430 + 60 * (zlib.crc32(tag.encode()) % 5)
        sfx(pop('chip' + tag, f0, f0 * 2.6, glide=0.035, tau=0.04, body=0.3, click=0.06, rise=True), t0 + 0.02, -17.0,
            pan=p, room=0.25, cue=f'bubbly pop — chip {tag}')
    for t0 in (7.13, 7.91):
        sfx(flick(f'flick{t0}'), t0, -15.5, room=0.3, cue='paper flick — card swap')
        for j, p in enumerate((0.5, -0.5)):
            sfx(pop(f'out{t0}{j}', 900, 420, tau=0.02, body=0.3, click=0.0), t0 + 0.01 + 0.012 * j, -26.0, pan=p)
    sfx(thup('drop2', 120), 7.215, -21.0)
    sfx(thup('drop3', 120), 7.995, -21.0)

    # 8.56–8.72 whip-down + flash
    sfx(rev_swell('prewhip', 0.26, 300, 6500, power=2.2), 8.30, -20.0, cue='riser into the whip')
    v = m.speed(m['card1.y']) + m.speed(m['camera.y'])
    sfx(swoosh('whip', 8.54, 8.72, v, lo=300, hi=7500, air=0.6, tone=(1500, 180, 0.6), attack=0.004, release=0.05, tail=0.06),
        8.54, -12.0, cue='fast downward whoosh')
    sfx(impact('flash', bright=0.55, boom=0.45), 8.705, -10.0, hall=0.45, cue='flash hit')
    # 8.72–8.86 the P drops and springs back
    v = m.speed(m['dropP.y'])
    sfx(swoosh('pdrop', 8.72, 8.80, v, lo=400, hi=5000, air=0.4, tone=(900, 260, 0.4), attack=0.003, release=0.03, tail=0.03),
        8.72, -17.0, cue='falling swish — P drops')
    sfx(kick('dropthud', f0=115, f1=52, tau=0.11, click=0.2), 8.80, -16.5, cue='soft drop thud')
    sfx(thup('dropknock', 150), 8.80, -21.0)
    # 8.88–9.03 the P slides into the logo and locks
    v = m.speed(m['dropP.x'])
    sfx(swoosh('slide-in', 8.86, 9.04, v, m['dropP.x'] + 579.07 + m['logo.x'], lo=300, hi=6500, air=0.45, attack=0.006,
               release=0.04, tail=0.06), 8.86, -14.5, cue='slide whoosh — P into the logo', cue_t=peak_time(8.86, 9.04, v))
    sfx(click('lock', 3300, 150, latch=0.012), 9.03, -13.5, pan=-0.4, room=0.25, cue='lock click')

    # 9.45–9.70 bronze sheen: faint metallic shimmer travelling right → left with the band
    sheen_x = 530 + (m['sheen.x'] + 30 - 61.69) * (860 / 374.91)
    sh = metal_shimmer('sheen', 0.75)
    n = sh.shape[0]
    ta = 9.44 + tvec(n)
    p = np.clip((np.interp(ta, M.t, sheen_x) - 960) / 960 * 0.8, -0.7, 0.7)
    sfx(pan2(sh, p), 9.44, -19.5, hall=0.35, cue='faint metallic shimmer — bronze sheen')


# ──────────────────────────── master ────────────────────────────
def measure(x):
    """Integrated loudness (LUFS) and true peak (dBTP) via FFmpeg's ebur128."""
    tmp = ROOT / 'renders/work-audio/measure.wav'
    write_wav(tmp, x, bits=32)
    out = subprocess.run(['ffmpeg', '-nostats', '-hide_banner', '-i', str(tmp), '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    tmp.unlink()
    i = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', out)[-1])
    tp = float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', out)[-1])
    lra = float(re.findall(r'LRA:\s+(-?[\d.]+) LU', out)[-1])
    return i, tp, lra


def limiter(x, ceiling_db, lookahead=0.0015, release=0.06):
    """Lookahead peak limiter driven by a 4× oversampled (true-peak) detector. Returns (output, max reduction dB)."""
    ceil = db(ceiling_db)
    up = signal.resample_poly(x, 4, 1, axis=1)
    pk = np.max(np.abs(up), axis=0)[:4 * x.shape[1]].reshape(-1, 4).max(axis=1)
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))          # highest gain each sample allows
    w = ns(lookahead)                                             # start reducing before the peak arrives
    need = np.lib.stride_tricks.sliding_window_view(np.concatenate([need, np.ones(w)]), w + 1).min(axis=1)
    gr = follower(1 - need, 0.0004, release)                      # smooth: fast attack, slow release
    g = np.minimum(1 - gr, need)
    return x * g, -20 * np.log10(g.min())


def write_wav(path, x, bits=24):
    path.parent.mkdir(parents=True, exist_ok=True)
    inter = np.ascontiguousarray(x.T).reshape(-1)
    if bits == 32:                          # 32-bit integer PCM for the loudness measurement
        data = np.clip(np.round(inter * 2147483647), -2147483648, 2147483647).astype('<i4').tobytes()
        width = 4
    else:
        v = np.clip(np.round(inter * 8388607), -8388608, 8388607).astype('<i4')
        data = v.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
        width = 3
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(width)
        w.setframerate(SR)
        w.writeframes(data)


def main():
    global M
    ap = argparse.ArgumentParser()
    ap.add_argument('--motion', default='renders/work-audio/motion.json')
    ap.add_argument('--no-export', action='store_true', help='reuse an existing motion export')
    ap.add_argument('--stems', action='store_true')
    ap.add_argument('--out', default='assets/audio/soundtrack.wav')
    args = ap.parse_args()

    motion = ROOT / args.motion
    if not (args.no_export and motion.exists()):
        subprocess.run(['node', str(ROOT / 'scripts/export-motion.mjs'), str(motion)], check=True, cwd=ROOT)
    M = Motion(motion)

    compose_music()
    compose_sfx()

    room = reverb(MIX.bus['room'], make_ir(0.55, 0.006, 9000, 3500, 'room'))
    hall = reverb(MIX.bus['hall'], make_ir(2.2, 0.022, 7000, 2000, 'hall'))
    tt = tvec(N)
    coda = MIX.bus['coda'] * np.where(tt < 9.10, 1.0, np.cos(np.clip((tt - 9.10) / 0.90, 0, 1) * np.pi / 2) ** 2)
    music = MIX.bus['music'] + coda
    effects = MIX.bus['sfx'] + 0.35 * room + 0.32 * hall
    mix = filt(music + effects, 'hp', 24, 0.7)
    end = np.where(tt < 9.72, 1.0, np.cos(np.clip((tt - 9.72) / 0.28, 0, 1) * np.pi / 2) ** 2)
    mix *= end
    mix = fade(mix, 0.003, 0.0)

    gain = 0.0
    for _ in range(4):                      # loudness to target, true peak under the ceiling
        out, reduction = limiter(mix * db(gain), CEILING_DBTP - 0.25)
        lufs, tp, lra = measure(out)
        if abs(lufs - TARGET_LUFS) < 0.2:
            break
        gain += TARGET_LUFS - lufs
    out = fade(out, 0.003, 0.0)
    write_wav(ROOT / args.out, out)
    print(f'soundtrack: {lufs:.1f} LUFS integrated, true peak {tp:.1f} dBTP, LRA {lra:.1f} LU, '
          f'limiter max reduction {reduction:.1f} dB → {args.out}')

    if args.stems:                          # dry music / effects + all reverb returns, at the master gain
        g = db(gain)
        write_wav(ROOT / 'renders/work-audio/music.wav', np.clip(music * end * g, -1, 1))
        write_wav(ROOT / 'renders/work-audio/sfx.wav', np.clip(effects * end * g, -1, 1))

    lines = ['# PROMPOLU — Nos gammes · soundtrack cue sheet (generated by scripts/compose-soundtrack.py)',
             '# Original synthesis, no samples. Bed: 125 BPM pop-house in F, bars at 1.20 · 3.12 · 5.04 · 6.96 · 8.88 s:',
             '#   Dm9 → Bbmaj9 → Fmaj9 → C6/9 → Fmaj9 (logo). Sustained sub-bass, soft pad and plucks, offbeat shaker,',
             '#   sidechain pump, soft kicks on transitions. Music fades from 9.10 s to silence at 10.00 s. No voiceover.',
             '# time (s)\tcue']
    seen = set()
    MIX.cues.append((9.10, 'music fades out (silence at 10.00)'))
    for t, label in sorted(MIX.cues):
        key = (round(t, 2), label)
        if key not in seen:
            seen.add(key)
            lines.append(f'{t:.2f}\t{label}')
    (ROOT / 'cues.txt').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
