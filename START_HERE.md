# First test: MiniMax H3 native 768P

Planning baseline v0.8.1, September 17, 2026. **One fal reference is now complete;
self-host matching and execution readiness remain unverified.**
The [execution addendum](REFERENCE_RUN.md) supersedes the earlier whole-pair
sequencing gate for that one API call; [RESULTS.md](RESULTS.md) records the result.
The later [variant comparison](VARIANT_RESULTS.md) also measures Max and Turbo as
commercial alternatives. The original open-base / one-B300 self-host candidate
remains unchanged; these are not claims of identical weights across variants.

The first allocation was rejected for capacity. [CAPACITY.md](CAPACITY.md)
records this unexecuted coverage, later stock changes and a proposed four-H100
fallback. Hardware selection is being reconsidered; no fallback has been rented
and the original request, quality checks and latency target remain unchanged.

## What we start with

The currently agreed work is the **baseline comparison only**: one English
prompt from the [Awesome Video Prompts H3 collection](https://awesomevideoprompts.com/en/models/minimaxh3),
one 5-second fal.ai output, then one 5-second self-host output. Choose a
text-only scene that fits five seconds without changing a longer storyboard or
requiring reference media. Freeze its exact text, source, attribution and reuse
record first. The collection is a discovery source, not an official benchmark.
The first prompt is now frozen with provenance and hashes in the addendum/results.
Optimizations and load tests require a later
decision; unused budget does not authorize them.

Comparison pair **P01** uses the fal.ai endpoint
[`minimax/h3/text-to-video`](https://fal.ai/models/minimax/h3/text-to-video).
The self-host candidate is **MiniMax H3 Base FL2VA**, task `t2va`, from the
[official MiniMax-H3 release](https://huggingface.co/MiniMaxAI/MiniMax-H3).
The release provides a [native 768p text-to-audio-video example](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/scripts/readme/reproducible-768p-t2va-request.sh).
The first self-host candidate is one B300 running SGLang Diffusion, specified
below. Checkpoint/runtime pins are recorded in the [allocation attempt](RUNPOD_ATTEMPT.md);
license applicability and on-host validation remain open. The allocation failed
for capacity; no self-host clip exists.

This deliberately selects ordinary H3, **not H3 Max or H3 Max Turbo**. It does
not claim to reproduce fal's post-trained Max variant. Matching the endpoint's
request contract is a starting point, not proof of identical weights or internals.

## Selected request profile

The proposed self-host test is a **Runpod GPU Pod**, not a Harmony validator,
not video inference on the user's laptop, and not a resale call to another
hosted video API. It has not been provisioned.

```text
Test client outside the serving deployments
  |-- fal.ai endpoint ----------------------------> video + audio
  |-- Runpod GPU Pod -> our runtime + H3 weights --> video + audio
  `-- download both results, record latency and reconcile costs
```

The Pod would run a pinned container/runtime, load the ready-made H3 Base FL2VA
weights and perform inference. We are not training a model from scratch. The
runtime generates video/audio, encodes the result and makes it downloadable.
The candidate hardware and serving program are selected below; the exact image,
host resources and secure access still need verification. No public unauthenticated
inference service is required for the pilot.

The client submits requests and records evidence; the rented GPUs do the model
computation. fal.ai charges for its API service; our trial pays for the GPU rental
and associated resources, including setup and idle time. This is the economic
comparison. A future autoscaling service is not part of the initial deployment.

### First self-host configuration: selected for a baseline measurement

| Item | Selected candidate |
|---|---|
| Compute | One Runpod Secure Cloud GPU Pod, **1 x NVIDIA B300 SXM6 AC**, 288 GB GPU memory |
| Serving program | **SGLang Diffusion**, `sglang serve`; source/container pins in [RUNPOD_ATTEMPT.md](RUNPOD_ATTEMPT.md), runtime not yet verified |
| Model | Official MiniMax H3 Base FL2VA, `t2va`; no Turbo, FastH3, VDN, adapters or replacement encoder |
| Baseline math | Native BF16/FP32, eager execution, no added quantization or approximate caching; 50-point schedule |
| Host requirements | Proposed 384 GiB-class RAM and 300 GB working disk; verify actual allocation and complete storage quote before renting |
| Requests | One at a time; first 5 seconds, native 768P, then review before further work |
| Deployment state | Not provisioned; single-B300 capacity, output quality, timing and API equivalence not measured |

The September 17 Runpod MCP catalog read (`SECURE`, `POD`, count 1) returned:

| GPU | GPU memory | Catalog USD/hour | Availability |
|---|---:|---:|---|
| B300 (`NVIDIA B300 SXM6 AC`) | 288 GB | 7.89 | LOW |
| B200 (`NVIDIA B200`) | 180 GB | 6.79 | NONE |
| H200 SXM (`NVIDIA H200`) | 141 GB | 4.59 | LOW |

These are live catalog observations, not reserved capacity or an all-in quote.
The broad catalog listed `LOW` for `EU-NL-1`, `EUR-IS-1` and `US-WA-2`; this did
not establish allocatable stock. The subsequent EUR-IS-1 allocation was rejected,
and the country-filtered query returned `NONE`. No region is booked.
At the listed rate, 30 minutes of one B300 is USD 3.945 in compute alone. Setup,
downloads and idle time are billed too. This is not a claim that setup or the
test will finish in 30 minutes. Storage, API calls, fees and shutdown reserve
must still fit the existing USD 25 total cap.

Why this candidate: one large-memory Blackwell GPU is a bounded starting point
for measuring the unchanged base model without immediately multiplying hourly
cost by four or eight. This is an engineering choice, not a published
single-B300 performance result or proof that it is the cheapest configuration.

**Important adverse evidence:** the [SGLang H3 cookbook](https://docs.sglang.io/cookbook/diffusion/MiniMax/MiniMax-H3)
reports 19.04 s latency for base FL2VA BF16 on **8 x B300**, with a 5-second
request, 1344x768, 124 frames at 24 fps, 50 steps and one measured request after
warmup. It reports 18.03 s with FP8. Neither meets our 15-second target; neither
is a measurement of our one-GPU configuration or our download boundary.
This is a strong warning against promising the target for an unoptimized
single-card base deployment, not proof that every H3 implementation must fail.

Therefore the first base run is diagnostic: measure the gap and cost, then stop
and review. Do not expand to 10 seconds or more GPUs just to chase the target.
Any accelerated checkpoint or approximation needs a separately identified,
reviewed configuration and quality comparison; never silently replace H3 Base.

Illustrative server command, **not a pinned or validated launch script**:

```bash
sglang serve \
  --model-path MiniMaxAI/MiniMax-H3 \
  --model-variant fl2va \
  --num-gpus 1 \
  --ulysses-degree 1 \
  --performance-mode speed \
  --enable-torch-compile false \
  --host 127.0.0.1 \
  --port 30010
```

Access would use an authenticated tunnel. The first request must explicitly
select `quality: "lossless"` and the baseline schedule; record all effective
sampling settings. The 50-point schedule is our open-model baseline, not a claim
that fal uses the same internal sampler or number of steps. Those provider
internals remain unknown. Do not run an unpinned `latest` image or install dependencies
on a paid Pod while still deciding which framework to use.

### API settings

| Setting | Baseline |
|---|---|
| Task | Text-to-video with native audio; no image, video or external audio input |
| Endpoint ID | `minimax/h3/text-to-video` |
| Resolution | Explicit `768P`, native generation; do not inherit the API's `2K` default |
| Aspect ratio | `16:9` |
| Duration | First 5 seconds; then 10 seconds on the same request if justified and funded |
| Seed | `42` on both sides where supported; not a guarantee of identical output |
| Prompt expansion | Explicit `prompt_expansion_mode: "disabled"` |
| Safety checker | `enable_safety_checker: true` |
| Delivery | `sync_mode: false`; measure until the final video is fully downloaded |
| Batch/concurrency | 1 / 1 for the interactive baseline |
| Prompt | One English source prompt, frozen with provenance/hash in the execution addendum |

The [API contract](https://fal.ai/models/minimax/h3/text-to-video/api) and
[OpenAPI schema](https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=minimax%2Fh3%2Ftext-to-video)
were inspected on September 17, 2026. They expose native 768P, durations from
5 to 15 seconds, and disabled prompt expansion. No `target_audio_url` is supplied:
we are not testing soundtrack replacement. Actual dimensions, fps, duration
tolerance, audio format and the self-host payload mapping still need verification.

Disabling expansion explicitly selects a supported API configuration; this is
not a comparison with the default expanded-prompt workflow. Use the same final
prepared prompt on both sides. A null `expanded_prompt` response alone does not
prove the absence of all hidden processing. A different expansion or upscale
workflow needs a separate configuration and full timing/cost accounting.

## What we test

| Question | Evidence |
|---|---|
| Is the result an acceptable substitute? | Decoding/output checks, blinded visual/audio review and `prompt_match` |
| How long does the customer wait? | Request-to-final-download time, including queueing and startup |
| What does an accepted result cost? | Actual API bill, GPU rental and attributable setup, idle, failure, storage and delivery costs |
| How does duration affect cost and latency? | Matched 5- and 10-second requests, reported separately |
| Does loading the GPU improve economics? | A separately budgeted bounded load test, if funds remain, including latency at load |
| What utilization could make it viable? | Modeled cost/contribution at 25%, 50%, 75% and 100%; not measured utilization or guaranteed profit |

Interactive acceptance remains **at most 15 seconds of waiting for a 5-second
clip, and 30 seconds for a 10-second clip**, plus acceptable output and prompt
adherence. Neither backend has demonstrated these limits in this pilot.
VBench, Max variants, other families and unbounded load tests are outside this baseline.

## Original paired execution sequence

The one-call addendum now permits and records the fal reference before Runpod
readiness. The remaining requirements below still apply before self-host rental.

1. Complete no-cost preflight: verify access, self-host feasibility, matching
   gaps, permitted prompt sources, current quotes, export and an independent
   stop mechanism. Pin the executable plan and reserve the entire exposure.
2. Run the same **5-second** request once through fal.ai and once through our
   deployment: two attempts, not two variants of the model.
3. Reconcile both charges, review the outputs and inspect latency before expanding.
4. If justified and within budget, repeat the same prompt at **10 seconds**
   on both backends: two more attempts.
5. Stop after the baseline work and report. Repetitions, batching and optimization
   are future work requiring a new explicit decision and bounded plan.

This is the intended sequence, **not a funded four-attempt schedule**. The active
CSV remains empty until the prompt, self-host profile and upper-bound quotes are
frozen. Setup and warm-up are not free; failed or late runs remain in the record.
No automatic retries and no unbounded resource rental.

## API price reference, not a complete pilot quote

On September 17, 2026, the [endpoint page](https://fal.ai/models/minimax/h3/text-to-video)
lists **USD 0.06 per generated second at 768p**. At that listed rate:

| One API output | Listed generation cost |
|---|---:|
| 5 seconds | USD 0.30 |
| 10 seconds | USD 0.60 |
| One of each | USD 0.90 |

These are reference calculations, not measured charges, a tax-inclusive bound,
or the total paired-test cost. Recheck billing before submission. The **USD 25
total cap** includes both backends, setup, failures, optional performance checks
and closeout; no extra budget is implied.

Detailed rules: [METHODOLOGY.md](METHODOLOGY.md). Open launch gates:
[PREFLIGHT.md](PREFLIGHT.md). Source claims: [CLAIMS.md](CLAIMS.md).
