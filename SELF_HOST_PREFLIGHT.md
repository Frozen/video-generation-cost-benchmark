# Self-host preflight: H3 Base on one B300

September 17, 2026. **One allocation request rejected; no self-host Pod created
or inference submitted.** See the [attempt report](RUNPOD_ATTEMPT.md).
The three [fal samples](VARIANT_RESULTS.md) are complete; do not rerun them.
This is a readiness record, not a completed self-host benchmark.

## Operator declaration and license clarification

The operator states that this trial is being run personally, not on behalf of a
company, and that no separate MiniMax authorization has been obtained. The
operator's applicable location remains unconfirmed. The allocation request
selected Iceland (EUR-IS-1), but no deployment was allocated.
This declaration is not a legal determination or clearance for later company use.

The [H3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/LICENSE)
excludes the US, EU, UK and South Korea from its territorial grant. The license
defines the licensee as a natural or legal person; a personal test is not an
automatic exception. It also requires separate prior written authorization when
commercial products/services exceed USD 20 million in annual revenue.

MiniMax's [FAQ](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/docs/QA-about-License.md)
distinguishes hosted API access from open-weight deployment and links an
[authorization application](https://platform.minimax.io/h3-license). These sources
do not establish a price for separate authorization. Do not assume a company
automatically pays a higher GPU rate or that API access grants self-host rights.

Confirm applicability before deployment. A laptop timezone or a different GPU
region alone does not establish that all license conditions are met. Later
company deployment, customer access and output distribution need their own review.

## Confirmed technical state

- Replacement Runpod-key authentication succeeds: Pod probe HTTP 200 and
  `runpodctl user` success. Earlier HTTP 401 observations are historical.
- Selected candidate: 1 x B300, 288 GB, Secure Cloud, SGLang Diffusion, H3 Base
  FL2VA. Broad catalog observation: USD 7.89/hour, LOW availability in EU-NL-1,
  EUR-IS-1 and US-WA-2. The later Iceland-filtered query returned NONE, and the
  actual EUR-IS-1 allocation failed. No capacity is reserved or all-in quote established.
- The official H3 repository is readable without a gated-access request.
  Observed revision: `42ed227ee7df40d41602854ae760620d6eb651fe`.
  Model weights have not been downloaded; public availability is not license clearance.
- Total experiment cap: USD 25. Three USD 1 API reservations remain outstanding,
  leaving USD 22 of exposure headroom, not a claim of USD 3 actual expenditure.
  New compute must also preserve the USD 2.50 closeout reserve.

## Rental deadline: software backstops prepared, remote behavior unverified

The latest official CLI release remains v2.14.0. The inspected executable reports
`2.14.0-dd55bcf`; its `pod create --help` has neither `--terminate-after` nor
`--stop-after`. Its observation timeout leaves the Pod running.

The live [REST v2 specification](https://api.runpod.io/v2/openapi.json) exposes no
Pod create/update deadline field. GraphQL introspection was rejected with
`INTROSPECTION_DISABLED`; a deadline mentioned in an SDK is not proof of enforcement.
Runpod's [management guide](https://docs.runpod.io/pods/manage-pods) shows a
client-side delayed stop. A laptop timer alone does not cover laptop shutdown or
network loss, and stopped persistent storage remains billable.

The latest attempt armed a detached local deadline and embedded a second
deadline program in the proposed Pod startup, using only the Pod-scoped key.
The account control key was not passed into the Pod. Remote behavior remains
unverified because allocation failed. Container/source/model pins, the proposed
384 GiB RAM / 300 GB disk request and the released USD 18 reservation are recorded
in [RUNPOD_ATTEMPT.md](RUNPOD_ATTEMPT.md).

Capacity is the observed immediate blocker. Verify remote shutdown control, SSH,
the actual quote and export before inference on a future allocated Pod. Do not
represent software timers as a provider-enforced cap, silently replace H3 Base
with fal Max/Turbo, change the GPU plan or submit extra API requests.
