# Synthesise every narration line with Kokoro ff_siwis (timed export), trim silence, write FLAC, and record
# when each clause starts (from the model's phoneme durations: a clause starts after each , : ; . mark).
# usage: kokoro_batch.py MODEL_DIR narration.json OUT_DIR SPEED
import sys, json, os, re, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
mdir, nar, out, speed = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
os.makedirs(out, exist_ok=True)
k = Kokoro(mdir + '/kokoro-v1.0.onnx', mdir + '/voices-v1.0.bin')
d = json.load(open(nar, encoding='utf-8'))
res = {}
for l in d['lines']:
    say = l.get('say', l['text'])
    x, sr, tim = k.create_timed(say, voice='ff_siwis', speed=speed, lang='fr-fr', clause_pause=0.14, sentence_pause=0.32)
    x = np.asarray(x, dtype=np.float32)
    env = np.convolve(np.abs(x), np.ones(240) / 240, mode='same')
    on = np.where(env > 0.01 * env.max())[0]
    a, b = max(0, on[0] - int(0.03 * sr)), min(len(x), on[-1] + int(0.08 * sr))
    x = x[a:b]; fade = int(0.01 * sr); x[:fade] *= np.linspace(0, 1, fade); x[-fade:] *= np.linspace(1, 0, fade)
    sf.write(os.path.join(out, l['id'] + '.flac'), x, sr)
    off = a / sr
    chunks = [c.strip() for c in re.split(r'(?<=[,:;.])\s+', say) if c.strip()]
    marks = [t for t in tim if t.phoneme in ',:;.!?']
    starts = [0.0]
    for m in marks[:len(chunks) - 1]:
        nxt = next((t for t in tim if t.start >= m.end - 1e-6 and t.phoneme.strip() and t.phoneme not in ',:;.!?ˈˌ'), None)
        starts.append(round(max(0.0, (nxt.start if nxt else m.end) - off), 3))
    ok = len(marks) >= len(chunks) - 1
    res[l['id']] = {'dur': round(len(x) / sr, 3), 'chunks': chunks, 'starts': starts, 'aligned': ok}
    print(f"{l['id']:5s} {len(x)/sr:6.2f}s {'ok ' if ok else 'BAD'} {[f'{s:.2f}' for s in starts]}", flush=True)
json.dump({'voice': 'Kokoro v1.0 (onnx, timed export) · ff_siwis', 'speed': speed, 'sr': sr, 'lines': res},
          open(os.path.join(out, 'voice.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('total', round(sum(v['dur'] for v in res.values()), 1), 's')
