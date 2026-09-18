# H3 acceleration retry: both videos produced

September 18, 2026. **The pinned LoRA compatibility fix worked for both public
adapters. Four-step H3 met the 15-second end-to-end target on this one request;
eight-step H3 did not. Quality acceptance is still pending.**

Watch the original files: [eight steps](results/P01_EN_RUNPOD_H100X4_LARRY8_5S_002.mp4)
and [four steps](results/P01_EN_RUNPOD_H100X4_LIGHT4_5S_002.mp4).
Both requests used P01_EN, seed 42, five seconds, 768p, 16:9, native audio, and
the same four H100 SXM GPUs in AP-IN-1. These are public H3 adapters, **not LTX
and not fal's proprietary Max/Turbo weights**. [Approved configuration](ACCELERATION_TRIAL.md).

| Configuration | Request to downloaded video | Runtime inference | GPU-only USD / requested video-second | 15 s target |
|---|---:|---:|---:|---|
| Earlier base H3, 49 evaluations | 83.462 s | 77.365 s | 0.060001 | Fail |
| Larry Turbo v4, 8 evaluations | 21.873 s | 13.751 s | 0.010665 | Fail |
| LightX2V v0.1, 4 evaluations | 13.741 s | 7.647 s | 0.005930 | Pass |

The new requests are approximately 3.82x and 6.07x faster end-to-end than the
earlier base request. These are observed single-sample ratios, not throughput,
p95 latency or a guarantee. The adapter runs also use the disclosed runtime fix;
the earlier base run did not need it. No repeated requests or fal reruns occurred.

## Cost: separate inference from the paid experiment

The quoted aggregate rental rate was **USD 13.96/hour for all four GPUs**.
Runtime-only cost is `inference_seconds × 13.96 / 3600 / 5`: approximately
USD 0.05333 for the eight-step clip and USD 0.02965 for the four-step clip.
This excludes setup, idle time, delivery and storage. It is not a demonstrated
all-in production price or profit margin.

The entire two-clip rental lasted **900.853 seconds / 15 min 0.853 s**, from
03:57:05.185 to verified deletion at 04:12:06.038 UTC. Estimated GPU cost:
USD 3.493307; 300 GB temporary disk: USD 0.010427; **total: USD 3.503734**.
Across ten requested output seconds, this pilot therefore cost approximately
**USD 0.35037 per video-second**, including its setup and idle time. Shared
startup is not arbitrarily assigned to one adapter. The window is an estimate,
not the provider's reconciled billable interval; the scoped billing query still
returned zero records. Actual charge remains unknown, not zero.

The [earlier failed adapter rental](ACCELERATION_RESULTS.md), approximately
USD 3.04, and [failed CPU preload](PRELOADED_MODELS.md) are separate experiment
expenses, not erased or included again in the USD 3.50 figure. Including the
earlier failed GPU attempt makes these two acceleration trials approximately
USD 6.54 before CPU/storage preparation. The successful base run's approximately
USD 3.92 is also separate. Outstanding admission holds total USD 22.20 of the
USD 25 cap; holds are not actual charges and remain unreconciled.

## What happened and what was measured

The source-pinned patch guards the `quant_method` capability lookup without
bypassing LoRA. Both services completed synthetic warmup before a user request
was admitted. The logs then confirmed **8/8** and **4/4** denoising iterations.
Larry's adapter applied to 259/266 wrapped layers; LightX2V's applied to 208/266.
Remaining layers retained base weights. Exact adapter/source pins and patch
hashes are in the JSON records; no silent weight or runtime substitution occurred.

| Stage | Eight-step service | Four-step service |
|---|---:|---:|
| Built-in synthetic warmup | 46.28 s | 6.35 s |
| User denoising stage | 11.0346 s | 4.9192 s |
| User decoding stage | 1.2963 s | 1.2965 s |
| Completion observed to download complete | 3.930 s | 3.243 s |

Warmup is separate from user inference. Both warmups logged the default
`1344x768x124f, 2/50 steps` profile, not their full user-request schedules.
The second service reused on-disk model and kernel caches on the same Pod:
its shorter startup/warmup is **not** an unbiased cold-start comparison.
The first service's 81-file base snapshot fetch took about 76 seconds according
to the progress log. Image startup, distributed initialization, VRAM loading
and warmup account for additional preparation time; they are not download time.

End-to-end measurements include the client's SSH transport, polling and file
download. They are not just the denoiser, nor latency from a production serving
stack. Sampled peak used memory was 68,103 MiB for eight steps and 67,591 MiB for
four steps on the most-used GPU. Per-GPU one-second samples and stage timings
are summarized in the JSON. Sampled GPU utilization is not customer-demand
utilization or measured sustainable batch throughput.

## Output checks and remaining review

Both original MP4s fully decode without errors: H.264, 1344×768, 124 frames at
24 fps, AAC stereo at 32 kHz. Native video duration is 5.166667 seconds; the cost
denominator remains the **five requested seconds**. Files are 1,115,202 and
1,028,924 bytes and were copied without re-encoding.

Five sampled frames from each show a chef, kitchen and expressive cartoon onion,
with different framing and onion deformation. This is only an informal still-
frame inspection, not motion/audio acceptance or a blind quality comparison.
English-only instructions were included, but speech language and intelligibility
have not been independently verified. Prompt match, human review and acceptable-
output cost remain open. VBench was not run.

**Next decision:** watch and listen to both files. Four-step is a candidate that
passed this latency check, not yet an accepted-quality or profitable service.
No additional paid run is automatically authorized by the remaining balance.

## Evidence and cleanup

- [Eight-step measurements](results/P01_EN_RUNPOD_H100X4_LARRY8_5S_002.json)
- [Four-step measurements](results/P01_EN_RUNPOD_H100X4_LIGHT4_5S_002.json)
- [Whole-rental accounting](results/P01_RUNPOD_H100X4ACCEL_5S_002.json)
- [Comparison CSV](results/ACCELERATION_MEASUREMENTS.csv)

Original videos, runtime records, service logs and GPU samples were downloaded
before deletion. An independent Pod GET returned 404; Pod and network-volume
lists were empty. Ephemeral model caches disappeared with the completed rental;
published outputs and private diagnostics remain available. No further paid
resource was retained. The Runpod workflow informed explicit readiness checks,
bounded spending and verified cleanup; the user's in-place-debugging preference
kept failure retention available until the original deadline.

Reproduce the offline export with `python3 scripts/export_acceleration.py`.
The script requires both completed private journals, validates full decoding and
pins, then generates the allowlisted JSON/CSV and copies the original videos.
Raw prompts, credentials, account identifiers and private logs are not published.

Validation: `python3 -m unittest discover -s tests -q` passed 110 tests;
`python3 scripts/h3_lora_compat.py --check-source private/upstream-minimax-h3.py`
reproduced the old capability-check error and passed the patched probe;
`python3 scripts/validate.py` passed the historical planning contract (not a new
paid-run authorization); `git diff --check` passed. The offline exporter ran
`ffprobe` and `ffmpeg -v error -xerror -i <video> -f null -` for both full files.
