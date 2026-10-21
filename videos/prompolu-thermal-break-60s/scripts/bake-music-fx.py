"""Bake the saved HyperFrames carve into a stem when browser file FX is blocked.
Keeps the original bed, source voice and generated audio-mix.json editable.
"""
from pathlib import Path
import json,math,re,html
import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
root=Path(__file__).resolve().parent.parent
mix=json.loads((root/'audio-mix.json').read_text());sr,samples=wavfile.read(root/'assets/audio/music-original.wav')
x=samples.astype(np.float64)/np.iinfo(samples.dtype).max if np.issubdtype(samples.dtype,np.integer) else samples.astype(np.float64)
if x.ndim>1:x=x.mean(axis=1)
t=np.arange(len(x))/sr
lanes={l['target']:l['points'] for l in mix['data-automation']['lanes']}
def env(name,times,default):
 p=lanes.get(name)
 if not p:return np.full_like(times,default,dtype=float)
 return np.interp(times,[v['t'] for v in p],[v['v'] for v in p])
for node in mix['data-fx-chain']['nodes']:
 par=node['params'];target='fx.'+node['id']+'.gain'
 if node['type']=='peaking':
  block=round(sr*.01);zi=np.zeros(2);out=np.empty_like(x)
  for offset in range(0,len(x),block):
   stop=min(offset+block,len(x));gain=float(env(target,np.array([(offset+stop)/(2*sr)]),par['gain'])[0]);A=10**(gain/40);w=2*np.pi*par['frequency']/sr;alpha=np.sin(w)/(2*par['q']);c=np.cos(w)
   b=np.array([1+alpha*A,-2*c,1-alpha*A]);a=np.array([1+alpha/A,-2*c,1-alpha/A]);b/=a[0];a/=a[0]
   out[offset:stop],zi=lfilter(b,a,x[offset:stop],zi=zi)
  x=out
 elif node['type']=='gain':x*=10**(env(target,t,par['gain'])/20)
 else:raise RuntimeError('Unsupported saved effect '+node['type'])
assert np.isfinite(x).all() and np.max(np.abs(x))<1
wavfile.write(root/'assets/audio/music-carved.wav',sr,(np.clip(x,-1,1)*32767).astype(np.int16))
s=(root/'index.html').read_text();tag=re.search(r'<audio\b[^>]*id="music-bed"[^>]*>',s).group();new=tag.replace('music-original.wav','music-carved.wav')
for attr in ['data-fx-chain','data-fx-carve']:new=re.sub(r'\s'+attr+r'="[^"]*"','',new)
volume={'version':1,'lanes':[l for l in mix['data-automation']['lanes'] if l['target']=='volume']}
new=re.sub(r'data-automation="[^"]*"','data-automation="'+html.escape(json.dumps(volume),quote=True)+'"',new)
(root/'index.html').write_text(s.replace(tag,new))
print('Baked five time-varying peaking filters + gain envelope, 10ms blocks. Volume fade remains live in HyperFrames.')
