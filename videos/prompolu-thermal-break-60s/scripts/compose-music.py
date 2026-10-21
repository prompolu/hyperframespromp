from pathlib import Path
import numpy as np, wave, subprocess
root=Path(__file__).resolve().parent.parent
sr=44100;length=60;n=int(sr*length);mix=np.zeros(n,dtype=np.float64)
def freq(m):return 440*2**((m-69)/12)
def note(m,start,dur,gain):
 a=int(start*sr);k=min(int(dur*sr),n-a)
 if k<=0:return
 t=np.arange(k)/sr;f=freq(m)
 tone=(np.sin(2*np.pi*f*t)+.22*np.sin(2*np.pi*2*f*t)+.07*np.sin(2*np.pi*3*f*t))
 env=(1-np.exp(-t/0.015))*np.exp(-t/1.5)*np.minimum(1,np.maximum(0,(dur-t)/.35))
 mix[a:a+k]+=tone*env*gain
# Original, restrained electric-piano progression; no sampled recording.
chords=[[50,57,61,64,69],[47,54,57,62,66],[43,50,54,57,62],[45,52,57,59,64],
        [50,57,61,64,69],[47,54,57,62,66],[43,50,54,57,62],[45,52,57,61,64]]
for bar,ch in enumerate(chords):
 start=bar*7.5
 for k,m in enumerate(ch[:3]):note(m,start,5.2,.055)
 for j in range(10):note(ch[2+(j%3)]+12,start+j*.75,2.4,.05 if j%2==0 else .035)
fade=np.minimum(1,np.arange(n)/sr/2)*np.minimum(1,(length-np.arange(n)/sr)/2.3);mix*=fade
mix/=max(1,np.max(np.abs(mix))*1.3)
target=root/'assets/audio/music-original-dry.wav'
with wave.open(str(target),'w') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((mix*32767).astype('<i2').tobytes())
subprocess.run(['ffmpeg','-v','error','-y','-i',str(target),'-af','aecho=0.8:0.3:120|240|480:0.12|0.07|0.04,lowpass=f=5000,loudnorm=I=-20:TP=-3:LRA=8','-t','60','-ar','48000',str(root/'assets/audio/music-original.wav')],check=True)
target.unlink()
print('Composed original 60-second instrumental bed')
