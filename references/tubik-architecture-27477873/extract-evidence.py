"""Extract attributed study sheets; source MP4 remains outside the repository.

Usage: python extract-evidence.py /path/to/reference.mp4
Requires FFmpeg and Pillow. Labels are absolute source-video timestamps.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io
import math
import subprocess
import sys

source = Path(sys.argv[1])
out = Path(__file__).resolve().parent / 'evidence'
out.mkdir(exist_ok=True)
font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font = ImageFont.truetype(font_path, 17)
small = ImageFont.truetype(font_path, 13)

def sheet(name, times, columns):
    width, height, caption, footer = 480, 360, 28, 34
    rows = math.ceil(len(times) / columns)
    image = Image.new('RGB', (width * columns, (height + caption) * rows + footer), '#F1F0EC')
    draw = ImageDraw.Draw(image)
    # One decode pass, preserving the supplied absolute timestamps in selection.
    expression = '+'.join(f'eq(n,{round(t * 60)})' for t in times)
    data = subprocess.run([
        'ffmpeg', '-v', 'error', '-i', str(source), '-vf',
        f"select='{expression}',scale={width}:{height}", '-fps_mode', 'vfr',
        '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '3', '-'
    ], check=True, capture_output=True).stdout
    frames = [chunk + b'\xff\xd9' for chunk in data.split(b'\xff\xd9') if chunk]
    if len(frames) != len(times):
        raise RuntimeError(f'{name}: expected {len(times)} frames, received {len(frames)}')
    for i, (t, frame) in enumerate(zip(times, frames)):
        x, y = (i % columns) * width, (i // columns) * (height + caption)
        image.paste(Image.open(io.BytesIO(frame)).convert('RGB'), (x, y + caption))
        draw.text((x + 10, y + 4), f'{t:05.1f} s | original source time', fill='#15171A', font=font)
    draw.text((10, image.height - 25), 'Reference: Tubik / Dribbble 27477873 | study excerpts, not PROMPOLU production assets', fill='#15171A', font=small)
    image.save(out / f'{name}.jpg', quality=87)

sheet('overview', list(range(0, 26, 2)), 4)
sheet('opening', [i / 2 for i in range(12)], 4)
sheet('team', [6 + i / 2 for i in range(13)], 4)
sheet('middle', [12 + i / 2 for i in range(16)], 4)
sheet('ending', [20 + i / 2 for i in range(13)], 4)
print(f'Saved 5 attributed evidence sheets to {out}')
