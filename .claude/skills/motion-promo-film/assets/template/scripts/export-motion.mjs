#!/usr/bin/env node
// Samples the film's GSAP timeline at 500 Hz and writes the position of everything that moves, so the
// soundtrack's swooshes can follow the picture's real speeds and screen positions.
// The page declares what to sample: window.__motionChannels = [[name, selector, property], ...], where property
// is a GSAP property ('x', 'y', 'scale', 'rotation'...) or 'cx' / 'cy': the element's on-screen centre in stage
// pixels, which includes every parent transform and works for any animation library.
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
const TYPES = { '.svg': 'image/svg+xml', '.html': 'text/html', '.js': 'text/javascript', '.otf': 'font/otf', '.woff2': 'font/woff2' };

const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const file = path.join(ROOT, path.normalize(rel).replace(/^([/\\])+/, ''));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404).end(); return; }
  const type = TYPES[path.extname(file)];
  res.writeHead(200, type ? { 'Content-Type': type } : {});
  fs.createReadStream(file).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('pageerror', e => { console.error('[page error]', e.message); process.exitCode = 1; });
await page.goto(`http://127.0.0.1:${server.address().port}/index.html?render`);
await page.evaluate(() => window.__ready);
await page.setViewportSize(await page.evaluate(() => ({ width: window.__width || 1920, height: window.__height || 1080 })));

const data = await page.evaluate(rate => {
  const channels = window.__motionChannels || [];
  const tl = window.__timeline;
  const go = tl ? t => tl.seek(t, false) : t => { window.seek(t); };   // pages without a GSAP timeline use their seek
  const read = (sel, prop) => {
    if (prop === 'cx' || prop === 'cy') {
      const r = document.querySelector(sel).getBoundingClientRect();
      return prop === 'cx' ? r.left + r.width / 2 : r.top + r.height / 2;
    }
    return parseFloat(gsap.getProperty(sel, prop)) || 0;
  };
  const total = Math.round(window.__duration * rate);
  const out = {};
  for (const [name] of channels) out[name] = new Array(total + 1);
  for (let i = 0; i <= total; i++) {
    go(i / rate);
    for (const [name, sel, prop] of channels) out[name][i] = Math.round(read(sel, prop) * 1000) / 1000;
  }
  window.seek(0);
  return { duration: window.__duration, channels: out };
}, RATE);

if (!Object.keys(data.channels).length) throw new Error('window.__motionChannels is empty — declare the channels to sample in index.html');
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ rate: RATE, duration: data.duration, channels: data.channels }));
console.log(`motion: ${Object.keys(data.channels).length} channels × ${Object.values(data.channels)[0].length} samples → ${path.relative(ROOT, OUT)}`);
await browser.close();
server.close();
