# fal H3 / H3 Max / H3 Max Turbo: one request per variant

**Completed:** all three clips and the [comparison results](VARIANT_RESULTS.md)
are published. Do not resubmit these completed attempts.

September 17, 2026. The operator explicitly approved adding **one H3 Max and one
H3 Max Turbo request** to the completed standard H3 reference. This is a small
commercial-reference comparison, not proof that these are the same weights or
that the open base deployment reproduces fal's post-trained variants.

## Frozen controls and spending

Keep the original prompt, 5-second duration, native 768P, requested 16:9, seed 42,
disabled prompt expansion, safety checking, asynchronous URL delivery, 2-second
poll sleeps and submission-through-download timing unchanged. The payload bytes
are copied from the completed H3 attempt and checked against its published hash:
`7ae3a094032d307f0d419ca4e86120788ca36f6126416c75fde01834cb0de845`.
Same seed across different variants does not mean identical stochastic behavior.

Run the two additional requests **sequentially**, Turbo then Max. Each has a
distinct private artifact directory, request marker and USD 1 budget reservation.
Retain all outstanding reservations until reconciliation. Existing H3 reservation:
USD 1; aggregate after both new submissions: USD 3, inside the unchanged USD 25 cap.
No automatic retries, additional durations/resolutions, load tests or GPU rental.

| Variant | Endpoint | Current 768P price on endpoint page | One 5-second request | Listed non-promotional price |
|---|---|---:|---:|---:|
| H3 | `minimax/h3/text-to-video` | USD 0.06/s | USD 0.30 | USD 0.30/request |
| H3 Max | `minimax/h3-max/text-to-video` | USD 0.04/s | USD 0.20 | USD 0.40/request |
| H3 Max Turbo | `minimax/h3-max-turbo/text-to-video` | USD 0.02/s | USD 0.10 | USD 0.20/request |

Total tariff calculation: USD 0.60 across the three requests, of which USD 0.30
is for the two newly authorized requests. This is not a reconciled invoice.
The current Max/Turbo endpoint pages state a 50% launch promotion ending September
30. The broader [marketing page](https://fal.ai/minimax-h3-max) lists higher rates
and an older promotion end date; record that discrepancy rather than silently
mixing prices. Prefer the exact endpoint and authenticated pricing/billing evidence:
[Max](https://fal.ai/models/minimax/h3-max/text-to-video),
[Turbo](https://fal.ai/models/minimax/h3-max-turbo/text-to-video).

## What to compare

Measure end-to-end wait and quality/output properties on each result. Separately
record queue `metrics.inference_time` and output `timings.inference`: the former
is provider runner time; the latter is documented as GPU DiT denoising time on
Max/Turbo. They are not interchangeable or independent hardware measurements.
The published 2.46 s Max / 1.54 s Turbo figures for 5-second 768P clips are fal's
denoising measurements from September 8, not our end-to-end predictions.

Interpret commercial alternatives separately from the original matched base-model
self-host experiment. A faster/cheaper Max Turbo result changes the competitive
reference, not the measured base H3 result or the chosen B300 hardware. It does not
authorize silently replacing the open checkpoint with different weights.

```bash
python3 scripts/fal_reference.py prepare --variant turbo
python3 scripts/fal_reference.py submit --variant turbo --env-file /absolute/path/to/.env.local
python3 scripts/fal_reference.py prepare --variant max
python3 scripts/fal_reference.py submit --variant max --env-file /absolute/path/to/.env.local
```

For interrupted collection, use `collect --variant turbo` or `collect --variant max`
with the same credentials. Never delete completed markers or reserve a new attempt
to retry implicitly. Published clips remain the original, unmodified MP4 outputs.
