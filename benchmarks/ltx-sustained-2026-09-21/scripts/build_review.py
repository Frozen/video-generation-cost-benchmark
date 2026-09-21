"""Create an offline randomized paired review; never invent quality scores."""

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shutil


HTML = '''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Twenty paired video reviews</title>
<style>
body{font:16px system-ui;background:#10151e;color:#edf2ff;margin:0 auto;padding:24px;max-width:1400px}h1{font-size:28px}
button,select,textarea,input{font:inherit;padding:10px;border:1px solid #718199;border-radius:6px;background:#202c40;color:inherit}
button{cursor:pointer}button:hover{background:#344866}nav{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:24px 0}video{width:100%;background:black}article{background:#192231;padding:14px;border-radius:10px}
label{display:block;margin:12px 0}select{float:right;max-width:42%}textarea{box-sizing:border-box;width:100%;min-height:80px}.prompt{white-space:pre-wrap;line-height:1.5}.muted{color:#b1bdd1;font-size:14px}
@media(max-width:700px){.pair{grid-template-columns:1fr}body{padding:14px}}
</style>
<h1>Paired video review</h1>
<p>Watch each clip twice at normal speed. Listen to each separately, then compare. Model names are hidden; the identity key is a separate file. Visible model characteristics can still reveal identity.</p>
<p class="muted">This form starts with no judgments. Playback/decoding alone does not establish quality. Your ratings stay in this browser until you export them.</p>
<nav><button id="prev">Previous</button><strong id="position"></strong><button id="next">Next</button><button id="play">Play both muted</button><button id="export">Export ratings</button><label>Reviewer <input id="reviewer" placeholder="Name or pseudonym"></label></nav>
<h2 id="scene"></h2><details><summary>Exact prompt</summary><p id="prompt" class="prompt"></p></details>
<p><b>Required content:</b> <span id="requirements"></span></p>
<div class="pair"><article id="A"><h2>A</h2><video controls preload="metadata"></video></article><article id="B"><h2>B</h2><video controls preload="metadata"></video></article></div>
<label>Overall preference <select id="preference"><option value="">Unrated</option><option>A</option><option>B</option><option>Tie</option><option>Both unacceptable</option></select></label>
<label>Notes<textarea id="notes" placeholder="Describe specific missing content, artifacts, or audio issues."></textarea></label>
<script id="data" type="application/json">DATA</script><script>
const data=JSON.parse(document.getElementById('data').textContent);const fields=['Prompt adherence','Visual coherence','Audio relevance','Speech/music synchronization'];
let index=0;let saved={};try{saved=JSON.parse(localStorage.getItem(data.storageKey)||'{}')}catch(e){}
for(const side of ['A','B'])for(const field of fields){const label=document.createElement('label');label.append(document.createTextNode(field));const sel=document.createElement('select');sel.dataset.field=field;for(const value of ['','pass','partial','fail','not applicable']){const o=document.createElement('option');o.value=value;o.textContent=value||'Unrated';sel.append(o)}label.append(sel);document.getElementById(side).append(label)}
function persist(){const p=data.pairs[index];const r={pair_id:p.pair_id,scene_id:p.scene_id,reviewer:document.getElementById('reviewer').value,review_method:'human paired normal-speed review',preference:document.getElementById('preference').value,notes:document.getElementById('notes').value,grades:{}};for(const side of ['A','B']){r.grades[side]={};for(const sel of document.querySelectorAll('#'+side+' select'))r.grades[side][sel.dataset.field]=sel.value}saved[p.pair_id]=r;try{localStorage.setItem(data.storageKey,JSON.stringify(saved))}catch(e){}}
function show(){const p=data.pairs[index],r=saved[p.pair_id]||{};document.getElementById('position').textContent=(index+1)+' / '+data.pairs.length;document.getElementById('scene').textContent=p.pair_id+' · '+p.scene_id;document.getElementById('prompt').textContent=p.prompt;document.getElementById('requirements').textContent=p.requirements.join('; ');for(const side of ['A','B']){const v=document.querySelector('#'+side+' video');v.pause();v.src='media/'+p.pair_id+'_'+side+'.mp4';v.muted=false;for(const sel of document.querySelectorAll('#'+side+' select'))sel.value=r.grades?.[side]?.[sel.dataset.field]||''}document.getElementById('preference').value=r.preference||'';document.getElementById('notes').value=r.notes||'';document.getElementById('prev').disabled=index===0;document.getElementById('next').disabled=index===data.pairs.length-1}
document.getElementById('prev').onclick=()=>{persist();index--;show()};document.getElementById('next').onclick=()=>{persist();index++;show()};document.getElementById('play').onclick=()=>{for(const v of document.querySelectorAll('video')){v.muted=true;v.currentTime=0;v.play().catch(()=>{})}};
document.getElementById('export').onclick=()=>{persist();const payload={version:1,criteria_sha256:data.criteria_sha256,mapping_sha256:data.mapping_sha256,exported_at:new Date().toISOString(),reviews:Object.values(saved)};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));a.download='quality-ratings.json';a.click();URL.revokeObjectURL(a.href)};for(const e of document.querySelectorAll('select,textarea,input'))e.addEventListener('change',persist);show();
</script>'''


def build(proposal, criteria, ltx, fal, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'media').mkdir(exist_ok=True)
    requests = json.loads(proposal.read_text())['fal_reference_requests']
    rubric = json.loads(criteria.read_text())
    keyfile = output / 'IDENTITY_KEY.json'
    if keyfile.exists():
        mapping = json.loads(keyfile.read_text())
    else:
        mapping = {r['request_id']: dict(zip(('A','B'), ('ltx','fal') if secrets.randbits(1) else ('fal','ltx'))) for r in requests}
        keyfile.write_text(json.dumps(mapping,indent=2)+'\n')
    pairs=[]
    checksums={}
    for request in requests:
        rid=request['request_id']
        for side, model in mapping[rid].items():
            source=(ltx/(rid+'.mp4')) if model=='ltx' else (fal/rid/'video.mp4')
            target=output/'media'/(rid+'_'+side+'.mp4')
            if not source.is_file():
                raise FileNotFoundError('Missing preregistered pair: '+rid+' '+model)
            shutil.copyfile(source,target)
            checksums[str(target.relative_to(output))]=hashlib.sha256(target.read_bytes()).hexdigest()
        pairs.append(dict(pair_id=rid,scene_id=request['scene_id'],prompt=request['prompt'],requirements=rubric['per_scene'][request['scene_id']]))
    data=dict(pairs=pairs,storageKey='ltx-fal-review-20260921',criteria_sha256=hashlib.sha256(criteria.read_bytes()).hexdigest(),mapping_sha256=hashlib.sha256(keyfile.read_bytes()).hexdigest())
    (output/'review.html').write_text(HTML.replace('DATA',json.dumps(data).replace('<','\\u003c')))
    (output/'VIDEO_SHA256.json').write_text(json.dumps(checksums,indent=2)+'\n')
    (output/'README.md').write_text('''# Offline paired quality review

Open `review.html` in a browser after extracting the complete archive. Play each video twice at normal speed, with audio assessed one clip at a time. The same twenty input prompts/seeds were selected before generation. A/B assignment was randomized independently for each pair. The first pair has a client latency observation gap but its original generated video remains included.

Avoid opening `IDENTITY_KEY.json` until ratings are exported. It contains the model mapping and enables later analysis. Filenames in the review do not identify the model, although visible output characteristics can reveal it. Grades start empty; no quality acceptance or parity has been inferred from decoding. Use “not applicable” for speech/music synchronization when neither is requested. Export ratings to a local JSON file using the button.

All forty original videos are preserved without cropping, normalization or audio alteration. Native durations differ slightly. File hashes tie judgments to the exact artifacts. Full clips remain available in the main evidence archive with their original attempt identifiers.
''')
    print('Prepared all',len(pairs),'randomized original-video pairs; no quality ratings assigned.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('proposal','criteria','ltx','fal','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();build(args.proposal,args.criteria,args.ltx,args.fal,args.output)
