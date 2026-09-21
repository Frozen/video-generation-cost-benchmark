# Preregistered one-hour LTX and twenty fal H3 Max Turbo pairs

Status: **completed**. [Full measured results](results/RESULTS.md): 131 LTX clips over 60 minutes 22 seconds, zero observed generation failures or retries; $0.003253 per requested video-second for the measured GPU/disk queue. All twenty fal references also completed ($0.02/s from provider billing units). This is a cross-model cost comparison, with human quality acceptance still unassigned.

[Download all 153 original videos, seeds and evidence](results/ARTIFACTS.md) · [Twenty-pair quality review](results/QUALITY_REVIEW.md) · [Raw LTX logs](evidence/ltx). The full evidence archive includes 131 measured LTX videos, 20 fal videos and two warmups, plus a searchable `videos.html`, CSV/JSON catalog and per-video replay inputs. [Reproduction instructions](REPRODUCE.md) · [Warmup, seeds and caching controls](WARMUP_AND_SEEDS.md).

This experiment tests the robustness of the earlier short LTX cost measurement. It does not establish that LTX and fal H3 Max Turbo are the same model or provide equal quality.

## Workload

- One RTX PRO 6000 Blackwell Server Edition, Runpod Secure, EUR-IS-1; compute quote $2.09/hour plus 200 GB disk at $0.02777778/hour. Pinned container, source, weights, dependency lock and complete generation profile are in the plan and scripts.
- LTX-2.5, resident transformer, BF16, no quantization/compile, native audio, 1344 × 768, 121 frames at 24 fps, requested five-second clips, full distilled 8+3 schedule. Two complete warmups excluded from steady-state throughput but included in experiment spending.
- Minimum 3,600 seconds of continuously backlogged sequential generation, batch size/concurrency one. Finish and count the entire last request. No deliberate idle pauses. Actual elapsed time includes failed work, retries, encoding and journaling; GPU utilization is recorded separately, never assumed to be 100%.
- Twenty varied hand-selected scenes: three preserved prior collection prompts and seventeen newly authored benchmark scenarios. This is not sampled production traffic. Every block visits all twenty scenes in a frozen shuffled order. The 500-primary-request pool has cryptographically drawn distinct 31-bit seeds; two warmup seeds are separate. Stop at the time target, not after all 500 requests.
- Both output and prompt-embedding caches are disabled. Every output records eleven fresh transformer forwards and the single resident weight build. Reusing resident weights is not reusing generated videos. Artifact hashes do not alone prove the absence of caching.

## Failure policy

Failures are not injected. Zero failures and zero retries are legitimate findings. A confirmed local nonfatal failure may receive one immediate attempt with the same input/seed and a separate attempt ID. Two consecutive failures, a CUDA/OOM or output-contract error stop the run. An uncertain timeout/connection outcome is never blindly resubmitted. The 90-second per-request bound is checked after completion; independent lease guards bound hangs. A stopped short run is published as incomplete, never relabeled a full hour. Every observed output is exported before normal teardown.

## API pairs and quality

The first twenty primary LTX inputs, selected before any output, are the twenty fal reference inputs. Same exact prompts and seed integers; this does not imply identical latent noise across different models. fal endpoint: `minimax/h3-max-turbo/text-to-video`, five seconds, 768P, 16:9, prompt expansion disabled, safety checker enabled, native audio/default endpoint behavior. Preserve native output geometry and frame count instead of silently resizing to LTX. No provider-model identity or quality equivalence is assumed.

Twenty primary fal submissions, at most two additional retries after explicit provider-confirmed failure, no hidden HTTP/provider retries. Persist submission claims before POST; recover by polling the same request ID. Capture client submit-to-completion and submit-to-download time. The API's `timings.inference` field is DiT denoising time, not end-to-end latency.

Publish all twenty pairs, a randomized left/right review sheet, a separate identity key and the frozen scene criteria. Assess prompt adherence, visual coherence, audio relevance and synchronization where applicable. Keep automatic decoding/format validation separate from subjective quality. Unreviewed outputs do not count as proven quality parity.

## Cost and reporting

Steady-state cost per technically valid requested output second = (GPU + disk hourly rate) × actual queue hours / successfully delivered, fully decoded output seconds. Failed attempts add elapsed cost and no successful output. Also report complete delivery-window cost, full lease/setup/warmup/export spending, clips/hour and video-seconds/hour, p50/p90/p95/p99/min/max/stddev latency, per-scene variation, errors, unresolved attempts and retries. Retain unsuccessful logs and artifacts. Report requested five-second normalization alongside actual container duration.

The public fal 768p quote is $0.02 per generated second ($0.10 per requested clip), a temporary promotion through September 30, 2026. The pricing API's $0.0125 base billing unit is not a 768p quote. Keep advertised estimates separate from confirmed billing. Sources: [endpoint/API](https://fal.ai/models/minimax/h3-max-turbo/text-to-video/api), [model pricing](https://fal.ai/models/minimax/h3-max-turbo/text-to-video). Ratios are cross-model cost comparisons, not a claim to serve fal's model more cheaply.

Additional authorized exposure: GPU lease up to $3.25 (5,400 seconds plus shutdown allowance), fal up to $2.20, total $5.45. The existing campaign cap remains $35, including earlier runs. No additional allocation or duplicate uncertain submissions are implicit in this protocol.

## Reproduction

The JSON files freeze all prompts, seeds, order, budgets and parameters. `scripts/ltx_sustained_trial.py` controls the guarded lease; `ltx_sustained_worker.py` executes the GPU queue; `sustained_collect.py` exports and validates; `fal_sustained.py` submits the twenty API pairs. Full local source dependencies are included. Credentials, account data and signed model/media URLs are deliberately excluded.

Offline checks (Python 3.12):

```sh
python3.12 -B -m unittest discover -s tests -p 'test_sustained_*.py'
python3.12 -B scripts/ltx_sustained_trial.py check --plan ltx-sustained-plan.json
```

Actual provisioning requires your own provider keys, private budget ledger and the plan's hash-pinned preparation archive/wheel. Do not run an unguarded GPU job or reuse an existing run journal. See [REPRODUCE.md](REPRODUCE.md) for preparation, guarded execution and free offline recomputation. The immutable preregistration remains available at commit `7e14d9e`; the final report preserves the registered inputs and discloses observation errors and telemetry limits.

Validation: `python3.12 -B -m unittest discover -s tests -p 'test_sustained_*.py'` passed all 17 tests; `python3.12 -B scripts/ltx_sustained_trial.py check --plan ltx-sustained-plan.json` passed. All 131 measured LTX outputs and 20 API outputs passed full audio/video decoding and profile checks; both warmups were verified separately. Archive and protocol hash inventories permit independent byte verification.
