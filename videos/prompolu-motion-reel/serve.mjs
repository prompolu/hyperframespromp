// Shared plumbing for render.mjs and sfx.mjs: a static HTTP server for this folder and a Playwright page
// opener. index.html loads Google Fonts and GSAP from the web; the headless browser gets those files from
// .cache/net/ (filled once with curl, which goes through the machine's proxy), so every render uses the
// same bytes and works offline after the first run.
//
//   node serve.mjs            → preview server on http://127.0.0.1:4173/?play  (real time, loops)
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

export const ROOT = path.dirname(fileURLToPath(import.meta.url));
const CACHE = path.join(ROOT, '.cache/net');
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.json': 'application/json', '.woff2': 'font/woff2',
};
const REMOTE = /^https:\/\/(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com)\//;
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36';

export function startServer(port = 0) {
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    const file = path.join(ROOT, path.normalize(rel === '/' ? '/index.html' : rel).replace(/^([/\\])+/, ''));
    if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise(r => server.listen(port, '127.0.0.1', () => r(server)));
}

function cached(url) {
  const key = crypto.createHash('sha1').update(url).digest('hex');
  const body = path.join(CACHE, key), meta = body + '.type';
  if (!fs.existsSync(body)) {
    fs.mkdirSync(CACHE, { recursive: true });
    const hdr = execFileSync('curl', ['-sS', '-f', '-L', '-A', UA, '-o', body, '-D', '-', url], { encoding: 'utf8' });
    const type = [...hdr.matchAll(/^content-type:\s*(.+)$/gim)].pop();
    fs.writeFileSync(meta, type ? type[1].trim() : 'application/octet-stream');
  }
  return { body: fs.readFileSync(body), contentType: fs.readFileSync(meta, 'utf8') };
}

// Opens index.html in a fresh page, waits for window.__ready (fonts, logo decode, timeline) and returns it.
export async function openFilm(browser, query = 'render', file = 'index.html') {
  const server = await startServer();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log(`[page ${m.type()}] ${m.text()}`); });
  page.on('pageerror', e => { console.error('[page error]', e.message); process.exitCode = 1; });
  await page.route(REMOTE, async route => {
    try {
      const { body, contentType } = cached(route.request().url());
      await route.fulfill({ status: 200, body, contentType, headers: { 'access-control-allow-origin': '*' } });
    } catch (e) {
      console.error('[net]', route.request().url(), e.message);
      await route.abort();
    }
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/${file}?${query}`, { waitUntil: 'load' });
  await page.evaluate(() => window.__ready);
  return { page, server };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const server = await startServer(4173);
  console.log('preview: http://127.0.0.1:4173/?play   (or ?t=4.55 to freeze a moment)');
  process.on('SIGINT', () => { server.close(); process.exit(0); });
}
