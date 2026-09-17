# Published-claim verification register

Version 0.7. **No claim below has been verified by a paid pilot run.**
This is the verification checklist; exact source claims and values are pending
selection of the first fal.ai endpoint and corresponding self-host deployment.

| ID | Claim category | Conditions that must be captured | Current status |
|---|---|---|---|
| C01 | Hardware cost | GPU type/count, CPU/RAM/storage, region, billing unit, date, fees and credits | Not tested; source/value pending |
| C02 | Interactive latency | Request/output profile, cold/warm, queueing, all pipeline stages and download boundary | Not tested; source/value pending |
| C03 | Batch throughput | GPU count, batch size, concurrency, wall-clock window, accepted output and latency at load | Not tested; source/value pending |
| C04 | Iterations/steps and optimization | Exact settings, runtime, measured speed/cost and quality trade-off | Not tested; source/value pending |
| C05 | Additional pipelines | Prompt enhancement, conditioning, upscaling/interpolation, audio, encoding and delivery | Not tested; source/value pending |
| C06 | API price and service configuration | Exact fal.ai endpoint/tier, version/date, input/output contract and actual billed amount | Not tested; source/value pending |

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
