#!/usr/bin/env python3
"""See a soundtrack you cannot hear: music-vs-effects balance, spectrogram, waveform, every cue marked.

    python3 analyze_audio.py --master assets/audio/soundtrack.wav --cues cues.txt --out evidence/soundtrack-analysis.png \\
        [--music renders/work-audio/music.wav --sfx renders/work-audio/sfx.wav]      # stems: compose-soundtrack.py --stems

Prints per-cue short-term peaks, octave-band balance, clipping, DC and L/R correlation.
What good looks like: effects (red) peak 6–12 dB above the bed (blue) at every transition; bed steady
around −20 LUFS short-term before mastering; 63 Hz band not far above 1 kHz; no clipped samples.
Needs numpy, scipy, matplotlib.
"""
import argparse
import wave

import numpy as np
from scipy import signal


def read(path):
    w = wave.open(str(path))
    n, sw, ch, sr = w.getnframes(), w.getsampwidth(), w.getnchannels(), w.getframerate()
    raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        v = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)
        v = np.where(v >= 1 << 23, v - (1 << 24), v) / 8388608.0
    elif sw == 2:
        v = np.frombuffer(raw, '<i2') / 32768.0
    else:
        v = np.frombuffer(raw, '<i4') / 2147483648.0
    return v.reshape(-1, ch).T, sr


def kweight(x, sr):
    # BS.1770 K-weighting (coefficients for 48 kHz)
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1, -2, 1], [1, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=1), axis=1)


def short_term(x, sr, win=0.1, hop=0.005):
    sq = np.mean(kweight(x, sr) ** 2, axis=0) * 2
    w, h = int(win * sr), int(hop * sr)
    c = np.convolve(sq, np.ones(w) / w, mode='same')
    return np.arange(0, len(c), h) / sr, -0.691 + 10 * np.log10(c[::h] + 1e-12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', required=True)
    ap.add_argument('--music')
    ap.add_argument('--sfx')
    ap.add_argument('--cues')
    ap.add_argument('--out', default='soundtrack-analysis.png')
    a = ap.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    x, sr = read(a.master)
    dur = x.shape[1] / sr
    cues = []
    if a.cues:
        for line in open(a.cues, encoding='utf-8'):
            if line.strip() and not line.startswith('#'):
                t, label = line.rstrip('\n').split('\t', 1)
                cues.append((float(t), label))
    fig, ax = plt.subplots(3, 1, figsize=(22, 13), gridspec_kw={'height_ratios': [1.2, 1.3, 1]})
    curves = [(x, 'master', 'k')]
    if a.music:
        curves.append((read(a.music)[0], 'music', 'tab:blue'))
    if a.sfx:
        sfx = read(a.sfx)[0]
        curves.append((sfx, 'effects + reverb', 'tab:red'))
    for sig, label, col in curves:
        t, l = short_term(sig, sr)
        ax[0].plot(t, l, col, lw=1, label=label + ' (100 ms)')
    ax[0].set_ylim(-50, -5)
    ax[0].set_ylabel('LUFS (short)')
    ax[0].legend(loc='lower left')
    ax[0].grid(alpha=0.3)
    for tc, label in cues:
        for axis in ax:
            axis.axvline(tc, color='tab:green', alpha=0.35, lw=0.8)
        ax[0].text(tc, -6, label[:30], rotation=90, fontsize=6.5, va='top')
    f, tt, S = signal.spectrogram(x.mean(axis=0), sr, nperseg=2048, noverlap=1792)
    ax[1].pcolormesh(tt, f, 10 * np.log10(S + 1e-14), shading='auto', vmin=-130, vmax=-40, cmap='magma')
    ax[1].set_yscale('symlog', linthresh=200)
    ax[1].set_ylim(20, sr / 2)
    tx = np.arange(x.shape[1]) / sr
    ax[2].plot(tx, x[0], lw=0.3, c='tab:blue')
    ax[2].plot(tx, x[-1], lw=0.3, c='tab:orange', alpha=0.6)
    ax[2].set_ylim(-1, 1)
    ax[2].grid(alpha=0.3)
    for axis in ax:
        axis.set_xlim(0, dur)
    plt.tight_layout()
    plt.savefig(a.out, dpi=70)
    print(f'plot → {a.out}')

    if a.sfx and cues:
        k = int(0.01 * sr)
        r = 10 * np.log10(np.convolve(np.mean(sfx ** 2, axis=0), np.ones(k) / k, mode='same') + 1e-12)
        print('effects short-term peak in the 250 ms after each cue:')
        for tc, label in cues:
            seg = r[int(tc * sr):int((tc + 0.25) * sr)]
            if len(seg):
                print(f'  {tc:6.2f}  {seg.max():6.1f} dB  {label}')
    spec = np.abs(np.fft.rfft(x.mean(axis=0) * np.hanning(x.shape[1]))) ** 2
    fr = np.fft.rfftfreq(x.shape[1], 1 / sr)
    bands = []
    for c in [63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]:
        m = (fr >= c / 2 ** 0.5) & (fr < c * 2 ** 0.5)
        bands.append(f'{c}:{10 * np.log10(spec[m].sum() + 1e-20):.1f}')
    print('octave bands (dB, relative):', '  '.join(bands))
    print('clipped samples:', int((np.abs(x) >= 0.999).sum()), ' max', round(float(np.abs(x).max()), 3),
          ' DC', [round(float(v), 5) for v in x.mean(axis=1)],
          ' L/R correlation', round(float(np.corrcoef(x[0], x[-1])[0, 1]), 3) if x.shape[0] > 1 else '-')


if __name__ == '__main__':
    main()
