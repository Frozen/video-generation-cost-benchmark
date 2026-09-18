# H3 acceleration trial: failed before producing a video

Historical attempt 001. **The subsequent patched attempt 002 produced both
videos:** [successful retry and measurements](ACCELERATION_RETRY_RESULTS.md).

September 18, 2026. **No new video was produced. The Pod was deleted and an
independent GET returned 404; the account's Pod list was empty.**
[Machine-readable measurements](results/P01_RUNPOD_H100X4ACCEL_5S_001.json).
The original [approved plan](ACCELERATION_TRIAL.md) remains the experiment contract.

| Configuration | User requests | Outcome |
|---|---:|---|
| Larry Turbo v4, eight evaluations, four H100 SXM GPUs | 1 | Failed in the first denoising-stage invocation; no output |
| LightX2V four-step v0.1, same planned hardware | 0 | Not started after the first failure |

Both were planned as sequential five-second, 768p, P01_EN, seed-42 requests.
There were no automatic generation retries or replacement rentals. The failed
deployment used benchmark commit `15a64fab545804051580b8cebc77dd25cae34695`, with
the same pinned SGLang source and base checkpoint as the successful base run.
It did not contain the compatibility workaround added after this failure.

## Failure and diagnosis

The Larry adapter downloaded successfully, passed its pinned size/SHA-256 check,
and was applied to 259 of 266 LoRA-wrapped layers. Loading weights was not enough
to establish a working inference path. The exact exception was:

```text
AttributeError: 'RowParallelLinearWithLoRA' object has no attribute 'quant_method'
```

The traceback reaches `_accepts_mxfp8_input(self.fc2)` in the token refiner's MLP
in the pinned SGLang `minimax_h3.py`. Its capability check directly accesses
`linear.quant_method`; the LoRA wrapper exposes the base layer separately and
does not expose that attribute. This occurred before a denoising iteration
completed. It is not evidence that the GPUs lack VRAM or that eight-step H3 is
slow. The four-step variant remains untested, not failed.

The same error occurred during the single synthetic warmup. SGLang logged
`Synthetic server warmup failed; continuing startup`, then returned HTTP 200
from `/health`. Our original readiness check therefore admitted the user
request, which failed for the same reason. **HTTP health was not proof of a
successful warmup.** The runner now requires successful warmup evidence before
submitting an adapter request. A failure or missing evidence is rejected.

## Cost and time, including the unsuccessful preparation

| Measurement | Observation |
|---|---:|
| All four GPUs, quoted aggregate hourly rate | USD 13.96/hour |
| Allocation through verified deletion | 781.129 s / 13 min 1.129 s |
| Allocation through user submission | 759.711 s |
| Model snapshot download, rounded log timestamps | 94 s |
| Failed synthetic warmup, log-reported elapsed time | 13.70 s |
| Whole-window GPU estimate | USD 3.029043 |
| 300 GB temporary-disk estimate | USD 0.009041 |
| **Total failed-rental estimate** | **USD 3.04** |
| Successful videos / generated seconds | **0 / 0** |
| Cost per successful video-second | **Undefined** |

The estimate uses the provider's `startedAt` and our verified-deletion timestamp;
it is not an invoice or confirmation of the exact billable interval. A scoped
billing query returned zero records; that is not a free rental. The USD 6 hold
remains reserved, not settled. Dividing the failed expense by the five requested
seconds gives USD 0.607617 of failed-attempt spending per requested second, **not
a production video-generation unit cost**. There is no valid request-to-video
latency, throughput, quality score or eight-vs-four speed comparison from this run.

| Event | UTC |
|---|---|
| Provider allocation | 03:11:47.214 |
| GPU telemetry starts after SSH/environment checks | 03:19:47.809 |
| Service wrapper starts | 03:19:56.844 |
| Base snapshot download begins | 03:21:25 |
| Base snapshot download finishes | 03:22:59 |
| Adapter applied; pipeline instantiated | 03:24:07 |
| Warmup fails; startup continues | 03:24:22 |
| User request submitted | 03:24:26.925 |
| User request failure logged | 03:24:28 |
| Pod deletion and absence verified | 03:24:48.343 |

The snapshot was downloaded on the paid Pod because the previous Pod's ephemeral
cache was deleted. The larger preparation interval also contains image download/
extraction, runtime initialization, distribution setup, loading and warmup; it
must not all be labeled model-download time. Preloading would not have fixed the
LoRA exception. Persistent storage was not bought or retained in this trial.

## GPU telemetry

One-second `nvidia-smi` sampling captured 288 complete rows per GPU from
03:19:47.809 through 03:24:35.074 UTC. An incomplete final row from copying the
live file was excluded. Sampling does not cover the earlier image startup.

| GPU | Maximum sampled used MiB | Mean sampled GPU utilization | Maximum sampled power |
|---|---:|---:|---:|
| 0 | 63,049 | 1.93% | 203.11 W |
| 1 | 63,113 | 1.70% | 197.37 W |
| 2 | 62,857 | 1.69% | 197.77 W |
| 3 | 61,967 | 1.66% | 204.49 W |

These describe setup and an unsuccessful request, not useful serving throughput
or business utilization. Sampled maxima are not continuous peaks. Rental prices
already include electricity; do not add sampled power as a second rental charge.
Private logs, hardware checks and GPU samples were exported before deletion;
their hashes are in the public measurement record. Raw private logs are not published.

## Prepared fix, not yet a successful GPU rerun

[h3_lora_compat.py](scripts/h3_lora_compat.py) changes only the MXFP8 capability
probe to use a guarded attribute lookup. A wrapper without `quant_method` keeps
its ordinary forward path; the patch does not unwrap it, bypass the adapter,
change weights, reduce steps or change precision. Existing plain/quantized
layers retain their previous capability result.

The opt-in `--lora-compat-fix` service flag validates the original source's
SHA-256 before applying the mechanical patch and records both hashes. It accepts
the already-patched file on a second service start but refuses unknown source.
Original hash: `2a61d5c8b0418eed72fd3443cc47b6a06ed8512f6c834b608aa4e3e55e7489fa`.
Patched hash: `2a8a5c9b63d3ae8f0b4dfd66135c5988004dab4b304dc5601e9b467bf767a53c`.

The exact pinned function reproduced the AttributeError in a CPU-only regression
test; its patched version passed. This verifies the failing capability check,
**not the full GPU pipeline or absence of further errors**. A future run must
identify the patched runtime separately and prove a successful warmup and request.
The completed lease journal is immutable evidence, not a retry target.

Subsequent work: [CPU-only storage preparation](PRELOADED_MODELS.md) failed;
the operator authorized an ephemeral-cache retry, which [produced both videos](ACCELERATION_RETRY_RESULTS.md).

## Videos available to watch

There are **no eight-step or four-step videos from this attempt**. These links
are earlier successful outputs, not substitutes for missing acceleration results:

- [Our base H3 on four H100 GPUs](results/P01_EN_RUNPOD_H100X4_5S_001.mp4)
- [fal H3](results/P01_FAL_5S_001.mp4)
- [fal H3 Max](results/P01_FAL_MAX_5S_001.mp4)
- [fal H3 Max Turbo](results/P01_FAL_TURBO_5S_001.mp4)

## Validation after the failure

- `python3 -m unittest discover -s tests -q`: 101 tests passed, including failed-
  attempt accounting, the capability workaround, warmup rejection and S3 secrecy.
- `python3 scripts/h3_lora_compat.py --check-source private/upstream-minimax-h3.py`:
  original source hash verified; original failure reproduced; patched probe passed.
- `python3 scripts/validate.py`: historical planning contract valid; it still
  reports `paid_execution_ready: false`, not permission for a new GPU run.
- `git diff --check`: passed. No accelerated output exists to decode or review.
