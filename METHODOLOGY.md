# Video Generation Cost and Quality Testing Methodology

Version 0.6, updated September 16, 2026. Public pilot protocol for H3 / LTX / Wan.
The spending cap is **$25 in total**, not per model. No videos have been generated yet.
This version supersedes the earlier two-model plan: the model count has increased
to three, but the budget has not. The methodology is published before results.
Parameters marked pending are not presented as approved or measured.

## 1. Research questions

The objective is to find the cheapest tested configuration that produces acceptable
video within the allowed wait time. Speed and quality are acceptance requirements;
cost determines the choice among configurations that meet those requirements.

1. What does each configuration cost per accepted video, including setup,
   loading, failures, idle time, evaluation and storage?
2. How do generation time and cost per output second differ between short and long clips?
3. Do the outputs meet the technical requirements for human review and VBench
   evaluation without generating them again?

We compare configurations: model + version + deployment method + GPU/workflow.
A managed API and a self-hosted GPU are different deployment options. When both
are included, conclusions apply to those configurations, not to model weights
in isolation. API latency is not evidence of single-GPU performance.

### Agreed stage-one target: at most 3 seconds of waiting per second of video

For the first stage, the fixed target is **1:3 — video duration : total wait time**.
This is a pilot acceptance requirement, not measured performance or an SLA promise.

| Planned video duration | Maximum end-to-end wait |
|---|---:|
| short: 5 seconds | 15 seconds |
| long: 10 seconds | 30 seconds |

```text
latency_limit_seconds = 3 × planned_video_seconds
latency_pass = end_to_end_seconds <= latency_limit_seconds
```

Measure from request submission to the fully downloaded video file, including
queueing, preparation within the request, generation, encoding and downloading.
Model inference time alone does not replace this measurement. Record initial
environment setup before the request separately; a cold start after submission
counts toward the wait. Label cold and warm requests separately, but apply the
same threshold. Subsequent human review and VBench evaluation do not count toward
the wait for the video; their costs remain within the total budget.

Apply the threshold to each attempt, not just the average. For the current plan,
use the 15- and 30-second limits above and record actual native output duration
separately. Do not increase the limit retroactively because the output is longer
or startup is slow. Assess GPU choices and optimizations against this target
while retaining the quality requirements.

Record a threshold breach as `latency_failed`: even a visually acceptable clip
then fails overall stage-one acceptance. Errors and missing measurements do not
count as success. Retain all costs and generated files in the report. Exceeding
the threshold does not mean the provider has stopped the job or stopped charging:
verify completion or cancellation separately, without automatic retries.

Published competitor timings provide context; they do not replace the agreed
threshold. The specific reference API and a comparable profile for the cost
comparison still need to be pinned. The $25 cap and independent rental limit
remain in effect.

## 2. Models and selection policy

H3 means MiniMax H3. The self-hosted text-to-video candidate is Base FL2VA.
LTX means LTX-2.5, with distilled as the candidate variant. For Wan, the latest
verified API family is 3.0, while the open text-to-video weights found belong
to the 2.2 family. See the [README](README.md) for sources and distinctions.

Explicitly identify the family, variant, deployment method and input type:

| Pilot label | Current candidate | Deployment and input | Do not conflate with |
|---|---|---|---|
| H3 | MiniMax H3 Base FL2VA | Self-hosted, text | H3 Max by fal is a separate post-trained variant; its comparison role is unresolved |
| LTX | LTX-2.5 distilled | Self-hosted, text | Other weight variants and API tiers without separate identification |
| WAN | wan3.0-video | Vendor API, text | Wan 2.2 open weights and frame-conditioned workflows |

Open weights alone do not make Wan 2.2 equivalent to Wan 3.0 or prove that it is
cheaper. The proposed first/last-frame workflow remains outside these 12 attempts:
it requires a separate configuration ID, a verified workflow and equivalent input
conditions across the compared solutions. If input frames must also be generated,
include their preparation in that workflow's cost and end-to-end wait. This
workflow is not yet approved and does not authorize additional paid attempts.

The choice between "latest release overall" and "latest open weights" must be
explicit. Until it is resolved, do not substitute Wan 2.2 for 3.0. Likewise, do not
silently substitute Hailuo for H3 or an older release for LTX-2.5.

Before execution, pin each model's repository and revision/commit, weight/workflow
hashes, API version or model ID, GPU type and count, price and billing unit, region,
container digest, libraries/driver, precision, steps/sampler/guidance,
offload/tiling/compilation settings, all internal stages, encoder and prompt processing.
For hidden API parameters, record "not disclosed by provider" rather than guessing.
A funded Runpod balance does not establish access to another paid service.

## 3. Inputs and the 12-attempt schedule

Source: VBench, commit `fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490`.
Submit prompts verbatim, without translation, enhancement, or added style or actions.

| Local ID | Zero-based source index | Prompt |
|---|---:|---|
| S01 | 262 | a person drinking coffee in a cafe |
| S02 | 29 | A tranquil tableau of a bowl on the kitchen counter |

S01 tests a recognizable human action and interaction with a drinking vessel.
S02 adds a calm object scene with a specific object and spatial relationship.
These cover two different scene types without requiring identical compositions.
The alternative at index 259 (`a person washing the dishes`) is valid, but repeats
the human–dishware interaction scenario, so it is not included in this small pilot.

Before any generation, S05 / index 823 (`kitchen`) was replaced with S02 / index 29:
the previous one-word prompt specified too few verifiable elements. The new prompt
is preserved verbatim; its index, hash, new run IDs and filenames are recorded in
the plan. The old scene ID is not reused, and Git retains the change history.

For each model: S01 short, S01 long, S02 long, S02 short; seed 42,
sample_index 0. Thus, 2 scenes × 2 durations × 3 models = 12 attempts.
The target is 30 seconds of video per model and 90 seconds overall; actual durations
come from the files. The schedule and identifiers are generated deterministically
from suite.json.

The targets are approximately 5 seconds for short and 10 seconds for long. The
initially proposed self-hosted profile of 1280×736 at 24 fps is not claimed to work
across all models: exact dimensions, fps, frame counts and actual durations must
be fixed after checking the interfaces. If no common native profile exists,
explicitly agree on and publish the differences. Do not crop, interpolate or
stretch outputs to create an appearance of equivalence.
Both native profiles must produce at least 5.0 seconds for the shared VBench-Long
evaluator. Check actual file duration, not only the requested number of seconds.
Choosing an evaluator neither increases the 15/30-second wait limits nor verifies
compatibility of model profiles that have not yet been tested.

Use one concurrent request, batch size 1 and zero automatic retries. Audio is not
evaluated; if generation necessarily includes audio, its cost remains part of
the model's cost. Within each model, short/long changes only frame count/duration.
The same seed does not guarantee identical noise across models or bitwise reproducibility.

Do not change model weights or the environment after inspecting output quality.
Retain failed attempts in the report. A diagnostic retry requires a separate record
and budget reservation; it does not replace the failure or allow selection of the
"best take." Fix the model execution order before running.

## 4. Measurements and retained artifacts

For every attempt, record run_id, profile, seed, exact prompt, submission/receipt
timestamps, queue delay if disclosed, generation and export times, cold/warm/unknown
status, compilation, actual dimensions/fps/frame_count/duration, file SHA-256 and status.
Also record end_to_end_seconds, latency_limit_seconds, the per-attempt latency result,
prompt_match and a short explanation of the human review.
Overall acceptance requires a valid output profile, prompt_match=pass, acceptable
visual quality and a passing latency result. One short and one long clip per scene
provide only a preliminary indication of scaling. Do not infer p95 latency, annual
GPU capacity or a reliable ranking from this sample.

File layout: `videos/<model>/<short|long>/<exact prompt>-0.mp4`. Preserve filenames
and sample_index; different models and durations must not overwrite each other.
Keep the original MP4 unchanged; VBench uses separate derived copies.

Acceptance checks include complete decoding, conformity to the declared output
profile, intact human/vessel appearance for S01, and a recognizable bowl with stable
bowl/counter geometry for S02. A static S02 scene is not inherently defective;
gentle camera motion is allowed. Do not penalize differences in color, interior
or composition that the prompt does not specify.
Record major defects lasting at least 0.5 seconds; do not add criteria after seeing
results. Review each video twice at 1× speed without model names or prices. Refer
disputes to a second reviewer; without agreement, the output is not accepted.
Automatic decoding does not replace human acceptance; before review, the status
is manual_review_pending.

`prompt_match` is a separate human judgment of prompt adherence, not a VBench metric:

| Label | Criterion |
|---|---|
| pass | All required scene elements are clearly present |
| partial | Some elements are present, but at least one is absent or ambiguous |
| fail | No required elements are established, or the result depicts a fundamentally different scene/action |

S01 requires a visible person, a visible drinking action with a vessel consistent
with drinking coffee, and a recognizable cafe setting. The drink's composition
cannot reliably be established from pixels; no evidence beyond this visual
criterion is required.
S02 requires a recognizable bowl, not merely a drinking cup, positioned on a
kitchen counter in a calm composition. These requirements are also pinned in suite.json.

Before review, the value is null, not an automatic pass; disputes go to a second
reviewer. Outputs marked `partial`, `fail` or not yet reviewed do not count as
accepted output in cost calculations. Their costs and diagnostic scores remain
in the report.

## 5. VBench evaluation on the same files

Use six diagnostic scorers: subject_consistency, background_consistency,
motion_smoothness, dynamic_degree, aesthetic_quality and imaging_quality.
Evaluate every decodable pilot file with a compatible duration in custom-input
mode, including outputs rejected for prompt_match, quality or latency.
Group results separately by model and duration: up to two source files per
metric/group. These two scenes do not cover the original official prompt groups
for every metric. This is a technical custom-input pilot, not an official
source-mapped VBench score.

The pinned [FAQ](https://github.com/Vchitect/VBench/blob/fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490/README-FAQ.md)
recommends VBench-Long for durations of at least 5.0 seconds. Fix
**VBench-Long / long_custom_input** for both profiles. Every file must have an
actual duration of at least 5.0 seconds. Otherwise, record the incompatibility and
the reason for the missing score; do not pad/stretch the file, silently switch
evaluators or purchase an automatic retry. Pin the evaluator, weights,
preprocessing and settings before execution and keep them identical across models
within each comparison group. Do not pool short and long results or claim their
scores are fully comparable merely because they share an evaluator.

In the original VBench metadata, index 29 belongs to temporal_flickering, which
is not among our six diagnostic scorers. Selecting this prompt does not add a
seventh metric or turn this small custom-input pilot into an official evaluation
covering every VBench dimension.

Do not average the six metrics into a homemade Total Score. Higher dynamic_degree
does not mean better quality for a still scene. Report decoding and evaluator
failures separately from quality: no fabricated zeros and no hidden omissions.
Derived evaluator segments do not count as additional generated videos.

## 6. Cost accounting and the fixed spending cap

```text
C_total = C_setup + C_generation + C_evaluation + C_storage + C_other_required
unit_cost = C_total / N_accepted
cost_per_accepted_minute = C_total / (accepted_output_seconds / 60)
```

N_accepted and accepted_output_seconds include only outputs that pass the output
profile check, prompt_match=pass, human quality review and the latency threshold.
Late outputs are excluded from accepted output, but not from C_total.

If there is no accepted output, unit cost is undefined. Include all paid failures,
waiting time, model downloads while a GPU is running, cold starts, compilation,
export and evaluation. An account balance or deposit is not itself an experiment
expense. Show promotional credits separately: resource cost before subsidy and
out-of-pocket cost after subsidy. Labor is outside the agreed $25 infrastructure budget.

The full cost of the three-model plan has not yet been measured. The earlier
two-model estimate does not automatically apply to three models. The working
allocation is up to $18 for setup and generation, $4 for evaluation and $3 for
storage/export/shutdown and mandatory fees; all categories are within the $25 cap.
Reallocation is allowed before committing expenditure; increasing the total cap is
not. Allocate shared expenses according to measured execution time for the relevant
worker. Indivisible shared costs are split equally across the three models under
a rule fixed in advance and shown as a separate line item.

Before every paid action, reserve **the upper bound of the entire commitment**,
including a potentially unfinished request, taxes, disks and closeout.
Count already reserved jobs even if their charges have not yet appeared in billing.
Do not schedule new compute beyond $22.50 of aggregate spending exposure;
preserve the remainder for closeout. Do not pay an unknown price or start work
whose completion and shutdown cannot fit within the remaining budget.

A rented GPU requires a verified independent stop/termination deadline that still
works if the agent session is lost. An API requires a known price for a bounded
request. Automatic account top-ups do not provide additional experiment budget.
The ledger controls whether work may start; it is **not a provider-enforced guarantee**.
If an infrastructure/provider-side bound cannot be established, paid execution is
prohibited. A temporary loss of visibility does not mean a job has finished and
does not justify retrying it.

Stop after two consecutive technical failures, loss of cost control, an incompatible
profile or approaching the budget cap. Verify export before closing temporary
resources. Delete only this test's resources after saving the required files;
leave unrelated resources untouched.
If the full test does not fit, publish the incomplete coverage, do not exceed $25,
and do not declare the objective complete. Neither stopping a Pod nor reaching
a zero balance guarantees data preservation or the end of all storage charges.

## 7. Publication and completion

Before execution, publish the methodology, prompt source, suite and protocol commit.
After execution, publish retained original outputs/checksums, exact profiles and
environment, attempt log, a redacted billing summary, six diagnostic metrics,
human acceptance results, limitations and actual cost.
Do not publish keys, payment details, personal account identifiers, private logs
or temporary signed URLs.

Publication readiness and experiment completion are different states. Completion
requires results for all three declared models, transparent recording of
failures/missing results, quality evaluation, verified total spending of no more
than $25, and no remaining paid compute or unapproved storage. Publishing the
protocol alone does not complete the experiment.
A larger run and the full VBench leaderboard evaluation are outside this budget.
