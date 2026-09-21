# LTX-2.5 on RTX PRO 6000: reproducible cost evidence

Measured on September 20, 2026: ten consecutive five-second requests completed
in **279.4023163696 seconds** after two full warmups. With the observed
**USD 2.09/GPU-hour** quote and **USD 0.02777778/disk-hour**, the warmed queue
cost was **USD 0.003287289 per requested video-second**.

This is GPU plus temporary disk cost, not a complete hosted-service price.
Setup, warmup, operations, delivery infrastructure and quality-driven retries are
not amortized into this steady-state estimate. The denominator is 50 requested
seconds; encoded files contain 121 frames at 24 fps, approximately 5.0417 seconds
each. The original benchmark is a single scene, ten distinct paired seeds, one
host and batch/concurrency one, not a long production soak or quality benchmark.

## Check the evidence without renting a GPU

Requires Python 3.11 or newer; no third-party packages, credentials or network:

```bash
python3 verify.py
```

The verifier checks all ten original video hashes, the unchanged worker source,
the original manifest hash, prompt hashes, two warmups, ten completed requests,
fresh transformer execution, delivery/decode receipts and the dependency lock.
It recomputes the cost and API price ratios directly from the original events.
Hashes establish consistency of this evidence bundle; they are not independent
third-party attestations of the benchmark.

Expected results include:

```text
verified_outputs: 10
worker_window_seconds: 279.40231636958197
mean_processing_seconds: 27.939381914958357
gpu_plus_disk_usd_per_video_second: 0.0032872889814840934
h3_max_published_price_divided_by_our_cost: 12.168081426763226
h3_max_turbo_published_price_divided_by_our_cost: 6.084040713381613
```

Evidence links:

- [Original measurement events](evidence/events.jsonl), including the final queue interval.
- [Per-request measurements and seeds](evidence/measurements.csv).
- [Exact prompts, profile and warmup seeds](evidence/resident.json).
- [Original execution plan and hashes](evidence/original-plan.json).
- [Runtime dependency versions](evidence/dependencies.txt) and [uv lock](evidence/uv.lock).
- [Host hardware, driver and resource limits](evidence/host-inventory.json).
- [Delivery and decode receipts](evidence/delivery-receipts.json).
- [Original generated videos](videos/), R01 through R10.
- [Unchanged generation worker](original-worker/ltx_gpu_price_worker.py).
- [Resident-transformer implementation](original-worker/ltx_reuse.py).
- [Offline verification script](verify.py).

## What the fal comparison actually says

On September 20, the endpoint pages displayed these promotional 768p prices:

| Endpoint | USD per output video-second | Published price / our warmed GPU + disk estimate |
|---|---:|---:|
| [H3 Max](https://fal.ai/models/minimax/h3-max/text-to-video) | 0.04 | 12.17 |
| [H3 Max Turbo](https://fal.ai/models/minimax/h3-max-turbo/text-to-video) | 0.02 | 6.08 |

Both pages stated a September 30 promotion end date. These are time-sensitive
public tariffs, not verified account invoices. [Recorded references](evidence/prices.json).

This compares our LTX compute/storage estimate with the retail price of a
different model. **Quality parity has not been evaluated.** We did not run fal
requests for this comparison. Our mean generation time was 27.94 seconds per
five-second clip, so this configuration does not meet the earlier 15-second
interactive target. No claim of equivalent latency or service capabilities is made.

## Frozen generation configuration

- GPU: one NVIDIA RTX PRO 6000 Blackwell Server Edition, 96 GB class.
- Measured host: AMD EPYC 9555; 188 GB assigned RAM; CPU quota 27.2 cores;
  driver 595.91.07; 600 W GPU power limit.
- Container: `runpod/pytorch@sha256:4d1721e62b56d345c83b4fd6090664be6daf9312caab5b2e76f23d8231941851`.
- Model: [Lightricks/LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5/tree/5e6e71018ee1756ed329b697a7b4aedc934dfce9), revision `5e6e71018ee1756ed329b697a7b4aedc934dfce9`.
- Source: [Lightricks/LTX-2](https://github.com/Lightricks/LTX-2/tree/a95ab856bf29407b6b066ede0abe1846050db56c), revision `a95ab856bf29407b6b066ede0abe1846050db56c`.
- Python 3.12, uv 0.12.17, Torch 2.13.0+cu132, NATTEN 0.21.7+torch2130cu132.
- Native audio, BF16, 1344 x 768, 121 frames, 24 fps, full 8 + 3 schedule.
- Decoder tiles: 128 frames with overlap 40; 1344 x 768 with spatial overlap 160.
- No compilation, quantization, prompt enhancement, output cache or embedding cache.
- Transformer weights remain resident. Prompt encoding and eleven transformer
  forwards execute afresh for every measured request.
- Two complete warmups precede ten requests. The first warmup records kernel
  names using a profiler; profiling is outside the measured queue.

## Repeat generation on a prepared GPU host

The original worker and its dependencies are included byte-for-byte. Their
SHA-256 values must match `evidence/original-plan.json`. New adapter `rerun.py`
only creates a new run identity, renews lease deadlines from the actual guard
and sends the start trigger after warmup. The original measurements did not
use this adapter. The adapter has been checked offline, not rerun on a paid GPU.

Provisioning is deliberately not automated by this package. Use the pinned
container on one matching GPU with at least 188 GB assigned host RAM and 200 GB
disk. Place this evidence bundle at `/root/benchmark/reproduction`. Set up an
independent provider lease termination guard; the unchanged worker requires a
live `/root/benchmark/guard-ready.json` with the verified own-Pod read, process
ID and actual deadline. Do not manufacture a guard receipt. The original guard
implementation is included as `original-control/runpod_deadline.py` for review;
it belongs in the Pod startup configuration with its own provider-scoped
credential, Pod name, deadline and SSH public key.

Prepare the pinned runtime inside the container (setup is outside the timed queue):

```bash
cd /root/benchmark
git clone https://github.com/Lightricks/LTX-2.git ltx-source
git -C ltx-source checkout --detach a95ab856bf29407b6b066ede0abe1846050db56c
python3.12 -m pip install 'uv==0.12.17'
cd /root/benchmark/ltx-source
uv sync --frozen --no-dev --package ltx-pipelines --python python3.12 --no-python-downloads
cd /root/benchmark
```

Install the exact NATTEN wheel named in `evidence/original-plan.json` from its
official release URL after checking its recorded SHA-256; install with
`uv pip install --python ltx-source/.venv/bin/python --no-deps WHEEL_PATH`.
Download the six model files listed in `original-worker/ltx_config.py` from the
pinned Hugging Face revision into `/root/benchmark/models`, retaining their
relative directories and complying with the model's access/license conditions.
The original worker checks every file's size and SHA-256 before loading it.
Check that the source checkout is clean and its `uv.lock` hash equals
`dd5d9b68281ab8536e245cffe236388f4ed73c872442705718e3f3baf3a46bf1`.

After preparation and a verified live lease guard, run:

```bash
cd /root/benchmark/reproduction
python3.12 rerun.py --base /root/benchmark
```

The worker enforces the original profile, GPU name/capability, Torch/CUDA
versions, two warmups and all ten measured requests. Renew the lease before
starting if insufficient time remains. Export and verify the new MP4 files and
events before teardown. Never count a partial queue or failed artifact as a
successful reproduction. A matching seed does not promise identical pixels
across hardware, kernels or software environments.

Recompute the new result using the observed GPU/disk rate, complete
`worker_window_seconds` and the requested output seconds. Expect host and market
variation; the quoted USD 2.09/hour is an observed historical rate, not a future
price guarantee. The original compute/disk estimate is based on elapsed time
and quoted rates, not a reconciled full-lease invoice.
