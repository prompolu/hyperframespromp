#!/usr/bin/env python3
"""Contact sheet of stills or frames, labelled with their file names — the fastest way to review a film.

    python3 contact_sheet.py sheet.jpg renders/stills/*.png              # 2 columns, 960 px tiles
    python3 contact_sheet.py sheet.jpg --cols 5 --width 384 frames/*.png  # overview of a whole film
    ffmpeg -i film.mp4 -vf "select='not(mod(n\\,10))',scale=384:-1" -vsync 0 frames/f%03d.png   # every 10th frame
Needs Pillow.
"""
import argparse
import os

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('images', nargs='+')
    ap.add_argument('--cols', type=int, default=2)
    ap.add_argument('--width', type=int, default=960, help='tile width in px')
    ap.add_argument('--labels', nargs='*', help='optional labels, one per image (default: file names)')
    a = ap.parse_args()
    first = Image.open(a.images[0])
    tw = a.width
    th = round(tw * first.height / first.width)
    rows = (len(a.images) + a.cols - 1) // a.cols
    sheet = Image.new('RGB', (a.cols * tw, rows * (th + 20)), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(a.images):
        im = Image.open(f).convert('RGB').resize((tw, th), Image.LANCZOS)
        x, y = (i % a.cols) * tw, (i // a.cols) * (th + 20)
        sheet.paste(im, (x, y))
        label = a.labels[i] if a.labels and i < len(a.labels) else os.path.basename(f)
        d.text((x + 6, y + th + 4), label, fill=(255, 255, 255))
    sheet.save(a.out, quality=88)
    print(f'{a.out}: {len(a.images)} images, {a.cols} columns')


if __name__ == '__main__':
    main()
