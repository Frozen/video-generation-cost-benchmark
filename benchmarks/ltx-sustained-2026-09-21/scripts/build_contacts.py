"""Extract evenly spaced frames for inspection; never replace full-video review."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw


def build(proposal, ltx, fal, output):
    output.mkdir(parents=True, exist_ok=True)
    rows=output/'rows';rows.mkdir(exist_ok=True)
    items=json.loads(proposal.read_text())['fal_reference_requests']
    available=[r for r in items if (ltx/(r['request_id']+'.mp4')).exists() and (fal/r['request_id']/'video.mp4').exists()]
    jobs=[]
    for item in available:
        rid=item['request_id']
        for model,source in [('ltx',ltx/(rid+'.mp4')),('fal',fal/rid/'video.mp4')]:
            jobs.append((source,rows/(rid+'_'+model+'.jpg')))
    def extract(job):
        source,target=job
        if not target.exists():
            subprocess.run(['ffmpeg','-v','error','-i',str(source),'-vf','fps=1,scale=320:-1,tile=5x1',
                            '-frames:v','1','-q:v','3','-y',str(target)],check=True,capture_output=True)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(extract,jobs))
    for item in available:
        rid=item['request_id'];canvas=Image.new('RGB',(1600,440),'#111827');draw=ImageDraw.Draw(canvas)
        for i,model in enumerate(('ltx','fal')):
            draw.text((8,i*220+5),rid+' | '+item['scene_id']+' | '+model+' | five sampled frames; audio not assessed here',fill='white')
            canvas.paste(Image.open(rows/(rid+'_'+model+'.jpg')),(0,i*220+28))
        canvas.save(output/(rid+'.jpg'),quality=90)
    print('Contact sheets available:',len(available),'of',len(items))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('proposal','ltx','fal','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();build(args.proposal,args.ltx,args.fal,args.output)
