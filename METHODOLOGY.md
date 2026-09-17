# Testing Methodology: API-Matched Video Generation and Operator Economics

Version 0.8, September 17, 2026. **Reference selected; no paid runs or results.**
Total spending cap: **USD 25 across the entire pilot**, not per model or backend.
All published content is in English.

## 1. Objective and scope change

The business objective is to maximize video operators' profit. The technical
question is: **can we deliver the service of a specific fal.ai endpoint using a
corresponding self-hosted open-weight deployment, at a lower fully accounted cost,
with acceptable quality and response time?**

This replaces the v0.6 cross-model quality pilot. H3, LTX and Wan remain candidate
families, not three mandatory arms of the first experiment. Start with **one
matched pair: one fal.ai endpoint and one self-hosted deployment**. The selected
reference is `minimax/h3/text-to-video`, native 768P, 16:9, 5/10 seconds, seed 42,
with prompt expansion disabled. The self-host candidate is MiniMax H3 Base FL2VA,
not H3 Max, on one B300 using SGLang Diffusion. See [START_HERE.md](START_HERE.md)
for the diagnostic baseline, latency warning and first-test sequence.
The self-host execution profile and matching evidence remain unverified.

The old 12-attempt schedule and VBench prompt subset are no longer active.
The earlier English protocol is retained in [Git history](https://github.com/Frozen/video-generation-cost-benchmark/tree/ee78f1f2ec20864139d4c0bda84e37e40938c4e2).
The active schedule is empty until realistic requests, self-host profiles and
cost bounds are pinned. Zero scheduled attempts means "not scheduled", not "complete".

VBench is **deferred**, with no first-stage automated VBench budget or requirement
that every file be at least 5 seconds. Retain outputs for possible later analysis.
Human review still checks that the service is usable and has not materially
degraded relative to the matched API output; this is not a cross-model ranking.

High utilization, high-end GPUs and complex workflows are hypotheses to test,
not assumptions of profitability or authorization to rent a particular GPU.

## 2. Select and match a service, not just a model name

The first endpoint and exposed settings are selected in [START_HERE.md](START_HERE.md).
Before execution, verify its contract, current price and relevant performance
claims against the self-host candidate. Record source URLs,
access dates, versions and the conditions attached to each claim in [CLAIMS.md](CLAIMS.md).

Use this matching checklist before paying:

| Property | Required comparison evidence |
|---|---|
| Model identity | Family, variant, checkpoint/revision, post-training, license and self-host access |
| Endpoint and workflow | Exact endpoint ID/version, workflow stages and available source/runtime pins |
| Inputs | Identical prompt text and input image/video/audio bytes; record hashes and payload mappings |
| Output contract | Task type, requested duration, actual duration tolerance, dimensions/aspect ratio, fps, codec and audio |
| Generation settings | Seed behavior, steps/iterations, sampler, guidance, precision and exposed controls |
| Additional stages | Prompt rewriting, conditioning, interpolation, upscaling, audio, encoding and delivery |
| Infrastructure | GPU type/count/VRAM, CPU/RAM, storage, region, runtime/container and hourly billing unit |
| Service behavior | Cold/warm start, queueing, batching, concurrency, limits, errors and retry policy |
| Price | Exact tier and billing unit, date, promotion/credit treatment, fees and per-request quote |

Classify each property as matched, different, or unknown, with evidence. Different
field names may be mapped explicitly; they do not justify changing the logical
request. Where both interfaces expose the same seed semantics, use the same seed,
but do not promise identical noise or pixel-identical outputs.

Do not call a Base checkpoint equivalent to a Max/post-trained API variant merely
because they share a family name. Likewise, Wan 2.2 and Wan 3.0 are not aliases.
A first/last-frame workflow is eligible only as an explicitly identified service
with the same input assets on both sides; it is not silently substituted for T2V.

Undisclosed provider internals remain unknown. Distinguish request-contract
matching from proven implementation equivalence. If the endpoint's weights or
essential workflow cannot be reproduced, record an unmatched/partially matched
comparison, not a verified replica. A different model/variant requires a newly
named comparison pair and an explicit scope decision.

## 3. Realistic, frozen customer requests

Select representative requests for the chosen service, using realistic examples
such as the suggested [Awesome Video Prompts collection](https://awesomevideoprompts.com/).
The collection is a candidate source, not proof that a prompt is popular or
representative of our customers. Document the use case and selection rationale.

For every selected request, freeze before generation:

- Request ID, original source URL, retrieval date and reuse/asset permissions.
- Exact English prompt; save the final submitted text and its hash.
- Input assets and hashes, task type, seed if supported and all output settings.
- API payload and corresponding self-host payload, including explicit differences.
- Required prompt elements and an acceptance checklist for visual/audio defects.

Do not select prompts after seeing which backend handles them best. Preserve the
chosen submitted text across backends. If prompt enhancement is part of the
reference service, include it in the workflow, timing and cost; record the
expanded prompt where available rather than silently disabling or rewriting it.

Keep approximately 5- and 10-second duration targets when the selected endpoint
supports them. Pin actual native profiles and tolerances before execution; do not
pad, crop or interpolate just to make results look equivalent. The old VBench
5-second evaluator boundary no longer determines the request design.

Both sides receive the same logical request and the same assets. Preparing any
required input assets counts toward experiment cost; production cost and customer
latency include that preparation if the operator, rather than the customer,
must provide it. Record this boundary explicitly.

## 4. Staged execution within USD 25

| Stage | Work | Exit evidence |
|---|---|---|
| A — specification | Inventory claims, select one endpoint, map the self-host deployment, freeze requests and quotes | Matching matrix and bounded executable plan |
| B — paired smoke test | Run the same request once through each backend, with batch 1 and one request at a time | Downloaded outputs, actual charges, timings and human review |
| C — interactive comparison | Cover supported short/long requests and explicitly budgeted repetitions on the same pair | Per-request end-to-end latency and accepted-output cost |
| D — bounded performance checks | If funds remain, measure batching/concurrency and selected optimization changes | Measured throughput, latency, quality and cost per configuration |
| E — economics and closeout | Reconcile charges, model utilization scenarios, export artifacts and stop test resources | Auditable cost summary and an honest coverage/limitations report |

The two sides of a paired request are **two separately billed attempts**. A
short/long pair on both backends would require four attempts for one prompt,
before repetitions, load tests, failures or additional configurations. This is
counting guidance, not a funded schedule or a new fixed attempt count.

Freeze the exact attempt count, run order, per-stage budget, load-test size and
maximum wall time in a new plan revision after quotes. Alternate or counterbalance
backend order where feasible. Label cold starts and compilation; do not hide
warm-up expense or mix warm and cold measurements.

Baseline batch size is 1 and interactive concurrency is 1. Any increase in batch
size or concurrency is a separate, bounded load configuration with its own ID,
request count, timeout, price bound and approval. It is not an unlimited stress test.

Reproduce the reference settings first. Then test a small, predeclared set of
step counts or other optimizations if budget permits. Record each configuration
and its quality/performance trade-off; "best tested" is not "globally optimal".
Include all pipeline stages, not only denoising. Do not change weights/settings
after review and present the result as the same baseline configuration.

No automatic retries. Every additional attempt needs a new record and reservation.
Preserve failures rather than replacing them with a successful rerun.
If the remaining budget cannot cover both sides and safe closeout, do not start
the pair. Unmeasured load/optimization claims remain unverified.

## 5. Latency, throughput and acceptance

### Interactive target: 1 second of video per at most 3 seconds of waiting

The previously agreed first-stage target remains in force:

| Planned video duration | Maximum end-to-end wait |
|---|---:|
| short: 5 seconds | 15 seconds |
| long: 10 seconds | 30 seconds |

```text
latency_limit_seconds = 3 × planned_video_seconds
latency_pass = end_to_end_seconds <= latency_limit_seconds
```

Measure from request submission to the fully downloaded final video. Include
queueing, post-submission cold start, request preparation, inference, extra
pipeline stages, encoding and delivery. Record component timings where available;
an unavailable component is unknown, not zero. Setup before the request is
recorded separately but remains an expense.

Apply the threshold per interactive attempt, not just to an average or denoising
time. Keep the planned 15/30-second limits even if actual native duration differs
slightly within an approved profile. Late files are marked latency_failed and
excluded from accepted interactive output, but their costs remain included.
Missing timing is not a pass. Also report API latency independently: an API
reference can fail our target too; it does not reset that target.

For throughput, measure completed and accepted clips per wall-clock interval,
accepted video seconds per interval, batch size, concurrency, offered load,
queueing and errors. Also report latency at that load. Include failures and
idle gaps in the measurement window, and wait for or account for every submitted
job at the cutoff. Do not obtain throughput by dividing one clip's duration by
one inference measurement, or equate batch size with request concurrency.

Keep batch-service and interactive-service results separate. A high-throughput
configuration that misses 15/30 seconds cannot be presented as meeting the
interactive target. Any alternative batch-service latency requirement must be
explicitly agreed. Small samples do not establish p95, stable capacity or an SLA.

### Lightweight human review, not VBench

Check full decoding, output-contract compliance, prompt_match (pass/partial/fail),
visual quality and audio where the selected service includes it. Use the same
predeclared checklist on both backends. Review blinded to backend and price,
twice at 1× speed; unresolved disagreement requires a second reviewer and does
not count as acceptance.

Record whether the self-host output has a material defect or missing capability
relative to the API reference, with a short reason. Different composition alone
is not a defect unless specified by the request. Both outputs may fail; API origin
does not make an output automatically acceptable.

Only prompt_match=pass, valid output, acceptable quality and passing interactive
latency count toward accepted interactive output. Unreviewed values remain null.
Retain partial/fail results and all their expenses. No VBench Total Score,
cross-model quality ranking or statistical equivalence claim is made.

## 6. Verify published claims

The research program covers published hardware cost, batch throughput, interactive
latency, iteration/step choices and additional pipeline measurements relevant to
each selected deployment. [CLAIMS.md](CLAIMS.md) records the verification checklist.

For each claim, retain the source, publication/access dates, original conditions,
measurement boundary, reported value, reproduction setup and observed result.
Separate provider-reported, independently measured and modeled values.
Classify the result as supported under matched conditions, not reproduced,
not comparable, or not tested. Do not call a mismatched resolution, workflow,
GPU count or timing boundary a reproduction.

USD 25 funds an initial feasibility check, not verification of every claim across
all models and hardware. Publish omissions explicitly. Later matched pairs or
longer load tests need separately agreed scope and funding.

## 7. Cost accounting and operator economics

Keep two views separate:

1. **Experiment spending:** all money spent to conduct this pilot, capped at USD 25.
2. **Service economics:** recurring self-host cost and potential contribution at a
   stated selling price and utilization. This is a model, not observed profit.

```text
C_experiment = C_API_reference + C_self_host_trial + C_shared_test + C_closeout
C_experiment <= 25 USD
```

Include setup, running-GPU downloads, warm-up, compilation, failures, idle rental,
CPU/RAM, input preparation, extra pipelines, export, storage and required fees.
Avoid double counting resources already included in the rental price.
Reconcile quoted prices with actual bills. A deposit is not an experiment expense.
Report credit/promotion subsidy separately from unsubsidized resource cost.
Labor is outside the USD 25 infrastructure cap; disclose its treatment in any
business model rather than claiming that infrastructure contribution is net profit.

Do not charge the API benchmarking bill to each future self-hosted customer clip.
Report trial all-in cost per accepted clip separately for each backend, allocating
shared trial expenses by documented usage or an explicitly stated allocation.
Zero accepted output means undefined unit cost, not a zero-cost success.

For each fixed output/workflow/load profile, report these utilization scenarios
as **estimates**, initially 25%, 50%, 75% and 100%:

```text
R = measured accepted clips per busy hour at the stated load and service requirement
u = assumed fraction of billed wall-clock time spent serving that measured workload
Q(u) = u × R
F = recurring fixed cost per billed hour, including idle rental
v = variable cost per accepted clip not already included in F
P_net = assumed net receipts per accepted clip after explicitly modeled deductions

service_cost_per_accepted_clip(u) = F / Q(u) + v
contribution_per_hour(u) = Q(u) × (P_net - v) - F
break_even_utilization = F / (R × (P_net - v))
```

These simplified formulas require R > 0 and u > 0; break-even also requires
P_net > v. A break-even utilization above 100% is not feasible under those
assumptions. At zero accepted output, report losses and undefined unit cost.
Here u is service workload utilization, not a GPU-monitor utilization percentage.

Report setup amortization, startup/scale-down effects, capacity limits and any
omitted overhead separately; add them to F or v once an allocation is specified.
Different durations/profiles need separate calculations or an explicitly weighted
request mix. Do not assume ideal linear scaling with GPUs or batches.
The 100% scenario is an upper-bound scenario, not evidence of customer demand.

Use the matched API's dated price as a market reference, not guaranteed revenue
or proof of customer willingness to pay. Show price headroom and contribution
under explicit selling-price assumptions. Do not label this a net-profit forecast.

### Spending controls

Working allocation: $18 for setup and the paired generation comparison, $4 for
optional bounded load/optimization checks, and $3 for storage, export, shutdown
and mandatory fees. The former VBench allocation is repurposed; VBench receives $0
in this stage. Reallocation is allowed before commitments, never above $25.

Reserve the upper bound of every commitment before spending, including outstanding
requests, fees, storage and closeout. Do not schedule new compute beyond $22.50
of aggregate exposure. Both paid API calls and self-host resources use the same
budget ledger; performance checks are generation work, not free diagnostics.

A rented GPU needs a verified independent stop/termination deadline that survives
session loss; an API request needs a known bounded price. The local ledger is
an admission check, not a provider spending cap. No unbounded rental, unknown-price
request, automatic budget expansion or implicit retry is allowed.

A latency timeout is not proof of provider cancellation or stopped billing.
Verify final job state and charges. Stop after two consecutive technical failures,
loss of cost control, incompatible output or budget exhaustion. Export and verify
artifacts before closing only the test's resources; preserve unrelated resources.
Report incomplete coverage rather than exceeding the cap.

## 8. Deliverables and completion

Publish the endpoint/self-host matching matrix, frozen requests and hashes,
configuration pins, claim-verification register, per-attempt timings and charges,
blinded quality review, measured throughput where available, utilization scenarios
with assumptions, and a limitations/next-test recommendation.

Keep original output files, pipeline intermediates needed for diagnosis, redacted
request/response records and billing evidence. Use unique pair/configuration/
request/attempt IDs so baselines, optimizations and failures cannot overwrite
one another. Do not publish credentials, payment details, account identifiers,
private conversations, private logs or signed URLs.

Completion of the first stage means the agreed first matched-pair plan is accounted
for, failures and omissions are explicit, required quality/cost/timing evidence is
reported, total spending is verified at no more than USD 25, and no paid compute
or unapproved storage remains. It does not require all three model families,
a VBench run, proof of maximum profit or verification of every published claim.
If matching or bounded access is impossible, publish a feasibility blocker, not
a successful comparison. Publishing this methodology alone is not execution.
