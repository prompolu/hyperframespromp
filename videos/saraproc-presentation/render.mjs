#!/usr/bin/env node
// Frame-accurate renderer for index.html (1920×1080, 16:9, 30 fps, 6840 frames = 3:48).
// A local static HTTP server serves this folder; headless Chromium waits for document.fonts.ready, the images and the
// timeline (window.__ready). For every frame i it captures 4 sub-frames at t = i/30 + k/120 and streams them as PNG
// straight into FFmpeg, which averages each group of 4 (tmix=frames=4, motion blur), keeps one frame in four and
// encodes H.264 (CRF 16, BT.709). Nothing large is written to disk: the film is rendered in 8 s chunks
// (work/chunks/c_0000.mp4 …) by a pool of workers, and a re-run skips the chunks already finished.
// The chunks are then joined without re-encoding and muxed with soundtrack.wav (AAC 192 kb/s).
//
//   node render.mjs                              → out.mp4 (master) + out-web.mp4 (lighter) + poster.jpg
//   node render.mjs --stills 2.5,63.2,227        → stills/t_02.500.png … (instantaneous, no sub-frames)
//   node render.mjs --workers 4 --fresh          → discard finished chunks and render everything again
//   node render.mjs --mux                         → only join the chunks and mux the current soundtrack.wav
import { chromium } from 'playwright';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, openFilm } from './serve.mjs';

const opts = {};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith('--')) opts[a.slice(2)] = process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[++i] : true;
}
const W = 1920, H = 1080, FPS = 30, SUB = 4, TOTAL = 6840, CHUNK = 240;
const VIEW = { width: W, height: H };
const ARGS = ['--force-color-profile=srgb', '--hide-scrollbars', '--font-render-hinting=none', '--disable-lcd-text'];
const t0 = Date.now();
const secs = () => ((Date.now() - t0) / 1000).toFixed(1) + 's';
const COLOR = ['-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv'];

function ffmpeg(args) {
  const r = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', ...args], { stdio: 'inherit' });
  if (r.status !== 0) throw new Error('ffmpeg failed: ' + args.join(' '));
}

if (opts.stills) {
  const dir = path.resolve(ROOT, typeof opts.dir === 'string' ? opts.dir : 'stills');
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ args: ARGS });
  const { page, server } = await openFilm(browser, 'render', 'index.html', VIEW);
  for (const v of String(opts.stills).split(',')) {
    const t = Number(v);
    await page.evaluate(x => window.seek(x).then(() => undefined), t);
    const f = path.join(dir, `t_${t.toFixed(3).padStart(6, '0')}.png`);
    await page.screenshot({ path: f, type: 'png', clip: { x: 0, y: 0, width: W, height: H } });
    console.log('still', path.relative(ROOT, f));
  }
  await browser.close(); server.close();
  process.exit(process.exitCode || 0);
}

// ---- full render, in chunks ----
const CH = path.join(ROOT, 'work', 'chunks');
if (opts.fresh) fs.rmSync(CH, { recursive: true, force: true });
fs.mkdirSync(CH, { recursive: true });
const chunks = [];
for (let a = 0; a < TOTAL; a += CHUNK) chunks.push({ a, b: Math.min(TOTAL, a + CHUNK) - 1, file: path.join(CH, `c_${String(a).padStart(4, '0')}.mp4`) });
const todo = opts.mux ? [] : chunks.filter(c => !fs.existsSync(c.file));
console.log(`${chunks.length} chunks of ${CHUNK} frames; ${todo.length} to render`);

let done = 0;
function encoder(file) {
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS * SUB), '-c:v', 'png', '-i', '-',
    '-vf', `tmix=frames=${SUB}:weights=1 1 1 1,select='eq(mod(n\\,${SUB})\\,${SUB - 1})',setpts=N/${FPS}/TB,scale=out_color_matrix=bt709:out_range=tv,format=yuv420p`,
    '-r', String(FPS), '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p', ...COLOR, file],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const exit = new Promise((res, rej) => ff.on('close', code => (code === 0 ? res() : rej(new Error('ffmpeg exited ' + code)))));
  const write = buf => (ff.stdin.write(buf) ? Promise.resolve() : new Promise(r => ff.stdin.once('drain', r)));
  return { write, end: () => { ff.stdin.end(); return exit; } };
}
async function worker() {
  const browser = await chromium.launch({ args: ARGS });
  const { page, server } = await openFilm(browser, 'render', 'index.html', VIEW);
  const cdp = await page.context().newCDPSession(page);
  for (let c; (c = todo.shift());) {
    const tmp = c.file.replace('.mp4', '.part.mp4'), enc = encoder(tmp);
    for (let i = c.a; i <= c.b; i++) {
      for (let k = 0; k < SUB; k++) {
        await page.evaluate(x => window.seek(x).then(() => undefined), i / FPS + k / (FPS * SUB));
        const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true, clip: { x: 0, y: 0, width: W, height: H, scale: 1 } });
        await enc.write(Buffer.from(data, 'base64'));
      }
      if (++done % 120 === 0) console.log(`  ${done} frames  ${secs()}`);
    }
    await enc.end();
    fs.renameSync(tmp, c.file);
    console.log(`chunk ${path.basename(c.file)} (${c.a}–${c.b}) done  ${secs()}`);
  }
  await browser.close(); server.close();
}
const WORKERS = Number(opts.workers || 4);
await Promise.all(Array.from({ length: Math.min(WORKERS, todo.length) }, worker));
const missing = chunks.filter(c => !fs.existsSync(c.file));
if (missing.length) throw new Error(`${missing.length} chunks missing`);

// Join (no re-encode), mux the soundtrack, then the lighter web version and the poster.
const list = path.join(CH, 'list.txt');
fs.writeFileSync(list, chunks.map(c => `file '${c.file}'`).join('\n') + '\n');
const AUDIO = path.join(ROOT, 'soundtrack.wav');
const withAudio = !opts['no-audio'] && fs.existsSync(AUDIO);
const OUT = path.join(ROOT, 'out.mp4');
ffmpeg(['-f', 'concat', '-safe', '0', '-i', list, ...(withAudio ? ['-i', AUDIO, '-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-shortest'] : []),
  '-c:v', 'copy', '-movflags', '+faststart', OUT]);
console.log(`wrote out.mp4 (${TOTAL} frames${withAudio ? ', AAC 192k' : ''})  ${secs()}`);
ffmpeg(['-i', OUT, '-map', '0', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '23', '-preset', 'slow', '-profile:v', 'high', ...COLOR,
  ...(withAudio ? ['-c:a', 'aac', '-b:a', '128k'] : []), '-movflags', '+faststart', path.join(ROOT, 'out-web.mp4')]);
ffmpeg(['-sseof', '-0.1', '-i', OUT, '-frames:v', '1', '-q:v', '3', path.join(ROOT, 'poster.jpg')]);
console.log(`wrote out-web.mp4 and poster.jpg  ${secs()}`);
