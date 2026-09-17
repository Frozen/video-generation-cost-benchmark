# API-matched video generation cost benchmark

**Objective:** determine whether a self-hosted open-weight deployment can deliver
the service of a specific fal.ai endpoint at a lower fully accounted cost, with
acceptable quality and response time. [Testing methodology](METHODOLOGY.md).

**Three API references completed: H3, H3 Max and H3 Max Turbo. Total cap: USD 25.**
All public content is in English.

[Latest comparison](VARIANT_RESULTS.md): identical 5-second 768P requests, one
sample each. H3: **102.644 s / USD 0.30**; Max: **13.552 s / USD 0.20**;
Turbo: **9.122 s / USD 0.10**. Prices are current tariff/billable-unit calculations,
with promotions for Max/Turbo and invoice reconciliation pending. Max and Turbo
passed the latency gate; full quality review and self-host testing remain pending.

**Self-host update:** the replacement Runpod key works. No GPU has been rented.
[Current preflight](SELF_HOST_PREFLIGHT.md) records the operator's personal-test
declaration, outstanding license applicability and the unverified rental deadline.

Original videos: [H3](results/P01_FAL_5S_001.mp4),
[H3 Max](results/P01_FAL_MAX_5S_001.mp4),
[H3 Max Turbo](results/P01_FAL_TURBO_5S_001.mp4).
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
The self-host candidate is **MiniMax H3 Base FL2VA on 1 x B300 (288 GB), using
SGLang Diffusion**. The catalog rate checked September 17 is USD 7.89/hour for
compute; no Pod has been created. Exact weights/runtime pins, on-host feasibility
and equivalence with the API have not yet been verified.

This is a diagnostic baseline, not a promised 15/30-second service. Published
base-model results already warn of a latency gap; see the hardware rationale
and adverse evidence in [START_HERE.md](START_HERE.md).

[START_HERE.md](START_HERE.md) fixes what we start with, what we measure and the
sequence: one matched 5-second request, review, then a matched 10-second request
if justified and funded. The API side is complete under the addendum; the self-host
schedule is not funded or ready. Selecting hardware does not establish readiness.

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
- [REFERENCE_RUN.md](REFERENCE_RUN.md): bounded one-call execution addendum.
- [METHODOLOGY.md](METHODOLOGY.md): matching, realistic requests, execution stages,
  quality, latency, throughput, cost accounting and completion criteria.
- [suite.json](suite.json): current planning contract and explicit unresolved choices.
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
The separate [reference runner](scripts/fal_reference.py) implements only the
single authorized API reference; no self-host runner is ready yet.

Do not provision a paid resource until the [preflight requirements](PREFLIGHT.md)
are met and the whole commitment is reserved. No automatic retries or hidden
spending expansion. Do not publish secrets, account/payment details, private
conversations, raw private logs or signed URLs.
