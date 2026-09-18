# H3 acceleration trial: two adapters, one H100 rental

**Executed September 18: first adapter failed, second was not started; no videos
were produced. Pod deleted.** [Failure, costs, telemetry and prepared fix](ACCELERATION_RESULTS.md).
The scope below records the approved plan, not a completed two-video comparison.

**Retry completed:** [attempt 002 results](ACCELERATION_RETRY_RESULTS.md) contain
both videos, measured 21.873 s / 13.741 s end-to-end and approximately USD 3.50
for the whole rental. The four-step request passed the 15-second target;
quality review remains pending. The Pod was deleted after successful export.

**Authorized retry:** attempt 002 enables the source-pinned LoRA compatibility
workaround and the successful-warmup admission check. Keep the same AP-IN-1,
four-H100 hardware and request profile; exactly one Larry8 and one Light4 user
request, sequentially. Use new lease/output journals ending in `002`, a fresh
USD 6 reservation and the same 24-minute deadline. This is an explicit operator-
approved retry, not an automatic resubmission. Persistent-storage preparation
must not block this functionality check; the operator authorized the ordinary
ephemeral-cache path. With the USD 1.20 CPU/storage preparation holds, admission
exposure is USD 22.20 including the new USD 6 GPU hold, within the USD 25 cap.

Approved scope: exactly one P01_EN, 5-second, 768p, seed-42 request with each of
two public adapters. This is a change of model weights, not fal Max/Turbo and not
a claim of quality equivalence. No fal reruns, additional seeds or other models.

1. Larry Turbo v4, `minimax_h3_turbo_v4_step600_ema.safetensors`: eight denoiser
   evaluations (`num_inference_steps: 9`), strength 1.0.
2. LightX2V, `minimax_h3_fl2v_turbo_4step_v0.1.safetensors`: four evaluations
   (`num_inference_steps: 5`), strength 1.0, explicit training alpha 8.

Exact adapter revisions, sizes and SHA-256 values are pinned in
[h3_adapters.py](scripts/h3_adapters.py). The base checkpoint, image, source,
TP2 + Ulysses2 topology and requested output profile remain those of the
[four-H100 baseline](SELF_HOST_RESULTS.md). Verify adapter compatibility before
accepting results; a valid base-model run alone does not prove adapter support.

Run sequentially on the same four H100 SXM GPUs in AP-IN-1. Restart the service
between adapters; each gets its own built-in warmup, logged separately. GPU
warmup does not train the model. Disk caches may benefit the second service
startup, so do not compare these two startup times as unbiased cold-start tests.
One output each is a pilot, not a randomized statistical comparison.

The live Secure Cloud quote is USD 3.49/GPU/hour, USD 13.96/hour for all four.
The planned rental deadline is 24 minutes from before create; compute plus
300 GB temporary disk is approximately USD 5.60 at that deadline. Reserve
USD 6 including a teardown margin. Local and Pod-side guards are best-effort
backstops, not a provider-enforced hard dollar cap. Delete after successful
export. For attempt 002 the operator requested in-place debugging: a failed
runner retains this same Pod until its original deadline instead of immediately
destroying its cache. The deadline is not extended, and no replacement rental
or extra generation is automatically admitted. Do not retain it for future models.

Prior spend is not fully invoiced. The verified-deleted first H100 lease had a
USD 3.92 window estimate; its outstanding reservation is conservatively revised
from USD 16 to USD 6 after another authenticated GET returned 404. It remains
reserved, not settled, with actual charge null and the original hold retained
in the journal. Together with three USD 1 fal holds and the new USD 6 hold,
admitted exposure is USD 15, below the unchanged USD 25 experiment cap and
USD 22.50 new-compute admission threshold. Reconcile authoritative billing later.

Report full request-to-download latency, runtime stages, USD per requested
video-second, whole-rental spending and informal audio/video review separately.
Keep both adapters' artifacts and failures; never silently substitute a model,
retry a request or present a theoretical speedup as a measurement.
