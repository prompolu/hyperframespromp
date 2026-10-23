#!/usr/bin/env node
// Soundtrack for the SARAPROC MAROC presentation: an original energetic corporate track (plain PCM synthesis, no
// samples) at 120 BPM, plus the French voiceover (assets/voice, Kokoro ff_siwis), written to soundtrack.wav.
//
// The bar map comes from score.json, shared with index.html, so every section starts on a downbeat. Each section
// marked stop=true ends on a silent breath: the band plays a stop hit on beat 3 of the last bar, the music is silent
// for the rest of that bar (about 0.7 s) and comes back on the next downbeat. There are no sound effects.
// The music ducks under the voice (bed −13 dB, drums −10 dB, 50 ms attack, 450 ms release).
//
//   node music.mjs     → soundtrack.wav (48 kHz, 24-bit) + cues.txt (+ work/music.wav, work/voice.wav stems)
// Mastered to −15 LUFS integrated, true peak ≤ −1 dBTP (measured with FFmpeg's ebur128).
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const SC = JSON.parse(fs.readFileSync(path.join(ROOT, 'score.json'), 'utf8'));
const VO = JSON.parse(fs.readFileSync(path.join(ROOT, 'assets/voice/voice.json'), 'utf8'));
const WORK = path.join(ROOT, 'work'); fs.mkdirSync(WORK, { recursive: true });
const SR = 48000, DUR = SC.duration, N = Math.round(SR * DUR);
const BEAT = 60 / SC.bpm, BAR = 4 * BEAT, STEP = BEAT / 4;
const SECS = SC.sections.map(s => ({ ...s, t0: s.bar * BAR, t1: (s.bar + s.bars) * BAR }));
const STOPS = SECS.filter(s => s.stop).map(s => ({ id: s.id, hit: s.t1 - 2 * BEAT, end: s.t1 }));
const CUES = [];

/* ---------- DSP helpers ---------- */
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const db = v => 10 ** (v / 20);
const midi = m => 440 * 2 ** ((m - 69) / 12);
const ns = s => Math.max(1, Math.round(s * SR));
function rng(tag) { let h = 2166136261; for (const c of tag) h = Math.imul(h ^ c.charCodeAt(0), 16777619); let a = h >>> 0;
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function white(n, tag) { const r = rng(tag), x = new Float32Array(n); for (let i = 0; i < n; i++) x[i] = r() * 2 - 1; return x; }
function coeffs(kind, f, q = 0.707, gain = 0) {
  const w = 2 * Math.PI * clamp(f, 10, SR * 0.49) / SR, c = Math.cos(w), s = Math.sin(w), a = s / (2 * q), A = 10 ** (gain / 40);
  let b0, b1, b2, a0, a1, a2;
  if (kind === 'lp') { b0 = (1 - c) / 2; b1 = 1 - c; b2 = b0; a0 = 1 + a; a1 = -2 * c; a2 = 1 - a; }
  else if (kind === 'hp') { b0 = (1 + c) / 2; b1 = -(1 + c); b2 = b0; a0 = 1 + a; a1 = -2 * c; a2 = 1 - a; }
  else if (kind === 'bp') { b0 = a; b1 = 0; b2 = -a; a0 = 1 + a; a1 = -2 * c; a2 = 1 - a; }
  else { b0 = 1 + a * A; b1 = -2 * c; b2 = 1 - a * A; a0 = 1 + a / A; a1 = -2 * c; a2 = 1 - a / A; }
  return [b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0];
}
function filt(x, kind, f, q = 0.707, gain = 0) {   // f: number, or function of the sample index (updated every 32 samples)
  const y = new Float32Array(x.length); let x1 = 0, x2 = 0, y1 = 0, y2 = 0, k = coeffs(kind, typeof f === 'number' ? f : f(0), q, gain);
  for (let i = 0; i < x.length; i++) {
    if (typeof f !== 'number' && i % 32 === 0) k = coeffs(kind, f(i), q, gain);
    const v = k[0] * x[i] + k[1] * x1 + k[2] * x2 - k[3] * y1 - k[4] * y2; x2 = x1; x1 = x[i]; y2 = y1; y1 = v; y[i] = v;
  }
  return y;
}
function sine(n, f, ph = 0) { const y = new Float32Array(n); let p = ph; for (let i = 0; i < n; i++) { y[i] = Math.sin(p); p += 2 * Math.PI * (typeof f === 'number' ? f : f(i)) / SR; } return y; }
// Band-limited sawtooth (PolyBLEP).
function saw(n, f, ph = 0) {
  const y = new Float32Array(n), dt = f / SR; let p = ph % 1;
  const blep = (t) => (t < dt ? (t /= dt, t + t - t * t - 1) : t > 1 - dt ? (t = (t - 1) / dt, t * t + t + t + 1) : 0);
  for (let i = 0; i < n; i++) { y[i] = 2 * p - 1 - blep(p); p += dt; if (p >= 1) p -= 1; }
  return y;
}
function square(n, f, ph = 0) { const a = saw(n, f, ph), b = saw(n, f, ph + 0.5); for (let i = 0; i < n; i++) a[i] = (a[i] - b[i]) * 0.5; return a; }
const mulEnv = (x, e) => { for (let i = 0; i < x.length; i++) x[i] *= e(i); return x; };
const expEnv = (a, tau) => { const na = ns(a); return i => (i < na ? i / na : Math.exp(-(i - na) / (tau * SR))); };
const peakOf = x => x.reduce((m, v) => Math.max(m, Math.abs(v)), 0);

/* ---------- buses ---------- */
const bus = () => ({ L: new Float32Array(N), R: new Float32Array(N) });
const B = { drums: bus(), bed: bus(), send: bus(), voice: bus() };
function place(b, x, t0, gDb = 0, pan = 0, send = 0) {
  const g = db(gDb), th = (clamp(pan, -1, 1) + 1) * Math.PI / 4, gl = g * Math.cos(th), gr = g * Math.sin(th), s = Math.round(t0 * SR);
  const st = Array.isArray(x), L = st ? x[0] : x, R = st ? x[1] : x, sg = send ? db(send) : 0;
  for (let i = 0; i < L.length; i++) { const j = s + i; if (j < 0 || j >= N) continue; b.L[j] += L[i] * gl; b.R[j] += R[i] * gr; if (sg) { B.send.L[j] += L[i] * gl * sg; B.send.R[j] += R[i] * gr * sg; } }
}

/* ---------- instruments ---------- */
function kick(tag, f0 = 125, f1 = 46) {
  const n = ns(0.5), body = mulEnv(sine(n, i => f1 + (f0 - f1) * Math.exp(-i / (0.03 * SR))), expEnv(0.001, 0.2));
  const click = mulEnv(filt(white(ns(0.008), tag), 'hp', 1800), expEnv(0.0004, 0.0018));
  for (let i = 0; i < click.length; i++) body[i] += click[i] * 0.3;
  for (let i = n - ns(0.04); i < n; i++) body[i] *= (n - i) / ns(0.04);
  return body;
}
function clap(tag) {
  const n = ns(0.32), nz = white(n, tag), e = new Float32Array(n);
  for (const [o, a] of [[0, 1], [0.011, 0.8], [0.022, 0.9]]) { const s = ns(o); for (let i = s; i < n; i++) e[i] = Math.max(e[i], a * Math.exp(-(i - s) / (0.006 * SR))); }
  for (let i = ns(0.03); i < n; i++) e[i] = Math.max(e[i], 0.5 * Math.exp(-(i - ns(0.03)) / (0.09 * SR)));
  return filt(filt(nz.map((v, i) => v * e[i]), 'bp', 1300, 1.1), 'hp', 500);
}
function hat(tag, tau = 0.03) { const n = ns(tau * 6 + 0.02); return mulEnv(filt(filt(white(n, tag), 'hp', 7200), 'peak', 10500, 1.2, 4), expEnv(0.0005, tau)); }
function snare(tag) { const n = ns(0.25), nz = mulEnv(filt(white(n, tag), 'bp', 2200, 0.9), expEnv(0.001, 0.07)), body = mulEnv(sine(n, i => 185 + 60 * Math.exp(-i / (0.01 * SR))), expEnv(0.001, 0.05)); for (let i = 0; i < n; i++) nz[i] = nz[i] * 0.9 + body[i] * 0.5; return nz; }
function crash(tag, dur = 2.2) {
  const n = ns(dur), r = rng(tag); let x = filt(white(n, tag), 'hp', 3800);
  const parts = [3150, 4430, 5870, 7210, 8650].map(f => f * (0.97 + 0.06 * r()));
  for (const f of parts) { const s = sine(n, f, r() * 6); for (let i = 0; i < n; i++) x[i] += s[i] * 0.05; }
  return mulEnv(x, i => Math.min(1, i / ns(0.002)) * Math.exp(-i / (0.55 * SR)));
}
function bassNote(m, dur, tag, bright = 1) {
  const f = midi(m), n = ns(dur + 0.03), s = saw(n, f), sub = sine(n, f);
  const x = filt(s, 'lp', i => 160 + 900 * bright * Math.exp(-i / (0.06 * SR)), 1.2);
  for (let i = 0; i < n; i++) x[i] = x[i] * 0.55 + sub[i] * 0.8;
  const a = ns(0.004), r = ns(0.03), d = ns(dur);
  return mulEnv(x, i => (i < a ? i / a : i < d ? 1 : Math.max(0, 1 - (i - d) / r)));
}
function padChord(notes, dur, tag, { cutoff = 2200, attack = 0.08, release = 0.35, air = 0 } = {}) {
  const n = ns(dur + release), r = rng(tag), out = [new Float32Array(n), new Float32Array(n)];
  for (const m of notes) for (const [d, side] of [[-7, 0], [7, 1], [0, 0], [0, 1]]) {
    const s = saw(n, midi(m) * 2 ** (d / 1200), r()); const o = out[side];
    for (let i = 0; i < n; i++) o[i] += s[i] / (notes.length * 2.2);
  }
  const a = ns(attack), dd = ns(dur);
  return out.map(o => mulEnv(filt(o, 'lp', typeof cutoff === 'number' ? cutoff : cutoff, 0.7), i => (i < a ? (1 - Math.cos(Math.PI * i / a)) / 2 : i < dd ? 1 : Math.exp(-(i - dd) / (release * SR * 0.4)))));
}
function pluck(m, tag, { tau = 0.14, bright = 1, cutoff = null } = {}) {
  const f = midi(m), n = ns(0.45), a = saw(n, f, 0.1), b = square(n, f * 2.001, 0.3);
  for (let i = 0; i < n; i++) a[i] = a[i] * 0.7 + b[i] * 0.25;
  const top = cutoff ?? 4200 * bright;
  return mulEnv(filt(a, 'lp', i => 500 + top * Math.exp(-i / (0.045 * SR)), 1.0), expEnv(0.002, tau));
}
function bell(m, tag, dur = 1.4) {      // FM bell
  const f = midi(m), n = ns(dur), y = new Float32Array(n); let pc = 0, pm = 0;
  for (let i = 0; i < n; i++) { const e = Math.exp(-i / (0.5 * SR)), I = 2.2 * Math.exp(-i / (0.25 * SR)); y[i] = Math.sin(pc + I * Math.sin(pm)) * e; pc += 2 * Math.PI * f / SR; pm += 2 * Math.PI * f * 3.5 / SR; }
  return mulEnv(y, i => Math.min(1, i / ns(0.002)));
}
function stab(notes, tag) {
  const n = ns(0.5), out = new Float32Array(n);
  for (const m of notes) { const s = saw(n, midi(m), 0.2); for (let i = 0; i < n; i++) out[i] += s[i] / notes.length; }
  return mulEnv(filt(out, 'lp', i => 900 + 5200 * Math.exp(-i / (0.05 * SR)), 0.9), expEnv(0.002, 0.075));
}
function riser(dur, tag) { const n = ns(dur); return [0, 1].map(k => mulEnv(filt(white(n, tag + k), 'bp', i => 400 * (9000 / 400) ** (i / n), 1.4), i => (i / n) ** 2.2)); }

/* ---------- harmony and arrangement ---------- */
const CH = {
  Am: { pad: [57, 60, 64, 71], bass: 33, arp: [69, 72, 76, 79] },
  F: { pad: [53, 57, 60, 64], bass: 29, arp: [65, 69, 72, 76] },
  C: { pad: [55, 60, 62, 64], bass: 36, arp: [67, 72, 74, 76] },
  G: { pad: [55, 59, 62, 64], bass: 31, arp: [67, 71, 74, 79] },
  Em: { pad: [52, 55, 59, 64], bass: 28, arp: [64, 67, 71, 76] },
  E: { pad: [56, 59, 64, 68], bass: 28, arp: [68, 71, 76, 80] },
  Cfin: { pad: [48, 55, 60, 64, 67, 72], bass: 36, arp: [72, 76, 79, 84] },
};
const PROG = {
  ouverture: ['Am', 'F', 'C', 'G', 'F', 'E'], histoire: ['Am', 'F', 'C', 'G'], medical: ['Am', 'F', 'C', 'G'], industriel: ['Am', 'G', 'F', 'G'],
  institutionnel: ['F', 'C', 'G', 'Am'], eaux: ['Am', 'F', 'C', 'G'], batiments: ['Am', 'G', 'F', 'G'], cuisines: ['F', 'C', 'G', 'Am'],
  cosmetique: ['F', 'G', 'Em', 'Am'], bases: ['F', 'G', 'Em', 'Am'], eaux2: ['Am', 'F', 'C', 'G'], elevage: ['Am', 'F', 'C', 'G'],
  agriculture: ['F', 'C', 'G', 'Am'], certifications: ['Am', 'F', 'C', 'G'], final: ['F', 'G', 'Cfin', 'Cfin', 'Cfin'],
};
// What plays in bar k of a section (n bars). Everything else is the full groove.
function layers(id, k, n, last) {
  const full = { kick: 'four', clap: true, hats: 16, open: true, bass: 8, pad: true, arp: 16, bells: false, crash: k === 0 };
  if (id === 'ouverture') return [
    { pad: true, arp: 8, arpCut: 900 }, { pad: true, arp: 8, arpCut: 1800 },
    { kick: 'half', hats: 8, bass: 'long', pad: true, arp: 16, arpCut: 2600 }, { kick: 'half', hats: 8, bass: 'long', pad: true, arp: 16, arpCut: 3400 },
    { kick: 'four', clap: true, hats: 16, bass: 8, pad: true, arp: 16 }, { kick: 'four', hats: 16, bass: 8, pad: true, arp: 16, roll: true, riser: true },
  ][k];
  if (id === 'final') return [
    { ...full, crash: true, bells: true }, { ...full, bells: true, roll: true }, { finalHit: true }, {}, {},
  ][k];
  if (id === 'bases') return { kick: 'half', hats: 8, bass: 'long', pad: true, arp: 8, bells: true, crash: k === 0, clap: k >= 3 };
  if (id === 'eaux2' && k < 2) return { pad: true, arp: 16, arpCut: 1600 + 1200 * k, bells: true, bass: 'long', hats: k ? 8 : 0, crash: k === 0, riser: k === 1 };
  const L = { ...full };
  if (id === 'industriel' || id === 'batiments') L.bass = 16;
  if (id === 'cosmetique' || id === 'certifications' || id === 'agriculture') L.bells = true;
  if (id === 'histoire' && k < 4) L.open = false;
  return L;
}

/* ---------- score ---------- */
const chordName = (s, k) => (s.stop && k === s.bars - 1 ? 'E' : PROG[s.id][k % PROG[s.id].length]);
const inStop = t => STOPS.some(st => t > st.hit + 1e-6 && t < st.end - 1e-6);
function score() {
  const kicks = [];
  for (const s of SECS) {
    for (let k = 0; k < s.bars; k++) {
      const tb = s.t0 + k * BAR, last = s.stop && k === s.bars - 1, ch = CH[chordName(s, k)], L = layers(s.id, k, s.bars, last);
      const barLen = last ? 2 * BEAT : BAR;                       // a stopping bar plays beats 1–2, then the stop hit on beat 3
      const tag = `${s.id}${k}`;
      if (L.crash) place(B.drums, [crash(tag + 'cL'), crash(tag + 'cR')], tb, -15, 0);
      // drums
      for (let b = 0; b < 4; b++) {
        const t = tb + b * BEAT; if (t >= tb + barLen) break;
        if (L.kick === 'four' || (L.kick === 'half' && b % 2 === 0)) { place(B.drums, kick(tag + 'k' + b), t, -4); kicks.push(t); }
        if (L.clap && b % 2 === 1 && !last) place(B.drums, clap(tag + 'cl' + b), t, -11, 0.05, -14);
        if (L.open) place(B.drums, hat(tag + 'o' + b, 0.09), t + BEAT / 2, -20, 0.22);
      }
      if (L.hats) for (let j = 0; j < 16; j += 16 / L.hats) {
        const t = tb + j * STEP; if (t >= tb + barLen) break;
        place(B.drums, hat(tag + 'h' + j, 0.022), t, j % 4 === 2 ? -21 : -26, j % 2 ? 0.3 : -0.25);
      }
      if (last) {                                                 // fill into the stop: 16th snares on beats 1–2, then the hit
        for (let j = 0; j < 8; j++) place(B.drums, snare(tag + 'f' + j), tb + j * STEP, -24 + j * 1.6, (j % 2 ? 0.2 : -0.2), -18);
        const hit = tb + 2 * BEAT;
        place(B.drums, kick(tag + 'hit'), hit, -2); place(B.drums, clap(tag + 'hc'), hit, -9, 0, -12); place(B.drums, snare(tag + 'hs'), hit, -12);
        place(B.bed, [stab(ch.pad.map(m => m + 12), tag + 'sL'), stab(ch.pad.map(m => m + 12), tag + 'sR')], hit, -9, 0, -16);
        place(B.bed, bassNote(ch.bass, 0.16, tag + 'hb'), hit, -7);
        CUES.push([hit, `stop — ${s.id} (silence until ${s.t1.toFixed(1)} s)`]);
        kicks.push(hit);
      }
      if (L.roll) for (let j = 0; j < 16; j++) place(B.drums, snare(tag + 'r' + j), tb + j * STEP, -30 + j * 1.2, 0, -18);
      if (L.riser) place(B.bed, riser(BAR, tag + 'ri'), tb, -22);
      // bass
      if (L.bass === 'long') place(B.bed, bassNote(ch.bass, barLen - 0.05, tag + 'bl', 0.6), tb, -7);
      else if (L.bass) for (let j = 0; j < 16; j += 16 / L.bass) {
        const t = tb + j * STEP; if (t >= tb + barLen) break;
        const oct = L.bass === 8 && j % 4 === 2 ? 12 : 0;
        place(B.bed, bassNote(ch.bass + oct, (16 / L.bass) * STEP * 0.8, tag + 'b' + j), t, oct ? -10 : -7);
      }
      // pad
      if (L.pad) place(B.bed, padChord(ch.pad, barLen, tag + 'p', { cutoff: id2cut(s.id) }), tb, -15, 0, -9);
      // arpeggio (16ths or 8ths), dotted-8th echo via the send
      if (L.arp) {
        const pat = [0, 1, 2, 3, 2, 1, 2, 3, 0, 1, 2, 3, 2, 3, 1, 2];
        for (let j = 0; j < 16; j += 16 / L.arp) {
          const t = tb + j * STEP; if (t >= tb + barLen) break;
          const m = ch.arp[pat[j]];
          place(B.bed, pluck(m, tag + 'a' + j, { cutoff: L.arpCut ?? null }), t, j % 4 === 0 ? -17 : -20, j % 2 ? 0.35 : -0.35, -10);
        }
      }
      if (L.bells) for (const [j, idx] of [[0, 3], [6, 2], [10, 1]]) {
        const t = tb + j * STEP; if (t >= tb + barLen) break;
        place(B.bed, bell(ch.arp[idx] + 12, tag + 'be' + j), t, -27, j ? 0.4 : -0.4, -8);
      }
      if (L.finalHit) {                                            // the resolution on C, held and fading
        place(B.drums, kick(tag + 'fk'), tb, -2); place(B.drums, [crash(tag + 'fcL', 4), crash(tag + 'fcR', 4)], tb, -13);
        place(B.bed, padChord(CH.Cfin.pad, 3 * BAR, tag + 'fp', { cutoff: 2600, attack: 0.02, release: 1.5 }), tb, -12, 0, -6);
        place(B.bed, bassNote(24, 3.5, tag + 'fb', 0.5), tb, -6); place(B.bed, bassNote(36, 3.5, tag + 'fb2', 0.3), tb, -12);
        [72, 76, 79, 84, 88].forEach((m, j) => place(B.bed, bell(m, tag + 'fbl' + j, 2.6), tb + j * STEP * 2, -22 - j, -0.4 + 0.2 * j, -6));
        CUES.push([tb, 'resolution on C major — official logo on screen']);
      }
    }
    CUES.push([s.t0, `section ${s.id} (bar ${s.bar}, ${s.bars} bars)`]);
  }
  return kicks;
}
function id2cut(id) { return { bases: 1500, eaux2: 1700, ouverture: 1600 }[id] ?? 2300; }

/* ---------- voice ---------- */
function decode(file) {
  const r = spawnSync('ffmpeg', ['-v', 'error', '-i', file, '-f', 'f32le', '-ac', '1', '-ar', String(SR), '-'], { maxBuffer: 1 << 28 });
  if (r.status !== 0) throw new Error('decode failed: ' + file);
  return new Float32Array(r.stdout.buffer, r.stdout.byteOffset, r.stdout.length / 4);
}
// Peak-normalise a line, then a feed-forward compressor (3 ms attack, 80 ms release) to tame the synthetic voice's transients.
function compress(x, thrDb, ratio) {
  const p = peakOf(x) || 1; for (let i = 0; i < x.length; i++) x[i] /= p;
  const thr = db(thrDb), ka = 1 - Math.exp(-1 / (0.003 * SR)), kr = 1 - Math.exp(-1 / (0.08 * SR)); let e = 0;
  for (let i = 0; i < x.length; i++) {
    const a = Math.abs(x[i]); e += (a > e ? ka : kr) * (a - e);
    x[i] *= e > thr ? (thr * (e / thr) ** (1 / ratio)) / e : 1;
  }
  return x;
}
function voice() {
  for (const [id, t0] of Object.entries(SC.voice)) {
    let x = Float32Array.from(decode(path.join(ROOT, 'assets/voice', id + '.flac')));
    x = compress(filt(filt(x, 'hp', 85, 0.7), 'peak', 3200, 0.9, 2.5), -16, 3);
    place(B.voice, x, t0, 0, 0);
    CUES.push([t0, `voice ${id} — « ${VO.lines[id].chunks.join(' ')} »`]);
  }
}

/* ---------- mixing ---------- */
function reverb(src, { room = 0.8, damp = 0.3, pre = 0.02 } = {}) {
  const k = SR / 44100, combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617], aps = [556, 441, 341, 225];
  const run = (x, spread) => {
    const out = new Float32Array(N), p = ns(pre);
    for (const c of combs) { const len = Math.round((c + spread) * k), buf = new Float32Array(len); let idx = 0, f = 0;
      for (let i = 0; i < N; i++) { const inp = i >= p ? x[i - p] : 0, o = buf[idx]; f = o * (1 - damp) + f * damp; buf[idx] = inp * 0.015 + f * room; idx = (idx + 1) % len; out[i] += o; } }
    for (const a of aps) { const len = Math.round((a + spread) * k), buf = new Float32Array(len); let idx = 0;
      for (let i = 0; i < N; i++) { const bo = buf[idx], o = -out[i] + bo; buf[idx] = out[i] + bo * 0.5; idx = (idx + 1) % len; out[i] = o; } }
    return out;
  };
  return [run(src.L, 0), run(src.R, 23)];
}
function delay(src, time, fb, mix) {   // ping-pong echo
  const d = ns(time), L = new Float32Array(N), R = new Float32Array(N);
  for (let i = 0; i < N; i++) { const l = i >= d ? R[i - d] * fb : 0, r = i >= d ? L[i - d] * fb : 0; L[i] = src.L[i] * 0 + (i >= d ? src.R[i - d] : 0) * mix + l; R[i] = (i >= d ? src.L[i - d] : 0) * mix + r; }
  return [L, R];
}
function pumpGain(kicks) {
  const g = new Float32Array(N).fill(1), len = ns(0.22);
  for (const t of kicks) { const s = Math.round(t * SR); for (let i = 0; i < len; i++) { const j = s + i; if (j < N) g[j] = Math.min(g[j], 1 - 0.4 * Math.exp(-i / (0.06 * SR))); } }
  return g;
}
function stopGate() {          // silence after each stop hit until the next downbeat
  const g = new Float32Array(N).fill(1);
  for (const st of STOPS) {
    const a = Math.round((st.hit + 0.22) * SR), b = Math.round((st.hit + 0.30) * SR), e = Math.round(st.end * SR) - ns(0.002);
    for (let i = a; i < e && i < N; i++) g[i] = i < b ? 0.5 * (1 + Math.cos(Math.PI * (i - a) / (b - a))) : 0;
  }
  return g;
}
function duckGain(depthDb) {   // follows the voice: lookahead 60 ms, attack 50 ms, release 450 ms
  const env = new Float32Array(N), w = ns(0.012); let acc = 0;
  const v = B.voice.L; for (let i = 0; i < N; i++) { acc += v[i] * v[i] - (i >= w ? v[i - w] * v[i - w] : 0); env[i] = Math.sqrt(Math.max(0, acc) / w); }
  const vmax = peakOf(env), look = ns(0.06), ka = 1 - Math.exp(-1 / (0.05 * SR)), kr = 1 - Math.exp(-1 / (0.45 * SR)), lo = db(depthDb);
  const g = new Float32Array(N); let y = 0;
  for (let i = 0; i < N; i++) { const on = env[Math.min(N - 1, i + look)] > vmax * 0.02 ? 1 : 0; y += (on > y ? ka : kr) * (on - y); g[i] = 1 - (1 - lo) * y; }
  return g;
}
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
  for (let i = 0; i < n; i++) for (const v of [L[i], R[i]]) { buf.writeIntLE(Math.round(clamp(v, -1, 1) * max), o, bps); o += bps; }
  fs.writeFileSync(file, buf);
}
function limit(L, R, ceilingDb) {   // true-peak-aware lookahead limiter (4× oversampled detection)
  const ceil = db(ceilingDb), look = ns(0.0015), rel = 1 - Math.exp(-1 / (0.06 * SR)), pk = new Float32Array(N), T = 16;
  const sinc = z => (Math.abs(z) < 1e-9 ? 1 : Math.sin(Math.PI * z) / (Math.PI * z));
  const H = [0.25, 0.5, 0.75].map(ph => { const h = []; for (let k = -T + 1; k <= T; k++) { const z = ph - k; h.push(sinc(z) * 0.5 * (1 + Math.cos(Math.PI * z / (T + 1)))); } return h; });
  for (const X of [L, R]) for (let i = T; i < N - T; i++) {
    let m = Math.abs(X[i]); if (m < ceil * 0.7) { pk[i] = Math.max(pk[i], m); continue; }
    for (const h of H) { let v = 0; for (let k = -T + 1, j = 0; k <= T; k++, j++) v += X[i + k] * h[j]; m = Math.max(m, Math.abs(v)); }
    pk[i] = Math.max(pk[i], m);
  }
  const g = new Float32Array(N); let y = 1, maxRed = 0;
  for (let i = 0; i < N; i++) { let m = 1; for (let j = i; j < Math.min(N, i + look); j++) if (pk[j] > ceil) m = Math.min(m, ceil / pk[j]); y = m < y ? m : y + rel * (m - y); g[i] = y; maxRed = Math.max(maxRed, -20 * Math.log10(y)); }
  for (let i = 0; i < N; i++) { L[i] *= g[i]; R[i] *= g[i]; }
  return maxRed;
}
const loud = (L, R, name) => { const f = path.join(WORK, name + '.wav'); writeWav(f, L, R); return measure(f); };

/* ---------- render ---------- */
const t0 = Date.now(), el = () => ((Date.now() - t0) / 1000).toFixed(1) + 's';
const kicks = score(); console.log(`score placed  ${el()}`);
voice(); console.log(`voice placed  ${el()}`);
// bed: echo + reverb on the send, sidechain pump from the kick, then the stop gate on everything musical
const [eL, eR] = delay(B.send, 3 * STEP, 0.32, 0.5);
const [rL, rR] = reverb({ L: B.send.L.map((v, i) => v + eL[i] * 0.6), R: B.send.R.map((v, i) => v + eR[i] * 0.6) }, { room: 0.82, damp: 0.28 });
const pg = pumpGain(kicks), gate = stopGate();
const mL = new Float32Array(N), mR = new Float32Array(N), dL = new Float32Array(N), dR = new Float32Array(N);
for (let i = 0; i < N; i++) {
  mL[i] = (B.bed.L[i] * pg[i] + (eL[i] * 0.35 + rL[i] * 0.9) * pg[i]) * gate[i]; mR[i] = (B.bed.R[i] * pg[i] + (eR[i] * 0.35 + rR[i] * 0.9) * pg[i]) * gate[i];
  dL[i] = B.drums.L[i] * gate[i]; dR[i] = B.drums.R[i] * gate[i];
}
// final bars: a gentle low-pass and fade so the resolution rings out
const fEnd = SECS.at(-1).t1, fadeA = fEnd - 4.5;
for (const X of [mL, mR, dL, dR]) for (let i = Math.round(fadeA * SR); i < N; i++) { const u = (i / SR - fadeA) / (DUR - 0.4 - fadeA); X[i] *= u >= 1 ? 0 : Math.cos(u * Math.PI / 2) ** 1.5; }
console.log(`music bus  ${el()}`);
// voice: a touch of room, levelled to −15.5 LUFS; music levelled to −17.5 LUFS before ducking
const vr = reverb({ L: B.voice.L.map(v => v * 0.25), R: B.voice.R.map(v => v * 0.25) }, { room: 0.55, damp: 0.5, pre: 0.008 });
const vL = B.voice.L.map((v, i) => v + vr[0][i] * 0.35), vR = B.voice.R.map((v, i) => v + vr[1][i] * 0.35);
const mm = loud(mL.map((v, i) => v + dL[i]), mR.map((v, i) => v + dR[i]), 'music-raw'), gm = db(-17.5 - mm.I);
const vm = loud(vL, vR, 'voice-raw'), gv = db(-15.5 - vm.I);
const duckBed = duckGain(-13), duckDr = duckGain(-10);
const ML = new Float32Array(N), MR = new Float32Array(N), VL = new Float32Array(N), VR = new Float32Array(N);
for (let i = 0; i < N; i++) {
  ML[i] = (mL[i] * duckBed[i] + dL[i] * duckDr[i]) * gm; MR[i] = (mR[i] * duckBed[i] + dR[i] * duckDr[i]) * gm;
  VL[i] = vL[i] * gv; VR[i] = vR[i] * gv;
}
for (const [k, X] of Object.entries({ ML, MR, VL, VR })) if (X.some(Number.isNaN)) throw new Error('NaN in ' + k);
const XL = ML.map((v, i) => v + VL[i]), XR = MR.map((v, i) => v + VR[i]);
const m0 = loud(XL, XR, 'pre-master'), g0 = db(-15 - m0.I);
for (let i = 0; i < N; i++) { XL[i] *= g0; XR[i] *= g0; ML[i] *= g0; MR[i] *= g0; VL[i] *= g0; VR[i] *= g0; }
const red = limit(XL, XR, -1.3);
writeWav(path.join(ROOT, 'soundtrack.wav'), XL, XR);
writeWav(path.join(WORK, 'music.wav'), ML, MR); writeWav(path.join(WORK, 'voice.wav'), VL, VR);
const m1 = measure(path.join(ROOT, 'soundtrack.wav'));
CUES.sort((a, b) => a[0] - b[0]);
fs.writeFileSync(path.join(ROOT, 'cues.txt'), [
  '# Soundtrack cue sheet (generated by music.mjs). Original procedural music, no samples; French voiceover by Kokoro (ff_siwis).',
  `# ${SC.bpm} BPM, one bar = 2 s. Stops: the band hits beat 3 of a section's last bar, then silence until the next downbeat.`,
  '# time (s)\tcue', ...CUES.map(([t, c]) => `${t.toFixed(2)}\t${c}`)].join('\n') + '\n');
console.log(`soundtrack.wav: ${m1.I} LUFS, true peak ${m1.tp} dBTP, LRA ${m1.lra} LU, limiter max ${red.toFixed(1)} dB  (music ${mm.I} → −17.5, voice ${vm.I} → −15.5)  ${el()}`);
