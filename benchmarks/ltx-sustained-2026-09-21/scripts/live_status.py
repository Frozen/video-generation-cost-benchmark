"""Read-only progress snapshots; never submit, retry, or alter the GPU queue."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import statistics
import time


def snapshot(root):
    lease=root/'private/ltx-sustained-rtx6000-001'
    delivery_folder=lease/'resident-delivery'
    delivery=json.loads((delivery_folder/'delivery.json').read_text())
    events=[json.loads(line) for line in (delivery_folder/'events.jsonl').read_text().splitlines()]
    plan=json.loads((root/'ltx-sustained-plan.json').read_text())
    allocation=json.loads((lease/'allocation-observation.json').read_text())
    state=json.loads((lease/'state.json').read_text())
    start=next(e for e in events if e['event']=='window_started')
    ended=next((e for e in events if e['event']=='window_finished'),None)
    receipts={r['request_id'] for r in delivery['receipts'] if r['decode_verified'] and r['output_contract_pass']}
    successful=[e for e in events if e['event']=='artifact_ready' and e['request_id'] in receipts]
    now=time.time()
    result={'observed_utc':datetime.fromtimestamp(now,timezone.utc).isoformat(),
            'queue_minutes':((ended['epoch'] if ended else now)-start['epoch'])/60,
            'generated':sum(e['event']=='artifact_ready' for e in events),'delivered_and_decoded':len(successful),
            'generation_failures':sum(e['event']=='request_failed' for e in events),
            'unresolved':sum(e['event']=='request_unresolved' for e in events),
            'retry_attempts':sum(e['event']=='request_started' and e.get('retry_of') is not None for e in events),
            'closed':ended is not None,'lease_status':state['status']}
    if successful:
        seconds=Decimal(str(successful[-1]['worker_elapsed_seconds']-start['worker_elapsed_seconds']))
        hourly=Decimal(plan['compute_hourly_usd'])+Decimal(plan['disk_gb'])*Decimal(plan['disk_monthly_usd_per_gb'])/720
        unit=hourly*seconds/3600/(len(successful)*5)
        old=Decimal('0.0032872889814840934')
        begin=datetime.fromisoformat(allocation['startedAt'].replace('Z','+00:00')).timestamp()
        until=state.get('verified_absent_at',now)
        full=hourly*Decimal(str(until-begin))/3600/(len(successful)*5)
        result.update(completed_prefix_seconds=str(seconds),warmed_cost_per_requested_second_usd=str(unit),
                      fal_to_warmed_cost_ratio=str(Decimal('.02')/unit),change_vs_previous_warmed_percent=str((unit/old-1)*100),
                      elapsed_lease_cost_per_delivered_second_estimate_usd=str(full),fal_to_elapsed_lease_cost_ratio=str(Decimal('.02')/full),
                      mean_processing_seconds=statistics.mean(e['processing_seconds'] for e in successful),
                      min_processing_seconds=min(e['processing_seconds'] for e in successful),
                      max_processing_seconds=max(e['processing_seconds'] for e in successful))
    result['scope']='Live completed-and-decoded prefix; quoted compute+disk costs. Full elapsed estimate includes setup and in-flight work, not future costs or service overhead. Not a human quality verdict.'
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--journal',type=Path);parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    while True:
        result=snapshot(args.root);line=json.dumps(result)
        if args.journal:
            with args.journal.open('a') as f:f.write(line+'\n')
        print(line,flush=True)
        if args.once or result['closed']:break
        time.sleep(60)
