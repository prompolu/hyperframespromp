import asyncio, json, os, subprocess
from pathlib import Path
import edge_tts, edge_tts.communicate
edge_tts.communicate._SSL_CTX.load_verify_locations(cafile=os.environ.get('SSL_CERT_FILE','/etc/ssl/certs/ca-certificates.crt'))
root=Path(__file__).resolve().parent.parent
async def one(i,c):
 target=root/'assets/audio'/f'voice-{i+1:02}.mp3'
 await edge_tts.Communicate(c['text'],voice='fr-FR-DeniseNeural',rate='+7%',proxy=os.environ.get('HTTPS_PROXY')).save(str(target))
 duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(target)]))
 print(i+1,duration,flush=True)
 return {**c,'file':str(target.relative_to(root)),'duration':duration}
async def main():
 cues=json.loads((root/'narration.json').read_text())
 results=await asyncio.gather(*(one(i,c) for i,c in enumerate(cues)))
 for i,c in enumerate(results):
  boundary=results[i+1]['start']-.25 if i<5 else 59.6
  if c['start']+c['duration']>boundary: raise RuntimeError(f'Voice cue {i+1} overruns its scene; adjust rate before rendering')
 (root/'audio-meta.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
asyncio.run(main())
