"""Export allowlisted measurements and original videos, never signed URLs or credentials."""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil

from summarize_sustained import distribution


def export(private, proposal, destination):
    destination.mkdir(parents=True, exist_ok=True)
    videos = destination / 'videos/fal'
    videos.mkdir(parents=True, exist_ok=True)
    rows = []
    pricing = json.loads((private / 'pricing-check.json').read_text())
    base_rate = Decimal(str(pricing['pricing']['unit_price']))
    for path in sorted(private.glob('*/state.json')):
        state = json.loads(path.read_text())
        fields = ('attempt_id', 'pair_id', 'scene_id', 'seed', 'prompt_sha256', 'retry_of',
                  'endpoint', 'status', 'submitted_epoch', 'completion_observed_epoch',
                  'submit_to_completion_seconds', 'submit_to_download_seconds', 'timing_clock',
                  'video_sha256', 'video_bytes', 'decode_verified', 'provider_dit_seconds')
        row = {key: state.get(key) for key in fields}
        row['provider_request_id'] = state.get('queue', {}).get('request_id')
        row['status_observations'] = state.get('events', [])
        header = path.parent / 'response-headers.txt'
        units = re.findall(r'^x-fal-billable-units:\s*(\S+)', header.read_text(), re.M | re.I) if header.exists() else []
        row['provider_reported_billable_units'] = units[0] if len(units) == 1 else None
        row['provider_reported_cost_usd'] = str(Decimal(units[0]) * base_rate) if len(units) == 1 else None
        if state['status'] == 'download_complete':
            video = path.parent / 'video.mp4'
            assert hashlib.sha256(video.read_bytes()).hexdigest() == state['video_sha256']
            shutil.copyfile(video, videos / (state['attempt_id'] + '.mp4'))
            probe = json.loads((path.parent / 'probe.json').read_text())
            row['streams'] = [{k: s.get(k) for k in ('codec_type', 'codec_name', 'width', 'height',
                              'nb_frames', 'r_frame_rate', 'duration', 'sample_rate', 'channels')}
                              for s in probe['streams']]
            row['container_duration_seconds'] = float(probe['format']['duration'])
        rows.append(row)
    (destination / 'fal-attempts.json').write_text(json.dumps(rows, indent=2) + '\n')
    uninterrupted = [r for r in rows if r['timing_clock'] == 'monotonic' and r['status'] == 'download_complete']
    summary = {'endpoint': proposal['fal']['endpoint'], 'primary_attempts': sum(r['retry_of'] is None for r in rows),
               'retry_attempts': sum(r['retry_of'] is not None for r in rows),
               'downloaded': sum(r['status'] == 'download_complete' for r in rows),
               'fully_decoded': sum(r.get('decode_verified') is True for r in rows),
               'generation_failures': sum(r['status'] == 'provider_failed' for r in rows),
               'controller_errors': 1,
               'controller_error_note': 'Initial HTTP 202 IN_PROGRESS observation rejection; original request resumed without resubmission.',
               'all_observed_submit_to_download_seconds_including_controller_error': distribution([r['submit_to_download_seconds'] for r in rows if r['status'] == 'download_complete']),
               'uninterrupted_submit_to_completion_seconds': distribution([r['submit_to_completion_seconds'] for r in uninterrupted]),
               'uninterrupted_submit_to_download_seconds': distribution([r['submit_to_download_seconds'] for r in uninterrupted]),
               'observation_gap_pairs_excluded_from_latency': [r['pair_id'] for r in rows if r['timing_clock'] != 'monotonic'],
               'reported_billable_units': str(sum(Decimal(r['provider_reported_billable_units']) for r in rows if r['provider_reported_billable_units'] is not None)),
               'authenticated_base_rate_usd_per_unit': str(base_rate),
               'provider_reported_cost_usd': str(sum(Decimal(r['provider_reported_cost_usd']) for r in rows if r['provider_reported_cost_usd'] is not None)),
               'billing_scope': 'Per-response billable units times authenticated pricing; no account invoice retrieved.',
               'human_quality_accepted': None,
               'api_timing_note': 'timings.inference is denoising only, never client end-to-end latency'}
    (destination / 'fal-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    export(args.private, json.loads(args.proposal.read_text()), args.output)
