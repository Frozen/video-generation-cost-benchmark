# Warmup, repeated prompts, seeds and caching controls

These controls were included in the registered workload before its first generation. This document makes their purpose explicit following the user's request; it does not change the running experiment or add paid requests.

## Does an hour make a video-second cheaper?

There are two different cost boundaries:

- **Warmed queue cost:** `(GPU + disk hourly rate) × actual queue hours / technically delivered output seconds`. A longer window does not automatically reduce this rate. The previous ten-request result already used a warmed resident model. This hour tests whether that throughput persists across twenty scenes and a longer operating interval, including any failed attempts.
- **Complete experiment cost:** all rental time, including allocation, installation, weight download, hash verification, warmup, generation and export, divided by delivered output. Producing more videos can amortize one-time setup costs. The hour costs more in total; its per-output setup burden can be lower. Both cost boundaries must be reported separately.

Warmup means loading weights, initializing the runtime and exercising the full pipeline. The two warmup requests are excluded from steady-state throughput, preserved as separate videos and included in full-lease spending. Keeping the transformer resident avoids reloading it between requests. It does not mean reusing a generated video.

The fal reference is priced per generated output, not by renting a GPU for an hour. All twenty responses reported eight billable units, or $0.10 per requested five-second clip at the observed unit rate. We do not control or observe fal's internal warmup. This experiment contains twenty fal requests, **not an hour of fal load**, and establishes no continuous-load discount or hourly API throughput guarantee.

## Exact workload and reuse policy

| Control | What this run does | What it establishes or limits |
|---|---|---|
| Video profile | Requested five seconds, 768p class, native audio, fixed generation parameters | Comparisons do not silently change duration, audio or precision |
| Scene set | Twenty scenes: three preserved prior prompts and seventeen benchmark-authored scenarios | Varied test content; not production traffic logs |
| Repeated prompts | Each cycle visits all twenty scenes in a preregistered shuffled order | Repeated measurements per scene without using one prompt for the whole hour |
| Primary seeds | 500 distinct cryptographically drawn 31-bit seeds in the frozen input pool | Every admitted primary request gets a new seed; the time limit determines how much of the pool is used |
| Warmup seeds | Two additional distinct seeds | Warmup outputs cannot be confused with selected measured outputs |
| Exact prompt + seed duplicates in the primary queue | None | No deliberate exact-input replay in the cost measurement |
| LTX/fal pairing | The first twenty primary LTX prompt/seed pairs are sent once to fal | Selection occurred before viewing outputs; equal seed integers do not imply equal latent noise across different models |
| Confirmed failure retry | Same original prompt and seed, new attempt ID with `retry_of` | Retry work is counted explicitly and cannot masquerade as a fresh sample |
| Uncertain timeout or lost response | Observe the original request; never blindly submit a replacement | Avoids duplicate paid work when completion is unknown |
| Intentional deterministic replay/cache experiment | Not executed in this run | Do not claim measured determinism or a server-cache hit rate from fresh-seed generation |

Every request ID, scene ID, prompt hash, seed and attempt relationship is preserved in the manifest and event log. Failures are not injected. If the measured failure count is zero, the retry policy remains an unexercised contingency, not evidence that real production retries never occur.

## What caching evidence is available?

For local LTX, output and prompt-embedding caches are disabled. Each successful request records the actual prompt-encoder/pipeline calls and eleven fresh transformer forwards, while the resident transformer build count remains one. This differentiates weight reuse from skipped generation. Output hashes and full decoding validate delivered artifacts; different hashes alone do not prove that no cache was used.

For fal, the client sends the registered fresh seeds and disables hidden retries. The provider does not expose its internal cache or return an echoed effective seed in these responses. Unique inputs and different output hashes are observable; independent proof of internal cache behavior or seed application is not available. We do not turn this limitation into a claim that caching occurred.

No test parameters were changed mid-hour in response to observed speed or output quality. All twenty selected pairs remain in the quality material, including the first fal pair affected by a client observation error.
