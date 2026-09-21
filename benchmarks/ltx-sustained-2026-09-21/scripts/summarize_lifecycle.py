"""Allowlisted lifecycle accounting and observed time variation for a closed trial."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from summarize_sustained import distribution


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def summarize(lease, plan, summary):
    state = json.loads((lease / 'state.json').read_text())
    if state['status'] != 'terminated':
        raise ValueError('Teardown must be verified before full-lease accounting')
    allocation = json.loads((lease / 'allocation-observation.json').read_text())
    events = [json.loads(x) for x in (lease / 'resident-delivery/events.jsonl').read_text().splitlines()]
    started = next(e for e in events if e['event'] == 'window_started')
    finished = next(e for e in events if e['event'] == 'window_finished')
    provider_start = datetime.fromisoformat(allocation['startedAt'].replace('Z', '+00:00')).timestamp()
    absent = state['verified_absent_at']
    hourly = Decimal(summary['gpu_plus_disk_hourly_usd'])
    if Decimal(str(allocation['cost'])) != Decimal(plan['compute_hourly_usd']):
        raise ValueError('Observed provider compute rate changed')
    duration = absent - provider_start
    cost = hourly * Decimal(str(duration)) / 3600
    output_seconds = Decimal(summary['requested_successful_output_seconds'])
    lifecycle = {
        'run_id': state['run_id'], 'pod_id': state['pod_id'],
        'provider_started_at_utc': allocation['startedAt'],
        'queue_started_at_utc': utc(started['epoch']),
        'queue_finished_at_utc': utc(finished['epoch']),
        'pod_absence_verified_at_utc': utc(absent),
        'provider_start_to_verified_absence_seconds': duration,
        'before_measured_queue_seconds': started['epoch'] - provider_start,
        'after_measured_queue_seconds': absent - finished['epoch'],
        'queue_seconds_monotonic': summary['queue_seconds'],
        'gpu_plus_disk_hourly_usd': str(hourly),
        'full_lease_gpu_plus_disk_usd_estimate': str(cost),
        'full_lease_usd_per_measured_requested_second_estimate': str(cost / output_seconds),
        'provider_actual_charge_usd': None,
        'provider_actual_charge_status': 'Separate billing evidence required; this is elapsed time times the quoted rate.',
        'scope': 'Includes preparation, warmup, measured work, export and teardown through verified absence; warmup outputs excluded from denominator. Excludes client computer, engineering and service overhead.',
        'provider_allocation_observation': {key: allocation[key] for key in ('id', 'name', 'status', 'startedAt', 'cost', 'dataCenterId', 'gpu')},
    }
    starts = {e['request_id']: e for e in events if e['event'] == 'request_started'}
    artifacts = [e for e in events if e['event'] == 'artifact_ready']
    bins = []
    for index in range(6):
        lower, upper = index * 600, (index + 1) * 600
        selected = [e for e in artifacts if lower <= starts[e['request_id']]['worker_elapsed_seconds'] - started['worker_elapsed_seconds'] < upper]
        bins.append({'request_start_minute_from': lower / 60, 'request_start_minute_to': upper / 60,
                     'completed_attempts': len(selected), 'processing_seconds': distribution([e['processing_seconds'] for e in selected])})
    primary_seeds = [e['seed'] for e in starts.values() if not e.get('retry_of')]
    variation = {
        'run_id': state['run_id'], 'ten_minute_bins': bins,
        'bin_assignment': 'Request start relative to queue start; finish the whole last request. Descriptive processing latency, not throughput estimated from an incomplete bin.',
        'first_to_last_bin_mean_change_percent': (bins[-1]['processing_seconds']['mean'] / bins[0]['processing_seconds']['mean'] - 1) * 100,
        'observed_primary_seed_count': len(primary_seeds),
        'observed_distinct_primary_seeds': len(set(primary_seeds)),
        'worker_process_ids': sorted(set(e['runtime']['worker_pid'] for e in artifacts)),
        'transformer_forward_counts': sorted(set(len(e['runtime']['transformer_calls']) for e in artifacts)),
        'resident_total_build_counts': sorted(set(e['runtime']['resident_total_build_count'] for e in artifacts)),
        'causal_claim': None,
        'limitation': 'One host and one hour. Prompt mix, host behavior and sampling can change latencies; this is not an estimate of fleet reliability or a production SLA.'
    }
    return lifecycle, variation


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lease', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    lifecycle, variation = summarize(args.lease, json.loads(args.plan.read_text()), json.loads((args.results/'ltx-summary.json').read_text()))
    for filename, value in [('lifecycle-costs.json', lifecycle), ('ltx-variation.json', variation)]:
        (args.results/filename).write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps({'lifecycle': lifecycle, 'variation': variation}, indent=2))
