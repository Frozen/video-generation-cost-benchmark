# Vast LTX-2.5: price results and stage closeout

**Vast testing is closed: this offer did not improve the measured unit price.** The newly published [LTX RTX PRO 6000 warmed queue](benchmarks/ltx-rtx-2026-09-20/README.md) provides the lowest current cost reference: **USD 0.003287 per requested video-second including GPU and temporary disk**. The earlier Runpod H100 result was USD 0.005525/s of GPU processing, versus USD 0.007488/s for the matched Vast 5-second request and USD 0.006113/s for Vast's 20-second request. These measurement boundaries differ, as detailed below. Price, not speed, is the operator's current selection criterion.

The whole Vast stage, including seven earlier failed rentals, drew down **USD 5.585449700** from the original USD 10 balance, below the **USD 9.99 cumulative allowance**. This is an observed usage snapshot, not a final invoice. Delayed provider billing is reconciled below rather than omitted from the successful run.

- [Six-case CSV](results/VAST_LTX_REUSE_ALTERNATE_MEASUREMENTS.csv)
- [Native run and closed-lease JSON](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_008.json)
- [Dated eight-attempt billing reconciliation](results/VAST_LTX_STAGE_RECONCILIATION_2026-09-21.json)
- [Protocol, exact pins and safeguards](VAST_TRIAL.md)
- [Historical Runpod comparison](LTX_REUSE_RESULTS.md)

## Price decision and next stage

| Resident transformer result | GPU allocation | Requested clip | Quoted GPU-processing USD / requested video-second |
| --- | --- | ---: | ---: |
| Previous Runpod | 1 × H100 | 5 s | **0.005525** |
| Current Vast | 1 × H100 | 5 s | 0.007488 |
| Current Vast | 1 × H100 | 20 s | 0.006113 |

For the matched 5-second request, this Vast offer was **35.5% more expensive** by the processing-only measure. The 20-second unit cost is also above the historical 5-second rate, but no previous 20-second result exists: it is not a controlled matched-duration comparison. Costs use the actual quoted GPU count/rate, include native processing, and exclude preparation, warmups, idle time, disk, transfer and failed rentals. Neither these numbers nor differently sized whole experiments establish an all-in production-service price.

### Lower-cost reference integrated at publication

The RTX PRO 6000 evidence package was published separately and discovered when this branch refreshed GitHub before publishing. It records ten consecutive 5-second LTX requests after two full warmups: 279.402316 seconds for 50 requested video-seconds, at USD 2.09/GPU-hour plus USD 0.02777778/disk-hour. Its **GPU-plus-disk warmed-queue estimate is USD 0.003287289 per requested video-second**. The older H100 result must not be presented as the cheapest result across the updated repository.

Adding the quoted disk rate to Vast's resident processing intervals gives USD 0.007572412/s at 5 seconds and USD 0.006182023/s at 20 seconds. This makes the included cost components explicit, but it does not turn the experiments into a controlled pair: RTX used ten seeds and two full warmups on different hardware, whereas Vast used single measured requests and short technical warmups. The RTX interval includes the measured queue; the Vast values cover native processing only. Both exclude amortized setup, operational overhead and quality-driven retries. Exact full-service cost and quality parity remain unestablished. The original RTX evidence and measurements are retained without modification.

### Within-Vast behavior and closure

All six requested native outputs completed. Within this one-GPU Vast lease, residency reduced request-to-download time by 38.0% at 5 seconds and 17.8% at 20 seconds. Those improvements are against the ordinary pipeline on the same lease, not against the previous best run. The historical 15-second target was missed, but it is **not the current selection gate**. Likewise, H3 on four H100 GPUs versus LTX on one is a comparison of different configurations, not a hardware-controlled model/provider experiment.

The operator chose to publish and close this stage, then move to another service. **No further Vast test is scheduled.** The next provider is not selected or provisioned by this publication; the next price comparison must retain explicit request duration, GPU allocation and cost boundaries. The six originals, all failed-attempt costs and frozen request evidence remain available. Controller and independent guard verified deletion and exited successfully; no GPU, persistent volume or temporary SSH key is retained.

## Measured results and original videos

Run `P01_EN_VAST_H100_LTX25_REUSE_5S20S_008`; instance `51824206`, now deleted. Both modes used the same private P01_EN prompt, seed 42, pinned LTX-2.5 BF16 weights/source/dependencies, 1344 × 768 canvas, 24 fps, native audio and full **8 + 3** schedule. No quantization, CPU offload, compilation, prompt/embedding/output cache or approximate cache was enabled.

| Original MP4 | Processing, s | Request → downloaded MP4, s | Quoted compute-only USD / requested video-second | Peak allocated / reserved, GiB | Transformer builds |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Baseline 5 s](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_008_BASE_WARM_5S.mp4) | 46.407 | 51.301 | 0.012770 | 39.210 / 43.342 | 2 |
| [Resident 5 s](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_008_REUSE_WARM_5S.mp4) | 27.212 | 31.807 | 0.007488 | 58.555 / 60.656 | 0 |
| [Baseline 20 s](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_008_BASE_WARM_20S.mp4) | 106.853 | 120.332 | 0.007351 | 49.860 / 58.688 | 2 |
| [Resident 20 s](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_008_REUSE_WARM_20S.mp4) | 88.863 | 98.859 | 0.006113 | 64.712 / 76.375 | 0 |

Processing speedup was 1.705× for 5 seconds and 1.202× for 20 seconds; client-observed speedup was 1.613× and 1.217× respectively. The resident transformer was built once during its technical warmup and not rebuilt for either measured request. Baseline rebuilt it twice per request.

Compute-only normalization is `processing_seconds × quoted_GPU_USD_per_hour / 3600 / requested_video_seconds`, using **USD 4.953333333/GPU-hour**. It excludes preparation, warmups, idle time, disk, transfers and failed rentals; it is not an all-in cost or a separately billed charge. The native frame grid produces 121 or 481 frames, encoded as 5.041667 or 20.041667 seconds; denominators remain the requested 5 or 20 seconds.

Both 20-second requests completed without OOM on this H100. The resident case reached **76.375 GiB reserved**. This establishes fit only for this exact request/environment, not general 20-second capacity. Each 20-second case was its mode's first request of that shape; there was no separate 20-second warmup.

### Technical warmups

| Original MP4 | Schedule | Processing, s | Request → downloaded MP4, s | Peak allocated / reserved, GiB | Transformer builds |
| --- | --- | ---: | ---: | ---: | ---: |
| [Baseline warmup](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_008_BASE_WARMUP.mp4) | 2 + 2, 121 frames | 51.080 | 56.819 | 39.210 / 43.342 | 2 |
| [Resident warmup](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_008_REUSE_WARMUP.mp4) | 2 + 2, 121 frames | 34.794 | 42.438 | 52.104 / 60.348 | 1 |

Execution order was baseline warmup, baseline 5 s, baseline 20 s, resident warmup, resident 5 s, resident 20 s. Warmups are exported technical outputs, not full-schedule performance samples or free work.

### Native stage measurements

All times below are seconds. Denoising stage timings **include weight loading**; transformer construction is a subset, not another duration to add. Lazy video decoding and encoding are measured together. Per-case JSON next to each MP4 retains full precision and resolved tiling.

| Case | Prompt encoder | Stage 1 | Upsampler | Stage 2 | Audio decoder | Lazy video decode + encode | Transformer construction subtotal |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline 5 s | 9.217 | 12.201 | 0.837 | 13.852 | 0.516 | 8.766 | 18.281 |
| Resident 5 s | 9.123 | 2.626 | 0.848 | 4.296 | 0.585 | 8.739 | 0 |
| Baseline 20 s | 9.149 | 21.544 | 0.939 | 37.671 | 0.776 | 35.730 | 18.944 |
| Resident 20 s | 9.025 | 11.031 | 0.898 | 27.891 | 0.792 | 38.227 | 0 |

Keeping the transformer resident removes repeated construction, not prompt encoding or video decoding/encoding. At 20 seconds, the resident lazy-decode/encode interval alone took 38.227 seconds. This run therefore does not establish a route to the 15-second end-to-end target merely by retaining more weights.

## Media validation and comparison limits

All six original MP4s were downloaded and exported without trimming or re-encoding. FFmpeg fully decoded video and audio streams; dimensions, frame counts, duration and 24 fps were checked. The outputs include stereo 48 kHz audio. Encoded-file, decoded-video and decoded-audio SHA-256 values are retained in the per-case records.

| Baseline versus resident | Encoded MP4 identical | Decoded video identical | Decoded audio identical |
| --- | --- | --- | --- |
| 5 s | No | Yes | No |
| 20 s | No | No | No |

Preview grids of all four measured videos were visually inspected. Audio was decoded, not listened to. **Human motion, audio quality and prompt-adherence acceptance remain pending.** Hash differences are diagnostic, not a quality verdict; the results are not fully bit-identical. There is one sample per measured case, fixed ordering and cache/shape bias: no p95, SLA, statistical confidence or provider-wide ranking is established.

The historical Runpod five-second request-to-download measurements were 55.432 seconds baseline and 34.987 seconds resident, at USD 3.49/GPU-hour. Its processing-only normalized costs were USD 0.009008 and USD 0.005525 per requested video-second. This selected Vast offer was faster in those single client-observed samples but **more expensive by the quoted processing-only measure**. Historical private Runpod `uv.lock` was not recovered, so this is same-model/settings replication, not a proven bit-identical software environment. Differences cannot be attributed solely to the provider.

## Successful host, preparation and lifetime

The create-time refreshed offer was `36346695` on verified machine `57753`; initial admission had selected `36346709` on the same machine. The quote was USD 4.953333333/hour compute plus USD 0.055555556/hour for 200 GB temporary disk, totaling **USD 5.008888889/hour**. Inbound and outbound were each quoted at USD 0.000001302083333/GB.

Actual execution reported one **NVIDIA H100 80GB HBM3**, MIG disabled, 81,559 MiB GPU memory and driver **580.126.20**. The native virtual environment used torch 2.13.0+cu132, CUDA 13.2 and NATTEN 0.21.7+torch2130cu132. Separate pre-generation BF16 matmul, PyTorch SDPA and NATTEN `na3d` probes passed; the six subsequent native outputs establish the full requested pipeline, not merely those kernels.

Guest-visible hardware inspection reported 645,671,157,760 memory bytes, 208 CPUs and 23,087,598,796,800 filesystem bytes. These host-backed visibility readings are **not dedicated CPU/RAM/disk allocation guarantees**. Contract admission remained one GPU and 200 GB temporary disk; quoted host RAM was 226,775 MB.

Preparation completed in **623.281 seconds**, including **548.618 seconds of model downloading**. Preparation start to download start was 17.675 seconds. All six pinned model files, totaling 71,118,761,094 bytes, passed integrity verification; source, lock and critical dependency evidence are in the run JSON. The full prompt and raw download links remain private.

The original create request was **2026-09-20 23:20:05.494 UTC**. Controller absence was verified at **23:52:45.198**, and independent absence at **23:52:47.031**. The earliest verified absence gives a **1,959.703-second (32 min 39.703 s) resource-lifetime upper bound**, within the original 45-minute deadline. The deadline never restarted during SSH repair or container recycle.

Approximately 15 minutes of initial startup/SSH repair preceded native preparation and remain included in rental accounting. Across all six outputs, pipeline processing totaled 355.209 seconds. The other 1,604.494 seconds include preparation, transfers, startup, idle intervals and teardown; they are not a measured idle-only interval. Warmup pipeline compute was USD 0.118156 and measured pipeline compute USD 0.370585 at the quote; neither is added again to the rental bill.

## Whole-stage accounting and delayed billing

At **2026-09-21 00:04:35 UTC**, original-baseline credit drawdown was **USD 5.585449699640002**, unchanged from the 00:00:19 observation. The account listed **zero instances and zero SSH keys**. Instance-specific provider usage rows subsequently summed to **USD 5.584**: **USD 2.632 for seven failed attempts plus USD 2.952 for the successful lease**. The difference from credit drawdown is approximately USD 0.00145; observation times and provider display precision differ. These are alternative observations of the same spending, not additive charges. **Final invoice reconciliation remains pending.**

Delayed reporting raised attempt 007 from its published USD 0.403 snapshot to USD 0.496, an additional USD 0.093. Earlier artifacts and admission snapshots are preserved. Accordingly, the native run JSON's `cumulative_stage_reported_usd` is 5.491, the sum of its frozen prior snapshots and its own 2.952 observation. The [dated stage reconciliation](results/VAST_LTX_STAGE_RECONCILIATION_2026-09-21.json) supplies the later all-attempt sum **5.584** without rewriting history. Earlier interim chat/account snapshots are not final costs.

For the successful lease, compute-plus-disk quote multiplied by the create-to-absence window gives **USD 2.726649**, excluding network. The provider's **USD 2.952 reported charge exceeds that quote-window estimate**; exact billed duration and final rate/charge reconciliation are not established. The rounded provider breakdown displayed USD 2.918 GPU and USD 0.034 storage, with transfer rows rounded to USD 0.000. Rounded-zero transfer rows do **not** establish free networking or exact billable units. Namespace counters recorded 75,054,254,400 inbound and 305,943,483 outbound bytes; these are not provider-certified billable bytes and may exclude host image pulls.

The USD 9.99 allowance is cumulative from the original USD 10 funded baseline, not fresh per lease. The successful admission carried a **USD 5.57 conservative prior exposure hold**, a full-horizon estimate of USD 9.326803385, a USD 8.39 spending stop and USD 1.60 closeout reserve. Holds are dated operational reserves, not extra paid charges or final bills; late usage adjustments are reported separately. The observed whole-stage spend remained below the allowance. No failed-rental cost is hidden, assigned to a nonexistent accepted video, or counted twice.

## Seven failed attempts, all closed with zero generations

The table uses the latest dated reconciliation; linked historical artifacts retain their original observations.

| Attempt / original closeout JSON | Instance | Observed failure | Latest reported charge, USD |
| --- | ---: | --- | ---: |
| [001](results/P01_EN_VAST_H100_LTX25_REUSE_5S_001.json) | 51778886 | Signed-debit parser rejected negative `total_spend` during preparation | 0.194 |
| [002](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_002.json) | 51807213 | Source SCP failed; original stderr was not retained | 0.267 |
| [003](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_003.json) | 51811500 | Connection published before full scoped-guard readiness | 0.072 |
| [004](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_004.json) | 51812997 | Control observation failed; precise exception was not retained | 0.424 |
| [005](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_005.json) | 51815605 | SSH observation returned exit 255, `Connection refused`, after valid guard handoff | 0.075 |
| [006](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_006.json) | 51818794 | Proxy reverse-port forwarding failed; later HTTP429 caused guard deletion | 1.104 |
| [007](results/P01_EN_VAST_H100_LTX25_REUSE_5S20S_007.json) | 51821924 | Direct SSH rejected the registered key; later generic API transport/response failure caused guard deletion | 0.496 |
| **Failed-attempt total, not a final invoice** | | | **2.632** |

Case CSVs: [001](results/VAST_LTX_REUSE_MEASUREMENTS.csv), [002](results/VAST_LTX_REUSE_RETRY_MEASUREMENTS.csv), [003](results/VAST_LTX_REUSE_RECOVERY_MEASUREMENTS.csv), [004](results/VAST_LTX_REUSE_HANDOFF_MEASUREMENTS.csv), [005](results/VAST_LTX_REUSE_RESUME_MEASUREMENTS.csv), [006](results/VAST_LTX_REUSE_PROXY_MEASUREMENTS.csv), [007](results/VAST_LTX_REUSE_STABLE_MEASUREMENTS.csv). Missing cases are not zero-duration measurements. No synthetic media are benchmark results. Every attempt has a separate journal and single-use create identity; the original 001 JSON and CSV remain unchanged.

001 reached SSH, hardware inspection and preparation launch on machine `147749`, driver 595.84, but not prepared readiness. Its failure was our signed-debit parsing bug, not user funding. 002 reached hardware inspection on driver 610.57.04 but failed source transfer before starting preparation. 003 was our premature manual guard handoff. 004's missing underlying exception cannot be reconstructed: neither a separately discovered roundoff issue nor later HTTP429 evidence proves its cause. 005 retained the actual private connection-refusal diagnostic after correct handoff; provider audit placed deletion after that failure, but the underlying network/host cause remains unknown.

006 and 007 used machine `108977`, driver quote 580.126.20, at USD 4.411111111/hour including disk. Neither executed the frozen native environment. In 006, logs showed sshd listening but repeated `remote port forwarding failed for listen port 18794`. An official same-instance template update requested a direct port; acceptance was not proof of readiness before guard deletion. In 007, the direct endpoint was reachable but rejected the key. Reattaching the same public key returned `SSH key already associated with instance`; it did not establish guest access. A startup-log request delivered after deletion returned `No such container` and cannot explain the earlier failure. Its later generic API error cannot be relabeled a proven timeout, DNS error or HTTP429. Machine `108977` was excluded from 008.

## SSH repair and controller corrections

On 008, live sshd logs identified `bad ownership or modes for file /root/.ssh/authorized_keys`. The repair restored root ownership, directory mode 0700 and key-file mode 0600; **StrictModes stayed enabled**. A same-instance template update stored the repair without changing image or deadline. A reboot alone did not restore access; an accepted container recycle did. A limited command-channel `chmod` was rejected as `Invalid command given` and was not treated as executed. Subsequent live checks confirmed uid/gid 0, modes 0700/0600 and `strictmodes yes`. The startup generator now performs that normalization. This was one paid create, not another hidden rental.

Other corrections retained in the controller:

- Preserve signed `total_spend` debits and use `credit`, always against the original stage baseline. A USD 1e-12 tolerance handles floating-point noise; a real USD 1e-6 deposit still fails isolation checks.
- Require funding for the remaining approved allowance, not another USD 8 after every failure. Preserve prior exposure holds, including already reported higher charges.
- Refresh quotes before the sole create; match offer identities locally instead of unsupported server-side ID filters.
- Publish connections only after full remote scoped-guard readiness. The manage probe writes the existing label to itself, not a runtime-state transition.
- Retain bounded private SSH/SCP diagnostics and preparation phase records. GET/SSH recovery is read-only, bounded and keeps the original freshness fence; malformed JSON fails immediately. Mutations, SCP and generation submissions are not automatically replayed.
- Preserve safe exception types rather than raw credential-bearing transport messages. The generic transport regression does not establish 007's unretained underlying exception.
- Export using the earliest independently supported absence bound; retain later bookkeeping timestamps separately. These are not provider-certified billed seconds. Historical 001/002 exports are not rewritten.

## Verification and remaining limits

- `python3 -m unittest discover -s tests -q` — **210 tests passed after the final source change**, including SSH startup normalization. Funding, signed-debit, roundoff, transient-read and late-closeout regressions were exercised before and after their fixes.
- `python3 scripts/export_vast_ltx.py --lease private/vast-h100-p01-008 --output results` — **completed**, exported all six native MP4/JSON pairs and the six-case CSV after both absence proofs; full audiovisual decoding and original hashes passed.
- Real native execution — two technical warmups plus all four measured 8 + 3 requests, including both 20-second requests; no generation retries or missing cases.
- Four measured video preview grids visually inspected; audio decoded but not listened to. Human quality acceptance remains open, as do final invoice and exact billable-duration/network reconciliation.
- Controller and independent guard exited 0; all owned instances and temporary account SSH keys are absent. No persistent volume, retained GPU or automatic top-up was created.

Sources and exact dependency/model hashes are retained in [the protocol](VAST_TRIAL.md) and machine-readable artifacts. Synthetic FFmpeg smoke fixtures used during controller development were removed and never contributed native benchmark measurements.
