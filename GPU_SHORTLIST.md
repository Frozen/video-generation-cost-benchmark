# GPU candidate shortlist

Evidence through September 18, 2026, 03:24:48 UTC, reconciled against repository
commit `94e51b7`. This is the working GPU inventory: recorded attempts and future
research proposals, with their evidence kept explicit. It does not schedule
additional rentals. Both H100 rentals ended and their Pods were deleted;
see the [base result](SELF_HOST_RESULTS.md) and the subsequent
[adapter failure](ACCELERATION_RESULTS.md).

## Decision we are trying to make

Find the least expensive reproducible self-host configuration that can produce
an acceptable five-second 768P MiniMax H3 Base FL2VA result without missing the
15-second customer-wait target. The primary cost metric is **USD per accepted
requested video-second**, with per-request and rental totals retained separately.

The recorded commercial reference prices per requested video-second are
USD 0.06 for ordinary H3, USD 0.04 for H3 Max and USD 0.02 for H3 Max Turbo
(USD 0.30, 0.20 and 0.10 respectively per five-second API request);
see [VARIANT_RESULTS.md](VARIANT_RESULTS.md). Exact weight equivalence and
equivalent quality across these variants have not been established.
The lower prices are competitive pressure, not permission to treat unlike
outputs as interchangeable.

## Shortlist at a glance

There are **two attempted configurations and five exploratory hardware entries**.
The five proposals are unranked; they are not an agreed five-run schedule.
A100's form factor still needs selection before it becomes an exact configuration.

| Configuration | Role in the shortlist | Current status |
|---|---|---|
| 1 x B300 288 GB | Original selected baseline | Two allocation rejections; no generation. [Attempts](RUNPOD_RETRY.md). |
| 4 x H100 SXM, 80 GB each | Selected fallback; later reused for a separate adapter trial | Base: one P01_EN output in 83.462 s, latency failed. Later eight-evaluation adapter: software error, no output; four-step variant not started. Both Pods deleted. [Base](SELF_HOST_RESULTS.md), [adapter](ACCELERATION_RESULTS.md). |
| 1 x RTX PRO 6000 Blackwell 96 GB | Exploratory cost/memory proposal | No local allocation or inference evidence |
| 1 x H100 PCIe 80 GB | Exploratory single-GPU proposal | No local allocation or inference evidence |
| 1 x A100 80 GB, PCIe or SXM still to be selected | Exploratory lower-price proposal | No local allocation or inference evidence |
| 1 x RTX 6000 Ada 48 GB | Exploratory offload proposal | No local allocation or inference evidence |
| 1 x H200 141 GB | Earlier catalog observation; exploratory single-GPU proposal | Catalog only; no local allocation or inference evidence |

The recorded accelerator name is **NVIDIA B300**. The H100 result belongs to
four SXM cards cooperating on one output, using TP2 + Ulysses2 and NVLink.
It provides no measurement of the separate one-H100-PCIe proposal. Its 320 GB
aggregate VRAM is distributed across four devices, not one 320 GB memory pool.

## Reconciliation with the experiment history

The original plan selected **one B300** for a diagnostic native H3 Base run.
After two capacity rejections, the operator selected **four H100 SXM GPUs**
using an upstream-documented topology. Both selections predate this shortlist.
The five single-GPU proposals were introduced in the shortlist draft; they did
not come from completed tests or a measured price/performance ranking.

A subsequent lease reused **4 x H100 SXM** for an accelerated model profile.
Larry Turbo v4 failed on a LoRA compatibility exception before any denoising
iteration completed; LightX2V four-step was not started. This adds an execution
attempt and a model profile, not another GPU type or a successful speed result.
The failed rental estimate is USD 3.04 with no generated video-seconds; see
[ACCELERATION_RESULTS.md](ACCELERATION_RESULTS.md). It is not a VRAM-failure result.

Price and VRAM alone do not establish RTX PRO 6000 as the best-value candidate
or determine an evaluation order. H200 is not a single-GPU memory upper bound:
B200 and B300 have more VRAM.

The B300 requests required at least **384 GiB host RAM**. The H100 request used
**96 GiB per GPU**, or 384 GiB total, and the allocated host reported 1006 GiB.
These are recorded request/allocation values, not a measured universal H3 RAM
minimum. The smaller hosts in future proposals require their own placement and
loading validation; listing them does not relax the original launch filters.

The execution helper's [lease profiles](scripts/runpod_trial.py) contain
`b300`, `h100x4` and `h100x4accel`; the latter two use the same GPU type/count
with different trial bounds. [suite.json](suite.json) preserves the original v0.8.1
planning contract with one B300; its `proposed_not_provisioned` state is not a
live experiment tracker. Read [CAPACITY.md](CAPACITY.md) for allocation history
and [SELF_HOST_RESULTS.md](SELF_HOST_RESULTS.md) for the completed fallback.

The fal H3, Max and Turbo samples are API measurements with undisclosed hardware.
They add no tested GPU to this inventory. Our H100 clip uses the explicitly
modified **P01_EN** prompt; the fal samples use **P01**. Preserve this difference
when interpreting cost or quality comparisons.

## What the completed GPU run establishes

On 4 x H100 SXM, the first user request after built-in warmup took **83.462 s**
through download. SGLang reported **77.365 s** processing, including **74.620 s**
denoising. Request-window compute is approximately **USD 0.06 per requested
video-second** (USD 0.30 total); the entire one-clip rental including setup and
disk is approximately **USD 0.7844 per requested video-second** (USD 3.92 total),
invoice pending. The clip failed the 15-second target and has no accepted-output
unit cost. These figures concern the base lease, not the later failed adapter lease.

The inference from this one run is that denoising dominated the measured
processing interval. Cheaper single-GPU/offload proposals therefore have no
established path to the latency target merely because their hourly price is
lower. They can still investigate cost or feasibility. No local cross-GPU
ranking, warm latency distribution or bottleneck diagnosis for another host
has been measured.

## What makes a GPU relevant

A candidate is interesting only when it helps answer a distinct question:

1. Can the unchanged native-precision base model fit with less weight movement?
2. Does additional memory bandwidth reduce service time enough to offset price?
3. Can a cheaper GPU plus host-memory offload lower cost per accepted output?
4. Is the configuration actually allocatable with enough host RAM, disk, CUDA
   compatibility and, for multiple GPUs, a suitable interconnect?
5. Can it preserve the frozen model, request and quality contract?

VRAM alone is not enough. Host RAM, loading peaks, activation memory, kernel
support and data transfer all need a full-host check. An advertised RAM number
above a recipe's pinned-buffer size does not prove that loading and generation
fit. Preserve the actual native component dtypes: the H100 runtime also used
FP16 decoder weights, as recorded in its result.

## Five exploratory proposals, without an execution order

These are price/memory hypotheses. The exact native H3 Base workload remains
unverified on every row, including its compatibility with our pinned runtime.

| Proposed configuration | VRAM | Public Pod rate | Published host RAM | Question to investigate |
|---|---:|---:|---:|---|
| 1 x RTX PRO 6000 Blackwell | 96 GB | USD 2.09/hour | 188 GB | Can this larger-VRAM workstation/server GPU improve completed-output cost with a validated offload profile? No best-value claim yet. |
| 1 x H100 PCIe | 80 GB | USD 2.89/hour | 188 GB | What does a single-card placement cost? The four-SXM result does not predict its latency. |
| 1 x A100 80 GB | 80 GB | USD 1.59/hour | PCIe: 117 GB; SXM: 125 GB | Does the lower hourly price compensate for processing time? Pin PCIe or SXM and check loading headroom before scheduling. |
| 1 x RTX 6000 Ada | 48 GB | USD 0.84/hour | 167 GB | Can an offload-heavy deployment produce a useful cost floor? No interactive-latency result exists. |
| 1 x H200 | 141 GB | USD 4.59/hour | 276 GB | Does greater per-card memory help enough to justify the rate? The upstream four-H200 recipe is a different configuration. |

Rates and published instance shapes come from the
[Runpod public pricing page](https://www.runpod.io/pricing), checked during this
audit. They are discovery data,
not quotes, reservations or evidence of stock. Query the live catalog and record
the full allocatable host immediately before any approved run.

## Conditional candidates

These remain visible for coverage; none has a local generation result. There is
no evidence-based reason to prescribe a fixed order between them and the five
proposals above.

| Candidate | Why it is conditional |
|---|---|
| 1 x RTX 5090, 32 GB | The listed 35 GB host RAM makes memory placement a separate feasibility problem. A constrained native offload path needs validation; quantization would be a different comparison. |
| 2 x RTX 5090, 32 GB each | Has an upstream native offload recipe; host RAM and topology must match. Not tested here. |
| 1 x RTX 4090, 24 GB | Consumer/offload coverage only; no local evidence for the native baseline or the 15-second target. |
| 1 x L40S, 48 GB | Useful Ada datacenter comparison, but the public shape is more expensive and lists less host RAM than RTX 6000 Ada. Add only if availability or measured kernels justify it. |
| 1 x RTX A6000 or A40, 48 GB | Cheap price-floor proposals. The listed 50 GB host RAM requires a validated memory/storage plan; low RAM can prevent loading or force disk reads. |
| 1 x B200, 180 GB | Already present in the original catalog comparison at USD 6.79/hour with `NONE` stock. Keep as a large-memory alternative; the old snapshot does not establish current unavailability. |
| MIG 24/48 GB slices | Exclude from the first comparison: a GPU slice is not equivalent to a full card and adds another isolation/resource-sharing variable. |

The [SGLang H3 cookbook](https://docs.sglang.io/cookbook/diffusion/MiniMax/MiniMax-H3)
documents four-H100, four-H200 and two-RTX-5090 recipes, plus an eight-B300
benchmark. These are exact GPU-count/runtime profiles, not single-card results.
Its two-5090 native 50-step run takes 559.67 s on a 384 GiB-class host; one
fast offload recipe pins about 112 GB RAM. Its RTX PRO 6000 measurements use
VDN-H3 with quantization, not our native Base profile. These observations inform
feasibility; their differing prompts, revisions and timing boundaries prevent
using them as our cross-GPU ranking. Larger upstream configurations remain
external references, not locally attempted or scheduled tests.

## Economic screening before rental

At perfect paid-time utilization and before storage, setup, failures and quality
losses, the GPU-only cost of one attempt is:

```text
gpu_cost_per_attempt = aggregate_gpu_hourly_rate * service_seconds / 3600
gpu_cost_per_requested_video_second = gpu_cost_per_attempt / requested_video_seconds
```

For a five-second request, the cheapest recorded commercial reference is
USD 0.02 per video-second, or USD 0.10 total. The maximum GPU service time
that merely equals this price is therefore:

| Configuration | Aggregate rate | Seconds at USD 0.10 parity |
|---|---:|---:|
| RTX 6000 Ada | USD 0.84/hour | 428.6 s |
| A100 80 GB | USD 1.59/hour | 226.4 s |
| RTX Pro 6000 | USD 2.09/hour | 172.2 s |
| H100 PCIe | USD 2.89/hour | 124.6 s |
| H200 | USD 4.59/hour | 78.4 s |
| B300 | USD 7.89/hour | 45.6 s |
| 4 x H100 SXM | USD 13.96/hour | 25.8 s |

These are break-even arithmetic, not predicted generation times. Real cost per
accepted output is higher when utilization is below 100%, setup or idle time is
billed, attempts fail, or quality acceptance is below 100%. Use
[ECONOMICS.md](ECONOMICS.md) and `scripts/economics.py` for the complete model.

The 15-second interactive target is a separate and stricter product requirement.
A configuration can be cheaper than an API while still being too slow for the
service, or fast enough while being more expensive than the commercial reference.

## Minimum comparable record for every tested configuration

Keep the model revision, SGLang revision, request, seed, resolution, duration,
sampling schedule and quality mode fixed. Record at least:

- exact GPU type and count, VRAM per GPU and aggregate rental rate;
- host RAM, CPU, disk, region, cloud type, CUDA/driver and interconnect;
- precision, quantization, offload, parallelism and attention settings;
- allocation outcome, setup time, cold start and warm-up treatment;
- request-to-downloaded-output latency and GPU-occupied service time separately;
- peak VRAM/RAM, failures, retries and output-contract checks;
- blinded quality acceptance and prompt adherence;
- total billed exposure and cost per accepted output.

Do not compare a quantized, cached, Turbo or reduced-step run against the native
lossless baseline without naming it as a separate configuration and reviewing
quality. Do not start another paid GPU because it appears in this document.

## Next selection rule

1. Review the H100 base result and later adapter failure. Both rentals ended;
   invoice reconciliation and base quality review remain pending. The prepared
   adapter compatibility fix still needs GPU validation.
2. State the next question: lower cost, native-model latency, or a separately
   identified accelerated model. Denoising dominates the existing measurement.
3. Choose **one** exact GPU/count/topology that tests that question, with a
   justified memory/runtime profile. No first-ranked GPU has been established.
4. Freeze its complete host profile, quote, budget reservation and independent
   termination control before provisioning.
5. Freeze the prompt too: P01 and P01_EN are different. Run one five-second
   request under the chosen comparison and review before expanding.

Primary technical reference:
[SGLang Diffusion MiniMax H3 cookbook](https://docs.sglang.io/cookbook/diffusion/MiniMax/MiniMax-H3).
