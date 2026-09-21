# API-matched video generation cost benchmark

**Objective:** determine whether a self-hosted open-weight deployment can deliver
the service of a specific fal.ai endpoint at a lower fully accounted cost, with
acceptable quality and response time. [Testing methodology](METHODOLOGY.md).

**Original API reference pilot: H3, H3 Max and H3 Max Turbo completed under a USD 25 cap.**
All public content is in English.

## Watch the benchmark videos

| Video | Watch on YouTube |
|---|---|
| 01 — H3 via fal | [Watch](https://www.youtube.com/watch?v=1X8fJc_-FJQ) |
| 02 — H3 Max via fal | [Watch](https://www.youtube.com/watch?v=jUGvfw4__Y4) |
| 03 — H3 Max Turbo via fal | [Watch](https://www.youtube.com/watch?v=PfTt3By6lpk) |
| 04 — H3 Base on 4 x H100 SXM | [Watch](https://www.youtube.com/watch?v=QH9OgSgDNsU) |
| 05 — H3 + Larry Turbo v4, 8 steps, 4 x H100 SXM | [Watch](https://www.youtube.com/watch?v=dvoLvC6WmSI) |
| 06 — H3 + LightX2V, 4 steps, 4 x H100 SXM | [Watch](https://www.youtube.com/watch?v=eWXFFeDpqZM) |

YouTube is for convenient playback and may transcode the videos. The unchanged
original MP4s and measurement records remain in the
[results directory](https://github.com/Frozen/video-generation-cost-benchmark/tree/main/results).
The fal samples use P01; self-hosted samples use the English-requested P01_EN
variant. This is not an exact-prompt six-way comparison.

## Latest results

[September 20: RTX PRO 6000 reproducibility package](benchmarks/ltx-rtx-2026-09-20/README.md):
ten consecutive five-second LTX-2.5 requests with native audio, after two full
warmups, produced 50 requested video-seconds in 279.402 seconds. The observed
GPU and temporary-disk rates give **USD 0.003287 per video-second** for this
warmed queue. Original logs, exact settings, seeds, worker source, ten original
videos and an offline verification script are included. The comparison with
fal's published API tariffs is a cost reference across different models;
quality parity and equivalent service performance have not been established.

[Warmed LTX-2.5 comparison](LTX_REUSE_RESULTS.md): **retaining transformer weights
on one H100 reduced processing from 46.459 to 28.496 s (1.63x)**, with identical
decoded video frames for this pair; decoded audio differs and quality review is
pending. Same prompt, seed, BF16 weights and full 8 + 3 schedule, with short
technical warmup before each mode.

| Five-second video | Request to download | Processing-only USD / requested video-second | 15 s target |
|---|---:|---:|---|
| [Ordinary warm LTX](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001_BASE_WARM.mp4) | 55.432 s | 0.009008 | Fail |
| [Resident warm LTX](results/P01_EN_RUNPOD_H100_LTX25_REUSE_5S_001_REUSE_WARM.mp4) | 34.987 s | 0.005525 | Fail |

Whole rental, including preparation, both warmups and temporary disk:
**USD 1.18 estimate**, invoice pending. All four originals exported; Pod deleted
and absence independently verified. H3 logs also confirm short built-in warmup;
the [report](LTX_REUSE_RESULTS.md#comparison-with-our-warmed-h3-measurements)
compares the warmed samples while disclosing hardware and pipeline differences.
No additional paid tests are scheduled.

[LTX-2.5 result](LTX_RESULTS.md): **one H100 SXM successfully produced
[video and audio](results/P01_EN_RUNPOD_H100_LTX25_5S_003.mp4).** Cold first request:
76.163 s to downloaded video, 60.642 s pipeline processing, **USD 0.011758 per
requested video-second for processing only**. The whole rental including setup
and disk is approximately **USD 0.78**, pending billing reconciliation. The
15-second target failed; quality review remains pending. Pod deleted and absence
verified. This is not an equal-warmth comparison against the H3 service below.
[Launch contract and failed preparation history](LTX_PREFLIGHT.md).

[Latest acceleration results](ACCELERATION_RETRY_RESULTS.md): **both public H3
adapters produced videos after the pinned compatibility fix.**

| Video | Request to download | Compute-only USD / requested video-second | 15 s target |
|---|---:|---:|---|
| [8 steps (YouTube)](https://www.youtube.com/watch?v=dvoLvC6WmSI) | 21.873 s | 0.010665 | Fail |
| [4 steps (YouTube)](https://www.youtube.com/watch?v=eWXFFeDpqZM) | 13.741 s | 0.005930 | Pass |

Same four H100 SXM GPUs, P01_EN, seed 42, five-second 768p requests, sequentially.
These are not fal Max/Turbo weights. **Quality review remains pending.** The
whole two-clip rental, including preparation, idle time and temporary disk, is
estimated at **USD 3.50**, or USD 0.35037 per requested video-second; invoice pending.
Pod deleted after export; subsequent Pod and network-volume lists were empty.
[Earlier failed rental](ACCELERATION_RESULTS.md): USD 3.04 estimate, retained in
experiment accounting. [CPU-only storage preparation](PRELOADED_MODELS.md) also
failed; no verified persistent cache remains. [Approved plan](ACCELERATION_TRIAL.md).

[Latest comparison](VARIANT_RESULTS.md): identical 5-second 768P requests, one
sample each. H3: **102.644 s wait / USD 0.06 per video-second**;
Max: **13.552 s / USD 0.04 per video-second**;
Turbo: **9.122 s / USD 0.02 per video-second**. Cost normalization uses the
requested five-second duration, not GPU runtime. Prices are recorded tariff/billable-unit calculations,
with promotions for Max/Turbo and invoice reconciliation pending. Max and Turbo
passed the latency gate; full quality review and exact-pair validation remain pending.

**Self-host completed, September 18:** H3 Base on **4 x H100 SXM in India**
produced a [five-second video (YouTube)](https://www.youtube.com/watch?v=QH9OgSgDNsU) in
**83.462 s end-to-end**, failing the 15 s target. Compute-only estimate:
**USD 0.06 per video-second** (USD 0.30 for this five-second request).
The whole one-clip rental including setup and disk is approximately
**USD 0.78 per video-second**, USD 3.92 total, invoice pending.
**Pod deleted; no servers running.** [Full statistics](SELF_HOST_RESULTS.md).
The operator requested English-only speech/text, so this is the explicit
P01_EN prompt variant, not an exact-prompt replay of the existing fal samples.

[Capacity is tracked explicitly](CAPACITY.md): failed allocations, changing
catalog stock and successful provisioning are separate observations. Two B300
requests were rejected before the H100 fallback succeeded. The operator reports
rapid, hard-to-understand speech and cannot identify its language despite the
English-only prompt; the language and cause are not established.
Formal quality review and final invoice reconciliation remain pending.

[Our economics model](ECONOMICS.md) separates measured results, missing self-host
inputs and utilization scenarios; it does not assume fal latency is B300 runtime.

**Execution update:** [REFERENCE_RUN.md](REFERENCE_RUN.md) authorizes one bounded
5-second fal reference before self-host readiness. It supersedes the sequencing
gate below, not the USD 25 cap or the selected B300 candidate. The paired suite
remains a planning contract. See that addendum for the active runner and status.
The subsequently approved [variant addendum](VARIANT_COMPARISON.md) covers exactly
one additional Max and one Turbo request, both now complete. It does not replace
the open-base self-host candidate with fal's post-trained variants.

## Start here

Current scope: one English prompt from the
[Awesome Video Prompts H3 collection](https://awesomevideoprompts.com/en/models/minimaxh3),
first through fal.ai and then through our deployment, targeting 5 seconds on
each side. This means two comparison outputs, not two models or a full benchmark.
The first source prompt is frozen in the [execution addendum](REFERENCE_RUN.md).
Optimization and load testing are deferred;
remaining budget is not permission to start them. Review the first pair before
scheduling 10-second clips or repetitions.

**First endpoint: `minimax/h3/text-to-video`, ordinary H3, not H3 Max.**
The selected baseline is native **768P, 16:9, 5/10 seconds, seed 42**, with prompt
expansion disabled, safety checking enabled and URL-based video delivery.
The original self-host candidate was **MiniMax H3 Base FL2VA on 1 x B300 (288 GB), using
SGLang Diffusion**. The catalog rate checked September 17 is USD 7.89/hour for
compute; that candidate could not be allocated. The completed fallback used
four H100 SXM GPUs as described above. Its [result](SELF_HOST_RESULTS.md) records
the verified runtime and remaining API-equivalence gaps. The
[GPU inventory](GPU_SHORTLIST.md) distinguishes both attempted configurations
from untested hardware proposals; no ranked queue of future GPU tests is agreed.

This is a diagnostic baseline, not a promised 15/30-second service. Published
base-model results already warn of a latency gap; see the hardware rationale
and adverse evidence in [START_HERE.md](START_HERE.md).

[START_HERE.md](START_HERE.md) fixes what we start with, what we measure and the
sequence: one matched 5-second request, review, then a matched 10-second request
if justified and funded. The API side is complete under the addendum; two B300
allocations failed and the H100 fallback completed one P01_EN clip. Exact-prompt
pairing and quality review remain open.

## What changed

- Start with one matched pair: one exact fal.ai endpoint and one corresponding
  self-hosted deployment. Ordinary H3 is the first selected reference; LTX and
  Wan remain future candidate families, not mandatory first-stage arms.
- Match the request, model variant, output contract and additional pipeline
  stages. Record differences and unknowns; do not claim an exact replica from
  a shared model-family name.
- Use frozen, realistic customer-style requests, with source attribution and
  the same input assets on both backends.
- Measure interactive latency and batch/load throughput separately, then assess
  service cost and contribution under explicit utilization and selling-price assumptions.
- Defer VBench. Keep blinded human review, prompt_match and output-contract checks.
- Withdraw the old 12-attempt VBench schedule. The active CSV has a header and no
  attempts until requests, self-host profiles, quotes and bounded execution are pinned.

The [previous English protocol](https://github.com/Frozen/video-generation-cost-benchmark/tree/ee78f1f2ec20864139d4c0bda84e37e40938c4e2)
and its unexecuted schedule remain in Git history. Retained VBench source assets
are historical provenance, not the active workload.

## First-stage constraints

The agreed interactive target remains **at most 3 seconds of end-to-end wait per
planned second of video: 15 seconds for 5 seconds, 30 seconds for 10 seconds**.
Measure request submission through final download, including queueing and any
post-submission cold start. This is an acceptance target, not a measured SLA.

Quality and prompt adherence must also pass. All failed and late attempts still
count toward cost. High-throughput batch results do not demonstrate interactive
latency. A high-end GPU or high utilization is a hypothesis, not proof of profit.

The USD 25 cap covers both the API reference and self-host trial, setup, failures,
closeout; the optimization allocation is parked while that stage is deferred.
The full funded attempt count is
pending quotes; four attempts would cover one prompt at two durations on both
backends, but that is not yet a funded schedule.

## Files

- [START_HERE.md](START_HERE.md): selected H3 baseline, first-test sequence and measurements.
- [RESULTS.md](RESULTS.md): the completed first reference and its limitations.
- [RUNPOD_ATTEMPT.md](RUNPOD_ATTEMPT.md): rejected B300 allocation, cost and prepared artifacts.
- [CAPACITY.md](CAPACITY.md): dated stock/allocatability evidence, untested coverage and proposed fallback.
- [GPU_SHORTLIST.md](GPU_SHORTLIST.md): reconciled GPU inventory, attempted configurations
  and unranked research proposals with supporting evidence.
- [SELF_HOST_RESULTS.md](SELF_HOST_RESULTS.md): completed four-H100 generation and rental economics.
- [REFERENCE_RUN.md](REFERENCE_RUN.md): bounded one-call execution addendum.
- [METHODOLOGY.md](METHODOLOGY.md): matching, realistic requests, execution stages,
  quality, latency, throughput, cost accounting and completion criteria.
- [suite.json](suite.json): original v0.8.1 planning contract, not a live tracker of later attempts.
- [pilot-plan.csv](pilot-plan.csv): generated schedule, currently empty.
- [CLAIMS.md](CLAIMS.md): published-claim verification checklist and evidence template.
- [PREFLIGHT.md](PREFLIGHT.md): current launch requirements and dated prior observations.
- [.env.example](.env.example): empty credential template; real credentials belong
  only in ignored `.env.local` or the process environment, never in Git or chat.
- [SOURCE.md](SOURCE.md): request-source policy and retained upstream attribution.
- [scripts/validate.py](scripts/validate.py): offline checks for the current planning contract.
- [scripts/check_access.py](scripts/check_access.py): read-only provider access
  checks; no generation or resource provisioning. See [PREFLIGHT.md](PREFLIGHT.md).
- [scripts/budget.py](scripts/budget.py): unchanged fail-closed reservation ledger;
  not a provider-enforced cap.
- [tests/test_protocol.py](tests/test_protocol.py) and [tests/test_budget.py](tests/test_budget.py):
  protocol and budget regression checks.

## Offline checks and publication

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
git diff --check
```

Regenerate the schedule from the planning contract:

```bash
python3 scripts/validate.py --plan > pilot-plan.csv
```

`python3 scripts/validate.py --ready` deliberately returns exit code 2 while
the execution plan is not frozen. Passing offline checks does not establish
provider access, matching equivalence, a price bound or a working stop mechanism.
The separate [reference runner](scripts/fal_reference.py) implements the API
addendum. The completed H100 run used [h3_trial.py](scripts/h3_trial.py); its
evidence is recorded in [SELF_HOST_RESULTS.md](SELF_HOST_RESULTS.md).

Do not provision a paid resource until the [preflight requirements](PREFLIGHT.md)
are met and the whole commitment is reserved. No automatic retries or hidden
spending expansion. Do not publish secrets, account/payment details, private
conversations, raw private logs or signed URLs.
