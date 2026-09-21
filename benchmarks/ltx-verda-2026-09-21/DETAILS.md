# Verda RTX PRO 6000 spot: matched LTX-2.5 queue

**Conservative comparison: at Verda's ordinary on-demand tariff, the measured runtime implies approximately 13.5% lower warmed-queue GPU/disk cost than the matched Runpod reference — $0.002844 versus $0.003287 per requested video-second.** This assumes the same runtime; **it is a tariff calculation, not a separate on-demand test**.

**Separately measured spot result: USD 0.001463 per requested video-second, GPU plus disk — 55.5% below the matched ten-request Runpod reference.** This is a **spot, warmed-queue** result, not an all-in service price or a demonstrated production saving.

| Measurement | Verda spot | Published Runpod reference |
|---|---:|---:|
| Measured requests | 10 × 5 s | 10 × 5 s |
| Full warmups before measurement | 2 | 2 |
| Requested measured output | 50 s | 50 s |
| Worker queue window | 267.363343 s | 279.402316 s |
| GPU instance rate | $0.93/h | $2.09/h |
| Attached disk rate | $0.05479452/h | $0.02777778/h |
| GPU + disk / requested video-second | **$0.0014627664** | **$0.0032872890** |
| GPU + disk / requested 5-second video | **$0.0073138321** | **$0.0164364449** |

The direct reference is the [September 20 ten-request package](../ltx-rtx-2026-09-20/README.md), not the separately published [one-hour, twenty-scene run](../ltx-sustained-2026-09-21/README.md). Its historical evidence is unchanged. This experiment measures price, not a model-speed optimization.

## Spot is a material qualification

The observed $0.93/h rate is **spot**, not the $1.86/h Verda on-demand catalog rate. A provider interruption can require another allocation, model preparation and warmup, and can lose unfinished work. There was **no observed spot interruption in this run**; the failed attempts below were setup/control failures. A ten-request sample does not establish interruption frequency or long-running availability.

At the **on-demand catalog rate**, reusing the measured runtime and disk rate gives an **arithmetic estimate** of $0.002844144 per requested video-second, approximately **13.5% below** the reference. This is **not an on-demand benchmark**. Most of the measured 55.5% advantage comes from the spot rate; do not present it as an unconditional provider-wide saving.

The actual successful model download took 817.350 seconds. Repeated cold starts can materially change the economics of a short queue. This package does not estimate production retries, capacity guarantees or a latency SLA.

Sources: [official instance catalog](https://api.verda.com/v1/instance-types?currency=usd), [Verda pricing](https://verda.com/pricing), [billing documentation](https://docs.verda.com/welcome-to-verda/pricing-and-billing/index.md). The authenticated compute/disk quote is preserved without resource identifiers in [prices.json](evidence/prices.json).

## Frozen workload and actual hardware

- Lightricks/LTX-2.5 weights at `5e6e71018ee1756ed329b697a7b4aedc934dfce9`; LTX-2 source at `a95ab856bf29407b6b066ede0abe1846050db56c`.
- Same original worker, requests, distinct seeds, quality contract and profile as the paired Runpod reference. Two full warmups, then ten sequential requests; batch size and concurrency both one.
- BF16, native audio, 1344 × 768, 121 frames at 24 fps, full 8 + 3 transformer schedule. No quantization or offload change. The denominator is **five requested seconds**, not the container duration of approximately 5.041667 seconds.
- One resident transformer build; zero measured-request rebuilds; eleven fresh video/audio forwards for every measured request.
- Same pinned container: `runpod/pytorch@sha256:4d1721e62b56d345c83b4fd6090664be6daf9312caab5b2e76f23d8231941851`.
- Python 3.12.3, PyTorch 2.13.0+cu132, CUDA 13.2, NATTEN 0.21.7. A real native GPU/NATTEN probe passed before model preparation.
- Verda `1RTXPRO6000.30V`, FIN-03: RTX PRO 6000 Blackwell Server Edition, 96 GB VRAM class, 30 CPUs, 90 GB advertised host RAM (94,879,367,168 bytes observed), 600 W limit, NVIDIA driver 580.178.04.
- Runpod reference: same GPU model and 600 W limit, but 188 GB host RAM, 27.2 CPU quota and driver 595.91.07. **These host/driver differences are not hidden or described as identical hardware.**

[Manifest overrides](evidence/manifest-overrides.json) reconstruct the exact consumed manifest from the existing public reference; only run ID and the two deadlines change. `verify.py` checks its original SHA-256. [Transport hashes](evidence/transport-manifest.json) anchor the unchanged reference files and [executed remote adapter](execution/verda_remote.py). [Preparation evidence](evidence/prepare-status.json) records all six verified weight files and the exact dependency lock.

The adapter substitutes only the provider-specific guard verification in memory; model worker files remain byte-identical. It uses a Verda guard receipt, not a fabricated Runpod receipt. The archived adapter is **execution evidence, not a standalone provisioning tool**: it requires staged inputs and a live independent provider guard. Never execute it against stale or fabricated guard evidence. Operator credentials, signed download links, model binaries and account-control automation are not distributed in this package.

## Original videos

These are the native MP4s, copied without re-encoding:

| Request | Video |
|---|---|
| R01 | [Original MP4](videos/R01.mp4) |
| R02 | [Original MP4](videos/R02.mp4) |
| R03 | [Original MP4](videos/R03.mp4) |
| R04 | [Original MP4](videos/R04.mp4) |
| R05 | [Original MP4](videos/R05.mp4) |
| R06 | [Original MP4](videos/R06.mp4) |
| R07 | [Original MP4](videos/R07.mp4) |
| R08 | [Original MP4](videos/R08.mp4) |
| R09 | [Original MP4](videos/R09.mp4) |
| R10 | [Original MP4](videos/R10.mp4) |

Technical warmups: [one](videos/technical-warmup-1.mp4), [two](videos/technical-warmup-2.mp4). All twelve outputs passed SHA-256, H.264/AAC stream-contract checks and full video/audio decoding. Four of ten measured MP4s are byte-identical to the Runpod outputs; six differ. Different file bytes alone do not establish a quality difference. Human quality acceptance and service-level parity are **not established**.

## Whole-stage spending, including failures

**Observed credit drawdown after refund: $0.68424**, below the single cumulative $5 allowance. This includes **all four attempts**, preparation, both successful warmups, generation and export. The cap was never reset after a failure.

| Attempt | Outcome |
|---|---|
| 1 | SSH-key create reply parsing failed before a GPU allocation; temporary key removed. |
| 2 | Create response timed out after allocation; independent guard found and deleted the VM and disk. |
| 3 | Native probe passed; a transient control API timeout triggered cleanup while weights were downloading. |
| 4 | Two complete warmups and all ten measured outputs succeeded; outputs exported and all resources deleted. |

This stage total is **$0.0136848 per measured requested video-second** when charged entirely to this one-off 50-second experiment. It is not the warmed-queue price. The warmed GPU/disk estimate ($0.07313832) is part of, **not additional to**, stage spending.

Verda prepays in ten-minute intervals and refunds unused time. Read-only observations continued for more than ten minutes after deletion, capturing the refund and subsequent stable balance. **This is reconciled account credit movement, not a final provider invoice.** Account balances and payment details are omitted; [reconciliation.json](evidence/reconciliation.json) retains cumulative spending observations, all-attempt outcomes and the verification time.

All stage VMs, attached volumes and temporary provider SSH keys were deleted; absence was verified. Temporary local private keys and signed download links were removed. No ongoing rental remains from this stage.

## Verify offline

From a full checkout of this repository, with Python 3.11+:

```bash
python3 -B benchmarks/ltx-verda-2026-09-21/verify.py
```

To also probe the media contract and fully decode all twelve videos, install FFmpeg/ffprobe and run:

```bash
python3 -B benchmarks/ltx-verda-2026-09-21/verify.py --decode
```

No API credentials, GPU or paid resources are needed. The verifier checks [SHA256SUMS.json](SHA256SUMS.json), the original worker/input hashes, complete journal sequence, two warmups, ten outputs, seeds, fresh forwards, native media hashes and quoted rates. It independently recomputes both queue costs and the 55.5% reduction. This verifies the published evidence and arithmetic, not the provider's billing ledger or a future runtime.

Machine-readable evidence: [measurements](evidence/measurements.csv), [worker events](evidence/events.jsonl), [delivery receipts](evidence/delivery-receipts.json), [verified result](evidence/verified-result.json), [hardware](evidence/host-inventory.json), [native runtime probe](evidence/runtime-probe.json), [dependencies](evidence/dependencies.txt), [paired output hashes](evidence/paired-output-hashes.json).
