# Reproduce the registered experiment

The exact immutable preregistration is commit `7e14d9e`. The HTTP-202 observer correction is documented in `DEVIATIONS.md`; use the corrected fal runner for a new execution. Prompts, seeds, model profile, request order and GPU worker were unchanged by that correction.

## Environment and input artifacts

The measured GPU runs Linux. The tested controller runs on macOS with Python 3.12, OpenSSH/scp, `ffmpeg`, `ffprobe` and `/usr/bin/caffeinate`. The latter is used by the deadline guard, so the controller is not claimed to run unchanged on Linux. Plotting additionally uses matplotlib and Pillow; neither affects GPU inference.

1. Check out this repository and enter `benchmarks/ltx-sustained-2026-09-21`.
2. Download and extract the release's evidence archive. Its `preparation/ltx-audio-source.tar.gz` is the exact source archive used by this run, including the upstream licenses and pinned clean Git checkout. Copy it to `private/ltx-audio-source.tar.gz`.
3. Download uv's Linux wheel from the hash-pinned public URL in `scripts/ltx_sustained_trial.py` and save it as `private/ltx-audio-uv-linux.whl`. Verify both files against `preparation_files` in `ltx-sustained-plan.json` before proceeding. The GPU downloads this same uv wheel directly to reduce controller upload time.
4. Put your own `RUNPOD_API_KEY`, `HF_TOKEN` and `FAL_KEY` in a private literal-assignment environment file outside version control. Do not source it as a shell script. The supplied parser accepts the documented aliases. Your Hugging Face account must have access to the pinned weights; signed download URLs remain private and expire.

The upstream source revision, weight revision and six file hashes are in `scripts/ltx_config.py`; the container digest, NATTEN wheel digest and dependency-lock hash are in the plan. The preparation worker installs from the frozen lock, tests a real NATTEN GPU kernel, downloads the six pinned files and verifies their hashes. No weights are redistributed in this report.

## Offline validation

```sh
python3.12 -B -m unittest discover -s tests -p 'test_sustained_*.py'
python3.12 -B scripts/ltx_sustained_trial.py check --plan ltx-sustained-plan.json
```

`SHA256SUMS.json` records published file hashes. The raw GPU manifest adds the actual lease deadlines to the registered inputs; it does not change their prompts or seeds.

## Paid execution with your own accounts

The commands below create real charges. Re-check availability and the $2.09/hour Secure GPU quote first; the controller rejects a higher compute price. The frozen plan targets one RTX PRO 6000 Blackwell Server Edition in EUR-IS-1 with at least 128 GB host RAM and CUDA 13.2 support. A failed allocation is not a benchmark result.

Create a new private journal for a new experiment. Never reset or reuse an existing live run's ledger or submission markers:

```sh
mkdir -p private
python3.12 -B scripts/budget.py --ledger private/ledger.json init
python3.12 -B scripts/budget.py --ledger private/ledger.json reserve \
  --id FAL_SUSTAINED_PAIRED_001 --usd 2.20 --phase generation
python3.12 -B scripts/ltx_sustained_trial.py arm \
  --plan ltx-sustained-plan.json --env-file /absolute/path/to/your-private.env
```

Arming reserves $3.25 for the GPU, starts the local deadline guard, creates a new SSH key and writes `private/ltx-sustained-rtx6000-001/create-request.json`. It does not allocate a GPU. The 90-minute deadline starts at arming, so have all local artifacts and tools ready first.

Our allocation used the Runpod MCP `create_pod` tool with `body` set to that exact JSON object. The same schema is Runpod's REST v2 `POST /pods` body. Submit it exactly once, record the returned Pod ID, and attach it:

```sh
python3.12 -B scripts/ltx_sustained_trial.py attach \
  --plan ltx-sustained-plan.json --env-file /absolute/path/to/your-private.env \
  --pod-id YOUR_NEW_POD_ID
caffeinate -ims python3.12 -B scripts/ltx_sustained_trial.py run \
  --plan ltx-sustained-plan.json --env-file /absolute/path/to/your-private.env
```

The controller verifies both the quote and the independent on-Pod shutdown guard, prepares the pinned environment, performs two complete warmups, then admits the full hour only if time remains for completion and export. Generation and export proceed independently. One worker retains the transformer throughout the entire queue. Normal teardown happens only after all completed measured artifacts are downloaded and verified. The hard lease deadline remains an independent backstop.

Run the API reference in a second controller terminal using its existing reservation:

```sh
caffeinate -ims python3.12 -B scripts/fal_sustained.py \
  --env-file /absolute/path/to/your-private.env
```

An interrupted fal runner resumes existing accepted requests from their saved IDs. It does not repeat a submission with an uncertain outcome. `X-Fal-No-Retry: 1` disables hidden generation retries. Do not delete its markers. API timing and advertised pricing can change independently of the pinned local model.

For this run the two warmup videos were additionally copied from the same Pod after warmup completion and matched against the event-log hashes; they are included separately and never counted in the measured hour. Hardware inventory was recorded while the run continued. Neither observation changed the generation queue.

## Recompute and review without paying

The evidence archive contains the actual manifest, event log, delivery receipts, all original videos and sanitized provider measurements. Extract it and run:

```sh
python3.12 -B scripts/summarize_sustained.py \
  --manifest /path/to/evidence/ltx/resident.json \
  --plan ltx-sustained-plan.json \
  --delivery-folder /path/to/evidence/ltx/resident-delivery \
  --output /tmp/recomputed-ltx
```

The analyzer verifies frozen input identities, sequential execution, fresh transformer forwards, resident-weight reuse, receipt hashes and the original video hashes before calculating cost. Cost includes failed attempt time and divides only by successfully delivered technical output. It never fills in human quality acceptance.

Open the separate quality archive's `review.html` locally to compare the twenty preselected pairs. Export ratings before reading `IDENTITY_KEY.json`. All original clips retain their native frame count, duration and audio; no trimming, normalization or best-of selection is applied. The review is prepared for human assessment, not proof that the two models have equal quality.
