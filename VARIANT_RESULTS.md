# Measured fal comparison: H3, H3 Max and H3 Max Turbo

The later [self-host result and video](SELF_HOST_RESULTS.md) use four H100 GPUs
and the operator-modified P01_EN prompt. The three identical fal requests below
remain their own comparison; do not silently add the modified prompt to that set.

September 17, 2026. **Three completed requests, one per variant. No self-host run.**
All three used identical payload bytes: the same unchanged source prompt, requested
5 seconds, 768P, 16:9, seed 42, disabled expansion, enabled safety checker and no
reference media. Execution was sequential: H3, then Turbo, then Max. This is not
a repeated, randomized performance benchmark or a quality-equivalence claim.

| Variant and original video | Measured wait through download | 15 s latency gate | Current generation-cost calculation | Listed non-promotional cost |
|---|---:|---|---:|---:|
| [H3](results/P01_FAL_5S_001.mp4) | **102.644 s** | Fail | USD 0.30 | USD 0.30 |
| [H3 Max](results/P01_FAL_MAX_5S_001.mp4) | **13.552 s** | Pass | USD 0.20 | USD 0.40 |
| [H3 Max Turbo](results/P01_FAL_TURBO_5S_001.mp4) | **9.122 s** | Pass | USD 0.10 | USD 0.20 |

Current costs are endpoint tariffs corroborated by returned billable units and
authenticated base-unit prices, not independently reconciled net invoice amounts.
Total generation calculation: **USD 0.60**. Max and Turbo endpoint pages currently
list 50% launch discounts ending September 30; the broader marketing page disagrees.
Keep both promotional and non-promotional scenarios. See [the execution record](VARIANT_COMPARISON.md).

## Main conclusion

**Turbo was the fastest and cheapest tested API alternative in these three samples.**
Both accelerated variants met our client-side 15-second latency target. The earlier
102.644-second result belongs to standard H3, not fal's optimized Max variants.
An open-model deployment merely beating USD 0.30 is therefore not enough to claim
competitiveness: test against Turbo's USD 0.10 promotional and USD 0.20 listed
non-promotional prices as well, while preserving acceptable quality and latency.

This does **not** yet establish equal quality or profitability. The candidate
one-B300 deployment is unmeasured; no claim that it is cheaper/faster is justified.
H3 Max/Max Turbo are fal's post-trained variants, not verified identical open-base
checkpoints. Comparing service alternatives and reproducing the same model are
different questions; do not silently switch the self-host model or GPU plan.

## Published versus returned processing times

| Variant | fal's published 5 s / 768P denoising time | Denoising returned by this response | Queue-reported runner time | Our end-to-end wait |
|---|---:|---:|---:|---:|
| H3 | No matched claim selected | Not exposed | 96.128 s | 102.644 s |
| H3 Max | 2.46 s | **2.495 s** | 3.110 s | 13.552 s |
| H3 Max Turbo | 1.54 s | **1.497 s** | 2.085 s | 9.122 s |

The [published measurements](https://fal.ai/minimax-h3-max) are dated September 8.
Returned `timings.inference` is documented as DiT denoising time; queue
`metrics.inference_time` is provider runner time. Both are provider-reported,
not independent GPU instrumentation. They must not replace customer wait time.
The returned denoising figures are close to the published figures for this profile;
one sample is not a statistical reproduction of the full benchmark table.

Our client was unchanged: 2-second poll sleeps, normal HTTPS calls and final media
download. Turbo completion was first observed at 2.843 s; Max at 5.114 s. Result
retrieval and download followed, so these stages materially affect user-visible
wait. No per-stage network instrument was used; do not attribute all residual time
to GPU work or claim a precise download-only duration. Cold/warm state is unknown.

## Output and review

All files contain 1344x768 H.264, 124 frames at 24 fps (5.166667 s video), with AAC
32 kHz stereo audio and 5.184 s container duration. All fully decode without errors.
The native dimensions are 7:4, not exact 16:9; no crop/trim or re-encoding was applied.
The common native output bucket is observed, not proof of matching internal weights.

Frame inspection shows the requested kitchen/onion transformation premise on all
three. The accelerated outputs need full temporal and audio review, including the
requested ending; identical quality and full prompt adherence are **not** established.
Blind human review and `prompt_match` remain pending. Passing latency alone does
not qualify an output as accepted under the complete methodology. No VBench ran.

## Evidence and spending

- [Measurement CSV](results/MEASUREMENTS.csv) includes all three rows.
- Individual JSON records: [H3](results/P01_FAL_5S_001.json), [Max](results/P01_FAL_MAX_5S_001.json), [Turbo](results/P01_FAL_TURBO_5S_001.json).
- All original MP4 files are public with operator approval; hashes match private artifacts.
- Identical payload SHA-256: `7ae3a094032d307f0d419ca4e86120788ca36f6126416c75fde01834cb0de845`.
- Billable calculations: H3 `6 x 0.05 = 0.30`; Max `8 x 0.025 = 0.20`; Turbo `8 x 0.0125 = 0.10` USD.
- All billing-event checks returned HTTP 403. Actual net charges remain unverified;
  three USD 1 reservations stay outstanding, not USD 3 of claimed actual spending.
- No retries, additional resolutions/durations, load tests or Runpod resources were launched.

The [economics model](ECONOMICS.md) now includes the tighter Turbo price benchmarks.
The USD 25 total experiment cap and selected one-B300 self-host candidate remain.
