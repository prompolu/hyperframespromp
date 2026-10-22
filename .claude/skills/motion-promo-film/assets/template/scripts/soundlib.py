"""soundlib — synthesis, motion-driven swooshes, mixing and mastering for short films.

Everything is synthesised (no samples, no third-party audio) and seeded per sound tag, so a score
renders byte-identically every time. A film's score script imports it:

    import soundlib as sl
    sl.configure(duration=10.0)
    M = sl.load_motion('renders/work-audio/motion.json')          # from scripts/export-motion.mjs
    v = M.speed(M['grid.y'])                                      # px/s of the element that moves
    sl.sfx(sl.swoosh('fling', 5.36, 6.0, v), 5.36, -11.5, cue='fast scroll whoosh')
    sl.sfx(sl.pop('icon', 1250, 360), 0.64, -12.5, room=0.25, cue='pop — icon')
    sl.bed('music', sl.pad([57, 60, 64, 67], 5.04, 6.96), 5.04, -10.0, hall=0.18)
    sl.finish('assets/audio/soundtrack.wav', cues_path='cues.txt', music_fade=(9.1, 10.0))

Level convention: every generator returns a signal whose loudest 10 ms window has RMS 1, so the gain
passed to sfx()/bed() is roughly that sound's short-term level in dB before mastering.
"""
import re
import subprocess
import tempfile
import wave
import zlib
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48000
DUR = 10.0
N = int(round(SR * DUR))
BED_DB = -12.5            # the music bed sits well under the transition effects (see finish())
M = None                  # Motion, set by load_motion()
MIX = None                # Mixer, set by configure()


def configure(duration, sr=48000, bed_db=-12.5):
    """Set the film length (seconds) and reset the mix."""
    global SR, DUR, N, MIX, BED_DB
    SR, DUR, BED_DB = sr, float(duration), bed_db
    N = int(round(SR * DUR))
    MIX = Mixer()
    return MIX


# ──────────────────────────── basics ────────────────────────────
def rng(tag):
    """Seeded per sound: adding or removing one sound never changes another's noise.
    (Python's hash() is randomised per process — never seed with it.)"""
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
    """Equal-power pan; p is a number or a per-sample array in [-1, 1]."""
    a = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.vstack([x * np.cos(a), x * np.sin(a)])


# ──────────────────────────── filters ────────────────────────────
def biquad(kind, f0, q=0.707, gain_db=0.0):
    """RBJ cookbook biquad: lp, hp, bp, peak, hs."""
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
    """The film's GSAP timeline sampled by scripts/export-motion.mjs (channels named 'element.prop')."""

    def __init__(self, path):
        import json
        m = json.loads(Path(path).read_text())
        self.rate = m['rate']
        self.duration = m.get('duration')
        self.c = {k: np.asarray(v, float) for k, v in m['channels'].items()}
        self.t = np.arange(len(next(iter(self.c.values())))) / self.rate

    def __getitem__(self, k):
        return self.c[k]

    def d(self, arr):
        return np.gradient(arr, 1 / self.rate)

    def speed(self, x, y=None):
        """|velocity| per second of one channel, or of an (x, y) pair."""
        return np.abs(self.d(x)) if y is None else np.hypot(self.d(x), self.d(y))

    def screen(self, x, y, cam='camera', w=1920, h=1080):
        """Camera space → stage pixels, if the film exports camera.x/.y/.scale (rotation ignored)."""
        if f'{cam}.scale' not in self.c:
            return x, y
        s, cx, cy = self.c[f'{cam}.scale'], self.c.get(f'{cam}.x', 0), self.c.get(f'{cam}.y', 0)
        return w / 2 + cx + s * (x - w / 2), h / 2 + cy + s * (y - h / 2)

    def peak(self, t0, t1, speed):
        """Time of the fastest moment of `speed` between t0 and t1 (use it as the cue time)."""
        i0, i1 = int(t0 * self.rate), int(t1 * self.rate)
        return (np.argmax(speed[i0:i1]) + i0) / self.rate


def load_motion(path):
    global M
    M = Motion(path)
    return M


def swoosh(tag, t0, t1, speed, xpos=None, *, lo=250.0, hi=5500.0, air=0.35, whistle=0.0, tone=None,
           tail=0.16, shape=0.9, attack=0.008, release=0.07, width=0.85, flutter=None, stage_w=1920):
    """Noise whoosh between t0 and t1 driven by a motion speed curve (array over M.t):
    level ∝ speed**shape, brightness sweeps lo→hi Hz with speed, the pan follows screen x (xpos).
    flutter: per-sample rate (Hz) of items passing the eye → a soft ripple (e.g. speed / row pitch).
    tone: (f_start, f_end, relative level) pitched sweep under the noise (doppler / falling feel)."""
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
    if flutter is not None:
        fr = np.interp(ta, M.t, flutter)
        x = x * (1 - 0.3 * (0.5 + 0.5 * np.sin(phase_of(fr))))
    if tone is not None:
        f = tone[0] * (tone[1] / tone[0]) ** np.linspace(0, 1, n)
        x = x + tone[2] * np.sin(phase_of(f))
    sig = fade(x * e ** shape, 0.004, 0.02)
    if xpos is None:
        return level(sig)
    p = np.clip((np.interp(ta, M.t, xpos) - stage_w / 2) / (stage_w / 2) * width, -width, width)
    return level(pan2(sig, p))


# ──────────────────────────── instruments & effects ────────────────────────────
def pop(tag, f0=1100.0, f1=330.0, glide=0.026, tau=0.030, body=0.45, click=0.25, rise=False):
    """Mouth-pop (pitch falls f0→f1) or bubble (rise=True, pitch climbs f0→f1)."""
    n = ns(0.18)
    t = tvec(n)
    k = np.clip(t / glide, 0, 1)
    f = f0 * (f1 / f0) ** (k ** 0.55) if rise else f1 + (f0 - f1) * (1 - k) ** 2
    x = np.sin(phase_of(f)) * perc(n, 0.0008, tau)
    x += body * np.sin(phase_of(f * 0.5)) * perc(n, 0.001, tau * 1.6)
    x += click * filt(white(n, tag), 'hp', 3000) * np.exp(-t / 0.0012)
    return level(fade(x, 0.0003, 0.01))


def glass(f=2349.3, dur=1.3):
    """Glass ping (inharmonic partials). Tune f to a chord tone, e.g. midi(98)."""
    t = tvec(ns(dur))
    parts = [(1.0, 1.0, 0.48), (2.32, 0.42, 0.25), (4.25, 0.20, 0.12), (6.63, 0.09, 0.07)]
    x = sum(a * np.sin(2 * np.pi * f * r * t + r) * np.exp(-t / tau) for r, a, tau in parts)
    return level(fade(x * np.clip(t / 0.0015, 0, 1)))


def bell(f, dur=1.4, bright=1.0, tau=0.7):
    """Soft bell / notification ding."""
    t = tvec(ns(dur))
    parts = [(1.0, 1.0, 1.0), (2.0, 0.30 * bright, 0.5), (3.0, 0.10 * bright, 0.28), (4.16, 0.07 * bright, 0.16), (5.43, 0.04 * bright, 0.09)]
    x = sum(a * np.sin(2 * np.pi * f * r * t + r) * np.exp(-t / (tau * k)) for r, a, k in parts)
    x += 0.25 * np.sin(2 * np.pi * f * 1.0018 * t) * np.exp(-t / tau)
    return level(fade(x * np.clip(t / 0.002, 0, 1)))


def blip(tag, f, tau=0.035, bright=0.3, click=0.12, dur=0.14):
    """Soft marimba-like blip (letters settling, typing). Pitch it on the bar's chord or pentatonic."""
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
    """Deep hit: kick + low noise boom + pitched thwump + a little crack (world changes, flashes)."""
    n = ns(dur)
    t = tvec(n)
    k = kick(tag + '/k', f0=125, f1=38, drop=0.06, tau=0.42, dur=dur, click=0.18, drive=1.8)
    b = filt(filt(pink(n, tag + '/b'), 'lp', 150, 0.8), 'lp', 150, 0.8) * perc(n, 0.004, 0.55)
    w = np.sin(phase_of(68 + 110 * np.exp(-t / 0.03))) * perc(n, 0.001, 0.12)
    c = filt(white(n, tag + '/c'), 'hp', 2500) * np.exp(-t / 0.012)
    return level(fade(level(k) + boom * level(b) + 0.5 * level(w) + bright * level(c)))


def rev_swell(tag, dur, lo=250.0, hi=7000.0, power=2.6):
    """Backwards-reverb style swell: place it at hit_time - dur so it ends on the hit."""
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
    """Rubbery stretch: a wobbling saw glide through a moving formant."""
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    f = f0 * (f1 / f0) ** (u ** 0.75) * (1 + 0.04 * np.sin(2 * np.pi * 26 * t))
    s = saw(f, harmonics=18)
    x = tvfilt(s, 'bp', np.minimum(f * 3.2, 9000), 2.6) + 0.5 * tvfilt(s, 'lp', 600 + 2500 * u, 0.9)
    env = np.minimum(np.clip(t / 0.012, 0, 1), np.clip((dur - t) / 0.035, 0, 1))
    return level(fade(x * env))


def flick(tag):
    """Paper flick: two quick noise transients + a little flap (card swaps, page turns)."""
    n = ns(0.16)
    t = tvec(n)
    nz = filt(filt(white(n, tag), 'bp', 2600, 0.8), 'hp', 700)
    e = np.exp(-t / 0.010) + 0.55 * np.exp(-np.maximum(t - 0.016, 0) / 0.026) * (t > 0.016)
    flap = 0.35 * np.sin(2 * np.pi * 210 * t) * np.exp(-t / 0.018)
    return level(fade(nz * e + flap))


def click(tag, tone=2900.0, knock=170.0, latch=0.0):
    """UI tap (knock ≈ 170) or a lock/snap (add latch=0.012 for the second click)."""
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
    """Soft low landing."""
    n = ns(0.2)
    t = tvec(n)
    x = np.sin(phase_of(70 + (f - 70) * np.exp(-t / 0.02))) * perc(n, 0.001, 0.05)
    x += 0.4 * filt(pink(n, tag), 'lp', 600) * perc(n, 0.001, 0.025)
    return level(fade(x))


def whff(tag, dur=0.16):
    """Short airy puff (something blurs away)."""
    n = ns(dur)
    t = tvec(n)
    x = tvfilt(pink(n, tag), 'lp', 3500 * np.exp(-t / 0.05) + 300, 0.7) * perc(n, 0.006, 0.05)
    return level(fade(x))


def shaker(tag, decay=0.032):
    n = ns(0.12)
    x = filt(filt(white(n, tag), 'hp', 6000, 0.7), 'lp', 12500, 0.7) * perc(n, 0.003, decay)
    return level(fade(x))


def shimmer_riser(tag, dur, notes=(84, 88, 91, 93)):
    """Dreamy riser: tremolo chord tones + rising sparkle (dissolves, hazes)."""
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    x = sum(np.sin(2 * np.pi * midi(m) * t + i) * (1 + 0.35 * np.sin(2 * np.pi * (7.5 + 1.3 * i) * t + i)) for i, m in enumerate(notes))
    x = x * u ** 1.8
    x += 0.35 * tvfilt(white(n, tag), 'bp', 4000 + 6000 * u, 2.0) * u ** 2
    return level(fade(x, 0.02, 0.01))


def metal_shimmer(tag, dur=0.7, f=1180.0):
    """Metallic sheen: inharmonic bell cluster with tremolo (pan it with the gloss sweep)."""
    n = ns(dur)
    t = tvec(n)
    ratios = [1.0, 1.58, 2.24, 2.83, 3.51, 4.71, 5.93]
    x = sum((0.8 ** i) * np.sin(2 * np.pi * f * r * t + i) * (1 + 0.4 * np.sin(2 * np.pi * (9 + 2.3 * i) * t)) for i, r in enumerate(ratios))
    env = np.clip(t / 0.06, 0, 1) ** 1.5 * np.exp(-np.maximum(t - 0.06, 0) / 0.22)
    sparkle = 0.25 * filt(white(n, tag), 'bp', 9000, 1.5) * env
    return level(fade(x * env + sparkle, 0.005, 0.02))


def pad(notes, t0, t1, *, attack=0.12, release=0.45, cutoff=2200.0, detune=7.0, tag='pad'):
    """Warm detuned-saw pad (MIDI notes), three voices per note spread across the stereo field."""
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


def sub_bass(segments, t_on, t_off, attack=0.02, release=0.06, glide=0.03):
    """Sustained sub-bass gliding between roots: segments = [(t0, t1, midi), ...]."""
    f = np.full(N, midi(segments[0][2]))
    for t0, t1, m in segments:
        f[ns(t0):ns(t1)] = midi(m)
    f[ns(segments[-1][1]):] = midi(segments[-1][2])
    a = np.exp(-1 / (glide * SR))
    f = signal.lfilter([1 - a], [1, -a], f, zi=[f[0] * a])[0]
    ph = phase_of(f)
    x = np.tanh(1.3 * (np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph))) / np.tanh(1.3)
    tt = tvec(N)
    amp = np.clip((tt - t_on) / attack, 0, 1) * np.clip((t_off - tt) / release, 0, 1)
    return pan2(level(x) * amp, 0.0)


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
        self.bus = {k: np.zeros((2, N)) for k in ('music', 'sfx', 'room', 'hall')}
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


def sfx(sig, t0, gain_db, pan=0.0, room=0.0, hall=0.0, cue=None, cue_t=None):
    """Place a sound effect (mono or stereo) at t0 seconds. cue/cue_t label it in cues.txt."""
    MIX.add('sfx', sig, t0, gain_db, pan, room, hall, cue, cue_t)


def bed(bus_name, sig, t0, gain_db, **kw):
    """Place a music-bed part; BED_DB is added so the bed sits under the effects."""
    MIX.add(bus_name, sig, t0, gain_db + BED_DB, **kw)


def cue(t, label):
    MIX.cues.append((t, label))


def pump(beats, depth=0.32, tau=0.11, extra=()):
    """Sidechain pump on the music bus: dip on each beat time; extra = [(time, depth)] for kicks."""
    tt = tvec(N)
    g = np.ones(N)
    step = np.median(np.diff(beats)) if len(beats) > 1 else 0.5
    for b, d in [(b, depth) for b in beats] + list(extra):
        i0, i1 = ns(b), min(N, ns(b + step))
        u = tt[i0:i1] - b
        g[i0:i1] = np.minimum(g[i0:i1], 1 - d * (1 - np.exp(-u / 0.004)) * np.exp(-u / tau))
    MIX.bus['music'] *= g


def automate_filter(bus_name, kind, curve, q=0.7):
    """Time-varying filter on a whole bus (curve: per-sample Hz, length N) — e.g. a muffled haze."""
    for c in range(2):
        MIX.bus[bus_name][c] = tvfilt(MIX.bus[bus_name][c], kind, curve, q, block=64)


# ──────────────────────────── master ────────────────────────────
def measure(x):
    """Integrated loudness (LUFS), true peak (dBTP) and LRA via FFmpeg's ebur128."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        tmp = Path(f.name)
    write_wav(tmp, x, bits=32)
    out = subprocess.run(['ffmpeg', '-nostats', '-hide_banner', '-i', str(tmp), '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    tmp.unlink()
    i = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', out)[-1])
    tp = float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', out)[-1])
    lra = float(re.findall(r'LRA:\s+(-?[\d.]+) LU', out)[-1])
    return i, tp, lra


def limiter(x, ceiling_db, lookahead=0.0015, release=0.06):
    """Look-ahead peak limiter on a 4× oversampled (true-peak) detector. Returns (out, max reduction dB)."""
    ceil = db(ceiling_db)
    up = signal.resample_poly(x, 4, 1, axis=1)
    pk = np.max(np.abs(up), axis=0)[:4 * x.shape[1]].reshape(-1, 4).max(axis=1)
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    w = ns(lookahead)
    need = np.lib.stride_tricks.sliding_window_view(np.concatenate([need, np.ones(w)]), w + 1).min(axis=1)
    gr = follower(1 - need, 0.0004, release)
    g = np.minimum(1 - gr, need)
    return x * g, -20 * np.log10(g.min())


def write_wav(path, x, bits=24):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    inter = np.ascontiguousarray(x.T).reshape(-1)
    if bits == 32:
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


def finish(out_path, *, cues_path=None, cue_header=(), music_fade=None, end_fade=0.28, target_lufs=-15.0,
           ceiling_dbtp=-1.0, room=(0.55, 0.006, 9000, 3500), hall=(2.2, 0.022, 7000, 2000),
           room_return=0.35, hall_return=0.32, stems_dir=None):
    """Reverb returns, fades, loudness to target, true-peak limiting, 24-bit WAV, cue sheet.
    music_fade=(start, end) fades the music bus to silence; end_fade fades everything into the last frame."""
    tt = tvec(N)
    room_wet = reverb(MIX.bus['room'], make_ir(*room, 'room'))
    hall_wet = reverb(MIX.bus['hall'], make_ir(*hall, 'hall'))
    music = MIX.bus['music']
    if music_fade:
        a, b = music_fade
        music = music * np.where(tt < a, 1.0, np.cos(np.clip((tt - a) / (b - a), 0, 1) * np.pi / 2) ** 2)
    effects = MIX.bus['sfx'] + room_return * room_wet + hall_return * hall_wet
    mix = filt(music + effects, 'hp', 24, 0.7)
    end = np.where(tt < DUR - end_fade, 1.0, np.cos(np.clip((tt - (DUR - end_fade)) / end_fade, 0, 1) * np.pi / 2) ** 2)
    mix = fade(mix * end, 0.003, 0.0)
    gain = 0.0
    for _ in range(5):
        out, reduction = limiter(mix * db(gain), ceiling_dbtp - 0.25)
        lufs, tp, lra = measure(out)
        if abs(lufs - target_lufs) < 0.2:
            break
        gain += target_lufs - lufs
    out = fade(out, 0.003, 0.0)
    write_wav(out_path, out)
    if stems_dir:
        g = db(gain)
        write_wav(Path(stems_dir) / 'music.wav', np.clip(music * end * g, -1, 1))
        write_wav(Path(stems_dir) / 'sfx.wav', np.clip(effects * end * g, -1, 1))
    if cues_path:
        lines = list(cue_header) + ['# time (s)\tcue']
        seen = set()
        for t, label in sorted(MIX.cues):
            if (round(t, 2), label) not in seen:
                seen.add((round(t, 2), label))
                lines.append(f'{t:.2f}\t{label}')
        Path(cues_path).write_text('\n'.join(lines) + '\n')
    report = dict(lufs=lufs, true_peak=tp, lra=lra, limiter_reduction_db=float(reduction))
    print(f'soundtrack: {lufs:.1f} LUFS, true peak {tp:.1f} dBTP, LRA {lra:.1f} LU, limiter max {reduction:.1f} dB → {out_path}')
    return report
