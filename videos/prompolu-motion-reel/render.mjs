#!/usr/bin/env node
// Frame-accurate renderer for index.html (1920×1080, 60 fps, 600 frames).
// A local static HTTP server serves this folder; headless Chromium waits for document.fonts.ready and the
// logo decode (window.__ready), then for every frame i captures 4 sub-frames at t = i/60 + k/240.
// FFmpeg averages each group of 4 (tmix=frames=4) and keeps every 4th frame → work/frames/f_%04d.png,
// then encodes: ffmpeg -framerate 60 -i f_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 16 -movflags +faststart out.mp4
// (plus BT.709 conversion/tags, and sfx.wav muxed as AAC 192 kb/s when present).
//
//   node render.mjs                              → out.mp4
//   node render.mjs --stills 0.40,1.15,10.00     → stills/t_00.400.png … (instantaneous, no sub-frames)
//   node render.mjs --frames 120-180             → only those frames (writes out-partial.mp4)
//   node render.mjs --workers 3 --no-audio --keep
//   node render.mjs --mux                         → re-encode work/frames with the current sfx.wav (no capture)
import { chromium } from 'playwright';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, openFilm } from './serve.mjs';

const opts = {};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith('--')) opts[a.slice(2)] = process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[++i] : true;
}
const FPS = 60, SUB = 4, TOTAL = 600;
const ARGS = ['--force-color-profile=srgb', '--hide-scrollbars', '--font-render-hinting=none', '--disable-lcd-text'];
const t0 = Date.now();
const secs = () => ((Date.now() - t0) / 1000).toFixed(1) + 's';

function ffmpeg(args) {
  const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', ...args], { stdio: 'inherit' });
  if (r.status !== 0) throw new Error('ffmpeg failed: ' + args.join(' '));
}

if (opts.stills) {
  const dir = path.resolve(ROOT, typeof opts.dir === 'string' ? opts.dir : 'stills');
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ args: ARGS });
  const { page, server } = await openFilm(browser);
  for (const v of String(opts.stills).split(',')) {
    const t = Number(v);
    await page.evaluate(x => window.seek(x).then(() => undefined), t);
    const f = path.join(dir, `t_${t.toFixed(3).padStart(6, '0')}.png`);
    await page.screenshot({ path: f, type: 'png', clip: { x: 0, y: 0, width: 1920, height: 1080 } });
    console.log('still', path.relative(ROOT, f));
  }
  await browser.close(); server.close();
  process.exit(process.exitCode || 0);
}

// ---- full render ----
let [first, last] = [0, TOTAL - 1];
if (opts.frames) [first, last] = String(opts.frames).split('-').map(Number);
const WORKERS = Number(opts.workers || 3);
const WORK = path.join(ROOT, 'work'), SUBDIR = path.join(WORK, 'sub'), FRAMES = path.join(WORK, 'frames');
const n = last - first + 1;
if (!opts.mux) {   // --mux re-encodes the frames already in work/frames (e.g. after a new sfx.wav)
fs.rmSync(SUBDIR, { recursive: true, force: true }); fs.rmSync(FRAMES, { recursive: true, force: true });
fs.mkdirSync(SUBDIR, { recursive: true }); fs.mkdirSync(FRAMES, { recursive: true });
console.log(`frames ${first}-${last} (${n}) × ${SUB} sub-frames, ${WORKERS} workers`);

let done = 0;
async function worker(w) {
  const a = first + Math.floor((n * w) / WORKERS), b = first + Math.floor((n * (w + 1)) / WORKERS) - 1;
  const browser = await chromium.launch({ args: ARGS });
  const { page, server } = await openFilm(browser);
  const cdp = await page.context().newCDPSession(page);
  for (let i = a; i <= b; i++) {
    for (let k = 0; k < SUB; k++) {
      await page.evaluate(x => window.seek(x).then(() => undefined), i / FPS + k / (FPS * SUB));
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true, clip: { x: 0, y: 0, width: 1920, height: 1080, scale: 1 } });
      fs.writeFileSync(path.join(SUBDIR, `s_${String((i - first) * SUB + k).padStart(5, '0')}.png`), Buffer.from(data, 'base64'));
    }
    if (++done % 30 === 0) console.log(`  ${done}/${n} frames  ${secs()}`);
  }
  await browser.close(); server.close();
}
await Promise.all(Array.from({ length: WORKERS }, (_, w) => worker(w)));
console.log(`sub-frames captured  ${secs()}`);

// Average the 4 sub-frames of each frame, keep one frame in four.
ffmpeg(['-framerate', String(FPS * SUB), '-i', path.join(SUBDIR, 's_%05d.png'),
  '-vf', `tmix=frames=${SUB}:weights=1 1 1 1,select='eq(mod(n\\,${SUB})\\,${SUB - 1})'`,
  '-fps_mode', 'passthrough', '-start_number', String(first), path.join(FRAMES, 'f_%04d.png')]);
const made = fs.readdirSync(FRAMES).length;
if (made !== n) throw new Error(`expected ${n} averaged frames, got ${made}`);
if (!opts.keep) fs.rmSync(SUBDIR, { recursive: true, force: true });
console.log(`averaged → work/frames/f_%04d.png (${made})  ${secs()}`);
}

// Encode (the brief's x264 settings), BT.709 matrix and tags, sfx.wav as AAC 192 kb/s.
const AUDIO = path.join(ROOT, 'sfx.wav');
const withAudio = !opts['no-audio'] && fs.existsSync(AUDIO);
const OUT = path.join(ROOT, typeof opts.out === 'string' ? opts.out : (opts.frames ? 'out-partial.mp4' : 'out.mp4'));
ffmpeg([
  '-framerate', String(FPS), '-start_number', String(first), '-i', path.join(FRAMES, 'f_%04d.png'),
  ...(withAudio ? ['-ss', (first / FPS).toFixed(6), '-t', (n / FPS).toFixed(6), '-i', AUDIO, '-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2'] : []),
  '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'slow',
  '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
  '-r', String(FPS), '-movflags', '+faststart', OUT,
]);
console.log(`wrote ${path.relative(ROOT, OUT)} (${n} frames${withAudio ? ', AAC 192k' : ''})  ${secs()}`);
