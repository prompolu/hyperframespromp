#!/usr/bin/env node
// Samples the film's GSAP timeline at 500 Hz and writes the positions of everything that moves,
// so the soundtrack's swooshes can follow the picture's real speeds and screen positions.
//
//   node scripts/export-motion.mjs [out.json]      (default renders/work-audio/motion.json)
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.resolve(ROOT, process.argv[2] || 'renders/work-audio/motion.json');
const RATE = 500;

// [channel name, selector, GSAP property]
const CHANNELS = [
  ['mark.y', '#markWrap', 'y'], ['mark.scale', '#mark', 'scale'], ['tile.scale', '#tile', 'scale'],
  ['icon.x', '#icon', 'x'], ['icon.y', '#icon', 'y'], ['icon.scale', '#icon', 'scale'],
  ['camera.x', '#camera', 'x'], ['camera.y', '#camera', 'y'], ['camera.scale', '#camera', 'scale'], ['camera.rotation', '#camera', 'rotation'],
  ['page.scroll', '#pageScroll', 'y'], ['btn.scale', '#btn', 'scale'],
  ['pointer.x', '#pointer', 'x'], ['pointer.y', '#pointer', 'y'],
  ['pill.x', '#pill', 'x'], ['pill.y', '#pill', 'y'], ['pill.rotation', '#pill', 'rotation'], ['pill.width', '#pill', 'width'],
  ['arm.rotation', '#ptileArm', 'rotation'], ['ptile.x', '#ptile', 'x'], ['ptile.y', '#ptile', 'y'], ['ptile.width', '#ptile', 'width'],
  ['badge.x', '#badge', 'x'], ['badge.y', '#badge', 'y'], ['badge.width', '#badge', 'width'],
  ['grid.y', '#grid', 'y'],
  ['card1.y', '#card1', 'y'], ['card1.rotationX', '#card1', 'rotationX'],
  ['card2.y', '#card2', 'y'], ['card2.rotationX', '#card2', 'rotationX'], ['card3.y', '#card3', 'y'],
  ['dropP.x', '#dropP', 'x'], ['dropP.y', '#dropP', 'y'], ['dropP.scale', '#dropP', 'scale'],
  ['sheen.x', '#sheenRect', 'x'], ['logo.x', '#endLogoWrap', 'x'],
  ['bloom.opacity', '#bloom', 'opacity'], ['flash.opacity', '#flash', 'opacity'],
];

const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const file = path.join(ROOT, path.normalize(rel).replace(/^([/\\])+/, ''));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404).end(); return; }
  const type = { '.svg': 'image/svg+xml', '.html': 'text/html', '.js': 'text/javascript', '.otf': 'font/otf' }[path.extname(file)];
  res.writeHead(200, type ? { 'Content-Type': type } : {});
  fs.createReadStream(file).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('pageerror', e => { console.error('[page error]', e.message); process.exitCode = 1; });
await page.goto(`http://127.0.0.1:${server.address().port}/index.html?render`);
await page.evaluate(() => window.__ready);

const data = await page.evaluate(({ channels, rate }) => {
  const tl = window.__timeline;
  const total = Math.round(window.__duration * rate);
  const out = {};
  for (const [name] of channels) out[name] = new Array(total + 1);
  for (let i = 0; i <= total; i++) {
    tl.seek(i / rate, false);
    for (const [name, sel, prop] of channels) out[name][i] = Math.round((parseFloat(gsap.getProperty(sel, prop)) || 0) * 1000) / 1000;
  }
  window.seek(0);
  return out;
}, { channels: CHANNELS, rate: RATE });

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ rate: RATE, duration: 10, channels: data }));
console.log(`motion: ${CHANNELS.length} channels × ${data['grid.y'].length} samples → ${path.relative(ROOT, OUT)}`);
await browser.close();
server.close();
