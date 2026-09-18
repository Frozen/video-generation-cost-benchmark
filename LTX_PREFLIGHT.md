# LTX-2.5: self-hosted smoke test

Status checked September 18, 2026, approximately 04:39 UTC: **not launched**.
No LTX video or timing result exists. No GPU or network volume is running.

## Access resolved and launch contract pinned

The operator subsequently accepted the model gate and supplied a read token
under the existing name `FACE_API`. Authenticated HEAD requests to all six
selected files returned HTTP 302 with the expected object sizes and SHA-256
ETags. Credentials are not published or passed in process arguments.

The launch code is now in [ltx_trial.py](scripts/ltx_trial.py) and the on-Pod
[worker](scripts/ltx_worker.py); [ltx_config.py](scripts/ltx_config.py) pins the
model manifest, native source and container. The source commit is
`a95ab856bf29407b6b066ede0abe1846050db56c`; the official PyTorch image's linux/amd64
digest is `sha256:4d1721e62b56d345c83b4fd6090664be6daf9312caab5b2e76f23d8231941851`.

Native code uses an **8-step first stage plus a 3-step refinement stage**,
ancestral stage-1 sampling and deterministic stage 2. DiffVAE uses the native
`chunked_eager` mode with the recommended NATTEN wheel. The current upstream
dependency configuration selects PyTorch 2.13/CUDA 13.2, so it cannot simply
reuse the template's preinstalled torch 2.8. Dependency installation is an
explicit part of this first rental. Freeze the installed dependency versions
and retain the setup cost; do not call the environment fully prebuilt for LTX.

A refreshed one-H100 Secure/CUDA-13.2 catalog read found `LOW` availability in
**CA-MTL-1** at USD 3.49/hour. Request 200 GB temporary disk and at least 128 GB
system RAM. No persistent volume is part of this attempt.

**No warmup or additional output is scheduled.** The first native Python
pipeline request includes its lazy per-stage weight loading, initialization
and first-use kernel costs. Measure client launch through completed download;
also measure processing through completed MP4 encoding and individual stages.
This is a cold first-request diagnostic, not an equal-warmth latency comparison
against the already warmed H3 service. No successful GPU execution is claimed
by the offline checks.

## Scope

The operator requested an LTX-2.5 test on the same GPU family, a results report,
and shutdown afterward. The first candidate is **one H100 SXM 80 GB**, not the
four-H100 topology used for H3. This is a new lease; the H3 leases are closed.
Successful execution, memory fit and latency on one GPU remain unverified.

Use the official **LTX-2.5 distilled BF16** checkpoint and native `ltx-pipelines`
two-stage pipeline. Do not substitute LTX-2.3, a fal-only variant, a community
LoRA or a four-step schedule. Record both stages and decoding in the timing;
the distilled model's eight-step description is not a complete cost boundary.

Planned first request, subject to native CLI validation before allocation:

- One P01_EN text-to-video request, seed 42, with native audio.
- Preserve the existing prompt and its English-only suffix; do not enable
  prompt enhancement. Prompt SHA-256:
  `9c924c21f39702c03de5287bb3307e1b6df82303b9e6d352704e7fa7a91a96a7`.
- Target five seconds: 121 frames at 24 fps, approximately 5.0417 seconds of
  native video; 1344 x 768 canvas. This matches the previous self-host canvas,
  not exact 16:9. Do not trim or re-encode the original artifact.
- Keep the existing 15-second request-to-download target and cost normalization
  by five requested video-seconds. Also report native duration separately.
- This is a diagnostic cross-model comparison, not an API-equivalent pair,
  quality ranking, load test or production SLA.

Export the original MP4, full-decode check, hashes, pinned versions, hardware,
memory samples, setup time, generation time, encoding/download time, and total
paid lease window. Separate compute-only USD/video-second from whole-rental
USD/video-second. Preserve failure costs. Shut down and verify resource absence
after export, or at the bounded deadline if the attempt cannot complete.

## Initial access blocker (resolved above)

The official model metadata is public, but its weight downloads are gated:

- Repository: `Lightricks/LTX-2.5`.
- Observed revision: `5e6e71018ee1756ed329b697a7b4aedc934dfce9`.
- Hugging Face metadata: HTTP 200, `gated: auto`.
- Anonymous HEAD for the BF16 distilled transformer: **HTTP 401**.
- No HF token found in the configured credential file, standard process
  variables, or the default local Hugging Face token-cache path.

The operator must review and accept the access conditions on the
[official model page](https://huggingface.co/Lightricks/LTX-2.5), then place an
appropriately scoped read token in the ignored credential file as `HF_TOKEN`.
That page also asks for contact-information sharing/marketing consent; the
operator makes that choice, not the benchmark runner. Never publish the token.
Verify authenticated access to every selected file before renting a GPU.
Do not bypass the gate through mirrors.

The current model card lists a split pack: transformer, Gemma4 text encoder,
video decoder, audio decoder, duration head and the **LTX-2.5** spatial upscaler
`latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors`.
Pin and validate the exact file manifest and native source before launch; older
recipes referencing an LTX-2.3 upscaler must not silently replace this pack.

## Hardware and spending admission

A live Runpod catalog read for one H100 SXM, Secure Cloud, CUDA >= 12.8 returned
`availability: HIGH` globally, and **USD 3.49/hour** compute. Per-data-center
stock was `LOW`. This is catalog stock, not proof of a successful allocation.
Storage is additional; recheck the actual Pod quote before starting it.

Two closed H3 leases now have provider-reported usage charges:

| Completed lease | Previous window estimate | Observed provider usage charge |
|---|---:|---:|
| H3 Base / four H100 / attempt 001 | USD 3.922011 | USD 3.914204922039062 |
| Failed acceleration / four H100 / attempt 001 | USD 3.038084 | USD 3.03625429677777 |

Scoped billing reads cover both full known lease windows. Both Pods were
independently rechecked and returned 404. Exact charge evidence is retained
privately; the admission ledger rounds upward to cents. These are usage
charges, not a tax invoice. Other unreported charges retain their reservations;
an empty billing response is not a zero-dollar charge.

After reconciliation, total settled-plus-reserved exposure is **USD 17.16**
within the unchanged USD 25 cap. **USD 5.34** remains admissible for new compute,
with USD 2.50 separately protected for closeout. This is not the account balance.

Target a **USD 4 maximum additional reservation** for this single-GPU smoke
test, including preparation and storage, with a lease deadline of no more than
one hour and verified local/remote shutdown guards. No LTX reservation or
allocation has been made. Do not consume closeout headroom or silently add API
calls, replicas, retries, persistent storage, or another GPU.

## Remaining launch checks

1. Operator grants Hugging Face access; authenticated file checks pass.
2. Pin the native code, container, weights and complete generation settings.
3. Validate the native launch command, memory strategy, artifact export and
   deadline cleanup locally as far as possible before allocation.
4. Recheck quote/capacity and reserve the whole bounded commitment.
5. Generate, export, report and terminate; verify the resource is absent.

Sources: [official model card](https://huggingface.co/Lightricks/LTX-2.5),
[native pipeline documentation](https://docs.ltx.io/open-source-model/integration-tools/pytorch-api).
Live account/catalog/billing checks above used authenticated Runpod MCP reads.
