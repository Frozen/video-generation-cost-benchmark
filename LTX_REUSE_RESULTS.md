# LTX-2.5: warmed baseline versus resident transformer

September 18, 2026. **Keeping transformer weights on the same H100 reduced
processing from 46.459 to 28.496 seconds: 1.63x faster, with 38.7% lower
processing-only cost.** Request-to-download time fell from 55.432 to 34.987
seconds. Both still fail our 15-second target for a five-second video.

This is one measured request per mode, each after its own short technical
warmup. It is not a sustained-load or p95 benchmark, and quality acceptance is
still pending. The Pod was deleted after export and independently returned 404;
the subsequent account Pod list was empty. No new rental is needed to review
these results.

## Watch and compare

| Five-second request | Processing through MP4 | Request to downloaded MP4 | Processing-only USD / requested video-second | 15 s target |
| --- | ---: | ---: | ---: | --- |
| [Warmed ordinary pipeline](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001_BASE_WARM.mp4) | 46.459 s | 55.432 s | 0.009008 | Fail |
| [Warmed resident transformer](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001_REUSE_WARM.mp4) | 28.496 s | 34.987 s | 0.005525 | Fail |

[Summary JSON](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001.json),
[CSV](results/LTX_REUSE_MEASUREMENTS.csv),
[baseline record](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001_BASE_WARM.json),
[resident record](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001_REUSE_WARM.json),
[approved experiment](LTX_REUSE_TRIAL.md).

Processing cost is `processing_seconds * 3.49 / 3600 / 5`. It includes all
pipeline work through encoded MP4, but excludes setup, warmup, idle time,
delivery and disk. It is **not an all-in API price**. Client timing includes
SSH submission, status polling and transfer to the local machine. The observed
client speedup is 1.58x; it is distinct from the 1.63x processing speedup.

## What stayed the same

Both modes ran sequentially on **one H100 SXM 80 GB in CA-MTL-1 at USD 3.49/hour**,
in the same persistent process and lease. The request remained P01_EN, seed 42,
five requested seconds, 1344 x 768, 24 fps and native audio. Each output contains
121 frames / 5.041667 seconds of video. Cost uses five requested seconds, not
the frame-aligned native duration.

Both measured requests used the official distilled BF16 **8 + 3** schedule,
the same six pinned weight files, source revision, model revision, container
and installed dependencies. There was no quantization, compilation, CPU
offload, prompt enhancement, embedding cache, latent cache or output cache.
DiffVAE remained `chunked_eager` with NATTEN 0.21.7; PyTorch 2.13.0+cu132.
Resolved decoder tiling was identical: frame tile 128 / overlap 40, height
768 / overlap 160, width 1344 / overlap 160. Pins and runtime details are in
the records; weight sizes and hashes are in [ltx_config.py](scripts/ltx_config.py).

Each mode first received a short technical warmup using the same target canvas
and two denoising intervals in each native stage, as fixed in the approved
plan. The fixed order was ordinary warmup, ordinary measurement, resident
warmup, resident measurement. The later mode shares filesystem/kernel caches;
this is not a randomized experiment or a fully stabilized throughput test.

## What the optimization changed

The ordinary native pipeline reconstructs and disposes the transformer for
each diffusion stage. The scoped lifecycle patch retains the actual GPU
weights between both stages and the next request. It does not reuse a result.
Prompt encoding, upsampling, decoding and encoding still run for every request.

| Measured boundary | Ordinary warm | Resident warm |
| --- | ---: | ---: |
| Transformer builds during the request | 2 | 0 |
| Transformer build time, included in diffusion stages | 17.704 s | 0 s |
| Prompt encoder | 9.321 s | 10.115 s |
| First diffusion stage, including any build | 11.837 s | 2.634 s |
| Spatial upsampler | 0.704 s | 0.740 s |
| Second diffusion stage, including any build | 13.778 s | 4.354 s |
| Audio decoder | 0.541 s | 0.565 s |
| Lazy video decode and MP4 encoding | 9.419 s | 9.213 s |
| PyTorch peak allocated memory, decimal GB | 42.102 | 62.873 |
| PyTorch peak reserved memory, decimal GB | 46.538 | 65.129 |

The resident transformer was built once during its own warmup and zero times
during its measured request. The 17.704 seconds of baseline construction are
already inside the stage timings; do not add them twice. Remaining small
pipeline overhead is included in the total but not every timed block. Resident
weights fit this 80 GB GPU; that does not establish fit on a 48 GB card.

The two resident diffusion stages total about seven seconds, but the full
processing time is 28.496 seconds. Prompt encoding and video decode/encoding
remain substantial. These are candidates for a future separately approved
experiment, not measured future gains or permission for another rental.

## Output checks and quality limits

All four originals passed SHA-256 transfer verification and full video/audio
decoding with `ffmpeg -v error -xerror`. Both measured videos have the expected
dimensions, frame count and frame rate. Their **full decoded video-stream hashes
are equal**, so the decoded image frames match exactly for this pair. Their
decoded audio hashes differ; the full MP4 files therefore also differ. The
cause and perceptual significance of the audio difference were not established.
Do not describe the complete audiovisual outputs as identical.

Five sampled frames show a chef, a kitchen and an expressive onion. Still-frame
inspection and matching hashes do not establish acceptable motion, prompt
adherence, speech language or intelligibility. Those remain for human review;
no claim that the English-speech issue is solved, and no VBench score is reported.

## Full experiment cost, including preparation

This one rental produced **two measured videos plus two diagnostic warmup
videos**. The whole allocation-to-verified-deletion window was 1,207.406 seconds
(20 min 7 s). GPU rental plus 200 GB temporary disk is approximately
**USD 1.179829 total**, pending provider billing reconciliation. This is below
the USD 4 reservation; the reservation is not the invoice.

- Weight download: 71,118,761,094 bytes in 838.109 seconds (13 min 58 s).
- Preparation after SSH readiness, including download and verification: 947.134 s.
- Processing GPU cost for both warmups: USD 0.088577.
- Processing GPU cost for both measured requests: USD 0.072664.
- Whole rental divided by ten requested measured video-seconds: USD 0.117983/s.

The processing subtotals are already included in the rental estimate, not
additional charges. Warmup processing took 56.200 s in ordinary mode and
35.169 s in resident mode. Their originals are retained as
[ordinary diagnostic](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001_BASE_WARMUP.mp4)
and [resident diagnostic](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001_REUSE_WARMUP.mp4),
not quality-comparison samples. Download timing is an observation of this
rental, not a measured explanation of the network bottleneck. No persistent
paid model cache remains. Prior experiments are separate costs, not included
in the USD 1.18 figure.

## Comparison with our warmed H3 measurements

| Configuration | GPUs | Request to downloaded MP4 | Processing-only USD / requested video-second | 15 s target |
| --- | ---: | ---: | ---: | --- |
| [H3 + Larry, 8 steps](ACCELERATION_RETRY_RESULTS.md) | 4 x H100 | 21.873 s | 0.010665 | Fail |
| [H3 + LightX2V, 4 steps](ACCELERATION_RETRY_RESULTS.md) | 4 x H100 | 13.741 s | 0.005930 | Pass |
| LTX-2.5, ordinary warm | 1 x H100 | 55.432 s | 0.009008 | Fail |
| LTX-2.5, resident warm | 1 x H100 | 34.987 s | 0.005525 | Fail |

H3 logs verify successful built-in synthetic warmup before the measured user
requests: 46.28 s for Larry and 6.35 s for LightX2V, each logged as
`1344x768x124f, 2/50 steps`. H3 is treated as warmed without rerunning it. LTX
also has short technical warmup rather than an extra full generation. This
aligns the broad warmed-service condition, not the architectures, warmup
internals, region, GPU count or frame count (H3 124; LTX 121). All use the same
P01_EN prompt, seed and requested duration, and price their actual GPU counts.

LTX residency has a slightly lower processing-only cost than our four-step H3
sample, but takes substantially longer to deliver. H3 four-step remains the
only self-hosted sample in this table within the latency target; its quality
acceptance also remains pending. No overall winner or production profitability
is established. The [first cold LTX result](LTX_RESULTS.md) remains separate and
unchanged; no warmup time was retrospectively subtracted from it.

## Validation and shutdown

`python3 -B scripts/export_ltx_reuse.py` checked the four completed requests,
closed lease, runtime identity, schedules, original hashes, native video
shape, full decoded streams and observed transformer build counts. The
regression suite (`python3 -B -m unittest discover -s tests -q`) passed 134
tests; `python3 -B scripts/validate.py`, module compilation and
`git diff --check` also passed. The protocol validator checks the retained
planning contract, not output quality or production readiness.

Both measured originals, both warmup originals, per-output records, summary,
CSV and reproducible runner/export code are published. The remote logs and
dependency lock are retained privately. The owned Pod and its temporary disk
were deleted after verified export; account credentials and private journals
are not published. No new test is scheduled.
