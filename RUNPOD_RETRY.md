# Bounded self-host retry and hardware fallback

September 18, 2026 (UTC). The operator authorized another B300 attempt, then
another region and alternative GPUs if the original hardware remained unavailable.
The USD 25 total experiment cap and the frozen P01 request remain unchanged.

## Second B300 allocation: rejected

Attempt `P01_RUNPOD_B300_5S_002` was prepared at 02:07:25 UTC using the same
one-B300 configuration in EUR-IS-1, CUDA 13.0, minimum 384 GiB host RAM and
300 GB temporary disk. Immediately before creation, the Iceland catalog said
`LOW` with CUDA 13.0 available. The actual create request again returned HTTP
400: the requested instance was unavailable.

Both MCP and a read with the creation account's key subsequently returned an
empty Pod list. No inference was submitted. The local guard exited after the
rejection; the unused USD 18 reservation was settled at zero. Incremental
GPU/storage expense is USD 0 from resource evidence, not a billed invoice item.
The first attempt's private journal is unchanged. No additional fal call occurred.

## Authorized fallback: four H100 SXM GPUs in India

At 02:09 UTC, a global one-B300 Secure Pod query with CUDA >= 13.0 returned
`NONE`, with both listed CUDA versions unavailable. There was no alternative
B300 region to request from that snapshot. A four-H100 Secure Pod query for
Canada, India and Iceland with CUDA 13.0 returned `LOW` in AP-IN-1 and EUR-IS-3.
The next selected region is **AP-IN-1 (India)**.

| Setting | Selected fallback |
|---|---|
| Attempt | `P01_RUNPOD_H100X4_5S_001` |
| Hardware | 4 x NVIDIA H100 80GB HBM3 (H100 SXM), Secure Cloud |
| Catalog compute rate | USD 3.49/GPU-hour; USD 13.96/hour for four |
| Host RAM filter | 96 GiB per GPU, 384 GiB total; proposed, not a measured minimum |
| Disk / access | 300 GB temporary container disk; SSH only; no network volume |
| CUDA filter | 13.0 |
| Attempt reservation | USD 16 within the existing USD 25 cap |
| Deadline | One hour from preparation, including boot, setup, downloads and export |
| Runtime | The same pinned SGLang image/source and H3 revision as the first attempt |
| Parallelism | TP2 + Ulysses2, automatic encoder placement, native precision, eager |

The [upstream H3 recipe](https://docs.sglang.io/cookbook/diffusion/MiniMax/MiniMax-H3)
documents this four-H100 topology. It is not our measurement. Verify the actual
host, price, interconnect, SSH and remote guard before loading the model.
The one-GPU RAM filter is not multiplied unchanged across four GPUs.

The selected request is still H3 Base FL2VA, `t2va`, P01, seed 42, five seconds,
native 768P with audio, the original 50-point schedule, no quantization, cache,
LoRA or Turbo substitution. The 15-second request-to-download target is unchanged.
No extra fal request, ten-second clip, optimization or load test is authorized.
License applicability remains as recorded in [SELF_HOST_PREFLIGHT.md](SELF_HOST_PREFLIGHT.md).

The lifecycle helper now requires explicit hardware, region and attempt selection
for this fallback. It preserves existing journals and has no automatic create
retry. Local and embedded remote shutdown guards are best-effort controls, not
a provider-enforced spending cap. A failed readiness check requires termination;
an ambiguous allocation requires reconciliation before any retry.

## Live checkpoint at 02:13 UTC: H100 allocated, image initializing

The H100 creation request succeeded at **02:11:25 UTC** in AP-IN-1. The
provider confirmed four H100 SXM GPUs, CUDA 13.0, USD 13.96/hour compute,
112 vCPUs, a reported 1006 GiB host-memory allocation and 300 GB disk.
On-host GPU memory and interconnect are not yet verified.

System logs show image layers downloading and extracting. The Pod's desired
status is `RUNNING`, but its runtime and direct SSH address are still absent;
the CLI reports `initializing`. This is **not inference readiness**.

- Local shutdown guard armed before creation; remote guard not yet verified.
- Deadline: **03:11:24 UTC**, including preparation and image initialization.
- USD 16 reservation remains outstanding; no actual invoice charge reconciled.
- Combined admission exposure: USD 19, including the three prior USD 1 fal
  reservations. USD 6 remains below the total cap, not authorization for more runs.
- No model inference, self-host MP4, measured latency or per-video cost yet.
- No additional fal request or automatic allocation retry.

This is an intermediate checkpoint, not the completed test report. The rental
will be terminated after export, on a failed readiness gate, or at the deadline.
Validation: 75 offline tests passed; `git diff --check` passed. These checks
do not validate the remote runtime or prove a successful model generation.
