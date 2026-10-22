#!/usr/bin/env python3
"""Original 20-second soundtrack for the PROMPOLU motion film.

Everything is synthesised here (no samples, no third-party audio):
120 BPM restrained house groove — warm sine bass, soft four-on-the-floor kick,
quiet hats/claps, FM plucks, a detuned pad — plus sound effects placed on the
film's cue points. Writes stems and an unmastered mix; scripts/master-audio.py
then normalises to about -16 LUFS integrated with true peak <= -1 dBTP.

    python scripts/compose-soundtrack.py   (needs numpy + scipy)
"""
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt, sosfilt_zi

SR = 48000
DUR = 20.0
N = int(SR * DUR)  # exactly 960 000 samples
BEAT = 0.5  # 120 BPM
OUT = Path(__file__).resolve().parent.parent / "assets" / "audio"
rng = np.random.default_rng(20)

# ------------------------------------------------------------- cue points (s)
CUES = {
    "letters": [0.10 + i * 0.022 for i in range(28)],  # one flutter per visible letter
    "dot": 1.65,
    "bronze_whoosh": 2.00,
    "sphere_appear": 3.25,
    "sphere_sweep": 3.50,
    "cards": [4.12, 4.25, 4.34, 4.43, 4.52],
    "nav_tick": 6.60,
    "pill": 6.78,
    "scroll": (8.30, 8.80, 0.35, 0.45, 0.50),  # morph start, scroll start, accel, fast, decel
    "impact": 10.40,
    "chips": [11.20, 11.30, 11.40],
    "frame_sweep": 13.10,
    "capsule": 15.50,
    "final_whoosh": 17.00,
    "resolution": 17.80,
}


# ------------------------------------------------------------------ helpers
def t_axis(n):
    return np.arange(n) / SR


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def place(buf, sig, at, gain=1.0, pan=0.0):
    """Add a mono or stereo signal at time `at` (s) with constant-power pan."""
    i0 = int(round(at * SR))
    if i0 >= N:
        return
    if sig.ndim == 1:
        lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * lg, sig * rg], axis=1)
    n = min(len(sig), N - i0)
    buf[i0 : i0 + n] += gain * sig[:n]


def env(n, a=0.005, d=0.1, s=0.0, r=0.05, hold=None):
    """ADSR envelope of n samples (s = sustain level; hold = sustain time in s)."""
    t = t_axis(n)
    e = np.zeros(n)
    a_n = max(1, int(a * SR))
    e[:a_n] = np.linspace(0, 1, a_n)
    rest = t[a_n:] - a
    if hold is None:
        e[a_n:] = s + (1 - s) * np.exp(-rest / max(d, 1e-4))
    else:
        dec = s + (1 - s) * np.exp(-rest / max(d, 1e-4))
        rel = np.where(rest > hold, np.exp(-(rest - hold) / max(r, 1e-4)), 1.0)
        e[a_n:] = dec * rel
    return e


def lp(x, fc, order=2):
    sos = butter(order, min(fc, SR / 2 * 0.95), "low", fs=SR, output="sos")
    return sosfilt(sos, x, axis=0)


def hp(x, fc, order=2):
    sos = butter(order, fc, "high", fs=SR, output="sos")
    return sosfilt(sos, x, axis=0)


def bp(x, lo, hi, order=2):
    sos = butter(order, [lo, min(hi, SR / 2 * 0.95)], "band", fs=SR, output="sos")
    return sosfilt(sos, x, axis=0)


def sweep_lp(x, cutoff, block=256):
    """Time-varying low-pass: cutoff is an array (Hz) per sample."""
    y = np.zeros_like(x)
    zi = None
    for i in range(0, len(x), block):
        fc = float(np.clip(cutoff[min(i, len(cutoff) - 1)], 40, SR / 2 * 0.9))
        sos = butter(2, fc, "low", fs=SR, output="sos")
        if zi is None:
            zi = sosfilt_zi(sos) * 0
            if x.ndim == 2:
                zi = np.repeat(zi[:, :, None], x.shape[1], axis=2)
        y[i : i + block], zi = sosfilt(sos, x[i : i + block], axis=0, zi=zi)
    return y


def noise(n, stereo=False):
    return rng.standard_normal((n, 2) if stereo else n)


def reverb_ir(seconds=1.8, decay=0.42, seed=3):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = t_axis(n)
    ir = r.standard_normal((n, 2)) * np.exp(-t / decay)[:, None]
    ir = lp(ir, 6500)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.sqrt(np.sum(ir**2, axis=0))


def add_reverb(x, wet=0.25, ir=None):
    ir = reverb_ir() if ir is None else ir
    w = np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return x + wet * w


# ------------------------------------------------------------------ voices
def pad_note(m, dur, detune=0.07):
    n = int(dur * SR)
    t = t_axis(n)
    f = midi(m)
    out = np.zeros((n, 2))
    # three detuned voices: flat -> left, centre -> both, sharp -> right
    for dt, (gl, gr) in zip((-detune, 0.0, detune), ((1.0, 0.0), (0.7, 0.7), (0.0, 1.0))):
        ph = 2 * np.pi * f * (2 ** (dt / 12)) * t + dt * 20
        w = sum(np.sin(h * ph) / h for h in range(1, 7))  # soft saw, a few harmonics only
        out[:, 0] += gl * w
        out[:, 1] += gr * w
    e = env(n, a=0.45, d=1.0, s=0.85, r=0.6, hold=max(0.0, dur - 0.6))
    return lp(out * e[:, None], 1700)


def pluck(m, dur=0.6, bright=2.2):
    n = int(dur * SR)
    t = t_axis(n)
    f = midi(m)
    idx = bright * np.exp(-t / 0.08)
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * 2 * f * t))
    y *= env(n, a=0.003, d=0.16)
    return lp(y, 4200)


def bell(m, dur=2.4):
    n = int(dur * SR)
    t = t_axis(n)
    f = midi(m)
    y = np.sin(2 * np.pi * f * t + 1.2 * np.exp(-t / 0.3) * np.sin(2 * np.pi * 3.5 * f * t))
    y += 0.3 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.4)
    return lp(y * env(n, a=0.004, d=0.9), 5000)


def bass_note(m, dur):
    n = int(dur * SR)
    t = t_axis(n)
    f = midi(m)
    y = np.sin(2 * np.pi * f * t) + 0.28 * np.sin(4 * np.pi * f * t) + 0.08 * np.sin(6 * np.pi * f * t)
    y = np.tanh(1.4 * y) / np.tanh(1.4)
    y *= env(n, a=0.006, d=0.22, s=0.55, r=0.05, hold=max(0.0, dur - 0.06))
    return lp(y, 520)


def kick(level=1.0):
    n = int(0.42 * SR)
    t = t_axis(n)
    f = 46 + 70 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t / 0.18)
    y += 0.15 * lp(noise(n), 2500) * np.exp(-t / 0.006)
    return level * y


def hat(n_s=0.045):
    n = int(n_s * SR)
    t = t_axis(n)
    return lp(hp(noise(n), 6500), 10500) * np.exp(-t / 0.014)


def clap():
    n = int(0.22 * SR)
    t = t_axis(n)
    y = np.zeros(n)
    for k, off in enumerate((0.0, 0.009, 0.019)):
        i = int(off * SR)
        y[i:] += np.exp(-(t[: n - i]) / (0.006 if k < 2 else 0.07))
    return bp(noise(n) * y, 900, 3200)


def whoosh(dur, f0, f1, peak=0.6, bandwidth=1.6, stereo_width=0.6):
    """Band-pass noise sweep with a rounded swell. peak = relative position of max level."""
    n = int(dur * SR)
    t = t_axis(n) / dur
    x = noise(n, stereo=True)
    x[:, 1] = stereo_width * x[:, 1] + (1 - stereo_width) * x[:, 0]
    fc = f0 * (f1 / f0) ** t
    y = sweep_lp(x, fc * bandwidth)
    y = hp(y, 120)
    shape = np.where(t < peak, (t / peak) ** 2, np.cos(np.clip((t - peak) / (1 - peak), 0, 1) * np.pi / 2) ** 2)
    return y * shape[:, None]


def thump(f=55, dur=0.6):
    n = int(dur * SR)
    t = t_axis(n)
    fr = f + 40 * np.exp(-t / 0.05)
    return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / 0.22) * env(n, a=0.004, d=10)


def tick(f=1800, dur=0.03):
    n = int(dur * SR)
    t = t_axis(n)
    return (np.sin(2 * np.pi * f * t) * 0.6 + 0.4 * bp(noise(n), f * 0.8, f * 1.6)) * np.exp(-t / 0.006)


# ------------------------------------------------------------------ harmony
# (start, end, bass midi, pad voicing) — 2-second bars at 120 BPM
CHORDS = [
    (0.0, 2.0, 41, [53, 57, 60, 64, 67]),    # Fmaj9
    (2.0, 4.0, 38, [53, 57, 60, 64]),        # Dm9
    (4.0, 6.0, 34, [50, 53, 57, 60]),        # Bbmaj9
    (6.0, 8.0, 36, [52, 55, 57, 62]),        # C6/9
    (8.0, 10.0, 41, [53, 57, 60, 64, 67]),   # Fmaj9
    (10.0, 12.0, 38, [53, 57, 60, 64]),      # Dm9
    (12.0, 14.0, 34, [50, 53, 57, 60]),      # Bbmaj9
    (14.0, 15.0, 43, [53, 58, 62, 69]),      # Gm9
    (15.0, 16.0, 36, [55, 58, 60, 65]),      # C7sus
    (16.0, 17.0, 34, [50, 53, 57, 62]),      # Bbmaj9 (lift)
    (17.0, 17.8, 36, [55, 58, 60, 65]),      # C7sus (dominant into the resolution)
    (17.8, 20.0, 41, [53, 57, 60, 64, 67]),  # Fmaj9 — resolution under the final hold
]


def chord_at(t):
    for c in CHORDS:
        if c[0] <= t < c[1]:
            return c
    return CHORDS[-1]


def build_music():
    pad = np.zeros((N, 2))
    for s, e, _, notes in CHORDS:
        dur = (e - s) + (2.2 if e >= 20.0 else 0.35)
        for m in notes:
            place(pad, pad_note(m, dur), s, gain=0.05)
    pad = lp(pad, 2400)

    bass = np.zeros((N, 2))
    # 2.0–4.0: long roots; 4.0+: root on the beat, octave on the off-beat (restrained house)
    for s, e, root, _ in CHORDS:
        if e <= 2.0:
            continue
        if s < 4.0 or s >= 17.8:
            place(bass, bass_note(root, (e - s) - 0.02 if s < 17.8 else 1.9), s, gain=0.3)
            continue
        t = s
        while t < e - 1e-6:
            if 15.5 <= t < 16.0:
                t += BEAT
                continue
            place(bass, bass_note(root, 0.22), t, gain=0.32)
            place(bass, bass_note(root + 12, 0.18), t + 0.25, gain=0.16)
            t += BEAT

    drums = np.zeros((N, 2))
    place(drums, kick(0.45), 2.0)
    place(drums, kick(0.35), 3.0)
    t = 4.0
    while t < 15.5 - 1e-6:
        place(drums, kick(0.5), t)
        if t >= 4.0:
            place(drums, hat(), t + 0.25, gain=0.09, pan=0.25)
        if t >= 6.0 and (round((t - 4.0) / BEAT) % 2 == 1):
            place(drums, clap(), t, gain=0.11, pan=-0.1)
        if t >= 6.0:  # quiet shaker on 16ths
            for k in (0.125, 0.375):
                place(drums, hat(0.03), t + k, gain=0.025, pan=-0.35)
        t += BEAT

    plucks = np.zeros((N, 2))
    pattern = [0, 2, 1, 3, 2, 4, 1, 3]  # chord-tone order per 8th note
    t = 2.0
    step = 0
    while t < 17.8 - 1e-6:
        _, _, _, notes = chord_at(t)
        tones = sorted(notes) + [notes[1] + 12]
        dense = 15.5 <= t < 17.8
        if t < 4.0 and step % 2:
            pass  # sparse intro
        elif 13.1 <= t < 15.5 and step % 2:
            pass  # breathe under the visualisation panel
        else:
            m = tones[pattern[step % 8] % len(tones)] + 12
            g = 0.06 if t < 4.0 else 0.075
            if dense:
                g = 0.05 + 0.04 * (t - 15.5) / 2.3
            place(plucks, pluck(m), t, gain=g, pan=0.35 if step % 2 else -0.35)
        step += 1
        t += 0.125 if dense else 0.25
    # echo for the plucks (dotted-8th ping-pong)
    d = int(0.375 * SR)
    echo = np.zeros_like(plucks)
    echo[d:, 0] = plucks[:-d, 1] * 0.35
    echo[2 * d :, 1] = plucks[: -2 * d, 0] * 0.25
    plucks = plucks + echo

    # final resolution at 17.80: soft bell chord + low root
    res = np.zeros((N, 2))
    for k, m in enumerate([65, 69, 72, 76, 79]):
        place(res, bell(m, 2.3), CUES["resolution"] + k * 0.035, gain=0.05, pan=-0.4 + 0.2 * k)
    place(res, bass_note(29, 2.1), CUES["resolution"], gain=0.22)

    # filter dip on the groove while the gallery scrolls (8.3 – 10.4)
    groove = drums + bass + plucks
    cutoff = np.full(N, 16000.0)
    t = t_axis(N)
    dip = (t > 8.3) & (t < 10.4)
    u = np.clip((t - 8.3) / 2.1, 0, 1)
    cutoff[dip] = 16000 * (1 - 0.92 * np.sin(np.pi * u[dip]) ** 0.7)
    groove = sweep_lp(groove, cutoff)

    music = pad + groove + res
    return add_reverb(music, wet=0.22)


def build_sfx():
    fx = np.zeros((N, 2))
    # 00.10–00.90 light typography flutters
    for i, at in enumerate(CUES["letters"]):
        n = int(0.05 * SR)
        tt = t_axis(n)
        g = bp(noise(n), 2200, 6000) * np.exp(-tt / 0.012) * (0.6 + 0.4 * np.sin(2 * np.pi * 70 * tt))
        place(fx, g, at, gain=0.3, pan=-0.6 + 1.2 * i / 27)
    place(fx, whoosh(0.9, 900, 4000, peak=0.5) * 0.5, 0.05, gain=0.5)
    place(fx, tick(1400, 0.05), CUES["dot"], gain=0.45, pan=0.5)
    # 02.00 soft bronze expansion whoosh
    place(fx, whoosh(0.75, 250, 2600, peak=0.42), CUES["bronze_whoosh"] - 0.12, gain=0.75)
    place(fx, thump(48, 0.7), CUES["bronze_whoosh"] + 0.2, gain=0.18)
    # 03.25 sphere appears, 03.50 smooth sphere sweep
    place(fx, tick(900, 0.06), CUES["sphere_appear"], gain=0.4, pan=-0.7)
    place(fx, whoosh(0.8, 300, 1800, peak=0.55, bandwidth=1.2), CUES["sphere_sweep"] - 0.05, gain=1.2)
    # 04.10–05.20 quiet staggered card arrivals
    for k, at in enumerate(CUES["cards"]):
        place(fx, tick(700 + 60 * k, 0.07), at + 0.12, gain=0.45, pan=-0.6 + 0.3 * k)
        place(fx, thump(90, 0.18), at + 0.12, gain=0.16)
    # 06.60 navigation tick (+ pill highlight)
    place(fx, tick(2100, 0.035), CUES["nav_tick"], gain=0.8, pan=0.3)
    place(fx, tick(1600, 0.04), CUES["pill"], gain=0.5, pan=-0.2)
    # 08.30–10.10 filtered scrolling air following the scroll speed
    morph, s0, ac, fa, de = CUES["scroll"]
    t = t_axis(N)
    ss = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
    speed = np.where(t < s0, 0.12 * ss((t - morph) / 0.5), 0.0)
    speed += np.where((t >= s0) & (t < s0 + ac), ss((t - s0) / ac), 0)
    speed += np.where((t >= s0 + ac) & (t < s0 + ac + fa), 1.0, 0)
    speed += np.where(t >= s0 + ac + fa, 1 - ss((t - s0 - ac - fa) / de), 0)
    speed = np.where(t > s0 + ac + fa + de, 0, speed)
    air = noise(N, stereo=True)
    air = sweep_lp(air, 400 + 3400 * speed)
    air = hp(air, 150) * (speed[:, None] ** 1.3)
    fx += 0.36 * air
    # 10.40 low, restrained selection impact
    place(fx, thump(52, 0.9), CUES["impact"], gain=0.45)
    place(fx, lp(noise(int(0.12 * SR)), 1800) * np.exp(-t_axis(int(0.12 * SR)) / 0.03), CUES["impact"], gain=0.08)
    for k, at in enumerate(CUES["chips"]):
        place(fx, tick(1300 + 120 * k, 0.03), at, gain=0.3, pan=0.6)
    # 13.10 smooth frame-expansion sweep (+ the edge wipe)
    place(fx, whoosh(0.7, 350, 2400, peak=0.5, bandwidth=1.3), CUES["frame_sweep"] - 0.05, gain=1.1)
    place(fx, whoosh(0.5, 1200, 500, peak=0.4, bandwidth=1.4), CUES["frame_sweep"] + 0.22, gain=0.4)
    # 15.50 soft capsule formation: inward sweep resolving into a rounded tone
    place(fx, whoosh(0.5, 2600, 400, peak=0.35, bandwidth=1.2), CUES["capsule"] - 0.02, gain=0.7)
    place(fx, thump(110, 0.35), CUES["capsule"] + 0.42, gain=0.14)
    place(fx, bell(72, 1.0), CUES["capsule"] + 0.44, gain=0.08)
    # 17.00 final transition whoosh (riser from the capsule expansion at 16.70)
    place(fx, whoosh(0.9, 200, 3200, peak=0.62, bandwidth=1.3), 16.45, gain=0.8)
    place(fx, thump(44, 0.9), CUES["final_whoosh"], gain=0.2)
    return add_reverb(fx, wet=0.18)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    music = build_music()
    sfx = build_sfx()
    mix = music + 0.85 * sfx
    # smooth ending: final chord decays, cosine fade over the last 0.8 s to exactly zero at 20.00
    fade = np.ones(N)
    k = int(0.8 * SR)
    fade[-k:] = np.cos(np.linspace(0, np.pi / 2, k)) ** 2
    for x in (music, sfx, mix):
        x *= fade[:, None]
    peak = np.max(np.abs(mix))
    scale = 0.5 / peak  # unmastered headroom; master-audio.py sets loudness
    stems = OUT / "stems"
    stems.mkdir(exist_ok=True)
    to16 = lambda x: np.round(np.clip(x, -1, 1) * 32767).astype(np.int16)
    wavfile.write(stems / "music.wav", SR, to16(music * scale))  # 16-bit stems for remixing
    wavfile.write(stems / "sfx.wav", SR, to16(0.85 * sfx * scale))
    wavfile.write(OUT / "mix-unmastered.wav", SR, (mix * scale).astype(np.float32))
    print(f"wrote {N} samples ({N / SR:.3f} s) to {OUT}")


if __name__ == "__main__":
    main()
