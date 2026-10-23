#!/usr/bin/env node
// Procedural soundtrack for the PROMPOLU 9:16 website video: plain PCM synthesis (no samples), written to sfx.wav.
// A minimal electronic groove at 89 BPM (bar 1 on the bronze O at 2.22 s, the logo on bar 5) under motion-driven
// sound effects: the page's own motion (window.motionAt, sampled at 500 Hz) drives every whoosh, each product
// transition gets its own sound (rolling pane, latch, drawer runners, louvre ticks), the reels tick per digit.
//
//   node sfx.mjs                → sfx.wav (48 kHz, 24-bit) + cues.txt (+ work/music.wav, work/fx.wav stems)
//   node sfx.mjs --no-export    → reuse work/motion.json
// Mastered to −15 LUFS integrated, true peak ≤ −1 dBTP (measured with FFmpeg's ebur128).
import { chromium } from 'playwright';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, openFilm } from './serve.mjs';

const SR = 48000, DUR = 15, N = SR * DUR;
const BPM = 89.15, BEAT = 60 / BPM, BAR = 4 * BEAT, T0 = 2.22;   // downbeats 2.22, 4.91, 7.60, 10.30, 12.99 (logo)
const args = new Set(process.argv.slice(2));
const WORK = path.join(ROOT, 'work');
fs.mkdirSync(WORK, { recursive: true });

/* ---------- motion from the page ---------- */
const MOTION = path.join(WORK, 'motion.json');
if (!args.has('--no-export') || !fs.existsSync(MOTION)) {
  const browser = await chromium.launch();
  const { page, server } = await openFilm(browser);
  const m = await page.evaluate(() => {
    const out = {};
    for (let i = 0; i <= 7500; i++) {
      const s = window.motionAt(i / 500);
      for (const k in s) (out[k] ||= []).push(Math.round(s[k] * 1e4) / 1e4);
    }
    return out;
  });
  fs.writeFileSync(MOTION, JSON.stringify({ rate: 500, channels: m }));
  await browser.close(); server.close();
  console.log(`motion: ${Object.keys(m).length} channels × 7501 samples`);
}
const MO = JSON.parse(fs.readFileSync(MOTION, 'utf8'));
const ch = k => MO.channels[k];
const at = (arr, t) => { const x = clamp(t * 500, 0, arr.length - 1), i = Math.floor(x), f = x - i; return arr[i] + (arr[Math.min(i + 1, arr.length - 1)] - arr[i]) * f; };
const deriv = arr => arr.map((v, i) => (arr[Math.min(i + 1, arr.length - 1)] - arr[Math.max(i - 1, 0)]) * 500 / ((i > 0 && i < arr.length - 1) ? 2 : 1));

/* ---------- DSP helpers ---------- */
function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
const db = v => 10 ** (v / 20);
const midi = m => 440 * 2 ** ((m - 69) / 12);
function rng(tag) {           // mulberry32 seeded from an FNV-1a hash of the tag → reproducible noise
  let h = 2166136261; for (const c of tag) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  let a = h >>> 0;
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const ns = s => Math.max(1, Math.round(s * SR));
function white(n, tag) { const r = rng(tag), x = new Float32Array(n); for (let i = 0; i < n; i++) x[i] = r() * 2 - 1; return x; }
function pink(n, tag) {
  const w = white(n, tag), x = new Float32Array(n); let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
  for (let i = 0; i < n; i++) { const v = w[i]; b0 = 0.99886 * b0 + v * 0.0555179; b1 = 0.99332 * b1 + v * 0.0750759; b2 = 0.969 * b2 + v * 0.153852; b3 = 0.8665 * b3 + v * 0.3104856; b4 = 0.55 * b4 + v * 0.5329522; b5 = -0.7616 * b5 - v * 0.016898; x[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + v * 0.5362) * 0.11; b6 = v * 0.115926; }
  return x;
}
function coeffs(kind, f, q = 0.707, gain = 0) {
  const w = 2 * Math.PI * clamp(f, 10, SR * 0.49) / SR, c = Math.cos(w), s = Math.sin(w), a = s / (2 * q), A = 10 ** (gain / 40);
  let b0, b1, b2, a0, a1, a2;
  if (kind === 'lp') { b0 = (1 - c) / 2; b1 = 1 - c; b2 = b0; a0 = 1 + a; a1 = -2 * c; a2 = 1 - a; }
  else if (kind === 'hp') { b0 = (1 + c) / 2; b1 = -(1 + c); b2 = b0; a0 = 1 + a; a1 = -2 * c; a2 = 1 - a; }
  else if (kind === 'bp') { b0 = a; b1 = 0; b2 = -a; a0 = 1 + a; a1 = -2 * c; a2 = 1 - a; }
  else { b0 = 1 + a * A; b1 = -2 * c; b2 = 1 - a * A; a0 = 1 + a / A; a1 = -2 * c; a2 = 1 - a / A; }   // peaking
  return [b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0];
}
// Biquad with a fixed or time-varying frequency (f: number, array per sample, or function of sample index).
function filt(x, kind, f, q = 0.707, gain = 0) {
  const y = new Float32Array(x.length); let x1 = 0, x2 = 0, y1 = 0, y2 = 0, k = coeffs(kind, typeof f === 'number' ? f : 1000, q, gain);
  for (let i = 0; i < x.length; i++) {
    if (typeof f !== 'number' && i % 32 === 0) k = coeffs(kind, typeof f === 'function' ? f(i) : f[i], q, gain);
    const v = k[0] * x[i] + k[1] * x1 + k[2] * x2 - k[3] * y1 - k[4] * y2;
    x2 = x1; x1 = x[i]; y2 = y1; y1 = v; y[i] = v;
  }
  return y;
}
function env(n, attack, tau) { const e = new Float32Array(n), a = ns(attack); for (let i = 0; i < n; i++) e[i] = i < a ? i / a : Math.exp(-(i - a) / (tau * SR)); return e; }
const mul = (x, e) => { const y = new Float32Array(x.length); for (let i = 0; i < x.length; i++) y[i] = x[i] * e[i]; return y; };
const sum = (...xs) => { const y = new Float32Array(Math.max(...xs.map(x => x.length))); for (const x of xs) for (let i = 0; i < x.length; i++) y[i] += x[i]; return y; };
const gain = (x, g) => x.map(v => v * g);
function sine(n, f, ph = 0) { const y = new Float32Array(n); let p = ph; for (let i = 0; i < n; i++) { y[i] = Math.sin(p); p += 2 * Math.PI * (typeof f === 'number' ? f : f(i)) / SR; } return y; }
function saw(n, f, harmonics = 20, ph = 0) {
  const y = new Float32Array(n); const H = Math.max(1, Math.min(harmonics, Math.floor(SR * 0.45 / f)));
  for (let h = 1; h <= H; h++) { const a = (h % 2 ? 1 : -1) / h; for (let i = 0; i < n; i++) y[i] += a * Math.sin(ph * h + 2 * Math.PI * f * h * i / SR); }
  return gain(y, 0.55);
}
const peakOf = x => (Array.isArray(x) ? Math.max(peakOf(x[0]), peakOf(x[1])) : x.reduce((m, v) => Math.max(m, Math.abs(v)), 0));
const norm = x => { const p = peakOf(x) || 1; return Array.isArray(x) ? x.map(c => c.map(v => v / p)) : x.map(v => v / p); };
const fadeEdges = (x, a = 0.002, b = 0.01) => { const y = Float32Array.from(x), na = ns(a), nb = ns(b); for (let i = 0; i < na && i < y.length; i++) y[i] *= i / na; for (let i = 0; i < nb && i < y.length; i++) y[y.length - 1 - i] *= i / nb; return y; };

/* ---------- mixer ---------- */
const bus = name => ({ name, L: new Float32Array(N), R: new Float32Array(N) });
const B = { music: bus('music'), drums: bus('drums'), fx: bus('fx'), room: bus('room'), hall: bus('hall') };
const CUES = [];
function place(b, x, t0, gDb = 0, pan = 0) {         // equal-power pan
  const g = db(gDb), th = (clamp(pan, -1, 1) + 1) * Math.PI / 4, gl = g * Math.cos(th), gr = g * Math.sin(th);
  const s = Math.round(t0 * SR);
  const stereo = Array.isArray(x), L = stereo ? x[0] : x, R = stereo ? x[1] : x;
  for (let i = 0; i < L.length; i++) { const j = s + i; if (j < 0 || j >= N) continue; b.L[j] += L[i] * gl; b.R[j] += R[i] * gr; }
}
function sfx(x, t0, gDb, { pan = 0, room = 0, hall = 0, cue = null, cueT = null } = {}) {
  place(B.fx, x, t0, gDb, pan);
  if (room) place(B.room, x, t0, gDb + 20 * Math.log10(room), pan);
  if (hall) place(B.hall, x, t0, gDb + 20 * Math.log10(hall), pan);
  if (cue) CUES.push([cueT ?? t0, cue]);
}
const BED_DB = -11;
const bed = (x, t0, gDb, pan = 0) => place(B.music, x, t0, gDb + BED_DB, pan);
const drum = (x, t0, gDb, pan = 0) => place(B.drums, x, t0, gDb + BED_DB, pan);   // not pumped

// Freeverb-style stereo reverb (8 damped combs + 4 allpasses per side).
function reverb(b, { room = 0.82, damp = 0.25, wet = 1, pre = 0.012 } = {}) {
  const k = SR / 44100, combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617], aps = [556, 441, 341, 225];
  const run = (x, spread) => {
    const out = new Float32Array(N), p = ns(pre);
    for (const c of combs) {
      const len = Math.round((c + spread) * k), buf = new Float32Array(len); let idx = 0, f = 0;
      for (let i = 0; i < N; i++) { const inp = i >= p ? x[i - p] : 0, o = buf[idx]; f = o * (1 - damp) + f * damp; buf[idx] = inp * 0.015 + f * room; idx = (idx + 1) % len; out[i] += o; }
    }
    for (const a of aps) {
      const len = Math.round((a + spread) * k), buf = new Float32Array(len); let idx = 0;
      for (let i = 0; i < N; i++) { const bo = buf[idx], o = -out[i] + bo; buf[idx] = out[i] + bo * 0.5; idx = (idx + 1) % len; out[i] = o; }
    }
    return out;
  };
  return [gain(run(b.L, 0), wet), gain(run(b.R, 23), wet)];
}

/* ---------- instruments ---------- */
function kick(tag, f0 = 118, f1 = 44, tau = 0.22) {
  const n = ns(0.55), body = sine(n, i => f1 + (f0 - f1) * Math.exp(-i / (0.035 * SR)));
  const click = filt(mul(white(ns(0.006), tag), env(ns(0.006), 0.0005, 0.0015)), 'hp', 1500);
  return fadeEdges(sum(mul(body, env(n, 0.001, tau)), gain(click, 0.25)), 0.001, 0.05);
}
function rim(tag) { const n = ns(0.09); return sum(mul(filt(white(n, tag), 'bp', 1800, 4), env(n, 0.0005, 0.012)), gain(mul(sine(n, 820), env(n, 0.0005, 0.02)), 0.4)); }
function hat(tag, tau = 0.028) { const n = ns(0.12); return mul(filt(filt(white(n, tag), 'hp', 7000), 'peak', 10500, 1.2, 4), env(n, 0.0005, tau)); }
function bass(f, dur, tag) {
  const n = ns(dur + 0.08), x = sum(sine(n, f), gain(sine(n, 2 * f), 0.18), gain(filt(saw(n, f, 8), 'lp', 420), 0.35));
  const e = env(n, 0.006, dur * 0.9); for (let i = n - ns(0.06); i < n; i++) e[i] *= (n - i) / ns(0.06);
  return mul(x, e);
}
function pad(notes, dur, o = {}) { return ['L', 'R'].map(sd => padMono(notes, dur, { ...o, tag: (o.tag || 'pad') + sd })); }
function padMono(notes, dur, { attack = 0.25, release = 0.5, cutoff = 1800, tag = 'pad', cutoffCurve = null } = {}) {
  const n = ns(dur + release), r = rng(tag); let x = new Float32Array(n);
  for (const m of notes) for (const d of [-6, 0, 7]) { const f = midi(m) * 2 ** (d / 1200); const s = saw(n, f, 16, r() * 6.28); for (let i = 0; i < n; i++) x[i] += s[i] / (notes.length * 3); }
  x = filt(x, 'lp', cutoffCurve || cutoff, 0.8);
  const e = new Float32Array(n), a = ns(attack), d = ns(dur);
  for (let i = 0; i < n; i++) e[i] = i < a ? (1 - Math.cos(Math.PI * i / a)) / 2 : i < d ? 1 : Math.exp(-(i - d) / (release * SR * 0.35));
  return mul(x, e);
}
function pluck(f, tag, tau = 0.16) { const n = ns(0.5); return mul(filt(sum(saw(n, f, 12), gain(sine(n, 2 * f), 0.3)), 'lp', i => 600 + 3400 * Math.exp(-i / (0.04 * SR)), 1.1), env(n, 0.002, tau)); }
// Glassy ping: inharmonic partials, fast attack, bright decay.
function glass(f, tag, dur = 0.9, bright = 1) {
  const n = ns(dur), parts = [[1, 1, 0.5], [2.76, 0.45 * bright, 0.22], [5.4, 0.22 * bright, 0.1], [8.93, 0.1 * bright, 0.05]];
  let x = new Float32Array(n);
  for (const [r, a, tau] of parts) { const s = mul(sine(n, f * r), env(n, 0.001, tau * dur)); for (let i = 0; i < n; i++) x[i] += s[i] * a; }
  return sum(x, gain(filt(mul(white(ns(0.004), tag), env(ns(0.004), 0.0003, 0.001)), 'hp', 4000), 0.2));
}
function thump(tag, f0 = 170, f1 = 62, k = 1) {   // soft rubbery ball contact
  const n = ns(0.32), body = mul(sine(n, i => f1 + (f0 - f1) * Math.exp(-i / (0.03 * SR))), env(n, 0.002, 0.085));
  const rub = mul(filt(white(n, tag), 'bp', i => 520 - 220 * Math.min(1, i / (0.05 * SR)), 3), env(n, 0.003, 0.03));
  return sum(body, gain(rub, 0.35 * k));
}
function click(tag, tone = 2600, body = 1200, level = 1) {   // crisp UI / mouse click
  const n = ns(0.06), tr = mul(filt(white(n, tag), 'hp', 2500), env(n, 0.0002, 0.0025));
  return gain(norm(sum(tr, gain(mul(sine(n, tone), env(n, 0.0003, 0.006)), 0.5), gain(mul(sine(n, body), env(n, 0.0005, 0.012)), 0.35))), level);
}
function tick(tag, f = 3400) { const n = ns(0.03); return norm(sum(mul(filt(white(n, tag), 'bp', f, 3), env(n, 0.0002, 0.004)), gain(mul(sine(n, f * 0.62), env(n, 0.0002, 0.006)), 0.25))); }
function clunk(tag) {
  const n = ns(0.6), low = mul(sine(n, i => 58 + 70 * Math.exp(-i / (0.02 * SR))), env(n, 0.001, 0.12));
  const metal = sum(...[2093, 3322, 4419].map((f, j) => mul(sine(n, f), env(n, 0.0005, 0.05 / (j + 1)))));
  const knock = mul(filt(white(n, tag), 'bp', 900, 1.5), env(n, 0.0005, 0.018));
  return sum(low, gain(metal, 0.08), gain(knock, 0.6));
}
// Motion-driven whoosh: level and brightness follow a speed curve (sampled at 500 Hz), pan follows a position curve.
function whoosh(tag, t0, t1, speed, { lo = 300, hi = 6000, air = 0.4, shape = 0.9, tail = 0.15, tone = null, attack = 0.012, release = 0.08 } = {}) {
  const n = ns(t1 - t0 + tail), v = new Float32Array(n);
  let vmax = 1e-9; for (let i = 0; i < n; i++) { const t = t0 + i / SR; v[i] = t <= t1 ? Math.max(0, at(speed, t)) : 0; vmax = Math.max(vmax, v[i]); }
  // envelope follower (attack/release) on the normalised speed
  const e = new Float32Array(n), ka = 1 - Math.exp(-1 / (attack * SR)), kr = 1 - Math.exp(-1 / (release * SR)); let y = 0;
  for (let i = 0; i < n; i++) { const x = (v[i] / vmax) ** shape; y += (x > y ? ka : kr) * (x - y); e[i] = y; }
  const cut = e.map(x => lo * (hi / lo) ** x);
  const one = side => {
    let x = filt(filt(pink(n, tag + side), 'lp', cut, 0.75), 'hp', 90);
    x = gain(x, 1 / (peakOf(x) || 1));
    if (air) { const a = filt(white(n, tag + side + 'air'), 'bp', cut.map(c => Math.min(c * 1.7, 15000)), 0.9); x = sum(x, gain(a, air / (peakOf(a) || 1))); }
    if (tone) { const [f0, f1, a] = tone; x = sum(x, gain(sine(n, i => f0 * (f1 / f0) ** (i / n)), a)); }
    return mul(x, e);
  };
  return norm([one('L'), one('R')]);
}
function revSwell(tag, dur, lo = 200, hi = 6000) { const n = ns(dur), e = Float32Array.from({ length: n }, (_, i) => (i / n) ** 2.4); return norm(['L', 'R'].map(sd => mul(filt(pink(n, tag + sd), 'lp', i => lo * (hi / lo) ** (i / n), 0.9), e))); }
function shimmer(notes, dur, tag) {
  const n = ns(dur), r = rng(tag); let x = new Float32Array(n);
  notes.forEach((m, j) => { const f = midi(m), ph = r() * 6.28, rate = 7 + 2 * j; for (let i = 0; i < n; i++) { const t = i / SR; x[i] += Math.sin(2 * Math.PI * f * t + ph) * (0.55 + 0.45 * Math.sin(2 * Math.PI * rate * t)) / notes.length; } });
  const e = Float32Array.from({ length: n }, (_, i) => { const u = i / n; return Math.min(1, u / 0.18) * (1 - u) ** 1.6; });
  return norm(sum(mul(x, e), gain(mul(filt(white(n, tag + 'n'), 'bp', 9000, 1.2), e), 0.25)));
}
function subDrop(tag, f0 = 72, f1 = 36, dur = 1.6) {
  const n = ns(dur), x = mul(sine(n, i => f1 + (f0 - f1) * Math.exp(-i / (0.25 * SR))), env(n, 0.004, 0.55));
  const boom = mul(filt(pink(n, tag), 'lp', 180), env(n, 0.002, 0.12));
  return sum(x, gain(boom, 0.8));
}

/* ---------- score: music ---------- */
const beatT = k => T0 + k * BEAT;                                     // beat k of the groove (k = 0 → 2.22 s, the bronze O)
const CHORDS = [   // [start beat, beats, pad notes, bass midi]
  [0, 4, [53, 57, 60, 64, 67], 29],          // Fmaj9    2.22  the window opens on the cream world
  [4, 4, [62, 65, 69, 72, 76], 38],          // Dm9      4.91
  [8, 4, [58, 62, 65, 69, 72], 34],          // Bbmaj9   7.60
  [12, 2, [55, 58, 62, 65, 69], 31],         // Gm9     10.30
  [14, 2, [60, 65, 67, 70, 74], 36],         // C9sus4  11.64
  [16, 3, [53, 57, 60, 64, 67], 29],         // Fmaj9   12.99  logo, muffled, fading
];
function music() {
  // 0.20–2.22 airy filtered intro under the opener: a high Dm9 voicing opening up, with air.
  bed(pad([74, 77, 81, 84, 88], 2.0, { attack: 0.8, release: 0.4, cutoffCurve: i => 500 + 3500 * Math.min(1, i / (1.9 * SR)), tag: 'intro' }), 0.20, -4);
  bed(revSwell('introAir', 1.9, 1500, 9000).map(c => gain(filt(c, 'hp', 1200), 0.6)), 0.25, -13, 0.1);
  for (const [b0, nb, notes, root] of CHORDS) {
    const t = beatT(b0), dur = nb * BEAT;
    bed(pad(notes, dur, { attack: 0.06, release: 0.6, cutoff: b0 === 16 ? 1400 : 2100, tag: 'pad' + b0 }), t, -10);
    const bpat = nb >= 4 ? [0, 1.5, 2, 3.5] : [0, 1.5];
    for (const o of bpat) if (o < nb) bed(bass(midi(root), BEAT * (o % 1 ? 0.45 : 0.9), 'b' + b0 + o), beatT(b0 + o), -13);
    for (let k = 0; k < nb * 2; k++) { if (k % 4 === 3) continue; const m = notes[(k * 2) % notes.length] + 12; bed(pluck(midi(m), 'pl' + b0 + k), beatT(b0 + k / 2) + 0.006, -21, (k % 2 ? 0.25 : -0.25)); }
  }
  for (let k = 0; k <= 16; k++) {                                       // kick 4/4, rim on 2 and 4, offbeat hats
    const t = beatT(k); if (t > 13.4) break;
    drum(kick('k' + k), t, k === 0 ? -5 : -8);
    if (k % 2 === 1) drum(rim('r' + k), t, -20, -0.15);
    drum(hat('ho' + k, 0.05), t + BEAT / 2, -19, 0.2);
    drum(hat('hs' + k, 0.018), t + BEAT / 4, -27, -0.25); drum(hat('hs2' + k, 0.018), t + 3 * BEAT / 4, -27, 0.3);
  }
}
// Sidechain pump on the bed (pads, bass, plucks); the drums bus is not pumped.
function pump() {
  const g = new Float32Array(N).fill(1);
  for (let k = 0; k <= 16; k++) { const s = Math.round(beatT(k) * SR); for (let i = 0; i < ns(0.25); i++) { const j = s + i; if (j < N) g[j] = Math.min(g[j], 1 - 0.32 * Math.exp(-i / (0.07 * SR))); } }
  return g;
}

/* ---------- score: effects ---------- */
const fxSpring = (ov, settle) => { const L = Math.log(ov), z = -L / Math.sqrt(Math.PI ** 2 + L * L), w = settle / z, wd = w * Math.sqrt(1 - z * z), c = z / Math.sqrt(1 - z * z); const x = u => 1 - Math.exp(-z * w * u) * (Math.cos(wd * u) + c * Math.sin(wd * u)); const e1 = x(1); return u => x(u) + (1 - e1) * u; };
const firstCross = sp => { let u = 0; while (sp(u) < 1 && u < 1) u += 0.0005; return u; };
function rumble(tag, dur) { const n = ns(dur), e = Float32Array.from({ length: n }, (_, i) => Math.sin(Math.PI * i / n) ** 0.8); return norm(['L', 'R'].map(sd => mul(filt(filt(white(n, tag + sd), 'lp', 260), 'hp', 45), e))); }
function effects() {
  // 0.25–0.80 the opening words blur in: soft airy pings on Dm9 tones
  [[0.25, 81, -0.25], [0.38, 84, 0.15], [0.55, 77, -0.2], [0.68, 88, 0.2]].forEach(([t, m, p], j) =>
    sfx(glass(midi(m), 'w' + j, 0.6, 0.5), t + 0.03, -27, { pan: p, room: 0.2, hall: 0.2, cue: j === 0 ? 'soft pings — "La qualité, notre meilleur"' : null }));
  // 0.85–1.43 PROFIL. letters land: glassy ticks, panned across the word
  const uc = firstCross(fxSpring(0.04, 4.6));
  const landNotes = [86, 89, 93, 96, 98, 100, 101], letterPan = [-0.6, -0.4, -0.2, 0, 0.2, 0.4, 0.55];
  for (let i = 0; i < 7; i++) sfx(glass(midi(landNotes[i]), 'L' + i, 0.5, 0.8), 0.85 + 0.06 * i + uc * 0.22, -27, { pan: letterPan[i], room: 0.2, hall: 0.12, cue: i === 0 ? 'glassy ticks — PROFIL. letters land' : null });
  // 1.75–2.05 flip ripple and spring upright
  for (let i = 0; i < 7; i++) sfx(whooshShort('flip' + i, 0.07), 1.76 + 0.012 * i, -28, { pan: letterPan[i] });
  sfx(whooshShort('upright', 0.12), 1.90, -21, { room: 0.2, cue: 'flip ripple, letters spring upright' });
  // 2.10–2.30 punch into the O; 2.22 sub drop on bar 1 as the O turns bronze
  sfx(whoosh('punch', 2.08, 2.32, deriv(ch('punch')), { lo: 250, hi: 7500, air: 0.5, tail: 0.25, tone: [180, 520, 0.12] }), 2.08, -14, { hall: 0.2, cue: 'zoom whoosh — camera punches into the O', cueT: 2.18 });
  sfx(revSwell('preDrop', 0.35, 300, 5000), 1.87, -19, { hall: 0.15 });
  sfx(subDrop('drop'), 2.22, -12, { cue: 'sub-bass drop — the O turns bronze (bar 1)' });
  // 2.30–2.95 the profile grows into the window frame; a metallic ring as it lands
  sfx(whoosh('frame', 2.30, 2.97, deriv(ch('frameW')).map(Math.abs), { lo: 300, hi: 6000, air: 0.55, tail: 0.3, tone: [220, 440, 0.08] }), 2.30, -12, { hall: 0.3, cue: 'opening whoosh — the profile becomes the window frame', cueT: 2.45 });
  [77, 81, 84].forEach((m, j) => sfx(glass(midi(m), 'land' + j, 1.2, 0.7), 2.93 + 0.02 * j, -22 - j, { pan: -0.2 + 0.2 * j, hall: 0.3, cue: j === 0 ? 'metallic ring — the frame lands' : null }));
  // label changes: soft tuned blips
  [[2.98, 96], [4.47, 93], [5.92, 98], [7.30, 93]].forEach(([t, m], j) => sfx(glass(midi(m), 'lab' + j, 0.35, 0.5), t + 0.05, -27, { room: 0.2 }));
  // 4.30–4.65 Coulissants: the pane rolls away on its track, soft clack at the end
  sfx(whoosh('slide', 4.28, 4.67, deriv(ch('slide')).map(Math.abs), { lo: 200, hi: 3500, air: 0.25, tail: 0.15 }), 4.28, -13, { pan: -0.3, cue: 'sliding pane rolls on its track' });
  sfx(rumble('roll', 0.37), 4.29, -19, { pan: -0.2 });
  sfx(click('clack1', 1800, 700, 1), 4.64, -16, { pan: -0.6, room: 0.25 });
  // 5.70–6.10 Battants: latch click, the sash swings on its hinge
  sfx(click('latch', 2200, 900, 1), 5.69, -14, { pan: -0.35, room: 0.2, cue: 'latch click, the sash swings open' });
  sfx(whoosh('swing', 5.70, 6.12, deriv(ch('swing')).map(Math.abs), { lo: 250, hi: 4200, air: 0.35, tail: 0.2 }), 5.70, -13, { pan: 0.25, hall: 0.15 });
  // 7.10–7.45 Agencement: the drawer slides out on its runners, soft stop
  sfx(whoosh('drawer', 7.08, 7.47, deriv(ch('drawer')).map(Math.abs), { lo: 180, hi: 3000, air: 0.2, tail: 0.12 }), 7.08, -13, { cue: 'drawer slides out on its runners' });
  sfx(rumble('runner', 0.36), 7.09, -19);
  sfx(thump('drawerStop', 150, 70, 0.3), 7.44, -18, { room: 0.2 });
  // 8.45–8.85 Extérieur: pergola louvres close, one tick per slat, then the lock
  for (let j = 0; j < 12; j++) sfx(tick('slat' + j, 2300 + 70 * j), 8.45 + 0.022 * j + 0.13, -18, { pan: -0.3 + 0.05 * j, room: 0.15, cue: j === 0 ? 'pergola louvres close, slat by slat' : null });
  sfx(click('louvreLock', 1500, 600, 1), 8.86, -15, { room: 0.25 });
  // 9.00–9.40 and 11.40–11.80: the page scrolls between sections
  const sc = deriv(ch('scroll')).map(Math.abs);
  sfx(whoosh('scroll1', 8.98, 9.45, sc, { lo: 250, hi: 6000, air: 0.5, tail: 0.2 }), 8.98, -11, { hall: 0.15, cue: 'scroll whoosh — Pourquoi PROMPOLU', cueT: 9.0 });
  sfx(whoosh('scroll2', 11.38, 11.85, sc, { lo: 250, hi: 6000, air: 0.5, tail: 0.2 }), 11.38, -11, { hall: 0.15, cue: 'scroll whoosh — Fès & Sefrou', cueT: 11.4 });
  // 9.45–10.10 odometer ticks, one per digit passing, then the clunk on the bronze 8
  [-0.12, 0.12].forEach((pn, k) => {
    const r = ch('reel' + k); let last = 0;
    for (let i = 1; i < r.length; i++) {
      const c = Math.floor(r[i] + 1e-6);
      if (c > last && i / 500 < 10.2) { last = c; const t = (i - 1 + (c - r[i - 1]) / Math.max(1e-6, r[i] - r[i - 1])) / 500; sfx(tick(`tk${k}_${c}`, 3000 + 400 * k), t, -16 - 1.5 * k, { pan: pn, room: 0.1 }); }
    }
  });
  CUES.push([9.45, 'mechanical ticks — reels spin (one per digit)']);
  sfx(clunk('clunk'), 10.10, -12, { pan: 0.1, room: 0.25, cue: 'clunk — the bronze 8 lands, "+18"' });
  sfx(whooshShort('ans', 0.14), 10.0, -24);
  // 10.38 the STRUGAL badge pops; 10.55–10.95 the norms type on
  sfx(thump('badge', 320, 150, 0.3), 10.40, -18, { room: 0.2 });
  sfx(glass(midi(89), 'badge', 0.5, 0.6), 10.41, -23, { hall: 0.2, cue: 'pop — Distributeur officiel STRUGAL' });
  for (let c = 1; c <= 30; c++) { const t = 10.55 + 0.4 * c / 30; if (c % 2) sfx(tick('key' + c, 3800), t, -31, { pan: -0.2 + 0.013 * c }); }
  // 11.84 / 11.99 the pins drop and land; 12.05–12.45 the route draws; 12.45 delivery line
  const ucp = firstCross(fxSpring(0.10, 4.6));
  [[11.84, 330, 'Fès', 89], [11.99, 740, 'Sefrou', 93]].forEach(([t0, x, name, m], j) => {
    const t = t0 + 0.34 * ucp, pan = clamp((535 + 1.3 * (x - 535) - 540) / 540, -1, 1) * 0.8;
    sfx(thump('pin' + j, 210, 80, 0.5), t - 0.01, -15, { pan, room: 0.2, cue: `pin lands — ${name}`, cueT: t });
    sfx(glass(midi(m), 'pinG' + j, 0.6, 0.6), t, -24, { pan, hall: 0.2 });
    sfx(whooshShort('pinAir' + j, 0.2), t0 + 0.02, -27, { pan });
  });
  sfx(shimmer([81, 84, 88, 91], 0.6, 'route'), 12.04, -24, { hall: 0.25, pan: 0.1, cue: 'the route draws from Fès to Sefrou' });
  sfx(whooshShort('livraison', 0.16), 12.45, -24);
  // 12.85–13.00 the page blurs away; 13.00 bright shimmer as the logo rises; 13.60 prompolu.com
  sfx(revSwell('blurOut', 0.16, 600, 8000), 12.84, -20, { hall: 0.2 });
  sfx(shimmer([89, 93, 96, 100, 103], 1.3, 'logoShimmer'), 12.98, -13, { hall: 0.35, cue: 'bright shimmer — the logo rises' });
  [77, 81, 84, 88, 89, 93, 96, 100].forEach((m, j) => sfx(glass(midi(m), 'win' + j, 0.4, 0.35), j === 0 ? 13.02 : 13.06 + 0.035 * (j - 1) + 0.06, -30, { pan: -0.55 + 0.157 * j, room: 0.2 }));
  sfx(glass(midi(84), 'url', 0.9, 0.6), 13.62, -21, { hall: 0.3, cue: 'prompolu.com' });
  CUES.push([13.0, 'music low-passed, fading to silence by 14.70']);
}
function whooshShort(tag, dur) { const n = ns(dur), e = Float32Array.from({ length: n }, (_, i) => Math.sin(Math.PI * i / n) ** 1.5); return norm(['L', 'R'].map(sd => mul(filt(pink(n, tag + sd), 'bp', i => 900 + 3500 * Math.sin(Math.PI * i / n), 0.8), e))); }

/* ---------- master ---------- */
function measure(file) {
  const r = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-af', 'ebur128=peak=true', '-f', 'null', '-'], { encoding: 'utf8' });
  const s = r.stderr, I = +s.match(/I:\s+(-?[\d.]+) LUFS/g).pop().match(/-?[\d.]+/)[0];
  const tp = s.match(/Peak:\s+(-?[\d.inf]+) dBFS/g).pop().match(/-?[\d.]+|-inf/)[0];
  const lra = +s.match(/LRA:\s+(-?[\d.]+) LU/g).pop().match(/-?[\d.]+/)[0];
  return { I, tp: +tp, lra };
}
function writeWav(file, L, R, bits = 24) {
  const n = L.length, bps = bits / 8, buf = Buffer.alloc(44 + n * 2 * bps);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 2 * bps, 4); buf.write('WAVE', 8); buf.write('fmt ', 12); buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 2 * bps, 28); buf.writeUInt16LE(2 * bps, 32); buf.writeUInt16LE(bits, 34);
  buf.write('data', 36); buf.writeUInt32LE(n * 2 * bps, 40);
  const max = 2 ** (bits - 1) - 1; let o = 44;
  for (let i = 0; i < n; i++) for (const v of [L[i], R[i]]) { const q = Math.round(clamp(v, -1, 1) * max); buf.writeIntLE(q, o, bps); o += bps; }
  fs.writeFileSync(file, buf);
}
// True-peak-aware lookahead limiter: 4× oversampled peak detection (Hann-windowed sinc, 32 taps per phase).
function limit(L, R, ceilingDb) {
  const ceil = db(ceilingDb), look = ns(0.0015), rel = 1 - Math.exp(-1 / (0.06 * SR));
  const pk = new Float32Array(N), T = 16;
  const sinc = z => (Math.abs(z) < 1e-9 ? 1 : Math.sin(Math.PI * z) / (Math.PI * z));
  const H = [0.25, 0.5, 0.75].map(ph => { const h = []; for (let k = -T + 1; k <= T; k++) { const z = ph - k; h.push(sinc(z) * 0.5 * (1 + Math.cos(Math.PI * z / (T + 1)))); } return h; });
  for (const X of [L, R]) for (let i = T; i < N - T; i++) {
    let m = Math.abs(X[i]);
    for (const h of H) { let v = 0; for (let k = -T + 1, j = 0; k <= T; k++, j++) v += X[i + k] * h[j]; m = Math.max(m, Math.abs(v)); }
    pk[i] = Math.max(pk[i], m);
  }
  const need = pk.map(p => (p > ceil ? ceil / p : 1));
  const g = new Float32Array(N); let y = 1, maxRed = 0;
  const win = new Float32Array(N);
  for (let i = 0; i < N; i++) { let m = 1; for (let j = i; j < Math.min(N, i + look); j++) m = Math.min(m, need[j]); win[i] = m; }
  for (let i = 0; i < N; i++) { y = win[i] < y ? win[i] : y + rel * (win[i] - y); g[i] = y; maxRed = Math.max(maxRed, -20 * Math.log10(y)); }
  // the gain already looks 1.5 ms ahead (window minimum), so it is applied without delaying the signal
  return { L: L.map((v, i) => v * g[i]), R: R.map((v, i) => v * g[i]), maxRed };
}

music();
effects();
// bed: sidechain pump, then the ending — low-pass sweep after 8.60 and silence by 9.70
const pg = pump();
const lpCurve = i => { const t = i / SR; return t < 13.0 ? 16000 : 16000 * (420 / 16000) ** Math.min(1, (t - 13.0) / 1.0); };
const lpArr = Float32Array.from({ length: N }, (_, i) => lpCurve(i));
for (const k of ['L', 'R']) {
  for (let i = 0; i < N; i++) B.music[k][i] = B.music[k][i] * pg[i] + B.drums[k][i];
  B.music[k] = filt(B.music[k], 'lp', lpArr, 0.7);
}
const fadeOut = i => { const t = i / SR; return t < 13.9 ? 1 : t >= 14.7 ? 0 : (1 + Math.cos(Math.PI * (t - 13.9) / 0.8)) / 2; };
const [roomL, roomR] = reverb(B.room, { room: 0.72, damp: 0.35, wet: 0.9 });
const [hallL, hallR] = reverb(B.hall, { room: 0.86, damp: 0.22, wet: 1.0, pre: 0.025 });
const fxL = new Float32Array(N), fxR = new Float32Array(N), muL = new Float32Array(N), muR = new Float32Array(N);
for (let i = 0; i < N; i++) {
  const f = fadeOut(i), fxFade = (i / SR) >= 14.72 ? Math.max(0, 1 - (i / SR - 14.72) / 0.22) : 1;
  muL[i] = B.music.L[i] * f; muR[i] = B.music.R[i] * f;
  fxL[i] = (B.fx.L[i] + roomL[i] + hallL[i]) * fxFade; fxR[i] = (B.fx.R[i] + roomR[i] + hallR[i]) * fxFade;
}
const mixL = new Float32Array(N), mixR = new Float32Array(N);
for (const [k, b] of Object.entries(B)) if (b.L.some(Number.isNaN) || b.R.some(Number.isNaN)) throw new Error(`NaN in bus ${k}`);
for (let i = 0; i < N; i++) { mixL[i] = muL[i] + fxL[i]; mixR[i] = muR[i] + fxR[i]; }
// loudness → −15 LUFS, then the true-peak limiter at −1.2 dBTP
const tmp = path.join(WORK, 'pre-master.wav');
writeWav(tmp, mixL, mixR);
const m0 = measure(tmp), g0 = db(-15 - m0.I);
for (let i = 0; i < N; i++) { mixL[i] *= g0; mixR[i] *= g0; muL[i] *= g0; muR[i] *= g0; fxL[i] *= g0; fxR[i] *= g0; }
const lim = limit(mixL, mixR, -1.3);
const OUT = path.join(ROOT, 'sfx.wav');
writeWav(OUT, lim.L, lim.R);
writeWav(path.join(WORK, 'music.wav'), muL, muR);
writeWav(path.join(WORK, 'fx.wav'), fxL, fxR);
const m1 = measure(OUT);
CUES.sort((a, b) => a[0] - b[0]);
fs.writeFileSync(path.join(ROOT, 'cues.txt'), [
  '# Sound cue sheet (generated by sfx.mjs). Original procedural synthesis, no samples.',
  `# Groove: ${BPM} BPM, bar 1 on the bronze O (2.22 s); Fmaj9 → Dm9 → Bbmaj9 → Gm9 → C9sus4 → Fmaj9 (logo, 12.99 s).`,
  '# time (s)\tcue', ...CUES.map(([t, c]) => `${t.toFixed(2)}\t${c}`)].join('\n') + '\n');
console.log(`sfx.wav: ${m1.I} LUFS, true peak ${m1.tp} dBTP, LRA ${m1.lra} LU, limiter max ${lim.maxRed.toFixed(1)} dB (pre-master ${m0.I} LUFS)`);
