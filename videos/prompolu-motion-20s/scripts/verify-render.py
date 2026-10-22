#!/usr/bin/env python3
"""Verify the delivered MP4 and extract evidence frames.

Checks container/stream properties, decodes every frame, looks for blank or
black frames, measures the audio (EBU R128 integrated loudness and true peak),
writes the final-frame PNG and a contact sheet of one frame per beat.

    python scripts/verify-render.py [renders/PROMPOLU_Motion_20s_FR.mp4]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MP4 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "renders" / "PROMPOLU_Motion_20s_FR.mp4"
EVID = ROOT / "evidence"
BEATS = [
    ("hook", 1.3), ("dot", 1.85), ("brand", 3.1), ("sphere", 3.8), ("families", 5.6), ("selection", 7.8),
    ("masonry", 9.3), ("detach", 10.3), ("hero", 12.6), ("visualisation", 14.8), ("cta", 16.4),
    ("expansion", 17.0), ("final", 19.9),
]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def main():
    EVID.mkdir(exist_ok=True)
    probe = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_format", "-show_streams", "-of", "json", str(MP4)]).stdout)
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)

    # decode all frames at low resolution to look for blank / black / stuck frames
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(MP4), "-vf", "scale=96:54", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96).astype(np.float32)
    means, stds = frames.mean(axis=(1, 2)), frames.std(axis=(1, 2))
    blank = [int(i) for i in np.where((stds < 1.0) | (means < 8))[0]]
    tail_diff = float(np.abs(frames[-1] - frames[int(17.8 * 30)]).max())

    # audio loudness of the delivered file
    r128 = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(MP4), "-af", "ebur128=peak=true", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    summ = r128[r128.rfind("Summary:"):]
    lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))

    # final frame PNG (frame 600 = index 599) and one frame per beat
    final_png = MP4.with_name(MP4.stem + "_final-frame.png")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(MP4), "-vf", "select=eq(n\\,599)", "-frames:v", "1", str(final_png)])
    fdir = EVID / "frames"
    fdir.mkdir(exist_ok=True)
    for name, t in BEATS:
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t}", "-i", str(MP4), "-frames:v", "1", str(fdir / f"{t:05.2f}-{name}.png")])
    inputs = sum([["-i", str(fdir / f"{t:05.2f}-{name}.png")] for name, t in BEATS], [])
    n = len(BEATS)
    layout = "|".join(f"{(i % 4) * 480}_{(i // 4) * 270}" for i in range(n))
    chain = "".join(f"[{i}:v]scale=480:270,drawtext=text='{t:.2f}s {name}':x=8:y=8:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5[v{i}];"
                    for i, (name, t) in enumerate(BEATS))
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
         chain + "".join(f"[v{i}]" for i in range(n)) + f"xstack=inputs={n}:layout={layout}:fill=black", str(EVID / "contact-sheet.jpg")])

    report = {
        "file": MP4.name,
        "bytes": int(probe["format"]["size"]),
        "container_duration_s": float(probe["format"]["duration"]),
        "video": {"codec": v["codec_name"], "profile": v.get("profile"), "width": v["width"], "height": v["height"],
                  "avg_frame_rate": v["avg_frame_rate"], "frames_decoded": int(v["nb_read_frames"]), "pix_fmt": v["pix_fmt"],
                  "duration_s": float(v.get("duration", 0))},
        "audio": None if a is None else {"codec": a["codec_name"], "channels": a["channels"], "sample_rate": int(a["sample_rate"]),
                                         "duration_s": float(a.get("duration", 0)), "integrated_lufs": lufs, "true_peak_dbtp": tp},
        "frames_scanned": int(len(frames)),
        "blank_or_black_frames": blank,
        "final_hold_max_pixel_change_17.8s_to_20.0s": tail_diff,
        "final_frame_png": final_png.name,
    }
    (EVID / "render-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
