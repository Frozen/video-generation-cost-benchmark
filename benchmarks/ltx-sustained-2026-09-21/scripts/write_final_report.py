"""Render the report from final machine-readable measurements only."""

import argparse
from decimal import Decimal
import json
from pathlib import Path


def read(root, name):
    return json.loads((root/name).read_text())


def render(root):
    s=read(root,'ltx-summary.json');l=read(root,'lifecycle-costs.json')
    t=read(root,'gpu-telemetry-summary.json');v=read(root,'ltx-variation.json')
    f=read(root,'fal-summary.json')
    if not s['complete_hour']:raise ValueError('Completed hour required')
    unit=Decimal(s['cost_usd_per_technically_delivered_requested_second'])
    full=Decimal(l['full_lease_usd_per_measured_requested_second_estimate'])
    fal=Decimal(f['provider_reported_cost_usd'])/(f['fully_decoded']*5)
    old=Decimal('0.0032872889814840934')
    d=s['successful_processing_seconds']
    bins='\n'.join(f"| {b['request_start_minute_from']:.0f}–{b['request_start_minute_to']:.0f} | {b['completed_attempts']} | {b['processing_seconds']['mean']:.3f} | {b['processing_seconds']['max']:.3f} |" for b in v['ten_minute_bins'])
    scenes='\n'.join(f"| {name} | {p['attempts']} | {p['technically_delivered']} | {p['processing_seconds']['mean']:.3f} | {p['processing_seconds']['max']:.3f} |" for name,p in s['per_scene'].items())
    return f'''# One hour of varied LTX generation: measured results

**LTX completed {s['technically_delivered']} five-second requests over {s['queue_seconds']:.3f} seconds ({s['queue_seconds']/60:.2f} minutes), with {s['failed']} generation failures and {s['retries']} retries.** All counted videos were downloaded, matched to their worker hashes and fully decoded. GPU plus disk cost was **${unit:.6f} per requested video-second**, or **${unit*5:.5f} per clip**. The twenty fal H3 Max Turbo references cost **${fal:.5f}/s** from provider-reported billing units: **{fal/unit:.2f}× the LTX measured-queue cost**.

This is a cross-model technical-output cost comparison. It does not establish equal quality or show that the same H3 model can be served at the LTX price. The hour tests the robustness of the earlier short LTX estimate.

## Cost and throughput

| Scope | Elapsed seconds | Cost per requested video-second | What is included |
|---|---:|---:|---|
| LTX measured GPU queue | {s['queue_seconds']:.3f} | ${unit:.9f} | Pipeline execution, encoding, journaling, inter-request gaps, failures and retries if any |
| LTX through final verified delivery | {s['delivery_window_seconds']:.3f} | ${Decimal(s['delivery_cost_usd_per_requested_second']):.9f} | Measured work plus controller observation, download and decode tail |
| LTX complete lease estimate | {l['provider_start_to_verified_absence_seconds']:.3f} | ${full:.9f} | Provider start through verified deletion; preparation, warmups and export included |
| fal twenty paired API requests | Not an hour-long load test | ${fal:.9f} | 160 reported billing units at $0.0125/unit; $2.00 total |

The GPU quote is $2.09/hour; 200 GB disk adds $0.02777778/hour. The formula is `(GPU + disk hourly rate) × elapsed hours / successfully delivered requested output seconds`. Each successful clip contributes five requested seconds. The last request finishes completely, so the actual queue exceeds the one-hour minimum.

The measured queue produced **{s['requested_successful_output_seconds']} requested video-seconds**, equivalent to **{s['clips_per_hour']:.2f} clips/hour** or **{s['output_seconds_per_hour']:.2f} video-seconds/hour**. Queue GPU/disk cost was **${Decimal(s['queue_cost_usd']):.4f}**. The complete lease estimate was **${Decimal(l['full_lease_gpu_plus_disk_usd_estimate']):.4f}**; on that boundary fal is **{fal/full:.2f}×** as expensive per measured output second. GPU figures are quoted-rate calculations, not an invented invoice; any retrieved billing reconciliation is a separate artifact. Client hardware, engineering, networking/storage outside the quoted disk and other service overhead are excluded.

The [earlier ten-request result](../../ltx-rtx-2026-09-20/README.md) was $0.003287289/s. This hour's figure differs by **{(unit/old-1)*100:+.2f}%**. The short-run cost estimate held over this measured hour. This is not a controlled speedup: the host CPU changed from AMD EPYC 9555 to EPYC 9535 and the prompt mix changed.

Native streams are preserved: LTX uses 121 frames at 24 fps; fal returns 124 frames at 24 fps. Both were requested as five-second clips. The comparison uses requested seconds consistently rather than crediting incidental extra container duration to one model.

![Measured cost with scope labels](cross-model-cost.png)

## Stability and observed failures

There were **{s['attempted']} attempts, {s['failed']} generation failures, {s['unresolved']} unresolved outcomes, {s['retries']} retries, and {s['encoded_but_not_validated_delivery']} encoded outputs without valid delivery**. No successful output hashes repeated ({s['duplicate_successful_artifact_hashes']} duplicates). Observed primary requests used {v['observed_distinct_primary_seeds']} distinct seeds. All measured artifacts came from worker PID {v['worker_process_ids'][0]}, one resident transformer build, and eleven fresh transformer forwards per request. Reusing loaded weights is not reusing generated output; the caching controls and limits are described in [WARMUP_AND_SEEDS.md](../WARMUP_AND_SEEDS.md).

| Processing latency | Seconds |
|---|---:|
| Mean | {d['mean']:.3f} |
| Population standard deviation | {d['stddev_population']:.3f} |
| Minimum / maximum | {d['min']:.3f} / {d['max']:.3f} |
| p50 / p90 | {d['p50']:.3f} / {d['p90']:.3f} |
| p95 / p99 | {d['p95']:.3f} / {d['p99']:.3f} |

Percentiles use nearest rank. These are descriptive pipeline-to-encoded-file timings, not a production SLA or client request latency under contention.

| Request start minutes | Completed attempts | Mean processing seconds | Maximum seconds |
|---|---:|---:|---:|
{bins}

The last bin's mean differs from the first by {v['first_to_last_bin_mean_change_percent']:+.2f}%. Assignment uses request start time, with the last whole request counted. This is descriptive variation, not a causal thermal or caching claim.

![Latency across the complete queue](ltx-hour-variation.png)

A continuously backlogged queue does not mean 100% hardware GPU utilization. The {t['samples']} one-second `nvidia-smi` samples inside the measured window reported mean utilization **{t['utilization']['mean']:.2f}%**, range {t['utilization']['min']:.0f}–{t['utilization']['max']:.0f}%. Mean board power was {t['power_watts']['mean']:.1f} W and maximum observed memory use was {t['memory_mib']['max']:.0f} MiB. Encoding, text/audio processing and transfers remain part of the pipeline. Original telemetry is retained; {t['incomplete_final_csv_record_excluded']} incomplete trailing CSV record(s) were excluded by the parser. The first sample is {t['first_sample_after_window_start_seconds']:.2f} seconds after queue start; the available CSV ends {t['window_end_after_last_sample_seconds']:.2f} seconds before queue finish. Reported utilization/power are averages of the available samples, not a reconstructed full-hour trace. The complete generation event journal covers the full queue.

Zero observed generation failures describes this sample; it does not establish a zero production failure rate. The protocol counts failed work and repeats if they occur; it does not inject them artificially.

## API reference and quality

fal received twenty preselected paired inputs, not an hour-long load test. All twenty original videos are preserved, with zero observed generation failures or retries. The first request hit a controller HTTP-202 observation bug; polling resumed the same provider request without a duplicate submission. All-twenty submit-to-download mean was {f['all_observed_submit_to_download_seconds_including_controller_error']['mean']:.3f} seconds, including that interruption. The nineteen uninterrupted observations averaged {f['uninterrupted_submit_to_download_seconds']['mean']:.3f} seconds. Full distributions and timing boundaries are in [FAL_RESULTS.md](FAL_RESULTS.md). The provider's denoising-only field is not end-to-end latency.

The [randomized A/B review package](QUALITY_REVIEW.md) contains all twenty original pairs and frozen scene criteria. [VISUAL_SCREEN.md](VISUAL_SCREEN.md) records an unblinded AI screen of five sampled frames from every video, including negative examples. It does not replace human full-motion/audio assessment. **Human acceptance rates, quality parity and quality-adjusted cost remain unmeasured.** No model winner is assigned from price alone.

## Per-scene observations

| Scene | Attempts | Technically delivered | Mean processing seconds | Maximum seconds |
|---|---:|---:|---:|---:|
{scenes}

## Reproduction and limits

[Protocol and source](../README.md) · [Recompute instructions](../REPRODUCE.md) · [Original videos and complete evidence release](https://github.com/Frozen/video-generation-cost-benchmark/releases/tag/ltx-sustained-2026-09-21).

Machine-readable summaries include [queue statistics](ltx-summary.json), [individual attempts](ltx-attempts.csv), [lease accounting](lifecycle-costs.json), [time variation](ltx-variation.json) and [GPU telemetry](gpu-telemetry-summary.json). The release preserves raw worker/setup logs, event journal, receipts, telemetry, actual manifest, all measured original videos, both warmup videos, the twenty API videos and the pinned source archive. Hash inventories permit offline integrity checks and recomputation without renting a GPU.

Twenty hand-selected prompts are more varied than the previous single-prompt check, but are not production-traffic sampling. This was one host-hour, one model profile and sequential batch-one requests. It cannot establish fleet reliability, concurrency performance or the cheapest achievable serving configuration. The fal figure is the observed promotional price at the time of this experiment, not a guaranteed future price. Different models can produce different adherence, motion, audio and acceptance rates; those differences must be judged from the paired videos.
'''


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('results',type=Path)
    args=parser.parse_args();(args.results/'RESULTS.md').write_text(render(args.results))
