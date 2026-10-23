#!/usr/bin/env node
// Procedural soundtrack for the PROMPOLU reel: plain PCM synthesis (no samples), written to sfx.wav.
// A minimal electronic groove at 93 BPM (bar 1 lands on the sub drop at 1.05 s) under motion-driven
// sound effects: the page's own motion (window.motionAt, sampled at 500 Hz) drives every whoosh, the
// odometer reels drive their ticks, and every cue in the brief is placed on its frame.
//
//   node sfx.mjs                → sfx.wav (48 kHz, 24-bit) + cues.txt (+ work/music.wav, work/fx.wav stems)
//   node sfx.mjs --no-export    → reuse work/motion.json
// Mastered to −15 LUFS integrated, true peak ≤ −1 dBTP (measured with FFmpeg's ebur128).
import { chromium } from 'playwright';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, openFilm } from './serve.mjs';

const SR = 48000, DUR = 10, N = SR * DUR;
const BPM = 93, BEAT = 60 / BPM, BAR = 4 * BEAT, T0 = 1.05;      // downbeats 1.05, 3.63, 6.21, 8.79
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
    for (let i = 0; i <= 5000; i++) {
      const s = window.motionAt(i / 500);
      for (const k in s) (out[k] ||= []).push(Math.round(s[k] * 1e4) / 1e4);
    }
    return out;
  });
  fs.writeFileSync(MOTION, JSON.stringify({ rate: 500, channels: m }));
  await browser.close(); server.close();
  console.log(`motion: ${Object.keys(m).length} channels × 5001 samples`);
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
const beatT = k => T0 + k * BEAT;                                     // beat k of the groove (k = 0 → 1.05 s)
const CHORDS = [   // [start beat, beats, pad notes, bass midi]
  [0, 4, [62, 65, 69, 72, 76], 38],          // Dm9      1.05
  [4, 4, [58, 62, 65, 69, 72], 34],          // Bbmaj9   3.63
  [8, 2, [55, 58, 62, 65, 69], 31],          // Gm9      6.21
  [10, 2, [60, 65, 67, 70, 74], 36],         // C9sus4   7.50
  [12, 3, [53, 57, 60, 64, 67], 29],         // Fmaj9    8.79 (logo, muffled, fading)
];
function music() {
  // 0.15–1.05 airy filtered intro: a high Dm9 voicing opening up, with air.
  bed(pad([74, 77, 81, 84, 88], 0.95, { attack: 0.5, release: 0.4, cutoffCurve: i => 500 + 3500 * Math.min(1, i / (0.9 * SR)), tag: 'intro' }), 0.12, -4);
  bed(revSwell('introAir', 0.9, 1500, 9000).map(c => gain(filt(c, 'hp', 1200), 0.6)), 0.15, -12, 0.1);
  // groove
  for (const [b0, nb, notes, root] of CHORDS) {
    const t = beatT(b0), dur = nb * BEAT;
    bed(pad(notes, dur, { attack: 0.06, release: 0.6, cutoff: b0 === 12 ? 1400 : 2100, tag: 'pad' + b0 }), t, -10);
    const bpat = nb >= 4 ? [0, 1.5, 2, 3.5] : nb === 3 ? [0, 1.5] : [0, 1.5];
    for (const o of bpat) if (o < nb) bed(bass(midi(root), BEAT * (o % 1 ? 0.45 : 0.9), 'b' + b0 + o), beatT(b0 + o), -13);
    // plucked arpeggio, 8ths, chord tones rising
    for (let k = 0; k < nb * 2; k++) { if (k % 4 === 3) continue; const m = notes[(k * 2) % notes.length] + 12; bed(pluck(midi(m), 'pl' + b0 + k), beatT(b0 + k / 2) + 0.006, -21, (k % 2 ? 0.25 : -0.25)); }
  }
  for (let k = 0; k <= 12; k++) {                                       // kick 4/4, rim on 2 and 4, offbeat hats
    const t = beatT(k); if (t > 9.2) break;
    drum(kick('k' + k), t, k === 0 ? -5 : -8);
    if (k % 2 === 1) drum(rim('r' + k), t, -20, -0.15);
    drum(hat('ho' + k, 0.05), t + BEAT / 2, -19, 0.2);
    drum(hat('hs' + k, 0.018), t + BEAT / 4, -27, -0.25); drum(hat('hs2' + k, 0.018), t + 3 * BEAT / 4, -27, 0.3);
  }
}
// Sidechain pump on the bed (pads, bass, plucks); the drums bus is not pumped.
function pump() {
  const g = new Float32Array(N).fill(1);
  for (let k = 0; k <= 12; k++) { const s = Math.round(beatT(k) * SR); for (let i = 0; i < ns(0.25); i++) { const j = s + i; if (j < N) g[j] = Math.min(g[j], 1 - 0.32 * Math.exp(-i / (0.07 * SR))); } }
  return g;
}

/* ---------- score: effects ---------- */
const fxSpring = (ov, settle) => { const L = Math.log(ov), z = -L / Math.sqrt(Math.PI ** 2 + L * L), w = settle / z, wd = w * Math.sqrt(1 - z * z), c = z / Math.sqrt(1 - z * z); const x = u => 1 - Math.exp(-z * w * u) * (Math.cos(wd * u) + c * Math.sin(wd * u)); const e1 = x(1); return u => x(u) + (1 - e1) * u; };
function effects() {
  // 0.15–0.45 letters land: glassy ticks on Dm9 tones, panned across the word.
  const sp = fxSpring(0.04, 4.6); let uc = 0; while (sp(uc) < 1 && uc < 1) uc += 0.0005;
  const landNotes = [86, 89, 93, 96, 98, 100], letterPan = [-0.62, -0.38, -0.14, 0.08, 0.3, 0.56];
  for (let i = 0; i < 6; i++) { const t = 0.15 + 0.06 * i + uc * 0.22; sfx(glass(midi(landNotes[i]), 'L' + i, 0.5, 0.8), t, -25, { pan: letterPan[i], room: 0.2, hall: 0.12, cue: i === 0 ? 'glassy ticks — letters land' : null }); }
  // 0.65–0.95 flip ripple and spring upright: soft flicks
  for (let i = 0; i < 6; i++) sfx(whooshShort('flip' + i, 0.07), 0.66 + 0.012 * i, -28, { pan: letterPan[i] });
  sfx(whooshShort('upright', 0.12), 0.80, -21, { room: 0.2, cue: 'flip ripple, letters spring upright' });
  // 0.95–1.10 punch-in: a zoom whoosh on the camera speed, into the drop
  sfx(whoosh('punch', 0.93, 1.12, deriv(ch('punch')), { lo: 250, hi: 7500, air: 0.5, tail: 0.25, tone: [180, 520, 0.12] }), 0.93, -12, { hall: 0.2, cue: 'zoom whoosh — camera punches into the O', cueT: 1.03 });
  // 1.05 deep sub-bass drop as the O turns bronze
  sfx(subDrop('drop'), 1.05, -8, { cue: 'sub-bass drop — the O turns bronze' });
  sfx(revSwell('preDrop', 0.35, 300, 5000), 0.70, -19, { hall: 0.15 });
  // 1.10–1.30 ring → sphere settles: a soft reverse air
  sfx(whoosh('settle', 1.10, 1.30, deriv(ch('ballX')).map(Math.abs), { lo: 400, hi: 4000, air: 0.3 }), 1.10, -20, { pan: 0.1 });
  // 1.50 / 1.86 / 2.18 / 2.34 rubbery thumps on the contacts (30 % softer each time)
  [1.50, 1.86, 2.18, 2.34].forEach((tc, i) => {
    const x = at(ch('ballX'), tc), pan = (x - 960) / 960 * 0.8;
    sfx(thump('c' + i, 175 + 12 * i, 62 + 4 * i), tc - 0.028, -9 - 3.1 * i, { pan, room: 0.18, cue: i === 0 ? 'rubbery thumps — ball contacts' : null });
  });
  // the falls and rises: very soft air following the ball
  sfx(whoosh('arcs', 1.30, 2.55, ball2DSpeed(), { lo: 350, hi: 3200, air: 0.15, shape: 1.3 }), 1.30, -27, { pan: 0.25 });
  // 2.65 short air whoosh on the dolly-out
  sfx(whoosh('dolly', 2.60, 3.00, deriv(ch('ballScale')).map(Math.abs), { lo: 300, hi: 5000, air: 0.55, tail: 0.2 }), 2.60, -12, { hall: 0.2, cue: 'air whoosh — dolly-out into the editor', cueT: 2.65 });
  // 3.20 soft UI tick as the cursor grabs the handle; 3.24–3.46 the curve smears
  sfx(click('grab', 2900, 1400, 1), 3.20, -13, { pan: -0.1, room: 0.2, cue: 'UI tick — cursor grabs the handle' });
  sfx(whooshShort('smear', 0.2), 3.26, -25, { pan: -0.1 });
  // 3.30–3.95 the ball springs along the floor (quiet)
  sfx(whoosh('travel', 3.30, 3.95, deriv(ch('ballX')).map(Math.abs), { lo: 300, hi: 2800, air: 0.2 }), 3.30, -21, { pan: -0.2 });
  // 4.00 big whoosh on the fly-through (ball to camera, editor away)
  const flySpeed = deriv(ch('flyW')).map((v, i) => Math.abs(v) + 0.6 * Math.hypot(deriv(ch('flyX'))[i], deriv(ch('flyY'))[i]));
  sfx(whoosh('fly', 3.98, 4.30, flySpeed, { lo: 200, hi: 9000, air: 0.7, tail: 0.35, tone: [140, 380, 0.15], attack: 0.02 }), 3.98, -5, { hall: 0.25, cue: 'big whoosh — fly-through', cueT: 4.0 });
  sfx(revSwell('flyPre', 0.25, 400, 7000), 3.75, -18, { hall: 0.2 });
  // 4.25–4.45 bronze drains into glass: a soft liquid sweep
  sfx((whoosh('drain', 4.25, 4.47, Array.from({ length: 5001 }, (_, i) => { const t = i / 500; return t > 4.25 && t < 4.45 ? Math.sin(Math.PI * (t - 4.25) / 0.2) : 0; }), { lo: 500, hi: 2500, air: 0.1 })), 4.25, -23, { pan: 0.3 });
  // 4.50 crisp mouse click; the knob springs and lands
  sfx(click('mouse', 3200, 1700, 1), 4.50, -8, { pan: -0.12, room: 0.15, cue: 'crisp mouse click — toggle' });
  sfx(whoosh('knob', 4.50, 4.66, deriv(ch('knobX')).map(Math.abs), { lo: 500, hi: 4500, air: 0.3 }), 4.50, -20, { pan: 0.2 });
  sfx(thump('knobLand', 260, 110, 0.4), 4.585, -21, { pan: 0.13 });
  // 4.65–4.75 capsule contracts, 4.75–4.82 bubble
  sfx(whooshShort('contract', 0.11), 4.65, -21);
  sfx(glass(midi(81), 'bubble', 0.35, 0.4), 4.765, -24, { room: 0.3 });
  // 4.82 glassy chime as the disc splits (Bbmaj9: A6, D7, F7)
  [93, 98, 101].forEach((m, j) => sfx(glass(midi(m), 'chime' + j, 1.1, 1), 4.82 + 0.018 * j, -20 - 2 * j, { pan: -0.2 + 0.2 * j, hall: 0.25, cue: j === 0 ? 'glassy chime — the disc splits' : null }));
  // 5.00 bass swell into the bronze flood (and the burst at 4.95)
  sfx(revSwell('floodSwell', 0.55, 120, 3000), 4.45, -14, { hall: 0.15 });
  sfx(subDrop('flood', 64, 40, 1.2), 5.0, -11, { cue: 'bass swell into the bronze flood' });
  sfx(glass(midi(74), 'burst', 0.25, 0.5), 4.955, -22, { pan: -0.1 });
  // 5.30 flood contracts into the Springs card
  sfx(whooshShort('contractCard', 0.16), 5.30, -19, { pan: -0.1 });
  // 5.55–6.35 swishes on the camera swoop
  const camSp = ['camFx', 'camFy'].map(k => deriv(ch(k)));
  const camSpeed = camSp[0].map((v, i) => Math.hypot(v, camSp[1][i]) * at(ch('camS'), i / 500) + 900 * Math.abs(deriv(ch('camS'))[i]) + 18 * (Math.abs(deriv(ch('camRx'))[i]) + Math.abs(deriv(ch('camRy'))[i]) + Math.abs(deriv(ch('camRz'))[i])));
  sfx(whoosh('swoop', 5.32, 6.62, camSpeed, { lo: 280, hi: 6500, air: 0.5, tail: 0.25, release: 0.06 }), 5.32, -10, { hall: 0.15, pan: 0.15, cue: 'swishes — camera swoop', cueT: 5.55 });
  // 7.28–7.42 tiles fade: a soft air
  sfx(whooshShort('tilesOut', 0.16), 7.28, -23);
  // 7.45–8.15 rapid mechanical ticks while the reels spin, one per digit passing
  const reelPan = [-0.32, -0.18, -0.04];
  for (let k = 0; k < 3; k++) {
    const r = ch('reel' + k); let last = 0;
    for (let i = 1; i < r.length; i++) {
      const c = Math.floor(r[i] + 1e-6);
      if (c > last && i / 500 < 8.2) { last = c; const t = (i - 1 + (c - r[i - 1]) / Math.max(1e-6, r[i] - r[i - 1])) / 500; sfx(tick(`tk${k}_${c}`, 3000 + 400 * k), t, -16 - 1.5 * k, { pan: reelPan[k], room: 0.1 }); }
    }
  }
  CUES.push([7.45, 'mechanical ticks — reels spin (one per digit)']);
  sfx(clunk('clunk'), 8.15, -8, { pan: -0.04, room: 0.25, cue: 'clunk — the bronze 0 lands, "600"' });
  sfx(click('dot', 2400, 900, 0.5), 8.17, -20, { pan: 0.02 });
  // 8.50–8.62 the counter blurs away; 8.60 bright shimmer as the logo rises
  sfx(revSwell('blurOut', 0.14, 600, 8000), 8.47, -20, { hall: 0.2 });
  sfx(shimmer([89, 93, 96, 100, 103], 1.2, 'logoShimmer'), 8.58, -13, { hall: 0.35, cue: 'bright shimmer — the logo rises' });
  [0, 1, 2, 3, 4, 5, 6, 7].forEach(j => sfx(glass(midi([77, 81, 84, 88, 89, 93, 96, 100][j]), 'win' + j, 0.4, 0.35), j === 0 ? 8.62 : 8.66 + 0.035 * (j - 1) + 0.06, -30, { pan: -0.55 + 0.157 * j, room: 0.2 }));
  CUES.push([8.60, 'music low-passed, fading to silence by 9.70']);
}
function whooshShort(tag, dur) { const n = ns(dur), e = Float32Array.from({ length: n }, (_, i) => Math.sin(Math.PI * i / n) ** 1.5); return norm(['L', 'R'].map(sd => mul(filt(pink(n, tag + sd), 'bp', i => 900 + 3500 * Math.sin(Math.PI * i / n), 0.8), e))); }
function ball2DSpeed() { const vx = deriv(ch('ballX')), vy = deriv(ch('ballY')); return vx.map((v, i) => Math.hypot(v, vy[i])); }

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
const lpCurve = i => { const t = i / SR; return t < 8.6 ? 16000 : 16000 * (420 / 16000) ** Math.min(1, (t - 8.6) / 0.95); };
const lpArr = Float32Array.from({ length: N }, (_, i) => lpCurve(i));
for (const k of ['L', 'R']) {
  for (let i = 0; i < N; i++) B.music[k][i] = B.music[k][i] * pg[i] + B.drums[k][i];
  B.music[k] = filt(B.music[k], 'lp', lpArr, 0.7);
}
const fadeOut = i => { const t = i / SR; return t < 8.9 ? 1 : t >= 9.7 ? 0 : (1 + Math.cos(Math.PI * (t - 8.9) / 0.8)) / 2; };
const [roomL, roomR] = reverb(B.room, { room: 0.72, damp: 0.35, wet: 0.9 });
const [hallL, hallR] = reverb(B.hall, { room: 0.86, damp: 0.22, wet: 1.0, pre: 0.025 });
const fxL = new Float32Array(N), fxR = new Float32Array(N), muL = new Float32Array(N), muR = new Float32Array(N);
for (let i = 0; i < N; i++) {
  const f = fadeOut(i), fxFade = (i / SR) >= 9.75 ? Math.max(0, 1 - (i / SR - 9.75) / 0.2) : 1;
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
  `# Groove: ${BPM} BPM, bar 1 on the sub drop (1.05 s); Dm9 → Bbmaj9 → Gm9 → C9sus4 → Fmaj9 (logo).`,
  '# time (s)\tcue', ...CUES.map(([t, c]) => `${t.toFixed(2)}\t${c}`)].join('\n') + '\n');
console.log(`sfx.wav: ${m1.I} LUFS, true peak ${m1.tp} dBTP, LRA ${m1.lra} LU, limiter max ${lim.maxRed.toFixed(1)} dB (pre-master ${m0.I} LUFS)`);
