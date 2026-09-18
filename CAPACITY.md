# Capacity and deployability: measured constraints, not missing results

Last updated September 18, 2026 (UTC).

**Two B300 allocation requests were rejected; a later four-H100 fallback in
India was allocated and completed one request.** It was then deleted. A second
four-H100 lease for an adapter trial also allocated, but failed in software
without a video and was deleted; see [ACCELERATION_RESULTS.md](ACCELERATION_RESULTS.md). The
[generation statistics](SELF_HOST_RESULTS.md) are separate from the allocation
findings here. [Retry report](RUNPOD_RETRY.md). Earlier failures remain recorded.

A third four-H100 allocation completed the patched eight-step and four-step
requests, then was deleted at 04:12:06 UTC. [Results](ACCELERATION_RETRY_RESULTS.md).
Separate CPU-only storage preparation failed and its Pod/volume were deleted.

The claim is specific to one configuration, region and time. It does **not** mean
that all B300s, all regions, or all Runpod GPUs were unavailable.

## Observation register

All catalog checks below concern Pods, not Serverless or clusters. Catalog
availability is a snapshot, not a reservation or a successful allocation.

| ID | Date (UTC) | Scope and evidence | Result |
|---|---|---|---|
| A01 | 2026-09-17 | Actual create request: 1 x B300, Secure Cloud, EUR-IS-1, CUDA 13.0, minimum 384 GiB host RAM, 300 GB container disk | HTTP 400: requested instance unavailable; no Pod allocated |
| A02 | 2026-09-17/18 | Subsequent one-B300 Secure Cloud checks restricted to Iceland | Top-level `NONE`; no compatible CUDA 13.0 stock reported, despite some broader/nested `LOW` summaries |
| A03 | 2026-09-18 | One B300, Secure Cloud, US, CUDA >= 13.0 | `LOW`, US-WA-2; USD 7.89/GPU-hour; not rented and not a license-cleared alternative |
| A04 | 2026-09-18 | One B300, Community Cloud, all countries, CUDA >= 13.0 | `NONE`; listed USD 6.94/GPU-hour is not an available offer |
| A05 | 2026-09-18 | Four H100 SXM GPUs, Secure Cloud, Iceland, CUDA >= 13.0 | `LOW`, EUR-IS-3; USD 3.49/GPU-hour, USD 13.96/hour for four; catalog only |
| A06 | 2026-09-18, after A02/A05 | One B300, Secure Cloud, Iceland, CUDA >= 13.0 | Changed to `LOW`, EUR-IS-1, CUDA 13.0 available, USD 7.89/GPU-hour; catalog only at this checkpoint |
| A07 | 2026-09-18 02:07 UTC | Second actual create: same B300/RAM/disk/region configuration as A01, after another Iceland `LOW` lookup | HTTP 400 capacity rejection; subsequent same-account Pod list empty; reservation settled at USD 0 |
| A08 | 2026-09-18 02:09 UTC | One B300, Secure Cloud, global, CUDA >= 13.0 | `NONE`, CUDA 13.0 and 13.2 unavailable; no alternative region listed |
| A09 | 2026-09-18 02:09 UTC | Four H100 SXM GPUs, Secure Cloud, Canada/India/Iceland, CUDA 13.0 | `LOW` in AP-IN-1 and EUR-IS-3; USD 13.96/hour aggregate compute |
| A10 | 2026-09-18 02:11 UTC | Actual create: 4 x H100 SXM, AP-IN-1, CUDA 13.0, minimum 96 GiB RAM/GPU, 300 GB disk | Allocated at USD 13.96/hour; image initializing at 02:13 UTC; inference not run |
| A11 | 2026-09-18 02:25–02:28 UTC | One P01_EN generation on the allocated H100 host, then export and deletion | MP4 downloaded in 83.462 s; latency failed; Pod absence verified at 02:28:13 UTC |
| A12 | 2026-09-18 03:11–03:24 UTC | Separate allocation: 4 x H100 SXM, AP-IN-1, for an adapter trial | Allocation succeeded; eight-evaluation request failed on a LoRA compatibility error, no video; four-step variant not started; deletion verified at 03:24:48 UTC. [Evidence](ACCELERATION_RESULTS.md). |
| A13 | 2026-09-18 03:51–03:55 UTC | CPU-only preload: two vCPUs, 8 GB RAM, EU-NL-1, 200 GB STANDARD volume | CPU/volume allocated; HF downloader killed with SIGKILL, cause unconfirmed. No verified cache; CPU and volume deletion verified. [Evidence](PRELOADED_MODELS.md). |
| A14 | 2026-09-18 03:57–04:12 UTC | Approved patched retry: 4 x H100 SXM, AP-IN-1 | Both outputs downloaded, 21.873 s / 13.741 s end-to-end. Four-step latency passed; quality pending. Pod deletion verified. [Evidence](ACCELERATION_RETRY_RESULTS.md). |

A06 does not erase A01. In particular, the later catalog query checks GPU count,
country and CUDA; it does not prove that A01's full RAM/disk request can be
allocated. A05 likewise does not establish an allocatable, correctly connected
four-GPU host with all required host resources.

We made **five actual GPU allocation requests: two rejected B300 requests and three
accepted four-H100 requests**. A01, A07, A10, A12 and A14 record those allocations;
A13 is a separate accepted CPU allocation. A11 records the base generation and deletion. The other entries are read-only
catalog observations. Together they cannot establish a
provider-wide success rate, permanent shortage, expected wait time or SLA.
The [GPU inventory](GPU_SHORTLIST.md) keeps these attempts separate from
unranked future hardware proposals.

## Coverage and cost of the failed attempt

This section concerns the first B300 attempt; the second rejection and completed
H100 rental have separate journals in [RUNPOD_RETRY.md](RUNPOD_RETRY.md).

- Allocation: attempted, rejected for capacity.
- GPU boot, model loading and inference: not run.
- Self-host output: none; generated-video count is zero.
- Latency, throughput, VRAM use, quality and self-host unit cost: unmeasured/null.
- Incremental GPU/storage rental expense: USD 0, based on rejected creation and
  the subsequent empty Pod listing; this is not a paid invoice observation.
- The unused USD 18 reservation was released. No additional fal calls were made.
- Original failure, intended configuration and artifact pins:
  [RUNPOD_ATTEMPT.md](RUNPOD_ATTEMPT.md).

Do not enter zero seconds or zero dollars per generated video: no video exists.
Do not count an allocation rejection as a model-generation failure or as evidence
that the model cannot meet the latency target. Record time spent looking for
capacity separately from model setup and request-to-download latency. No reliable
capacity-wait-duration measurement was collected for A01.

## Historical fallback proposal: flexible hardware, unchanged comparison

**Update:** the operator selected the H100 fallback after the second B300
rejection and global no-stock check. It completed one P01_EN request and was
deleted; billing reconciliation remains pending. The proposal and its original
USD 16 / one-hour bound below are retained for history. The later P01_EN language
instruction superseded the unchanged-prompt requirement in this proposal.

The operator requested reconsideration of the test conditions after the shortage.
The recommendation is to remove the assumption that only one particular GPU
configuration is worth testing, while retaining identifiable configurations and
bounded execution. **The table below was a proposal; A10 records its subsequent
H100 allocation, not a completed generation.**

| Candidate | Why consider it | Catalog compute rate | Proposed maximum rental | Proposed full-attempt reservation |
|---|---|---:|---:|---:|
| H3 Base / 1 x B300 | Original candidate; A06 again reports eligible stock | USD 7.89/hour | 2 hours | USD 18 |
| H3 Base / 4 x H100 SXM | A05 reports stock; SGLang documents this exact GPU-count/topology recipe | USD 13.96/hour | 1 hour | USD 16 |

The second candidate is more expensive per hour, not a claim of cheaper video.
One hour is USD 13.96 in compute before storage/fees; the USD 16 proposal must be
validated against the actual complete quote. Both alternatives are within the
existing **USD 25 total experiment cap** only when admitted individually alongside
the existing ledger exposure and closeout reserve. They are alternatives, not
permission to rent both. Setup, weight download, idle time and export consume the
same rental deadline. A deadline does not guarantee successful setup or a clip.

The upstream [SGLang H3 recipe](https://docs.sglang.io/cookbook/diffusion/MiniMax/MiniMax-H3)
documents four H100 80 GB GPUs using TP2 + Ulysses2, automatic encoder placement,
native BF16/FP32 and eager execution. Use that as the starting topology if the
fallback is selected; it is upstream evidence, not our reproduced measurement.
Verify the pinned runtime, interconnect and host allocation before launch. In
particular, do not carry a single-GPU `minRamPerGpu` filter over unchanged to a
four-GPU request: that would multiply the host-RAM requirement unintentionally.

Keep unchanged:

- H3 Base FL2VA, task `t2va`, native precision and the 50-point schedule.
- The existing frozen P01 prompt, seed 42, five-second 768P request with audio.
- One self-host generation before review; no repeat fal charges, extra scenes,
  10-second run, Turbo substitution or unplanned optimization.
- The 15-second end-to-end target. A completed but slower diagnostic clip is a
  latency failure, not a reason to relax the product requirement or hide the file.
- Separate first-request/cold-start evidence from any later warm measurements.
  No unmeasured warm latency or accepted-video unit cost may be inferred.

Before another paid attempt, record the selected candidate, exact quote,
applicable region, complete runtime/host profile, new attempt ID/reservation,
deadline and export/shutdown checks. Preserve A01 rather than overwriting or
automatically retrying it. The existing lifecycle helper is B300-specific and
must not be used unchanged for the H100 fallback. Unresolved readiness and
license-applicability items remain in [SELF_HOST_PREFLIGHT.md](SELF_HOST_PREFLIGHT.md).

Do not enlarge the budget merely to chase capacity. If allocation fails again,
record another capacity result and stop that attempt before any inference claim.
