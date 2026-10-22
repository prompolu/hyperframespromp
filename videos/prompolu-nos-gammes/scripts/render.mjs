#!/usr/bin/env node
// Frame-accurate renderer for index.html.
// Headless Chromium (Playwright) seeks the paused GSAP timeline to t = frame / 30, screenshots each
// frame as PNG and pipes it to FFmpeg (libx264, yuv420p, CRF 16, +faststart, BT.709 tagged).
//
//   node scripts/render.mjs                         → renders/prompolu-nos-gammes-1920x1080.mp4
//   node scripts/render.mjs --out renders/x.mp4     → custom output path
//   node scripts/render.mjs --stills 0.5,2.3,9.97   → PNG stills in renders/stills/ (no video)
//   node scripts/render.mjs --frames 60-120         → render only that frame range (inclusive)
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const W = 1920, H = 1080, FPS = 30;

const opts = {};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith('--')) opts[a.slice(2)] = process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[++i] : true;
}
const OUT = path.resolve(ROOT, opts.out || 'renders/prompolu-nos-gammes-1920x1080.mp4');

/* Static file server, so the page loads over http:// exactly like a browser preview. */
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.otf': 'font/otf',
};
const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const file = path.join(ROOT, path.normalize(rel).replace(/^([/\\])+/, ''));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const url = `http://127.0.0.1:${server.address().port}/index.html?render`;

const browser = await chromium.launch({
  args: ['--force-color-profile=srgb', '--hide-scrollbars', '--font-render-hinting=none', '--disable-lcd-text'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
let pageFailed = false;
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log(`[page ${m.type()}] ${m.text()}`); });
page.on('pageerror', e => { pageFailed = true; console.error('[page error]', e.message); });
page.on('requestfailed', r => console.log('[request failed]', r.url()));

await page.goto(url, { waitUntil: 'load' });
await page.evaluate(() => window.__ready);           // fonts loaded, every image decoded, timeline built
if (pageFailed) throw new Error('page script error, aborting');
const duration = await page.evaluate(() => window.__duration);
const total = Math.round(duration * FPS);            // 10.00 s → 300 frames
const seek = t => page.evaluate(v => window.seek(v), t);
const shot = () => page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: W, height: H } });

const t0 = Date.now();
if (opts.stills) {
  const dir = path.resolve(ROOT, opts.dir || 'renders/stills');
  fs.mkdirSync(dir, { recursive: true });
  for (const v of String(opts.stills).split(',')) {
    const t = Number(v);
    await seek(t);
    const f = path.join(dir, `t${t.toFixed(3).padStart(6, '0')}.png`);
    fs.writeFileSync(f, await shot());
    console.log('still', f);
  }
} else {
  let [first, last] = [0, total - 1];
  if (opts.frames) [first, last] = String(opts.frames).split('-').map(Number);
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const ff = spawn('ffmpeg', [
    '-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
    '-r', String(FPS), '-movflags', '+faststart', OUT,
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => ff.on('close', c => (c === 0 ? res() : rej(new Error(`ffmpeg exited ${c}`)))));
  for (let f = first; f <= last; f++) {
    await seek(f / FPS);
    const buf = await shot();
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 30 === 0) console.log(`frame ${f}/${last}  ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  }
  ff.stdin.end();
  await done;
  console.log(`wrote ${OUT}  (${last - first + 1} frames, ${((Date.now() - t0) / 1000).toFixed(1)}s)`);
}

await browser.close();
server.close();
if (pageFailed) process.exitCode = 1;
