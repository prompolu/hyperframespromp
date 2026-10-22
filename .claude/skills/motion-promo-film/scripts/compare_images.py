#!/usr/bin/env python3
"""Compare two frames: pixel differences and, for logo checks, the ink bounding box and ink pixel count.

    python3 compare_images.py final.png reference.png [--box 520,470,1400,612] [--ink 120]

Use it to prove a last frame matches the brand file: render a reference page that shows the original SVG
as an <img> at the exact intended box over the same background, screenshot it with the same Chromium,
then compare. Identical ink bounding boxes and an ink count within ~0.1 % mean the logo matches; the
remaining differences are sub-pixel anti-aliasing (inline SVG vs <img> snap differently).
"""
import argparse

import numpy as np
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--box', help='x0,y0,x1,y1 region for the ink comparison (default: whole frame)')
    ap.add_argument('--ink', type=int, default=120, help='luminance below this counts as ink (dark logo on light)')
    ap.add_argument('--light', action='store_true', help='ink is light on a dark background')
    a = ap.parse_args()
    A = np.asarray(Image.open(a.a).convert('RGB')).astype(int)
    B = np.asarray(Image.open(a.b).convert('RGB')).astype(int)
    if A.shape != B.shape:
        raise SystemExit(f'size mismatch {A.shape} vs {B.shape}')
    d = np.abs(A - B)
    print(f'whole frame: max diff {d.max()}, mean {d.mean():.4f}, pixels differing by >2: {int((d.max(axis=2) > 2).sum())}')
    x0, y0, x1, y1 = map(int, a.box.split(',')) if a.box else (0, 0, A.shape[1], A.shape[0])
    for name, im in (('a', A), ('b', B)):
        lum = im[y0:y1, x0:x1].mean(axis=2)
        mask = lum > a.ink if a.light else lum < a.ink
        ys, xs = np.where(mask)
        if len(xs):
            print(f'{name}: ink pixels {int(mask.sum())}, bbox x {xs.min() + x0}–{xs.max() + x0}, y {ys.min() + y0}–{ys.max() + y0}')
        else:
            print(f'{name}: no ink found in the region')


if __name__ == '__main__':
    main()
