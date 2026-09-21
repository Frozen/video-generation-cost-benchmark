# Vast.ai: bounded LTX-2.5 replication

Status: **completed and closed. Attempt 008 exported all six real native outputs, including both measured 5-second and 20-second baseline/resident pairs. All eight paid leases and temporary SSH keys are deleted.** The matched Vast 5-second resident request cost USD 0.007488 per requested video-second of GPU processing versus USD 0.005525 on the previous Runpod lease: no price improvement. Price is now the selection criterion; this historical protocol's latency target is retained as a recorded measurement, not the current decision gate. See [the results and closeout](VAST_LTX_RESULTS.md).

## Objective and authorized scope

Compare ordinary warm versus resident-transformer LTX-2.5 on one verified H100 SXM 80 GB, for both 5-second and 20-second outputs. Preserve the prompt, model, BF16 precision, native source, pinned image, seed and sampling schedules. No alternative GPU, quantization, compilation, model substitution or shortened replacement for a failed 20-second request is included.

The operator initially approved an additional USD 8 Vast-stage allowance, then explicitly instructed execution without further financial confirmation below USD 10. The implemented limit is now **USD 9.99 cumulative across every Vast attempt**, not a fresh allowance for each lease. The original USD 10 funded-account snapshot remains the accounting baseline. This is separate from the historical Runpod experiment ledger; that historical ledger is not reset.

Completed run: `P01_EN_VAST_H100_LTX25_REUSE_5S20S_008`, deleted instance `51824206`.
Each earlier attempt retains its own private journal and public closeout artifacts. Each run identity permits only one paid create; an ambiguous create is discovered by its unique ownership label, never blindly resubmitted. There are no automatic generation retries.

At 2026-09-21 00:04:35 UTC, whole-stage credit drawdown was **USD 5.585449700**, unchanged from the previous snapshot and below USD 9.99; account inventory showed zero instances and zero SSH keys. The [dated reconciliation](results/VAST_LTX_STAGE_RECONCILIATION_2026-09-21.json) includes late charges from earlier failed attempts without rewriting their historical records. Final invoice reconciliation remains pending.

The operator ended Vast testing and requested publication before moving to another service. No further Vast run is scheduled. A next provider has not been selected or provisioned by this closeout. Future comparisons must distinguish the measured GPU-processing unit price from whole-experiment spending and from an unmeasured all-in service price.

| Order | Case | Mode | Requested seconds | Frames at 24 fps | Schedule |
| --- | --- | --- | ---: | ---: | --- |
| 1 | BASE_WARMUP | Baseline | 5 | 121 | Technical warmup, 2 + 2 |
| 2 | BASE_WARM_5S | Baseline | 5 | 121 | Full measurement, 8 + 3 |
| 3 | BASE_WARM_20S | Baseline | 20 | 481 | Full measurement, 8 + 3 |
| 4 | REUSE_WARMUP | Resident transformer | 5 | 121 | Technical warmup, 2 + 2 |
| 5 | REUSE_WARM_5S | Resident transformer | 5 | 121 | Full measurement, 8 + 3 |
| 6 | REUSE_WARM_20S | Resident transformer | 20 | 481 | Full measurement, 8 + 3 |

Six real outputs are required: two exported technical warmups and four measured outputs. The initial `_5S_001` attempt had the older four-case protocol; it submitted zero generations. All subsequent attempts use the six-case matrix above.

The native `8k + 1` grid yields 5.041667 and 20.041667 seconds of encoded video. Cost normalization uses the requested 5 or 20 seconds. Both 20-second cases are first requests of that shape in their respective modes; there is no separate 20-second warmup. Native automatic VAE tiling follows the requested geometry. At this canvas, stage two has 16,128 video tokens for 121 frames and 61,488 for 481 frames. **Both 20-second cases completed without OOM on attempt 008; resident peak reserved memory was 76.375 GiB.** This proves fit for the exact tested request, not a general capacity guarantee. OOM or timeout is a protective stop; missing cases cannot be replaced by shorter clips.

## Frozen workload and reproducibility

Follow [LTX_REUSE_TRIAL.md](LTX_REUSE_TRIAL.md) for the baseline/resident distinction.

- Model: `Lightricks/LTX-2.5`, revision `5e6e71018ee1756ed329b697a7b4aedc934dfce9`; six BF16 objects and SHA-256 hashes in `scripts/ltx_config.py`, totaling 71,118,761,094 bytes.
- Native source: `a95ab856bf29407b6b066ede0abe1846050db56c`.
- Image: `runpod/pytorch@sha256:4d1721e62b56d345c83b4fd6090664be6daf9312caab5b2e76f23d8231941851`, linux/amd64.
- Private source archive: 1,310,511 bytes; SHA-256 `620536364cdb1f768a620a621cb12695fb4a1e2db458c857679ff609c7fa951e`.
- P01_EN verbatim prompt SHA-256: `9c924c21f39702c03de5287bb3307e1b6df82303b9e6d352704e7fa7a91a96a7`. Original source-prompt hash: `493ef9be797d7fbf6407589f08a76830078ba2dfd0d8eaf990d2209852f0de6a`. Full text remains private under the existing source-reuse policy.
- Seed 42; BF16; 1344 × 768; 24 fps; native audio; batch and request concurrency one. Preserve original encodings without trimming or re-encoding.
- Measured stage-one sigmas: `[1, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0]`; stage two: `[0.909375, 0.725, 0.421875, 0]`.
- Technical warmup stage one: `[1, 0.725, 0]`; stage two: `[0.909375, 0.421875, 0]`.
- Native `chunked_eager` decoder. No CPU offload, quantization, compiler, approximate cache, prompt enhancement, embedding cache or completed-output cache.
- CPython 3.12; uv 0.12.17; torch 2.13.0+cu132; NATTEN 0.21.7+torch2130cu132; transformers 5.14.1; upstream cuDNN 9.24.0.43 override.
- Generated lock SHA-256: `9525795117e21350aef8773c1be07a79f10b00fad04572ce549d290206a6d3ff`. NATTEN's 203,625,872-byte wheel is separately hash-enforced with SHA-256 `99c504a0f190f8415ae04e4b55a4d145a54db3948718d07da4f0c1914a1e7396`. The PyTorch index omits wheel digests: its version and exact URL are locked, but the entire environment is not artifact-hash-locked.

The historical private Runpod archive and generated lock were not recovered. This is **same-model/settings replication, not a proven bit-identical software environment**. The new capsule is frozen across the Vast attempts. Differences from historical Runpod outputs cannot automatically be attributed solely to the rental provider.

## Host admission and driver compatibility

Require a verified, on-demand, non-interruptible amd64 Docker offer: exactly one H100 SXM, at least 80,000 MiB advertised GPU memory, 64,000 MB host RAM, 200 GB temporary disk, reliability at least 0.99, and available direct SSH. No MIG or GPU-model substitute. Marketplace verification and reliability are not an SLA or protection from a host operator reading memory/storage.

Earlier attempts required an advertised CUDA maximum of at least 13.2. Attempts 006–008 retain the exact frozen CUDA 13.2 dependencies but admit driver 580 or newer with advertised CUDA 13.0 or newer under [NVIDIA CUDA 13.x minor-version compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html). PTX JIT and newer driver-dependent features can still fail. **Documentation alone does not establish that this exact native pipeline works on driver 580; successful real GPU execution is required.** No dependency downgrade or compatibility-package substitution is permitted.

Attempt 008 executed real BF16 matrix multiplication, scaled-dot-product attention and NATTEN 3D attention successfully in the exact torch 2.13.0+cu132 / NATTEN 0.21.7+torch2130cu132 environment on driver 580.126.20. Subsequent native preparation and all six audiovisual outputs completed, including both 20-second cases. The native results, rather than the kernel probes alone, establish this workload's compatibility and memory fit.

The pinned container base is CUDA 12.8.1, while the frozen native virtual environment is CUDA 13.2. Inspect the virtual environment, not the image's system torch, when testing compatibility.

The eighth admission initially selected offer `36346709`, machine `57753`; the create-time refresh selected `36346695` on the same machine at the same listed rates. Machine `108977`, which failed both proxy and direct SSH in 006/007, was excluded:

| Quoted field | Value |
| --- | ---: |
| GPU memory | 81,559 MiB |
| Host RAM | 226,775 MB |
| Driver | 580.126.20 |
| Compute plus 200 GB disk | USD 5.008888889/hour |
| Inbound and outbound, each | USD 0.000001302083333/GB |
| Prior conservative exposure hold | USD 5.57 |
| Full 45-minute, 100 GB inbound, 5 GB outbound cumulative admission estimate | USD 9.326803385 |

These are quotes/admission estimates, not dedicated host-resource guarantees or final charges. Actual H100 identity and driver were separately observed during the completed native run. Offers are refreshed immediately before the sole create and selected by total compute/disk/transfer exposure, not advertised hourly GPU price alone. Attempts 006–008 permit at most USD 5.10/hour including disk; all transfer limits and the cumulative USD 9.99 admission bound still apply.

## Deadlines, spending and credentials

- Start the absolute 45-minute lifetime at the create request, not model readiness. Abort preparation at minute 30, prohibit new generation after minute 35, bound each generation to five minutes, and start deadline closeout before the absolute lease limit.
- The independent spending stop is **USD 8.39 cumulative**, leaving USD 1.60 for closeout and billing lag. It may stop a run before the full 45-minute quote horizon. Earlier USD 8 attempts used USD 6.40; their immutable artifacts retain that boundary.
- Preserve all failed-rental exposure holds. The USD 5.57 eighth-run hold is not an invoice and is not added to actual charges as another debit. Each incremental hold covers its attempt's charges known at admission; later provider adjustments are recorded in the dated whole-stage reconciliation, not silently discarded or used to rewrite old admission snapshots.
- Admission requires `can_pay=true` and sufficient prepaid `credit` for the **remaining** approved allowance after observed stage spending, rather than requiring a fresh USD 8 after every failed attempt. The original funded-account baseline never moves.
- Vast `total_spend` contains signed negative cumulative usage debits. Observed spend is the larger of prepaid-credit drawdown and growth in debit magnitude. A USD 1e-12 numerical tolerance handles provider floating-point roundoff; real deposits, counter resets, unrelated resources and missing observations remain protective failures.
- Bound admitted traffic at 100 GB inbound and 5 GB outbound. The pinned image has 10,564,340,940 compressed layer bytes; selected dependencies/bootstrap wheels total 2,549,585,473 bytes. Weights, source and 2 GB overhead bring planned ingress to 86,233,998,018 bytes. Host image-pull retries cannot be measured from container namespace counters.
- Launch the independent local guard before allocation; keep the local machine awake. Verify the remote bootstrap identity/deadline and full instance-scoped guard readiness **before publishing its connection to the local guard**, uploading model links or starting inference.
- The instance-scoped manage-permission probe updates the existing label to itself; it does not request a runtime-state transition. Account-wide Vast/Hugging Face credentials remain local. Only the provider-injected scoped credential and expiring file-scoped model URLs may reach the host. The parent `.env.local` is never uploaded.
- Direct SSH uses the official combined `ssh_direc ssh_proxy` runtime. The sixth lease's proxy failed to establish its reverse port; its accepted same-instance template update is recorded separately and was not another paid create.
- Attempt 008 exposed invalid ownership/modes on the provider-installed `authorized_keys`. The startup command now normalizes root ownership and modes 0700/0600, without disabling `StrictModes`. On the existing lease, an accepted template update followed by container recycle applied the repair; the original image, deadline and single-create count were preserved. SSH and scoped-guard readiness were verified before native preparation; subsequent metadata checks confirmed root ownership, modes 0700/0600 and effective `strictmodes yes`.
- Read-only SSH observations may retry transport exit 255 at most three times with an eight-second retry budget. GET HTTP429 uses 1.5-second pauses; GET transport errors use 0.5-second pauses, at most three attempts, an eight-second retry budget and three-second per-attempt socket timeout. Malformed JSON fails immediately. Failure diagnostics retain exception types, not raw transport messages. The original 15-second freshness fence remains. Mutation requests, generation submissions and SCP are not automatically replayed.
- These are operational bounds, **not a provider-enforced hard spending cap**. Provider or control-plane failures can delay deletion. Report all actual charges and any overrun.

## Execution and evidence

Controller: `scripts/vast_trial.py`. Independent local and remote guards: `scripts/vast_deadline.py`. Closed-lease exporter: `scripts/export_vast_ltx.py`.

`arm` performs private-input, funding, source, dependency and quote admission without provisioning. `guard` and `execute` run as separate supervised processes; `guard-ready` must be observed before execution. Already-claimed identities cannot be armed or executed again. Use `recover` or `close` for interruption; never repeat a create or generation to hide a failed attempt.

Read-only closed-run status command:

```bash
python3 scripts/vast_trial.py status --attempt alternate --env-file ../.env.local
```

Export command used after independently verified deletion:

```bash
python3 scripts/export_vast_ltx.py \
  --lease private/vast-h100-p01-008 --output results
```

The exporter requires controller and independent-guard evidence of owned-instance absence. It uses the earliest verified absence to bound resource lifetime while retaining later controller bookkeeping timestamps separately; these are not provider-certified billed seconds. Unknown bills, network charges or billable-byte counts remain unknown, never zero.

For completed cases, export original MP4s and per-case JSON immediately. Verify video/audio streams, expected frames, canvas and duration; fully decode both streams; hash encoded files and decoded video/audio separately. Keep processing time distinct from client submission-to-local-download time. Report transformer construction, native stages, encoding, peak VRAM, preparation, downloads, warmups, idle time and full rental cost. Missing 20-second cases cannot be replaced by short clips or omitted from success criteria.

Historical latency target for this executed protocol: at most 15 seconds from client submission to the fully downloaded MP4 for each measured request. At closeout, the operator made **price the sole current selection criterion**; the old latency result is preserved, not applied as the next-provider gate. Compute-only cost per requested video-second is distinct from the whole-stage bill including disk, transfer, warmups and all failures. Do not double-count pipeline subtotals on top of rental charges. Credit purchases, usage debits and invoice estimates are separate observations.

Compare within-Vast baseline/resident results and the historical [Runpod reuse records](LTX_REUSE_RESULTS.md). Those historical five-second request-to-download times are 55.432 seconds baseline and 34.987 seconds resident, at USD 3.49/GPU-hour. Fixed ordering, one sample per measured case, differing host resources and the environment limitation prevent provider-wide rankings, p95 or SLA claims. Hash equality/difference is diagnostic, not a human quality verdict; motion/audio/prompt-adherence acceptance remains pending review.

Delete the owned instance rather than stopping it; independently verify absence and remove only its temporary account SSH key. Export must not delay deadline deletion. No persistent volume, retained GPU, automatic top-up, H3/multi-GPU run, other model or unrelated workload is included.

## Verification record

- `python3 -m unittest discover -s tests -q`: **210 tests passed after the final source change**, including SSH startup permission normalization.
- The cumulative-funding regression reproduced a false refusal at USD 7.80 credit after USD 2.20 observed spending, then passed without moving the original USD 10 baseline.
- Signed-debit parsing, numerical roundoff, transient read-only SSH/HTTP429 handling and late-closeout timestamp regressions were reproduced before their respective fixes.
- A real FFmpeg export smoke exercised synthetic 5-second and 20-second audiovisual fixtures across the six-case matrix. All streams decoded and original hashes were retained; temporary fixtures were removed. **This was not GPU inference and supplied no benchmark measurements.**
- Attempts 001–007 have failed zero-output public JSON/CSV closeouts. Attempt 008 completed all six native outputs; the real exporter fully decoded both streams and retained original hashes. Four measured preview grids were visually inspected; audio was not listened to. See [the execution report](VAST_LTX_RESULTS.md) and [six-case CSV](results/VAST_LTX_REUSE_ALTERNATE_MEASUREMENTS.csv).

Sources: [Vast offer API](https://docs.vast.ai/api-reference/search/search-offers), [Vast billing](https://docs.vast.ai/guides/reference/billing), [Vast SSH](https://docs.vast.ai/guides/instances/connect/ssh.md), [Vast rate limits](https://docs.vast.ai/api-reference/rate-limits-and-errors), [NVIDIA minor-version compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html), and [the sanitized original preflight](results/VAST_PREFLIGHT_2026-09-20.json).
