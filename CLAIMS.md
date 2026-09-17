# Published-claim verification register

Version 0.8.1. **No claim below has been verified by a paid pilot run.**
The selected reference is `minimax/h3/text-to-video`, native 768P, with expansion
disabled. The self-host candidate is H3 Base FL2VA; implementation equivalence
is unverified. [START_HERE.md](START_HERE.md) records the selected profile.

| ID | Claim category | Conditions that must be captured | Current status |
|---|---|---|---|
| C01 | Hardware cost | GPU type/count, CPU/RAM/storage, region, billing unit, date, fees and credits | Runpod catalog recorded; actual allocation and bill not tested |
| C02 | Interactive latency | Request/output profile, cold/warm, queueing, all pipeline stages and download boundary | Published SGLang base-model result recorded; our candidate not tested |
| C03 | Batch throughput | GPU count, batch size, concurrency, wall-clock window, accepted output and latency at load | Not tested; source/value pending |
| C04 | Iterations/steps and optimization | Exact settings, runtime, measured speed/cost and quality trade-off | Not tested; source/value pending |
| C05 | Additional pipelines | Prompt enhancement, conditioning, upscaling/interpolation, audio, encoding and delivery | API contract inspected; actual behavior and self-host matching not tested |
| C06 | API price and service configuration | Exact fal.ai endpoint/tier, version/date, input/output contract and actual billed amount | Published 768p rate recorded; actual billing not tested |

## Initial evidence recorded on September 17, 2026

- **C01 — live catalog, not a paid bill:** Runpod MCP returned USD 7.89/hour,
  288 GB and LOW availability for one B300 in Secure Cloud Pods. The selected
  candidate and alternative catalog observations are in [START_HERE.md](START_HERE.md).
- **C02 — upstream-reported, not reproduced:** [START_HERE.md](START_HERE.md)
  records the SGLang eight-B300 result and its conditions. It warns of a gap
  against our target; it is not a one-B300 estimate or customer SLA.
- **C05 — provider-documented, not runtime-verified:** the selected
  [API contract](https://fal.ai/models/minimax/h3/text-to-video/api) exposes native
  `768P` and disabled prompt expansion. We explicitly select those settings and
  do not supply `target_audio_url`. Actual output properties and hidden processing
  remain unverified; null `expanded_prompt` alone is not proof of no preprocessing.
- **C06 — provider-published, not a measured charge:** the
  [endpoint page](https://fal.ai/models/minimax/h3/text-to-video) lists USD 0.06
  per generated second at 768p. Derived API-only amounts are USD 0.30 for 5 seconds
  and USD 0.60 for 10 seconds. These exclude self-host trial costs and are not a
  tax-inclusive reservation or guaranteed future price. Recheck before spending.
- **Candidate feasibility, not confirmed equivalence:** the
  [official MiniMax release](https://huggingface.co/MiniMaxAI/MiniMax-H3) includes
  H3 Base FL2VA and a native text-to-audio-video path. One B300 and SGLang Diffusion
  are selected for a baseline, but exact pins, host requirements, output behavior
  and the match to the selected API still require verification.

## Evidence record for each selected claim

- Claim ID and linked comparison-pair/configuration IDs.
- Source URL, publisher, publication date if available and access date.
- Reported value, units, scope and original test conditions.
- Whether the value is provider-reported, independently measured or modeled.
- Reproduction request hashes, code/workflow pins, hardware and measurement boundaries.
- Differences or unknowns that prevent a matched comparison.
- Attempt IDs, sample count, observed values, failures and redacted billing evidence.
- Outcome: supported under matched conditions / not reproduced / not comparable /
  not tested, with a short reason.

Do not silently turn a published value into a measurement or label a changed
workflow a reproduction. Claims that cannot be covered by the USD 25 pilot remain
not tested. The register is not a promise to verify every model and configuration
within this initial budget.
