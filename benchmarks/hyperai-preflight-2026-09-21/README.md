# HyperAI: capacity check, not a generation benchmark

HyperAI advertises an RTX PRO 6000 96GB tier for **$0.80/hour**, but the authenticated console marked every RTX PRO 6000 size **Full Load** at **2026-09-21 06:39:58 UTC**. No allocation or payment was submitted. **There are no new videos, measured runtimes, or video-cost results from HyperAI.**

This is a dated admission check, not a claim about future availability or provider-wide performance. The intended workload remains the [unchanged ten-request LTX-2.5 queue](../ltx-rtx-2026-09-20/evidence/resident.json), with two full warmups, used in the [measured Verda comparison](../ltx-verda-2026-09-21/DETAILS.md).

## Advertised configuration and availability

| Console tier | Hourly instance price | CPU cores | Total GPU memory | Host RAM | Disk | Console status |
|---|---:|---:|---:|---:|---:|---|
| `rtx-pro-6000` | $0.80 | 32 | 96 GB | 90 GB | 100 GB | Full Load |
| `rtx-pro-6000-2` | $1.60 | 64 | 192 GB | 180 GB | 200 GB | Full Load |
| `rtx-pro-6000-4` | $3.20 | 128 | 384 GB | 360 GB | 400 GB | Full Load |
| `rtx-pro-6000-8` | $6.40 | 256 | 768 GB | 720 GB | 800 GB | Full Load |

These are console specifications, not measurements from an allocated machine. GPU edition, power limits, native CUDA compatibility, free filesystem space, and model fit were not verified. The disk column does not establish a persistent-storage entitlement.

Evidence: [machine-readable observation](preflight.json), [resource menu, top](capacity-top.png), and [resource menu, bottom](capacity-bottom.png). Screenshots capture only the actual resource menu, excluding account identity and balance; the bottom image was captured after scrolling.

## Billing check and spending

The deposit form offered a **$5 preset** and displayed Stripe, but also stated **"Credit card deposits are currently unsupported"**. Payment-method viability was not tested: no checkout was opened, no coupon claimed, and no deposit, membership, storage subscription, or compute order submitted.

The authorized cumulative stage cap was **$5**, including preparation and all attempts. **Spending caused by this check: $0.** No paid resources were created. Zero spending is not a zero cost per video: no video was generated, so that metric is undefined.

Decision: do not fund the account solely for this unavailable tier. A future test needs a fresh capacity check, a working funding method, verified runtime/storage fit, and a cumulative spending guard before allocation. No cheaper-video claim is made from the advertised hourly rate.

Sources: [public pricing](https://hyper.ai/en/pricing), [authenticated console](https://app.hyper.ai/console), [storage and billing documentation](https://hyper.ai/en/docs/getting-started/quota-and-usage). The console requires the reader's own sign-in; no account-specific URLs or credentials are included here.
