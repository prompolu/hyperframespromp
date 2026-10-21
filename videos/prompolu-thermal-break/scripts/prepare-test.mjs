import { readFile, writeFile, mkdir, cp } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const source = await readFile(new URL('index.html', root), 'utf8');
if (!source.includes('design-canvas') || !source.includes('--render-scale')) {
  throw new Error('Expected the full-size composition design-canvas scale wrapper.');
}
// This is the same editable composition at half scale, rendered by HyperFrames.
// HyperFrames 0.8.183 has no arbitrary downscale flag, so use an explicit entry.
let proof = source
  .replace(/data-width="1080"/g, 'data-width="540"')
  .replace(/data-height="1920"/g, 'data-height="960"')
  .replace(/width=1080,\s*height=1920/g, 'width=540, height=960');
proof = proof.replace('</head>', `<style>
  html, body { width: 540px !important; height: 960px !important; }
  :root { --render-scale: 0.5 !important; }
</style></head>`);
const testRoot = new URL('.hyperframes/test-project/', root);
await mkdir(testRoot, { recursive: true });
await cp(new URL('assets/', root), new URL('assets/', testRoot), { recursive: true });
await cp(new URL('hyperframes.json', root), new URL('hyperframes.json', testRoot));
await cp(new URL('index.motion.json', root), new URL('index.motion.json', testRoot));
const target = new URL('index.html', testRoot);
await writeFile(target, proof);
console.log(`Prepared 540 × 960 HyperFrames render entry: ${fileURLToPath(target)}`);
