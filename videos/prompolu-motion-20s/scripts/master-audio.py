#!/usr/bin/env python3
"""Master assets/audio/mix-unmastered.wav to about -16 LUFS integrated, true peak <= -1 dBTP.

Loudness is measured with FFmpeg's EBU R128 meter; peaks are held by a 4x-oversampled
look-ahead limiter. Output: assets/audio/prompolu-soundtrack.wav (48 kHz, 24-bit, stereo).

    python scripts/master-audio.py   (needs numpy, scipy, ffmpeg)
"""
import re
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d
from scipy.signal import resample_poly

AUDIO = Path(__file__).resolve().parent.parent / "assets" / "audio"
TARGET_LUFS = -16.0
CEILING_DBTP = -1.5  # leaves margin for AAC encoding


def measure(path):
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    summary = out[out.rfind("Summary:"):]
    lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary).group(1))
    return lufs, tp


def true_peak_limit(x, sr, ceiling_db, lookahead=0.003, release=0.08):
    ceiling = 10 ** (ceiling_db / 20)
    over = np.max(np.abs(resample_poly(x, 4, 1, axis=0)), axis=1)
    peak = over[: len(over) // 4 * 4].reshape(-1, 4).max(axis=1)
    peak = np.pad(peak, (0, len(x) - len(peak)), mode="edge")
    gain = np.minimum(1.0, ceiling / np.maximum(peak, 1e-9))
    la = max(1, int(lookahead * sr))
    gain = minimum_filter1d(gain, size=2 * la + 1, mode="nearest")
    a = np.exp(-1.0 / (release * sr))
    red = 1.0 - gain
    out = np.empty_like(red)
    acc = 0.0
    for i, r in enumerate(red):  # instant attack (look-ahead), exponential release
        acc = r if r > acc else a * acc
        out[i] = acc
    return x * (1.0 - out)[:, None]


def main():
    src = AUDIO / "mix-unmastered.wav"
    sr, x = wavfile.read(src)
    x = x.astype(np.float64)
    lufs, tp = measure(src)
    print(f"unmastered: {lufs:.2f} LUFS, true peak {tp:.2f} dBTP")
    tmp = AUDIO / "_master-tmp.wav"
    for _ in range(4):
        x = x * 10 ** ((TARGET_LUFS - lufs) / 20)
        x = true_peak_limit(x, sr, CEILING_DBTP)
        wavfile.write(tmp, sr, x.astype(np.float32))
        lufs, tp = measure(tmp)
        print(f"pass: {lufs:.2f} LUFS, true peak {tp:.2f} dBTP")
        if abs(lufs - TARGET_LUFS) < 0.15 and tp <= -1.0:
            break
    dst = AUDIO / "prompolu-soundtrack.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-c:a", "pcm_s24le", str(dst)], check=True)
    tmp.unlink()
    lufs, tp = measure(dst)
    print(f"master: {dst.name}: {lufs:.2f} LUFS integrated, true peak {tp:.2f} dBTP")


if __name__ == "__main__":
    main()
