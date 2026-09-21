"""Recompute observed queue economics without equating technical and human quality."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics


def distribution(values):
    values = sorted(values)
    if not values:
        return {"count": 0}
    result = {"count": len(values), "mean": statistics.mean(values),
              "stddev_population": statistics.pstdev(values), "min": values[0], "max": values[-1]}
    result.update({"p" + str(p): values[math.ceil(p / 100 * len(values)) - 1] for p in (50, 90, 95, 99)})
    result["percentile_method"] = "nearest rank; descriptive, not an SLA"
    return result


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def analyze(manifest, events, delivery, plan, folder=None):
    requests = {r['request_id']: r for r in manifest['requests'] + manifest.get('retry_requests', [])}
    starts, outcomes = {}, {}
    windows = [e for e in events if e['event'] == 'window_finished']
    opened = [e for e in events if e['event'] == 'window_started']
    if len(opened) != 1 or len(windows) != 1:
        raise ValueError('Exactly one closed queue required; retain incomplete data separately')
    for i, event in enumerate(events):
        if event['sequence'] != i or event['run_id'] != manifest['run_id']:
            raise ValueError('Event identity/sequence mismatch')
        if i and event['worker_elapsed_seconds'] < events[i-1]['worker_elapsed_seconds']:
            raise ValueError('Nonmonotonic event clock')
        kind = event['event']
        if kind == 'request_started':
            rid = event['request_id']
            if rid in starts or len(starts) != len(outcomes):
                raise ValueError('Duplicate submission or changed sequential concurrency')
            for key in ('prompt_sha256', 'scene_id', 'seed', 'requested_video_seconds'):
                if event[key] != requests[rid][key]:
                    raise ValueError('Request differs from frozen input')
            starts[rid] = event
        elif kind in ('artifact_ready', 'request_failed', 'request_unresolved'):
            rid = event['request_id']
            if rid not in starts or rid in outcomes:
                raise ValueError('Outcome has no unique attempt')
            outcomes[rid] = event
    closed = windows[0]
    seconds = closed['worker_window_seconds']
    if seconds <= 0 or not delivery['controller_complete']:
        raise ValueError('Missing complete collection evidence')
    receipts = {r['request_id']: r for r in delivery['receipts']}
    if len(receipts) != len(delivery['receipts']):
        raise ValueError('Duplicate receipts')
    success, rows, hashes = [], [], []
    for rid, start in starts.items():
        result, receipt = outcomes.get(rid, {}), receipts.get(rid, {})
        valid = (result.get('event') == 'artifact_ready' and receipt.get('decode_verified') is True
                 and receipt.get('output_contract_pass') is True
                 and receipt.get('artifact_sha256') == result.get('artifact_sha256'))
        if valid:
            if folder and digest(folder / (rid + '.mp4')) != receipt['artifact_sha256']:
                raise ValueError('Video digest mismatch')
            runtime = result['runtime']
            if (len(runtime['transformer_calls']) != 11 or runtime['resident_total_build_count'] != 1
                    or runtime['transformer_builds_this_request'] != 0):
                raise ValueError('Fresh eleven-forward resident execution not verified')
            success.append(rid)
            hashes.append(receipt['artifact_sha256'])
        rows.append(dict(request_id=rid, scene_id=start['scene_id'], seed=start['seed'],
                         retry_of=start.get('retry_of'), outcome=result.get('event', 'missing'),
                         processing_seconds=result.get('processing_seconds'), technically_delivered=valid,
                         artifact_sha256=receipt.get('artifact_sha256')))
    hourly = Decimal(plan['compute_hourly_usd']) + Decimal(plan['disk_gb']) * Decimal(plan['disk_monthly_usd_per_gb']) / (30 * 24)
    output_seconds = sum(requests[r]['requested_video_seconds'] for r in success)
    cost = hourly * Decimal(str(seconds)) / 3600
    full_delivery_cost = hourly * Decimal(str(delivery['window_seconds'])) / 3600
    per_scene = {}
    for scene in sorted({r['scene_id'] for r in manifest['requests']}):
        selected = [r for r in rows if r['scene_id'] == scene]
        per_scene[scene] = {'attempts': len(selected), 'technically_delivered': sum(r['technically_delivered'] for r in selected),
                            'processing_seconds': distribution([r['processing_seconds'] for r in selected if r['processing_seconds'] is not None])}
    stats = dict(run_id=manifest['run_id'], complete_hour=(seconds >= 3600 and closed['stop_reason'] == 'target_duration_reached'),
                 stop_reason=closed['stop_reason'], queue_seconds=seconds, delivery_window_seconds=delivery['window_seconds'],
                 attempted=len(starts), failed=sum(r['outcome']=='request_failed' for r in rows),
                 unresolved=sum(r['outcome'] in ('request_unresolved','missing') for r in rows),
                 encoded_but_not_validated_delivery=sum(r['outcome']=='artifact_ready' and not r['technically_delivered'] for r in rows),
                 retries=sum(r['retry_of'] is not None for r in rows), technically_delivered=len(success),
                 duplicate_successful_artifact_hashes=len(hashes)-len(set(hashes)),
                 requested_successful_output_seconds=output_seconds,
                 gpu_plus_disk_hourly_usd=str(hourly), queue_cost_usd=str(cost),
                 cost_usd_per_technically_delivered_requested_second=str(cost/Decimal(output_seconds)) if output_seconds else None,
                 delivery_cost_usd_per_requested_second=str(full_delivery_cost/Decimal(output_seconds)) if output_seconds else None,
                 clips_per_hour=len(success)*3600/seconds, output_seconds_per_hour=output_seconds*3600/seconds,
                 successful_processing_seconds=distribution([outcomes[r]['processing_seconds'] for r in success]),
                 all_attempt_processing_seconds=distribution([r['processing_seconds'] for r in rows if r['processing_seconds'] is not None]),
                 per_scene=per_scene, human_quality_accepted=None, quality_adjusted_unit_cost_usd=None,
                 cost_scope='GPU and disk only; startup, warmup and export in separate full-lease accounting; no quality parity claim')
    return stats, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--delivery-folder', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest, plan = json.loads(args.manifest.read_text()), json.loads(args.plan.read_text())
    events = [json.loads(line) for line in (args.delivery_folder/'events.jsonl').read_text().splitlines()]
    delivery = json.loads((args.delivery_folder/'delivery.json').read_text())
    stats, rows = analyze(manifest, events, delivery, plan, args.delivery_folder)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'ltx-summary.json').write_text(json.dumps(stats, indent=2)+'\n')
    with (args.output/'ltx-attempts.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in stats.items() if k!='per_scene'},indent=2))


if __name__ == '__main__':
    main()
