"""Index every published original video with its exact replay inputs."""

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path


def catalog(root):
    manifest=json.loads((root/'ltx/resident.json').read_text())
    events=[json.loads(x) for x in (root/'ltx/resident-delivery/events.jsonl').read_text().splitlines()]
    requests={r['request_id']:r for r in manifest['requests']+manifest.get('retry_requests',[])}
    profile=manifest['profile'];rows=[]
    def add(model, kind, rid, request, video, sha, config):
        if hashlib.sha256((root/video).read_bytes()).hexdigest()!=sha:
            raise ValueError('Catalog artifact mismatch')
        replay=f'replay-inputs/{model}/{rid}.json'
        target=root/replay;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({'model_family':model,'kind':kind,'request':request,'profile':config,
                                     'original_artifact':video,'original_artifact_sha256':sha,
                                     'note':'Same inputs are reproducible; bit-identical output across environments or provider versions is not guaranteed.'},indent=2)+'\n')
        rows.append({'model':model,'kind':kind,'request_id':rid,'scene_id':request['scene_id'],
                     'seed':request['seed'],'prompt':request['prompt'],'prompt_sha256':request['prompt_sha256'],
                     'requested_seconds':5,'video_path':video,'replay_input':replay,'artifact_sha256':sha,
                     'profile_json':json.dumps(config,separators=(',',':'))})
    for event in events:
        if event['event']=='artifact_ready':
            rid=event['request_id'];add('ltx','measured',rid,requests[rid],f'ltx/resident-delivery/{rid}.mp4',event['artifact_sha256'],profile)
        elif event['event']=='warmup_finished':
            ordinal=event['ordinal'];request=dict(manifest['requests'][0],seed=manifest['technical_warmup_seeds'][ordinal-1],request_id=f'warmup-{ordinal}')
            add('ltx','warmup',request['request_id'],request,'ltx/warmups/'+event['artifact'],event['artifact_sha256'],profile)
    fal_rows=json.loads((root/'analysis/fal-attempts.json').read_text())
    for row in fal_rows:
        rid=row['attempt_id'];payload=json.loads((root/f'fal/requests/{rid}.json').read_text())
        request=requests[row['pair_id']]
        if payload['prompt']!=request['prompt'] or payload['seed']!=request['seed']:
            raise ValueError('Paired API replay inputs changed')
        config={'endpoint':row['endpoint'],'payload':payload,'provider_effective_seed_echoed':False}
        add('fal','paired_reference',rid,request,f'fal/videos/{rid}.mp4',row['video_sha256'],config)
    with (root/'VIDEO_CATALOG.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    (root/'VIDEO_CATALOG.json').write_text(json.dumps(rows,indent=2)+'\n')
    escape=html.escape;cards=[]
    for row in rows:
        title=f"{row['model'].upper()} · {row['request_id']} · {row['kind']}"
        search=' '.join(str(row[k]) for k in ('model','kind','request_id','scene_id','seed','prompt'))
        cards.append(f'''<article data-search="{escape(search.lower(),quote=True)}"><h2>{escape(title)}</h2>
<p>{escape(row['scene_id'])} · seed <code>{row['seed']}</code></p>
<video controls preload="none" src="{escape(row['video_path'],quote=True)}"></video>
<p>{escape(row['prompt'])}</p><p><a href="{row['video_path']}" download>Original MP4</a> · <a href="{row['replay_input']}">Exact replay inputs</a></p>
<details><summary>SHA-256 and profile</summary><code>{row['artifact_sha256']}</code><pre>{escape(json.dumps(json.loads(row['profile_json']),indent=2))}</pre></details></article>''')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>All original benchmark videos</title>
<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px;background:#fafafa;color:#17202a}input{width:95%;padding:14px;font:inherit}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}article{background:white;padding:20px;border:1px solid #ddd;border-radius:10px}h2{font-size:19px}video{width:100%;background:#111}pre{white-space:pre-wrap;overflow-wrap:anywhere}code{overflow-wrap:anywhere}[hidden]{display:none!important}</style>
<h1>All original benchmark videos</h1><p>131 measured LTX clips, 20 fal references and two LTX warmups. Every output is included. Extract the complete evidence archive before opening this page. No media loads until you play it.</p>
<p>Exact prompts, seeds and generation profiles accompany every video. A matching seed does not guarantee bit-identical output on a different environment or a changed hosted model. These videos have passed decoding checks; human quality acceptance is unassigned.</p>
<p><a href="VIDEO_CATALOG.csv">CSV catalog</a> · <a href="VIDEO_CATALOG.json">JSON catalog</a> · <a href="protocol/REPRODUCE.md">Reproduction instructions</a></p>
<label for="filter">Find a request, scene, model, seed or prompt</label><p><input id="filter" placeholder="R0042, fal, warmup, coffee, a seed…"></p><p id="count"></p><main>'''+''.join(cards)+'''</main>
<script>const cards=[...document.querySelectorAll('article')], filter=document.querySelector('#filter'), count=document.querySelector('#count');function update(){const q=filter.value.toLowerCase().trim();let n=0;for(const card of cards){card.hidden=!card.dataset.search.includes(q);if(!card.hidden)n++;}count.textContent=n+' / '+cards.length+' videos';}filter.addEventListener('input',update);update();</script></html>'''
    (root/'videos.html').write_text(page)
    print(json.dumps({'catalog_videos':len(rows),'ltx_measured':sum(r['model']=='ltx' and r['kind']=='measured' for r in rows),
                      'fal':sum(r['model']=='fal' for r in rows),'warmups':sum(r['kind']=='warmup' for r in rows)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path)
    catalog(parser.parse_args().evidence)
