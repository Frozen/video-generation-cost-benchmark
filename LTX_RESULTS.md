# LTX-2.5: first single-H100 result

September 18, 2026. **The official LTX-2.5 distilled BF16 pipeline successfully
generated video and audio on one H100 SXM 80 GB.** This is one cold first request,
not a warmed service or a production throughput benchmark.

[Watch the original video](results/P01_EN_RUNPOD_H100_LTX25_5S_003.mp4).
[Machine-readable measurements](results/P01_EN_RUNPOD_H100_LTX25_5S_003.json).
[CSV](results/LTX_MEASUREMENTS.csv). [Approved contract and preparation history](LTX_PREFLIGHT.md).

| Measurement | Observed result |
| --- | ---: |
| Request to downloaded original video | 76.163 s |
| Pipeline processing through encoded MP4 | 60.642 s |
| Processing-only GPU cost / requested video-second | USD 0.011758 |
| Processing-only GPU cost / five-second request | USD 0.058789 |
| Whole successful rental, including setup and disk | USD 0.782058 estimate |
| Whole successful rental / requested video-second | USD 0.156412 estimate |
| 15-second request-to-download target | Fail |
| Quality acceptance | Pending human review |

The compute-only figure includes lazy component loading within the pipeline
call, first-use kernels, video decoding and encoding. It excludes imports,
environment setup, weight download, idle time, delivery and disk. The full Python
worker took 65.564 seconds; the client boundary additionally includes SSH,
polling and download. Do not present USD 0.011758 as an all-in API price.

## Exact workload

One P01_EN text-to-video request, seed 42, five requested seconds, 1344 x 768,
24 fps, native audio, prompt enhancement disabled. The original output contains
121 frames / **5.041667 seconds** of video and 5.010 seconds of stereo audio.
All headline cost denominators use the five requested seconds.

The official distilled schedule is **eight first-stage steps plus three
refinement steps**. No community acceleration adapter, FP8 quantization,
transformer compilation, CPU offload or warmup was enabled. DiffVAE used
`chunked_eager` with NATTEN 0.21.7; PyTorch 2.13.0+cu132 / CUDA 13.2.
Model revision, source revision, image digest and six weight hashes are pinned
in the JSON. The installed dependency freeze and uv lock are retained privately.

Sampled peak GPU memory used: **45,083 MiB**. PyTorch peak allocated bytes:
42,101,509,120; reserved: 46,537,900,032. The export retained 744 complete
one-second GPU samples for summary calculation and excluded one partial trailing
CSV row copied while the sampler was appending. This is not a measured workload
utilization or acceptance rate.

## Where processing time went

| Timed boundary, including component loading | Seconds |
| --- | ---: |
| Prompt encoder | 17.327 |
| First diffusion stage | 15.254 |
| Spatial upsampler | 0.784 |
| Second diffusion stage | 14.929 |
| Audio decoder | 1.411 |
| Lazy video decode and MP4 encoding | 10.013 |

These boundaries are not pure kernel times. Native progress logs show roughly
4.5 and 4.8 seconds inside the two denoising loops, but those rounded progress
figures are not a separate validated end-to-end benchmark. The pinned native
`DiffusionStage.__call__` builds and releases the transformer on every call;
the two-stage pipeline therefore rebuilds it twice. Loading and other overhead
must be profiled separately before assigning an exact removable portion.

## Preparation and rental cost

One H100 in CA-MTL-1 cost USD 3.49/hour. Six weight files totaling
**71,118,761,094 bytes** downloaded in **543.977 seconds**, about 130.7 MB/s
aggregate. This download alone corresponds to approximately USD 0.527 of GPU
rental. The precise network bottleneck was not measured; do not infer that this
is an inherent LTX or Runpod download limit.

Preparation after SSH readiness took 669.300 seconds, including dependencies,
download and SHA-256 verification. Allocation to readiness took 711.325 seconds.
The complete allocation-to-verified-deletion window was **800.337 seconds**,
about 13 min 20 s. GPU window estimate: USD 0.775883; 200 GB temporary disk
estimate: USD 0.006175 (USD 0.10/GB per 30-day month). Actual provider usage
charge remains pending reconciliation; the USD 4 admission reservation is not
the cost of the run and has not been settled at an estimate.

Earlier LTX attempt 001 had no allocation and zero charge. Empty attempt 002
was deleted after a permission blocker and retains a separate USD 0.06856 window
estimate. Including that failed preparation gives approximately **USD 0.85062**
for the LTX allocation windows so far, not USD 0.058789 for the entire experiment.

## Output inspection and comparison limits

The original MP4 is 2,433,325 bytes: H.264 video, AAC stereo at 48 kHz. Its SHA-256
matches the on-Pod file, and full decoding with `ffmpeg -v error -xerror` passed.
Five sampled frames show a chef, kitchen and expressive onion, with changes in
framing and presentation. This is only a still-frame inspection: motion quality,
speech language, intelligibility and prompt acceptance are **not verified**.
No VBench evaluation was run.

The earlier [four-step H3 run](ACCELERATION_RETRY_RESULTS.md) was a warmed
four-GPU service. Its 13.741-second client latency and USD 0.005930 processing
cost per requested video-second are not equal-warmth or equal-model comparisons
to this one-GPU LTX cold request. No LTX fal request or API-equivalent pair was
run here. No performance or cost advantage over every competing setup is claimed.

## Optimization candidates, not measured gains

The first candidate is a persistent warm process that reuses loaded components,
especially the transformer between both stages. Merely issuing another request
to the default pipeline does not remove its per-stage reconstruction. Validate
VRAM fit and output correctness; keeping every component resident is unproven.

Then test transformer compilation and DiffVAE `chunked_compile` or
`combined_compile` with compilation/warmup billed separately. FP8 scaled matrix
multiplication is a separate quality/performance experiment on H100, not an
assumed speedup. NATTEN is already installed, so adding it is not a remaining
optimization. These options are described in the
[official optimization guide](https://github.com/Lightricks/LTX-2/blob/a95ab856bf29407b6b066ede0abe1846050db56c/packages/ltx-pipelines/docs/optimization.md).

The model is already distilled: do not copy H3's four-step adapter or arbitrarily
halve the LTX schedule and call that an equivalent optimized model. Keep the
current prompt, seed, dimensions and duration as the baseline. Neither a new
paid optimization run nor a persistent storage rental was started.

## Cleanup and validation

All output, stage logs, dependency records and sampled metrics were downloaded
before deletion. An independent Pod GET returned 404 and the Pod list was empty.
The ephemeral model cache was removed with the completed rental; outputs and
local diagnostics remain. The Runpod workflow supplied bounded admission,
readiness checks and verified cleanup; file-scoped download authorization kept
the HF account credential local.

Reproduce the offline export with `python3 -B scripts/export_ltx.py` using the
completed private journal. Validation: `python3 -B -m unittest discover -s tests
-q` passed **124 tests**; `python3 scripts/validate.py` checks the historical
planning contract, not a new paid-run authorization; `git diff --check` passed.
