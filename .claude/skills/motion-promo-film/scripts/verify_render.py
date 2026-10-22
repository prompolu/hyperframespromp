#!/usr/bin/env python3
"""Check a finished film and write the facts to a JSON report.

    python3 verify_render.py renders/film-1920x1080.mp4 [--wav assets/audio/soundtrack.wav] [--fps 30] [--duration 10]
                             [--out evidence/verification.json]

Checks: video codec/size/pix_fmt/colour tags, exact frame count and duration, full decode, and when the film
has sound: audio stream format, loudness and true peak after AAC, and the sample offset between the MP4's
audio and the source WAV (must be 0 — a non-zero offset means the mux shifted the sound against the picture).
Needs FFmpeg/ffprobe, numpy, scipy.
"""
import argparse
import json
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy import signal


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def read_wav(path):
    w = wave.open(str(path))
    n, sw, ch = w.getnframes(), w.getsampwidth(), w.getnchannels()
    raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        v = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)
        v = np.where(v >= 1 << 23, v - (1 << 24), v) / 8388608.0
    else:
        v = np.frombuffer(raw, '<i2') / 32768.0
    return v.reshape(-1, ch).T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mp4')
    ap.add_argument('--wav')
    ap.add_argument('--fps', type=float)
    ap.add_argument('--duration', type=float)
    ap.add_argument('--out')
    a = ap.parse_args()
    report, problems = {'file': a.mp4}, []

    probe = json.loads(run(['ffprobe', '-v', 'error', '-count_frames', '-show_entries',
                            'stream=index,codec_type,codec_name,profile,width,height,pix_fmt,r_frame_rate,nb_read_frames,'
                            'sample_rate,channels,duration,bit_rate,color_space,color_primaries,color_transfer,color_range:'
                            'format=duration,size', '-of', 'json', a.mp4]).stdout)
    report['ffprobe'] = probe
    v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    frames = int(v.get('nb_read_frames', 0))
    if a.fps and a.duration and frames != round(a.fps * a.duration):
        problems.append(f'frame count {frames} != {round(a.fps * a.duration)}')
    if v.get('pix_fmt') != 'yuv420p':
        problems.append(f"pix_fmt {v.get('pix_fmt')}")
    if v.get('color_space') != 'bt709':
        problems.append('not tagged BT.709')
    dec = run(['ffmpeg', '-v', 'error', '-i', a.mp4, '-f', 'null', '-'])
    report['full_decode'] = 'ok' if not dec.stderr.strip() else dec.stderr.strip()[:500]
    if dec.stderr.strip():
        problems.append('decode errors')

    audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
    if audio:
        with tempfile.TemporaryDirectory() as d:
            dw = Path(d) / 'decoded.wav'
            run(['ffmpeg', '-v', 'error', '-y', '-i', a.mp4, '-vn', '-acodec', 'pcm_s24le', '-ar', '48000', str(dw)])
            err = run(['ffmpeg', '-nostats', '-hide_banner', '-i', str(dw), '-filter_complex', 'ebur128=peak=true', '-f', 'null', '-']).stderr
            loud = {'integrated_LUFS': float(re.findall(r'I:\s+(-?[\d.]+) LUFS', err)[-1]),
                    'true_peak_dBTP': float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', err)[-1]),
                    'LRA_LU': float(re.findall(r'LRA:\s+(-?[\d.]+) LU', err)[-1])}
            report['audio_after_aac'] = loud
            if loud['true_peak_dBTP'] > -0.9:
                problems.append(f"true peak {loud['true_peak_dBTP']} dBTP")
            if a.wav:
                src, dec_a = read_wav(a.wav), read_wav(dw)
                n = min(src.shape[1], dec_a.shape[1])
                c = signal.correlate(dec_a[0, :n], src[0, :n], mode='full', method='fft')
                lag = int(np.argmax(c) - (n - 1))
                k = abs(lag)
                corr = float(np.corrcoef(src[0, :n - k], dec_a[0, k:n])[0, 1])
                report['audio_sync'] = {'offset_samples': lag, 'offset_ms': round(lag / 48, 3), 'correlation': round(corr, 5)}
                if lag != 0:
                    problems.append(f'audio offset {lag} samples')
    report['problems'] = problems
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
    print(json.dumps({k: report[k] for k in report if k != 'ffprobe'}, indent=2, ensure_ascii=False))
    print(f"video: {v['codec_name']} {v['width']}x{v['height']} {v['pix_fmt']} {frames} frames; audio: "
          f"{audio['codec_name'] + ' ' + audio['sample_rate'] + ' Hz' if audio else 'none'}")
    print('OK' if not problems else 'PROBLEMS: ' + '; '.join(problems))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
