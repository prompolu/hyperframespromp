from pathlib import Path
import json,html
root=Path(__file__).resolve().parent.parent
scenes=[
 {'id':'scene-01','kicker':'LE CONFORT PREND FORME','title':['RUPTURE DE','PONT THERMIQUE'],'body':'Le détail qui change la façon de penser votre fenêtre.','photo':'residential-1.jpg','layout':'hero','credit':'Photographie d’illustration · Unsplash','tag':'COMPRENDRE EN 60 SECONDES'},
 {'id':'scene-02','kicker':'01 / COMPRENDRE LE MATÉRIAU','title':['L’ALUMINIUM','CONDUIT LA CHALEUR.'],'body':'Un matériau solide et durable, mais naturellement conducteur.','photo':'residential-2.jpg','layout':'photo-top','credit':'Photographie d’illustration · Unsplash','tag':'EXTÉRIEUR / INTÉRIEUR'},
 {'id':'scene-03','kicker':'02 / INTERROMPRE LA CONTINUITÉ','title':['UNE COUPURE.','UNE LIAISON.'],'body':'Le polyamide relie les parties aluminium tout en créant une liaison isolante.','photo':'residential-2.jpg','layout':'hero','credit':'Photographie d’illustration · Unsplash','tag':'POLYAMIDE ISOLANT'},
 {'id':'scene-04','kicker':'03 / PENSER LE CONFORT','title':['L’HIVER. L’ÉTÉ.','LE MÊME SOIN.'],'body':'Limiter les échanges thermiques, selon le système et la configuration choisis.','photo':'residential-3.jpg','layout':'photo-top','credit':'Photographie d’illustration · Unsplash','tag':'UNE MENUISERIE BIEN PENSÉE'},
 {'id':'scene-05','kicker':'04 / CHOISIR L’ENSEMBLE','title':['PROFILÉ. VITRAGE.','QUALITÉ DE POSE.'],'body':'La performance se construit avec tous les éléments de la fenêtre.','photo':'facade.jpg','layout':'hero','credit':'Photo : SEIER+SEIER · CC BY 2.0 · recadrée','tag':'UNE CONFIGURATION ADAPTÉE'},
 {'id':'scene-06','kicker':'FÈS / SEFROU','title':['PARLONS DE','VOTRE PROJET.'],'body':'La qualité, notre meilleur profil.','photo':'residential-1.jpg','layout':'closing','credit':'Photographie d’illustration · Unsplash','tag':'prompolu.com'}
]
(root/'compositions/scenes').mkdir(parents=True,exist_ok=True)
for i,s in enumerate(scenes):
 sid=s['id'];prefix='#'+sid;photo=s['photo'];layout=s['layout'];title=''.join(f'<span class="headline-line">{html.escape(t)}</span>' for t in s['title'])
 # Every photo keeps its original color. Motion and cropping only; no generative imagery.
 css=f'''
 @font-face {{font-family:"Anton";src:url("../../assets/fonts/Anton-Regular.ttf") format("truetype");font-weight:400;font-style:normal;font-display:block;}}
 @font-face {{font-family:"DM Sans";src:url("../../assets/fonts/DM-Sans-Regular.ttf") format("truetype");font-weight:400;font-style:normal;font-display:block;}}
 @font-face {{font-family:"DM Sans";src:url("../../assets/fonts/DM-Sans-Semibold.ttf") format("truetype");font-weight:600;font-style:normal;font-display:block;}}
 {prefix} {{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;background:#F1F0EC;color:#15171A;font-family:"DM Sans",sans-serif;}}
 {prefix} * {{box-sizing:border-box;}}
 {prefix} .masthead {{position:absolute;left:108px;right:108px;top:91px;height:80px;display:flex;align-items:flex-start;justify-content:space-between;border-bottom:2px solid #D8D5CE;}}
 {prefix} .logo {{display:block;width:326px;height:auto;}}
 {prefix} .number {{font-size:25px;letter-spacing:.13em;padding-top:4px;}}
 {prefix} .copy {{position:absolute;left:108px;right:108px;top:230px;}}
 {prefix} .kicker {{margin:0 0 28px;font-size:24px;font-weight:600;letter-spacing:.12em;color:#765333;line-height:1.4;}}
 {prefix} h1 {{margin:0;display:flex;flex-direction:column;gap:8px;font-family:"Anton",sans-serif;font-size:91px;line-height:1.16;font-weight:400;letter-spacing:-.018em;}}
 {prefix} .headline-line {{display:block;}}
 {prefix} .photo-window {{position:absolute;left:72px;right:72px;top:565px;height:867px;overflow:hidden;background:#D8D5CE;}}
 {prefix} .photo-motion {{position:absolute;inset:0;will-change:transform;}}
 {prefix} .photo {{display:block;width:100%;height:100%;object-fit:cover;object-position:{'30% 50%' if i==2 else '50% 50%'};}}
 {prefix} .photo-credit {{position:absolute;left:108px;right:108px;top:1453px;margin:0;font-size:23px;line-height:1.4;color:#15171A;}}
 {prefix} .lower {{position:absolute;left:108px;right:108px;top:1530px;}}
 {prefix} .tag {{display:inline-block;margin:0 0 22px;color:#765333;font-size:25px;letter-spacing:.09em;font-weight:600;line-height:1.4;}}
 {prefix} .body {{margin:0;font-size:36px;line-height:1.42;max-width:850px;}}
 {prefix} .footer {{position:absolute;left:108px;right:108px;bottom:105px;display:flex;justify-content:space-between;gap:20px;padding-top:22px;border-top:2px solid #D8D5CE;font-size:24px;line-height:1.4;}}
 {prefix} .progress-track {{position:absolute;left:108px;right:108px;bottom:84px;height:5px;background:#D8D5CE;}}
 {prefix} .progress-fill {{height:100%;width:100%;background:#8C6A45;transform-origin:0 50%;}}
 '''
 if layout=='photo-top':
  css+=f'''{prefix} .photo-window {{top:217px;height:865px;left:72px;right:72px;}} {prefix} .photo-credit {{top:1100px;}} {prefix} .copy {{top:1170px;}} {prefix} h1 {{font-size:86px;}} {prefix} .lower {{top:1506px;}} {prefix} .body {{font-size:35px;}}'''
 if layout=='closing':
  css+=f'''{prefix} .photo-window {{top:230px;height:890px;}} {prefix} .photo-credit {{top:1138px;}} {prefix} .copy {{top:1208px;}} {prefix} h1 {{font-size:103px;}} {prefix} .lower {{top:1555px;}} {prefix} .tag {{font-size:43px;letter-spacing:0;font-weight:600;}} {prefix} .body {{font-size:33px;}}'''
 # One continuous camera channel per image; all movements are deterministic.
 pose=[(1.02,1.12,0,-24),(1.12,1.03,-22,10),(1.08,1.15,28,-18),(1.1,1.04,16,-14),(1.02,1.10,-15,22),(1.1,1.03,-8,8)][i]
 ease=['expo.out','power4.out','circ.out','power3.out','sine.out','power2.out'][i]
 content=f'''<!doctype html><html lang="fr"><head><meta charset="UTF-8"></head><body><template>
 <style>{css}</style>
 <div id="{sid}" data-composition-id="{sid}" data-width="1080" data-height="1920" data-duration="10" data-fps="30">
 <header class="masthead"><img class="logo" src="../../assets/brand/logo-prompolu.png" alt="PROMPOLU Aluminium" width="602" height="83"><span class="number">0{i+1} / 06</span></header>
 <div class="photo-window" data-layout-allow-overflow><div class="photo-motion"><img class="photo" src="../../assets/photos/{photo}" alt="Photographie architecturale d’illustration : menuiserie et espace réel" /></div></div>
 <p class="photo-credit">{html.escape(s['credit'])}</p>
 <div class="copy"><p class="kicker">{html.escape(s['kicker'])}</p><h1>{title}</h1></div>
 <div class="lower"><p class="tag">{html.escape(s['tag'])}</p><p class="body">{html.escape(s['body'])}</p></div>
 <footer class="footer"><span>PROMPOLU ALUMINIUM</span><span>{'prompolu.com' if i<5 else 'FÈS · SEFROU'}</span></footer>
 <div class="progress-track"><div class="progress-fill"></div></div>
 </div>
 <script>
 (()=>{{const tl=gsap.timeline({{paused:true}});
 tl.fromTo("{prefix} .photo-motion",{{scale:{pose[0]},x:{pose[2]}}},{{scale:{pose[1]},x:{pose[3]},duration:10,ease:"none"}},0);
 tl.fromTo("{prefix} .kicker",{{opacity:0}},{{opacity:1,duration:.3,ease:"power1.out"}},.12);
 tl.fromTo("{prefix} .headline-line",{{clipPath:"inset(0 100% 0 0)",y:16}},{{clipPath:"inset(0 0% 0 0)",y:0,duration:.75,stagger:.12,ease:"{ease}"}},.20);
 tl.fromTo("{prefix} .tag",{{opacity:0,x:-12}},{{opacity:1,x:0,duration:.4,ease:"sine.out"}},1.0);
 tl.fromTo("{prefix} .body",{{opacity:0,y:18}},{{opacity:1,y:0,duration:.65,ease:"power2.out"}},1.2);
 tl.fromTo("{prefix} .progress-fill",{{scaleX:0}},{{scaleX:1,duration:10,ease:"none"}},0);
 window.__timelines["{sid}"]=tl;tl.seek(0);}})();
 </script></template></body></html>'''
 (root/f'compositions/scenes/{sid}.html').write_text(content)
 (root/f'compositions/scenes/{sid}.motion.json').write_text(json.dumps({'duration':10,'assertions':[{'kind':'appearsBy','selector':f'{prefix} .body','bySec':2.1},{'kind':'staysInFrame','selector':f'{prefix} .copy'},{'kind':'staysInFrame','selector':f'{prefix} .lower'},{'kind':'keepsMoving','withinSelector':prefix,'maxStaticSec':2}]},indent=2)+'\n')
fontcss='''@font-face{font-family:"Anton";src:url("assets/fonts/Anton-Regular.ttf") format("truetype");font-weight:400;font-style:normal;font-display:block;}@font-face{font-family:"DM Sans";src:url("assets/fonts/DM-Sans-Regular.ttf") format("truetype");font-weight:400;font-style:normal;font-display:block;}@font-face{font-family:"DM Sans";src:url("assets/fonts/DM-Sans-Semibold.ttf") format("truetype");font-weight:600;font-style:normal;font-display:block;}'''
hosts='\n'.join(f'<div id="host-{s["id"]}" class="clip" data-composition-id="{s["id"]}" data-composition-src="compositions/scenes/{s["id"]}.html" data-start="{i*10}" data-duration="10" data-track-index="0" data-track-kind="graphics" data-width="1080" data-height="1920"></div>' for i,s in enumerate(scenes))
automation=html.escape(json.dumps({'version':1,'lanes':[{'target':'volume','points':[{'t':0,'v':0},{'t':2,'v':.34},{'t':57,'v':.34},{'t':60,'v':0}]}]}),quote=True)
main=f'''<!doctype html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080, height=1920"><title>PROMPOLU — Rupture de pont thermique, 60 secondes</title><link rel="icon" href="data:,"><script src="assets/vendor/gsap.min.js"></script><style>{fontcss}html,body{{margin:0;width:1080px;height:1920px;overflow:hidden;background:#F1F0EC;}}#film{{position:relative;width:100%;height:100%;overflow:hidden;background:#F1F0EC;}}#film>.clip{{position:absolute;inset:0;}}</style></head><body><div id="film" data-composition-id="prompolu-film-60s" data-start="0" data-duration="60" data-fps="30" data-width="1080" data-height="1920">
{hosts}
<audio id="voiceover" src="assets/audio/voiceover-fr.wav" data-start="0" data-duration="60" data-track-index="1" data-volume="1"></audio>
<audio id="music-bed" src="assets/audio/music-original.wav" data-start="0" data-duration="60" data-track-index="2" data-volume="0.34" data-automation="{automation}"></audio>
</div><script>const master=gsap.timeline({{paused:true}});window.__timelines["prompolu-film-60s"]=master;master.seek(0);</script></body></html>'''
(root/'index.html').write_text(main)
(root/'scenes.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2)+'\n')
(root/'STORYBOARD.md').write_text('# PROMPOLU — 60 secondes\n\nPhotographies réelles uniquement. Fond ivoire #F1F0EC dominant, encre #15171A, bronze #8C6A45. Six scènes de 10 secondes. Voix off française et musique originale.\n\n'+ '\n\n'.join(f'## Frame {i+1}\nstatus: built\nsrc: compositions/scenes/{s["id"]}.html\nstart: {10*i}\nduration: 10\nmotion: caption-clip-wipe adapted; multi-phase-camera transform principle, one continuous photographic crop\nbeat: {" / ".join(s["title"])}\nphoto: assets/photos/{s["photo"]}\n' for i,s in enumerate(scenes)))
print('Built six editable photo-led sub-compositions, 60 seconds, French narration and original music.')
