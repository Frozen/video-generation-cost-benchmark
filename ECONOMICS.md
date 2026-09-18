# Our operator economics: measured inputs and explicit scenarios

This is our own cost model for the selected **5-second, native 768P H3 request**.
Do not import another worksheet's 10-second/1080p API price, RTX 5090 purchase
cost or assumed render time into this comparison. Runpod rental and owned-hardware
depreciation are different economic models.

**Measured fallback update, September 18:** one H3 Base request on four H100 SXM
GPUs completed in 83.462 s, after startup warmup, and failed the 15 s latency gate.
The primary reporting unit is **USD per requested video-second**. Request-window
compute is USD 0.060001/video-second (USD 0.300003 for the five-second request).
The whole allocation-window estimate including temporary disk is
USD 0.784402/video-second for this one-clip trial, USD 3.92 total.
These are not reconciled charges. Per-clip formulas below remain useful
intermediate calculations; divide by requested duration for the headline metric.
The English-only instruction makes it a distinct P01_EN request, not an exact
paired replay. [Full measured inputs and utilization scenarios](SELF_HOST_RESULTS.md).
The B300 scenarios below remain historical and unmeasured; do not substitute
the four-H100 runtime into the one-B300 hourly rate. GPU utilization at a sampled
instant is different from the fraction of paid wall time spent serving requests.

## Updated commercial reference: Max and Turbo measured

The later [variant comparison](VARIANT_RESULTS.md) changes the competitive picture:
H3 Max completed in **13.552 s** at a USD 0.20 promotional generation calculation;
H3 Max Turbo in **9.122 s** at USD 0.10. Both met the 15 s wait gate, but full
quality review remains pending. Listed non-promotional costs are USD 0.40 for Max
and USD 0.20 for Turbo. Net invoice reconciliation remains unverified.

Therefore USD 0.30 from standard H3 is not the only relevant commercial reference.
For a service that can deliver acceptable quality, test our cost against **Turbo's
USD 0.10 promotional and USD 0.20 non-promotional prices**, while retaining the same
15-second customer wait limit. Do not mistake the different post-trained model
for a verified replica of our open-base self-host candidate.

With the same optimistic assumptions as below (USD 7.89/h, 100% acceptance, zero
extra overhead), the economic price-parity thresholds become:

| Workload utilization | GPU service seconds at USD 0.10 parity | GPU service seconds at USD 0.20 parity |
|---|---:|---:|
| 100% | 45.63 s | 91.25 s |
| 75% | 34.22 s | 68.44 s |
| 50% | 22.81 s | 45.63 s |
| 25% | 11.41 s | 22.81 s |
| 10% | 4.56 s | 9.13 s |

These remain modeled thresholds, **not measured B300 times or an all-in cost**.
Use `scripts/economics.py --gpu-hourly 7.89 --reference-price 0.10 --accepted-fraction 1`
and repeat with `--reference-price 0.20` to reproduce them. All rental/runtime/quality
inputs for our own deployment remain unmeasured. The original base-model reference
and USD 0.30 scenarios below remain valid for that separate matched comparison.

## Original standard H3 reference and unmeasured self-host candidate

| Input | fal reference | Our selected self-host deployment |
|---|---|---|
| Configuration | `minimax/h3/text-to-video`, 5 s, 768P | H3 Base FL2VA, 1 x B300, SGLang Diffusion candidate |
| Sample count | 1 completed request | 0; no rented Pod |
| End-to-end wait | **102.644 s measured** | Not measured |
| Customer latency gate | At most 15 s; **failed** | Same gate, not measured |
| Generation cost | **USD 0.30** tariff and billable-unit calculation; net invoice unverified | Not measured |
| GPU-occupied time | Unknown; provider hardware hidden | Not measured |
| Hourly rental | Not applicable to API client | **USD 7.89/h dated catalog reference**, not an all-in quote |
| Accepted fraction | 0/1 under the latency gate; not an estimate of long-run acceptance | Unknown |
| Cost per accepted output | Undefined for this sample with zero accepted outputs | Unknown |
| Quality | Informal frame inspection only; blind review pending | Not measured |

**Current conclusion:** we have a real reference price and customer wait time.
We do **not** yet know whether our deployment is cheaper, faster, or profitable.
The 102.644 s API latency must never be inserted as the B300's runtime. A single
request does not establish a typical latency, acceptance rate or business outcome.

## Rental-cost formula

For on-demand Pods, the hourly compute rate is unchanged whether the GPU is
busy or idle. Setup and idle time consume the same paid rental window.
[Runpod bills compute per second](https://docs.runpod.io/pods/pricing): the
one-hour credit balance required to deploy is not a one-hour minimum charge.
At the USD 7.89/hour catalog rate, ten minutes is USD 1.315 in compute before
storage and any applicable fees. This is arithmetic, not our observed bill.

For this initial single-request, no-batching workload:

```text
C_accepted = ((R_gpu + R_other) * T_gpu / (3600 * u) + V_attempt) / q
price_headroom = P_reference - C_accepted
```

- `R_gpu`: actual aggregate GPU rental rate, USD/hour; include every GPU.
- `R_other`: separately billed hourly CPU/storage/serving overhead, USD/hour.
- `T_gpu`: measured mean GPU-occupied service seconds per attempt, including
  failed attempts and required pipeline work, not client-only download time.
- `u`: fraction of billed wall time used by that workload. This includes the
  cost of paid idle capacity; it is not a GPU-monitor utilization percentage.
- `V_attempt`: delivery and other per-attempt charges plus any explicitly
  allocated setup/startup overhead. Report the amortization denominator.
- `q`: fraction of attempts that jointly pass the agreed output, quality,
  prompt and latency gates. Zero accepted outputs means undefined unit cost.
- `P_reference`: the matched API's dated price, not guaranteed selling revenue.

Rent includes the provider's electricity costs: do not add a second electricity
charge unless actually billed separately. Likewise, do not add GPU purchase
depreciation to a rental bill. Experiment setup/API-baseline spending is reported
separately from steady-state self-host service cost. Actual experiment spending
still includes everything and must remain within USD 25.

`price_headroom` is not net profit. Fees, discounts, operations, demand, tax and
selling price need their own evidence before making profit or annual-revenue claims.
If batching is later approved, measure accepted completions per billed wall hour;
do not assume linear scaling from this single-request model.

## What speed would make GPU rental cheaper than the API?

These are **economic thresholds, not predicted B300 performance**. Inputs:
USD 7.89/GPU-hour, USD 0.30 per reference request, **100% acceptance assumed**,
zero additional overhead assumed. These optimistic scenarios are not all-in quotes.
At the boundary, GPU-only cost equals USD 0.30; faster service is cheaper.
The same assumptions and empty, unmeasured cost fields are available in the
[scenario CSV](results/ECONOMICS_SCENARIOS.csv).

| Workload utilization of paid time | GPU-occupied seconds per attempt at price parity |
|---|---:|
| 100% | 136.88 s |
| 75% | 102.66 s |
| 50% | 68.44 s |
| 25% | 34.22 s |
| 10% | 13.69 s |
| 5% | 6.84 s |
| 1% | 1.37 s |

The separate **15-second end-to-end latency gate still applies**. Being cheaper
in an economic scenario is not sufficient if the customer waits too long or the
output is unusable. Lower acceptance and extra costs reduce these thresholds.

Reproduce the assumptions and thresholds without inventing a runtime:

```bash
python3 scripts/economics.py --gpu-hourly 7.89 --reference-price 0.30 --accepted-fraction 1
```

Once self-host time and overhead are measured, pass `--service-seconds`,
`--other-hourly`, `--extra-per-attempt` and a supported `--accepted-fraction`.
Until then, cost and price-headroom output columns intentionally remain empty.
The CLI never spends money or launches requests.

## What the B300 test must add

Record the actual rental/host/storage quote; setup/warmup/idle/stop timestamps;
GPU-occupied service time and customer end-to-end latency separately; output
properties and review; and reconciled bills. Then fill our utilization table with
cost per accepted output and API-price headroom, including assumptions and omissions.
Do not upgrade, optimize or test budget GPUs before reviewing the selected baseline.

Our final decision will be one of: lower cost and acceptable latency/quality;
lower cost but unacceptable latency/quality; acceptable service but not cheaper;
or insufficient evidence. The current evidence remains in the last category.
