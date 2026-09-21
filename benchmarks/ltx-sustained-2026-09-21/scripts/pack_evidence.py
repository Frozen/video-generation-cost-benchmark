"""Build a self-contained public evidence tree from an allowlist of experiment files."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

from summarize_sustained import analyze, digest
from build_video_catalog import catalog


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def package(repo, public, results, output):
    lease=repo/'private/ltx-sustained-rtx6000-001'
    delivery=lease/'resident-delivery'
    manifest=json.loads((lease/'resident.json').read_text())
    plan=json.loads((repo/'ltx-sustained-plan.json').read_text())
    events=[json.loads(x) for x in (delivery/'events.jsonl').read_text().splitlines()]
    receipts=json.loads((delivery/'delivery.json').read_text())
    stats,_=analyze(manifest,events,receipts,plan,delivery)
    if not stats['complete_hour']:
        raise ValueError('Do not package an incomplete run as completed; preserve negative evidence separately')
    if json.loads((lease/'state.json').read_text())['status']!='terminated':
        raise ValueError('Verify lease teardown before preparing the complete release')
    if output.exists():raise FileExistsError('Use a new evidence directory; never overwrite released evidence')
    output.mkdir()
    for path in sorted(public.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            copy(path,output/'protocol'/path.relative_to(public))
    copy(lease/'resident.json',output/'ltx/resident.json')
    state=json.loads((lease/'state.json').read_text())
    write(output/'ltx/state.json', {key:state[key] for key in ('run_id','pod_id','status','verified_absent_at','worker_pid','generation_submissions','windows')})
    allocation=json.loads((lease/'allocation-observation.json').read_text())
    write(output/'ltx/allocation-observation.json', {key:allocation[key] for key in ('id','name','status','startedAt','cost','dataCenterId','gpu')})
    for name in ('events.jsonl','delivery.json'):
        copy(delivery/name,output/'ltx/resident-delivery'/name)
    for receipt in receipts['receipts']:
        name=receipt['request_id']+'.mp4'
        copy(delivery/name,output/'ltx/resident-delivery'/name)
    warmups=[e for e in events if e['event']=='warmup_finished']
    for event in warmups:
        assert digest(lease/event['artifact'])==event['artifact_sha256']
        copy(lease/event['artifact'],output/'ltx/warmups'/event['artifact'])
    for name in ('duration.log','prepare.log','prepare-status.json','dependencies.txt','uv.lock',
                 'gpu-samples.csv','hardware.json','controller.log','guard.log'):
        copy(lease/name,output/'ltx/raw'/name)
    for path in sorted(results.glob('*')):
        if path.is_file():copy(path,output/'analysis'/path.name)
    copy(repo/'private/ltx-audio-source.tar.gz',output/'preparation/ltx-audio-source.tar.gz')
    fal=repo/'private/fal-sustained-paired-001'
    for name in ('billing-reconciliation.json','pricing-check.json'):
        copy(fal/name,output/'fal'/name)
    for state_file in sorted(fal.glob('*/state.json')):
        folder=state_file.parent;state=json.loads(state_file.read_text());rid=state['attempt_id']
        copy(folder/'payload.json',output/'fal/requests'/(rid+'.json'))
        if state['status']=='download_complete':
            copy(folder/'video.mp4',output/'fal/videos'/(rid+'.mp4'))
            response=json.loads((folder/'response.json').read_text())
            response['video']={k:v for k,v in response['video'].items() if k!='url'}
            response['redaction_note']='Signed artifact URL removed. Original response retained privately.'
            write(output/'fal/responses-redacted'/(rid+'.json'),response)
    # Keep credentials, connection files, live signed URLs and account ledgers out.
    forbidden=(b'Authorization: Key ',b'Authorization: Bearer ',b'BEGIN OPENSSH PRIVATE KEY')
    for path in [*output.glob('ltx/raw/*'),*output.glob('fal/responses-redacted/*')]:
        if path.is_file() and any(marker in path.read_bytes() for marker in forbidden):
            raise ValueError('Potential credential material in exported log; inspect privately')
    write(output/'SNAPSHOT.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'status':'completed_hour',
          'ltx_measured_videos':len(receipts['receipts']),'warmup_videos':len(warmups),
          'fal_videos':len(list((output/'fal/videos').glob('*.mp4'))),'human_quality_acceptance':None,
          'public_protocol_directory':'protocol','immutable_preregistration_commit':'7e14d9e','protocol_snapshot_identity':'Exact package bytes are recorded in FILE_SHA256SUMS.json; release index may subsequently add this archive digest.','redactions':'No credentials, signed URLs, SSH connection files or account ledger. Raw measured GPU logs and original videos retained.'})
    (output/'README.md').write_text('''# Completed sustained-load evidence

The `protocol` directory contains the full public report, registered inputs, reproduction instructions and source code. `ltx` contains the actual timed manifest, append-only event log, delivery receipts, all measured original videos, both warmup videos and raw worker/setup/GPU logs. `fal` contains all twenty request bodies, original videos, redacted provider results and billing-unit evidence. `analysis` contains recomputed summaries and figures. The exact pinned source archive is in `preparation`.

Open `videos.html` to browse all 153 originals, search by scene/seed, and download per-video replay JSON. `VIDEO_CATALOG.csv` and `VIDEO_CATALOG.json` map each original file to its exact prompt, seed, profile and SHA-256. Verify bytes with `python3 verify_evidence.py`. It checks the complete file-hash inventory; the protocol's analysis scripts additionally verify request identity, runtime traces, receipts and economics. The separate review archive provides a randomized A/B form for the first twenty pairs. Human quality ratings are not fabricated or assumed.
''')
    verifier='''import hashlib,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\nm=json.loads((r/'FILE_SHA256SUMS.json').read_text())\nfor name,expected in m.items():\n p=r/name\n if not p.is_file():raise SystemExit('Missing file: '+name)\n h=hashlib.sha256()\n with p.open('rb') as f:\n  for b in iter(lambda:f.read(1048576),b''):h.update(b)\n if h.hexdigest()!=expected:raise SystemExit('Hash mismatch: '+name)\nprint('Verified',len(m),'files against the public evidence inventory.')\n'''
    (output/'verify_evidence.py').write_text(verifier)
    catalog(output)
    hashes={str(p.relative_to(output)):digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    write(output/'FILE_SHA256SUMS.json',hashes)
    print(json.dumps({'files':len(hashes),'measured_videos':len(receipts['receipts']),
                      'total_bytes':sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','public','results','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();package(args.repo,args.public,args.results,args.output)
