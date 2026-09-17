# First reference result: MiniMax H3 on fal.ai

September 17, 2026. **One real API request completed; no self-host run yet.**
This is a single observation, not an average, p95, throughput benchmark or SLA.

[Watch/download the original generated video (MP4, 2.6 MB)](results/P01_FAL_5S_001.mp4).
Published with the operator's explicit approval; no trimming, resizing or re-encoding.

| Measurement | Published or planned | Observed |
|---|---|---|
| Request | 5 seconds, native 768P, 16:9, seed 42; expansion disabled | One request with those explicit settings |
| Customer wait | Our target: at most 15 s, not a fal promise | **102.644 s** submission through completed download; target failed |
| Provider processing | No matched published latency claim selected | Provider returned **96.128 s** inference time; not an independent GPU measurement |
| Generation charge | USD 0.06 per requested output-second at 768P: **USD 0.30** | Response reported 6.0 billable units; authenticated base unit price USD 0.05 also gives **USD 0.30** |
| Invoice reconciliation | Actual net charge must be checked | Billing-events API returned 403; final charge remains unverified, not zero |
| Output | Requested 5 s / 768P / 16:9 | H.264, **1344x768, 124 frames at 24 fps**, 5.166667 s video; 5.184 s container |
| Audio | Native generated soundtrack | AAC, 32 kHz, stereo; audio quality review pending |
| File integrity | Downloadable and decodable | 2,639,051 bytes; full audio/video decode completed without errors |
| Self-host | 1 x B300, SGLang Diffusion candidate | Not rented or measured; no budget-GPU substitution |

The observed wait is **20.53 seconds per requested second of video**, versus our
target of 3. This run fails the latency gate regardless of later quality review.
It does not prove that all fal H3 requests take this long. Cold/warm state, provider
hardware and internal settings are unknown. First polling observation was already
`IN_PROGRESS`; do not claim zero queue time from that.

The last in-progress observation was at 95.965 s and completion was first observed
at 98.261 s. Poll sleeps were 2 s; request/network time adds overhead. The headline
102.644 s includes polling, result retrieval and media download. Do not replace it
with the provider-reported 96.128 s when discussing customer wait.

## Cost interpretation

The [endpoint price](https://fal.ai/models/minimax/h3/text-to-video) and the returned
`X-Fal-Billable-Units: 6.0`, combined with the authenticated USD 0.05 base billing
unit price, independently give the same USD 0.30 generation calculation. **Six
billable units do not mean six seconds of output**, and must not be multiplied
again by the resolution-specific USD 0.06 rate. Discounts, credits and any taxes
are not independently reconciled. Retain the USD 1 local reservation until the
actual billing entry is checked; this reservation is not a claim of spending USD 1.
No additional requests or rentals were started. The overall cap remains USD 25.

## Quality and output-contract limitations

Five extracted frames show the expected kitchen, onion transformation and cartoon
eyes on vegetables. This is an informal agent inspection, **not** a blinded human
quality score or proof of complete prompt adherence. Audio quality and detailed
temporal/prompt review remain pending. No VBench was run.

The native output dimensions have ratio **7:4**, not exact 16:9, and the video
lasts 124/24 seconds, not exactly five seconds. Record these facts for the self-host
mapping; no post-hoc crop, trim, upscale or new acceptance tolerance is applied.
The returned expanded-prompt field was null; this does not establish the absence
of all hidden provider processing.

## Reproducibility and next step

- [Execution addendum](REFERENCE_RUN.md): frozen profile, provenance and one-call scope.
- [Machine-readable result](results/P01_FAL_5S_001.json): input/output hashes and separate evidence types.
- [Measurement sheet](results/MEASUREMENTS.csv): compact published/planned-versus-measured record, suitable for linking or importing into a shared sheet.
- [Our economics model](ECONOMICS.md): rental-cost formula, explicit utilization
  scenarios and the remaining measurements needed before drawing a cost conclusion.
- [Runner](scripts/fal_reference.py): one submission, durable duplicate guard,
  private artifacts and same-request collection recovery.

The full prompt, raw API responses, request identifiers and provider media URLs
are kept in ignored private storage. The generated MP4 is public with the operator's
approval and matches the recorded SHA-256. The source text is unchanged; provenance and hashes
are public without asserting a new license for the original creator's prompt.

Next: review this output, then prepare the same request on the selected B300
candidate. Runpod access, pinned runtime/model, full quote and an independent
shutdown bound must be verified before renting. No repetitions, 10-second clips,
optimization or alternative GPUs are automatically authorized by this result.

## Validation

`python3 scripts/validate.py` validates the historical v0.8.1 paired planning
contract, not this completed reference or self-host readiness.
`python3 -m unittest discover -s tests -v` passes 56 offline tests.
`ffprobe` inspected media streams; `ffmpeg -v error -i video.mp4 -f null -`
fully decoded the downloaded file without errors. `git diff --check` passed.
