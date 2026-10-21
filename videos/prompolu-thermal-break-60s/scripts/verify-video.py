from pathlib import Path
import subprocess,json,sys,hashlib
p=Path(sys.argv[1]);w=int(sys.argv[2]);h=int(sys.argv[3]);out=Path(sys.argv[4])
j=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)]));v=next(s for s in j['streams'] if s['codec_type']=='video');a=next(s for s in j['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'])==(w,h)
assert v['avg_frame_rate']=='30/1' and int(v['nb_read_frames'])==1800
assert abs(float(j['format']['duration'])-60)<.05
assert float(a['duration'])>=59.9
subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True)
probe=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(p),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True,check=True)
vol=[l.strip() for l in probe.stderr.splitlines() if 'mean_volume:' in l or 'max_volume:' in l]
report={'file':str(p),'width':w,'height':h,'fps':30,'frames':1800,'durationSeconds':float(j['format']['duration']),'videoCodec':v['codec_name'],'audioCodec':a['codec_name'],'audioSampleRate':a.get('sample_rate'),'audioDuration':a['duration'],'fullDecode':'passed','audioLevels':vol,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
