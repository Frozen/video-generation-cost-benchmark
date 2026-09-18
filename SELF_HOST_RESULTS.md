# First self-host result: H3 Base on four H100 SXM GPUs

September 18, 2026. **One five-second request completed; the Pod was deleted
and its absence verified. No paid resource remains running.**

[Watch or download the original MP4 (0.59 MB)](results/P01_EN_RUNPOD_H100X4_5S_001.mp4).
The public file is byte-identical to the download; no trimming or re-encoding.
[Machine-readable evidence](results/P01_EN_RUNPOD_H100X4_5S_001.json) and
[measurement CSV](results/SELF_HOST_MEASUREMENTS.csv).

## Outcome

| Measurement | Observed |
|---|---:|
| Request through completed local download | **83.462 s** |
| Agreed latency limit | 15 s; **failed, 5.56x over the limit** |
| SGLang-reported inference time | 77.365 s |
| Denoising stage | 74.620 s |
| Decoding stage | 1.308 s |
| Automatic startup warmup | 46.74 s, separate from the measured request |
| Request-window compute estimate | **USD 0.300003**, before setup/storage/idle time |
| Allocation-to-verified-deletion window | 16 min 48.397 s |
| Whole-rental window estimate | **USD 3.92**, compute plus temporary disk |
| Actual provider charge | Not reconciled; billing returned no records yet |

This configuration did **not** meet the customer wait target. Even the optimistic
compute-only estimate is about the standard fal H3 tariff of USD 0.30, before
adding setup, storage, paid idle time and failed/low-quality outputs. It does not
establish a cheaper service than the already measured fal Max/Turbo alternatives.

One observation is not an average, p95, throughput test or profitability result.
There are zero accepted outputs under the latency gate, so **cost per accepted
output is undefined**, not USD 0.30. The whole experiment's tariff/window estimate
is approximately USD 4.52 including the earlier USD 0.60 fal calculation; neither
provider's final invoice has been reconciled.

## Same scene, explicitly changed language instruction

The operator requested English-only speech/text after seeing the API samples.
This output therefore uses **P01_EN**, not the unchanged P01 comparison request.
The original kitchen/cartoon-onion prompt is retained verbatim, followed by:

> Any spoken words, dialogue, narration, or on-screen text must be in English only. Do not use Spanish, Russian, or other languages.

Original prompt hash: `493ef9be797d7fbf6407589f08a76830078ba2dfd0d8eaf990d2209852f0de6a`.
Modified prompt hash: `9c924c21f39702c03de5287bb3307e1b6df82303b9e6d352704e7fa7a91a96a7`.
No fal request was rerun. This is a related-scene diagnostic, **not an exact-prompt
paired comparison or proof that the deployments are equivalent**. English was
requested; speech language and audio quality have not yet been verified by review.

## Actual configuration

- Runpod Secure Cloud, AP-IN-1 (India), **4 x H100 SXM 80 GB**, USD 13.96/hour
  aggregate compute. All four cards cooperate on one output, not four replicas.
- GPU-visible memory: 81,559 MiB per card. Pairwise topology: NV18. Provider
  allocation: 112 vCPUs, reported host memory 1006 GiB, 300 GB temporary disk.
- H3 Base FL2VA, `t2va`; 5 s, 768-pixel short edge, requested 16:9, seed 42;
  50-point schedule / 49 denoising iterations, `quality=lossless`, batch 1.
- SGLang TP2 + Ulysses2, encoder placement `auto`, eager execution;
  no quantization, LoRA, AdaLN/Cache-DiT acceleration or Turbo substitution.
- Model revision `42ed227ee7df40d41602854ae760620d6eb651fe`;
  SGLang source `408d2334c34d387a36a26398dff9a8f004328344`;
  container digest `sha256:6bcaa47db52f78ce0d67863b8b2431221b79bc23204a80cad757fa819d00e921`.
- Preinstalled `/opt/sglang/bin/python`: torch 2.13.0+cu130, transformers 5.12.1,
  diffusers 0.37.0, av 16.1.0. No replacement PyTorch installation was required.
- Observed native loader behavior includes FP16 video-decoder weights. The earlier
  shorthand "BF16/FP32" was not a complete description of every runtime component.
  We did not add a precision override. CUDA multicast initialization was skipped
  by the runtime; the request still completed with NVLink connectivity.

The [official SGLang recipe](https://docs.sglang.io/cookbook/diffusion/MiniMax/MiniMax-H3)
documents the four-H100 topology. This run verifies that it executes here; it
does not reproduce every upstream prompt, timing boundary or benchmark condition.

## Where the rental window went

| Event | UTC |
|---|---|
| Pod allocated | 02:11:25 |
| Container starts after image download/extraction | 02:17:05 |
| Remote deadline guard verified | 02:17:06 |
| Correct-environment service launcher starts | 02:21:09 |
| Model snapshot download begins | 02:22:33 |
| Pipeline loaded; API starts | 02:24:30 |
| One built-in warmup | 46.74 s before readiness |
| Client submits P01_EN | 02:25:24 |
| MP4 completely downloaded | 02:26:47 |
| Logs exported and Pod deletion verified | 02:28:13 |

Allocation to submission was **838.896 s**, including image pull, SSH/runtime
verification, local orchestration/preparation, checkpoint loading and warmup.
This is not all model download time. The first SSH probe used system Python,
which lacked torch; the image's preinstalled environment resolved that issue.
Download to verified deletion was **86.038 s**, including detection, evidence
export and teardown. That closeout overhead is included, not hidden.

The measured request is the **first user request after built-in warmup**, not a
fully cold startup and not an average of repeated warm requests. A log sample
during denoising showed all GPUs at 100% utilization and 65,087–65,261 MiB used.
The API reported `peak_memory_mb=61070`; its aggregation/allocator scope is not
independently verified, so it must not be presented as the sum across four cards.

## Cost calculation and utilization

The request-window compute estimate uses the runtime's measured processing
interval, not the client download time:

`13.96 * 77.36466605588794 / 3600 = USD 0.300003`.

The allocation window estimate uses the provider's `startedAt` through our
verified-absence timestamp: USD 3.910339 compute plus USD 0.011671 for 300 GB disk,
using the published USD 0.10/GB/month tariff and a 30-day month approximation.
This is a window-based estimate, **not an invoice or a proven billable duration**.
The billing query returned zero records; that does not mean the rental was free.
The USD 16 ledger reservation remains pending reconciliation.

Assuming the same per-request processing time, no batching, no failures and no
other overhead, the compute-only cost per completed output would be:

| Workload utilization | Compute-only scenario |
|---|---:|
| 100% | USD 0.30 |
| 75% | USD 0.40 |
| 50% | USD 0.60 |
| 25% | USD 1.20 |
| 10% | USD 3.00 |

These are modeled utilization scenarios, not a load test or accepted-output costs.
Hourly Pod price is unchanged during idle time; lower utilization spreads the
same rental cost over fewer outputs. Do not add electricity again to a rental bill.

## Output integrity and remaining review

H.264, 1344x768, 124 frames at 24 fps; 5.166667 s video and 5.175 s container.
AAC 32 kHz stereo. Size: 593,907 bytes. SHA-256:
`8f4e8e81cd7380417137dd69f690d4299f68521683ff2d619d202f47a4ca7676`.
Full audio/video decoding passed. The native canvas is 7:4 rather than exact
16:9; no corrective crop, trim or quality-matching re-encode was applied.
Its smaller file size than fal is not proof of equal compression or quality.

Five extracted frames show the kitchen, chef, stretched cartoon onion and eyes
on vegetables. This is an informal visual check, not blind human evaluation.
Full temporal quality, prompt adherence, speech language and audio review remain
pending. No VBench was run. One short built-in warmup and one full user generation
occurred; only the user generation is a published benchmark clip.

## Next-run preparation, before renting more GPUs

Prepare and test scripts, payload mappings, environment paths, output validation
and automatic export/termination locally before allocation. Reuse the pinned
runtime; do not reinstall PyTorch unnecessarily. Automate the complete paid
window so documentation and user interaction are not on its critical path.

For repeat runs in a chosen data center, consider preloading the pinned weights
to a [network volume via S3 without a GPU Pod](https://docs.runpod.io/storage/network-volumes).
Include storage and transfer/CPU preparation costs, verify that the region has
usable GPU stock, and compare volume read speed with the already fast Hub download.
A volume is data-center-specific and does not guarantee GPU availability.
It cannot remove image pulls, model-to-VRAM loading, kernel startup or warmup.

No persistent volume was bought in this run. Terminating the Pod removed its
temporary model cache; original video, logs and runtime evidence are saved locally.
The pinned public weights can be downloaded again. More expensive cards or
quantized/distilled variants need a separately identified comparison, not an
assumption that a higher hourly price produces a cheaper acceptable clip.

Validation: `python3 -m unittest discover -s tests -q`,
`python3 scripts/validate.py`, `git diff --check`, MP4 hash verification,
`ffprobe`, and a full `ffmpeg -v error -i video.mp4 -f null -` decode. The protocol
validator still describes historical v0.8.1 planning; it is not a readiness claim
for the completed fallback. Runtime, SSH and one real request were verified live.
