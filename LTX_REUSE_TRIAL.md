# LTX-2.5: warm baseline versus resident-transformer experiment

Approved September 18, 2026 after the first cold LTX result. This is a separate
experiment, not a retrospective change to previous numbers. H3 is accepted as
already warmed; do not rerun H3. Its logs confirm successful built-in synthetic
warmup (46.28 s for eight steps; 6.35 s for four steps), not a full output warmup.
The operator requested approximately comparable conditions: use a short technical
warmup for LTX too, not an extra complete generation before the measured request.

Use the same pinned LTX source, six BF16 weight files, H100 SXM, image, P01_EN,
seed 42, 1344 x 768, 121 frames at 24 fps, native audio and 8 + 3 schedule.
One lease at a quoted USD 3.49/hour, 200 GB temporary disk, one-hour guards and
USD 4 maximum reservation. Prepare and test the lifecycle patch before renting.
No compiler, FP8, decoder-mode, prompt, seed or quality-setting changes.

## Fixed request order

1. Ordinary pipeline: one short-schedule technical warmup, exported and billed.
2. Ordinary pipeline: one measured five-second request in the same process.
3. Resident-transformer pipeline: one short-schedule technical warmup, exported and billed.
4. Resident-transformer pipeline: one measured five-second request in that process.

Four outputs in total; only two are comparison samples. The second mode runs
later and shares filesystem/kernel caches, so this is not randomized or a p95
benchmark. Both modes have their own identical technical warmup: the target
five-second canvas, with two denoising intervals per native stage. Stage-1 sigmas
are `[1.0, 0.725, 0.0]`; stage-2 sigmas are `[0.909375, 0.421875, 0.0]`. Warmup
artifacts are diagnostics, not accepted-quality comparison videos. Measured
requests retain the full official eight-plus-three schedule. H3 has one denoiser;
LTX has two stages, so the warmup implementations are not literally identical.
H3 uses four H100s and 124 frames; LTX one H100 and 121 frames. Report these
native differences explicitly and price the actual GPU count. Record every request; no
automatic inference retries and no hidden warmups. Preserve failures.

Only the transformer lifecycle changes: keep its actual GPU weights between
the two stages and the following request, rather than disposing/rebuilding them.
Do not cache embeddings, latents or completed videos. Count real transformer
builds; expected ordinary measured count is two, resident measured count zero.
The normal text encoder and decoders still execute for each request.

The patch rejects streaming, quantized and compiled stages, forbids concurrent
use, and restores/disposes the resident component explicitly on exit. VRAM fit
with a resident transformer during text encoding/decoding remains to be tested.
An OOM is a failed configuration, not permission to silently change precision.

Measure pipeline-to-encoded-file and client-request-to-downloaded-file times,
GPU memory, per-stage and build times, checksums, full decoding and output
differences. Normalize processing GPU cost by five requested seconds. Report
warmup, preparation, idle time, disk and the whole rental separately. A faster
denoising loop alone is not a passed 15-second end-to-end target.

## Spending admission

Provider usage for the completed H3 adapter retry is now USD 3.500005583046004,
consistent with its USD 3.503734 full-window estimate. After independently
rechecking absence, that USD 6 hold was settled at USD 3.51 (rounded upward).
The deleted cold LTX rental has a USD 0.782058 window estimate but no provider
charge yet; its USD 4 hold was revised to USD 2, over 2.5 times the estimate,
without treating the estimate as a settled bill. Current settled-plus-reserved
exposure is USD 16.92 before the new USD 4 reservation, within the unchanged
USD 25 cap and its USD 2.50 closeout reserve. Holds are not actual charges.

Export all four originals, compare decoded outputs, save the English report,
then delete this owned Pod and independently verify absence. No persistent
storage, new GPU family, H3 rerun or additional optimization is authorized by
this experiment.
