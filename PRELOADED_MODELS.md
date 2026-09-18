# Persistent model storage: unsuccessful CPU-only preparation

Status, September 18, 2026: **attempted; no verified cache remains**. A two-vCPU,
8 GB CPU Pod and 200 GB STANDARD volume were provisioned in EU-NL-1. The HF
download process was killed with SIGKILL (signal 9); the exact cause is not
established. The runner exported diagnostics and deleted both resources before
the operator's later request to retain failed GPU deployments for in-place fixes.
The partial public-model download was discarded; it can be downloaded again.

| Event | UTC, September 18 |
|---|---|
| CPU allocation | 03:51:03.330 |
| Preload worker starts | 03:53:01.320 |
| Pinned HF download starts | 03:53:49.194 |
| Worker records failed download | 03:55:28.324 |
| CPU deletion verified | 03:55:50.965 |
| Volume deletion verified | 03:55:52.531 |

The standalone HF CLI was installed at version 1.31.0. Download progress reached
44 of 81 base files before failure; file count is not byte completion or integrity
verification. **Zero files/bytes were independently verified.** Do not infer an
out-of-memory diagnosis from SIGKILL alone. The quoted CPU rate was USD 0.08/hour;
the approximately 287.635-second allocation window gives USD 0.006392 compute,
before temporary-disk and network-volume charges. This is an estimate, not an
invoice. The USD 0.20 CPU and USD 1 storage holds remain reserved, not settled.

[preload-manifest.json](preload-manifest.json) pins 81 required FL2VA base files
(144,051,182,625 bytes) plus two adapters (2,163,527,704 bytes):
**146,214,710,329 bytes total**. Small source/configuration files use Git blob SHA-1;
large weight files use SHA-256. These are integrity records, not additional models.

The operator explicitly authorized skipping storage optimization for the next
functionality check. [GPU attempt 002](ACCELERATION_TRIAL.md) therefore uses the
ordinary ephemeral cache in AP-IN-1. CPU preparation is not running alongside it.
The optional workflow below is retained for a future separately approved attempt,
not a prerequisite or instruction to provision more resources now.

Use the Runpod skills' persistent-storage workflow: select a supported data
center, preload pinned artifacts without GPU compute, verify them, and only
then attach the volume during a new Pod deployment. Direct S3 upload and a
temporary CPU downloader are different options; the region must support the
chosen path.

## Catalog evidence recorded during preparation

- The previous AP-IN-1 data center returned `networkVolumeTypes: []`. It cannot
  be assumed to support this plan just because it hosted our four-H100 Pod.
- A live catalog read listed **AP-JP-1, EU-NL-1 and EUR-IS-3** with STANDARD
  volumes and H100 SXM availability `LOW`. This is not a guarantee that four
  cards can be allocated together; no GPU allocation was attempted in those regions.
- These three regions' S3 hostnames failed DNS resolution, and they are not in
  Runpod's published S3-supported-region list. A STANDARD-volume catalog entry
  alone does **not** establish S3 access. No credential was transmitted to an
  unresolved hostname, and no volume was bought on that assumption.
- The operator added S3 credentials under `RUNPOD_S3_API_USER` and
  `RUNPOD_S3_API`. The read-only [S3 probe](scripts/check_s3.py) returned **HTTP
  200** from the documented EUR-IS-1 endpoint, with zero buckets. Credentials
  work; they are no longer the blocker. Their values were not printed or committed.
  The probe also accepts `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` aliases.
- EU-NL-1 reports STANDARD storage, H100 SXM stock `LOW`, and general-purpose CPU
  stock `HIGH`. A two-vCPU `cpu3g` Pod is quoted at **USD 0.08/hour** (USD
  0.04/vCPU/hour, 4 GB RAM/vCPU). This offers a CPU-only path to preload the disk
  in the target H100 region without S3. The CPU-only attempt above used this path.
- No verified model volume remains after the failed attempt. Do not treat working
  S3 credentials as proof of a populated cache or available four-GPU capacity.

## Original bounded proposal and future retry requirements

Start with one approximately 200 GB STANDARD volume, subject to an exact pinned
manifest size check. At the published USD 0.07/GB/month tariff this is USD 14
per month, approximately USD 0.47/day using a 30-day month. Storage uses the
**same Runpod account balance** and continues billing without any running GPU.
Before provisioning, record the chosen data center, size, retention window and
budget reservation within the unchanged USD 25 experiment cap. Do not buy an
empty volume while upload access is missing or assume indefinite retention is free.

The proposed bounded preparation is 200 GB for 48 hours (approximately USD 0.93
storage) plus a temporary two-vCPU downloader at USD 0.08/hour. Delete the CPU Pod
as soon as verification completes, with a separately bounded timeout. Record the
retention decision and budget before creating either resource. This is an
estimate of the original reservation, not the actual duration billed: the
unsuccessful volume was removed within minutes, not retained for 48 hours.

## Required preparation and acceptance

These requirements apply to a future **preloaded-storage** deployment, not the
operator-authorized ephemeral-cache functionality retry.

1. Keep the base H3 revision and both adapter revisions from
   [h3_adapters.py](scripts/h3_adapters.py) / [the trial plan](ACCELERATION_TRIAL.md).
   Verify the exact files required by the native FL2VA loader; do not copy the
   unrelated full model family or silently use mutable latest weights.
2. Use S3 in an S3-supported region, or an explicitly budgeted temporary CPU
   Pod with the volume mounted in its data center. Do not start a GPU Pod for
   downloading. Network storage does not itself run an HF downloader.
   Preserve paths required by the loader and pin a size/checksum manifest.
3. Verify uploaded contents before marking the cache ready. Uploading filenames
   alone or seeing the expected aggregate size does not prove weight integrity.
4. Point both the base model loader and adapter loader at the mounted paths,
   with network fallback disabled. The old ephemeral `/root/benchmark/hf` path
   is not the new configuration. Adapt and test this mapping before allocating.
5. Deploy a fresh Pod in the volume's data center with the mount attached **at
   creation**. Use fresh run IDs and a new budget reservation; do not overwrite
   the completed failed trial. Enable and record the explicit compatibility patch.
6. Verify successful warmup, run the two approved requests sequentially, export
   outputs and measurements, then terminate the GPU Pod. Retain or delete the
   model volume according to the recorded retention decision.

Mounting weights removes repeated Internet downloads, not image pulls, loading
weights into VRAM or warmup. Network-volume read speed may change startup time;
measure it instead of promising an improvement. A new data center is a disclosed
configuration change. Storage work and the LoRA compatibility fix solve different
problems. A future storage retry must verify the cache; the current functionality
retry instead verifies the runtime patch on the existing paid GPUs.

Sources: [Runpod network volumes](https://docs.runpod.io/storage/network-volumes),
[Runpod S3 API](https://docs.runpod.io/storage/s3-api), and the dated live
`get_data_center`, `list_data_centers` and `list_network_volumes` responses.
