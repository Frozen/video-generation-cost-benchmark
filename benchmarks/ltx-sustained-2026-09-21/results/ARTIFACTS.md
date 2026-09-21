# All original videos and replay inputs

[Download the complete evidence archive](https://github.com/Frozen/video-generation-cost-benchmark/releases/download/ltx-sustained-2026-09-21/ltx-sustained-evidence-20260921.zip).

- Size: 486,879,516 bytes (approximately 487 MB).
- SHA-256: `ed6134d00167897010dce28e896ab6505c1d1235d95883c4339fcab841b58dbf`.
- Videos: all 131 measured LTX clips, all twenty fal H3 Max Turbo references and both LTX warmups. No best-of selection.
- Integrity inventory: 484 files, including raw logs, exact inputs, pinned source archive and the complete report snapshot.

Extract the whole archive and open **`videos.html`**. Search by request ID, scene, model, prompt or seed. Each video links to an original MP4 and a `replay-inputs/<model>/<request-id>.json` containing its exact prompt, seed, generation profile and original file hash. The [CSV catalog](VIDEO_CATALOG.csv) and [JSON catalog](VIDEO_CATALOG.json) are also available directly in this repository; their media paths are relative to the extracted evidence archive.

For LTX, the profile pins source and weight revisions, container, resolution, frames, fps, native audio, BF16 precision, 8+3 schedule and decoder tiling. Follow [REPRODUCE.md](../REPRODUCE.md) to prepare the same environment and execute the registered inputs. The existing measured manifest preserves every seed in its original order. The fal replay records contain the exact endpoint and original API payload, but the hosted model's internal revision and effective seed are not independently exposed.

**Repeating an input is not a guarantee of bit-identical video on another GPU/runtime or a changed hosted model.** The original SHA-256 identifies the published artifact; it is not an acceptance threshold for reruns. The current experiment did not run a separate deterministic-replay test.

After extraction, run `python3 verify_evidence.py` to check every file against the inventory. The [analysis commands](../REPRODUCE.md#recompute-and-review-without-paying) recompute throughput and costs from the original event journal and receipts, without renting a GPU.

For masked human comparison, [download the separate forty-video A/B review](QUALITY_REVIEW.md). It includes all twenty preregistered pairs and starts without ratings. The all-video catalog reveals model names by design.
