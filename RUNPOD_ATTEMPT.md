# B300 trial: provisioning rejected, inference not run

September 17, 2026. Attempt `P01_RUNPOD_B300_5S_001`.

**Historical attempt; not a permanent no-stock claim.** The September 18 UTC
follow-up again reports `LOW` for an Iceland B300. [CAPACITY.md](CAPACITY.md)
preserves both observations and the proposed hardware fallback. No second
allocation request has been submitted.

**Outcome: no self-host measurement and no new video.** Runpod rejected the
single provisioning request with HTTP 400 because the requested instance was
unavailable. A subsequent Pod listing was empty. No model inference or additional
fal request was submitted; no Pod or storage resource remains running.

## Requested configuration

| Setting | Submitted value |
|---|---|
| GPU | 1 x NVIDIA B300 SXM6 AC, 288 GB, Secure Cloud |
| Region | EUR-IS-1 (Iceland) |
| Host RAM filter | 384 GiB minimum, proposed rather than measured necessary |
| Container disk | 300 GB; no persistent or network volume |
| Host CUDA filter | 13.0 |
| GPU catalog rate | USD 7.89/hour, not a successful rental quote |
| Attempt reservation | USD 18 within the existing USD 25 experiment cap |
| Deadline | Two hours from launch preparation, including boot/setup/download |
| Access | SSH only; no public inference or Jupyter port |

Intended model: official H3 Base FL2VA, native BF16/FP32, eager execution,
50-point schedule, one frozen P01 prompt, seed 42, a requested five-second
768P clip. These inference settings were **not executed**.

## Evidence and cost

The provider's create response stated:

> There are no longer any instances available with the requested specifications.

The subsequent country-filtered GPU query (`countryCodes=["IS"]`, Secure Cloud,
one B300) returned top-level availability `NONE` and CUDA 13.0
`available=false`. Its nested EUR-IS-1 entry still said `LOW`. The broad global
catalog likewise said `LOW`. These conflicting catalog summaries are not proof
that a matching instance can be rented; the actual allocation request failed.

The host RAM filter was considered as a possible unnecessary restriction, but
the separate country-wide no-stock result gave no evidence that lowering it
would permit deployment. No second create request was submitted. No GPU, model,
or region was silently substituted.

- Incremental GPU/storage rental expense for this attempt: **USD 0**, based on
  rejected creation and the empty resource listing, not an invoice line item.
- The unused USD 18 reservation was settled at zero in the private admission
  ledger. Three earlier USD 1 fal reservations remain pending reconciliation.
- Existing fal tariff-derived generation total remains USD 0.60; its invoice
  reconciliation is still outstanding. No new API generation charges were added.
- GPU runtime, setup duration, request latency, peak VRAM, output quality and
  self-host cost per accepted clip are **not measured**. Do not fill them with
  zeros or infer them from fal's results.

## Reproducibility and shutdown preparation

Selected immutable artifacts:

- SGLang container: `lmsysorg/sglang@sha256:6bcaa47db52f78ce0d67863b8b2431221b79bc23204a80cad757fa819d00e921`.
- Corresponding SGLang source: `408d2334c34d387a36a26398dff9a8f004328344`
  (image tag `nightly-dev-cu13-20260917-408d2334`).
- H3 model revision: `42ed227ee7df40d41602854ae760620d6eb651fe`.

The lifecycle helpers are [runpod_trial.py](scripts/runpod_trial.py) and
[runpod_deadline.py](scripts/runpod_deadline.py). They are **not a completed
end-to-end inference runner**. The first helper reserves the whole rental,
records a private creation journal, starts a detached local deletion timer under
`caffeinate`, and submits only one create request. It refuses to overwrite an
existing attempt directory. Do not erase its journal to retry.

The submitted Pod environment contains **no account control key**; it uses Runpod's documented
[automatically provisioned Pod-scoped key](https://docs.runpod.io/pods/templates/environment-variables)
for the remote backstop. The account credential stays on the client and is sent
only in authorization headers to Runpod's control API.

The local guard did arm and exited after the allocation rejection. The embedded
remote guard verifies its own Pod identity before deletion and is intended to
survive client disconnection. **Remote boot, SSH access, deletion permission and
actual timed deletion were not verified**, because no Pod was allocated. The
guards are best-effort software controls, not a provider-enforced spending cap.
A control-plane outage or simultaneous client/Pod failure remains a risk.
An ambiguous creation response without a known Pod ID requires reconciliation;
it is not permission to repeat the create request.

## Next execution boundary

Recheck actual one-B300 capacity in the selected region before arranging another
bounded attempt. Preserve this failed-attempt journal and use a separately
reviewed admission entry for any future allocation. A different region requires
an explicit decision and license-applicability review; a different GPU/model
requires a separately identified configuration. License applicability remains
as recorded in [SELF_HOST_PREFLIGHT.md](SELF_HOST_PREFLIGHT.md), not newly certified.

On a successful allocation, first verify the hourly quote, host resources,
SSH and remote guard; then install the pinned diffusion dependencies, load the
pinned model, record setup separately, submit P01 once, export the original MP4
and evidence, and verify that the rental has been deleted. Stop if guard
verification fails; do not leave a paid Pod waiting for operator input.

Validation: `python3 -m unittest discover -s tests -q` passed 69 offline tests;
`git diff --check` passed. No GPU/SSH/inference integration test passed or was
possible in this attempt.
