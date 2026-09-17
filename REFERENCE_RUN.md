# P01: first fal reference attempt

**Completed:** one reference downloaded in 102.644 s; see [RESULTS.md](RESULTS.md).
Do not run `submit` again. The USD 0.30 generation calculation is corroborated by
provider billable units, but invoice reconciliation is pending.

September 17, 2026. This execution addendum supersedes the v0.8.1 requirement to
finish self-host readiness before the first API call. The operator explicitly
authorized one fal test now and confirmed funding on both providers. The full
paired experiment remains incomplete; `suite.json` describes the earlier paired
planning contract, not authorization to provision Runpod.

## Frozen scope

- One submission to `minimax/h3/text-to-video`: 5 seconds, native 768P, 16:9,
  seed 42, prompt expansion disabled, safety checker enabled, `sync_mode: false`.
- No reference media or external soundtrack. No API/model fallback implemented.
- Source: [Chef Slicing Cartoon Onion](https://awesomevideoprompts.com/en/prompts/2085162073810739210-chef-slicing-cartoon-onion),
  attributed to cocktail peanut, August 6, 2026. Text is used without rewriting.
  This is a creator-style live-action/animation comedy request, not a claim of
  statistical representativeness or a measured popularity ranking. Its multiple
  action beats may compress poorly into five seconds; judge adherence explicitly.
- The collection's [About page](https://awesomevideoprompts.com/en/about) offers
  prompts free to use. No standalone republication license was verified. Keep
  full prompt text and raw input private; publish provenance and hashes only.
- Generation price checked on the [endpoint page](https://fal.ai/models/minimax/h3/text-to-video):
  USD 0.06/output-second at 768P, hence USD 0.30 for this request. The generic
  pricing API's USD 0.05 is not the 768P tier. Reserve USD 1 locally for this
  commitment including uncertainty; this is headroom, not a provider-enforced cap
  or an instruction to spend USD 1. Reconcile the actual charge afterward.
- Client submission attempts: one. Set `X-Fal-No-Retry: 1` to disable the queue's
  automatic retries. Set a 120-second time-to-start deadline; this is not a total
  inference-time cap. Stop collecting after 15 minutes without creating another
  request; retain the outstanding reservation if its billing is unresolved.
- Record submission through final download. Acceptance target: at most 15 seconds.
  Polling interval: 2 seconds; report client polling/download overhead, not just
  provider inference timing. Visual/audio and prompt review are separate gates.

## Safe execution

The runner freezes a private payload and manifest before submission. A unique
budget reservation and durable submission marker prevent accidental repeat calls.
It never provisions resources, enables top-ups or starts further experiments.
Private raw responses, request identifiers and signed URLs stay ignored. The
operator subsequently approved publishing the generated MP4; a hash-identical
copy is stored with the public results, without private API metadata.

```bash
python3 scripts/fal_reference.py prepare
python3 scripts/fal_reference.py submit --env-file /absolute/path/to/.env.local
# If collection is interrupted, resume the same request, never resubmit:
python3 scripts/fal_reference.py collect --env-file /absolute/path/to/.env.local
```

Review the prepared manifest before paying. `prepare` refuses to overwrite frozen
input. `submit` refuses a pre-existing submission marker. An ambiguous submission
requires checking provider history, not deleting the marker and trying again.
The ledger is not settled from a price estimate: billing evidence is required.

## Self-host decision remains unchanged

The selected next candidate remains **1 x B300 with SGLang Diffusion**. The operator
explicitly declined switching this pilot to a budget GPU. Cheaper cards are future
options, not current work. No Runpod rental is authorized by this API-only step;
its deployment, access, full quote and independent shutdown gates remain open.
The overall experiment cap stays USD 25. No daily spending allowance, optimization,
10-second clips or repetitions are added by this addendum.
