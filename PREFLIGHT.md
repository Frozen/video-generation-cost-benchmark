# Execution preflight

Planning baseline v0.8.1, September 17, 2026. **One fal reference completed;
self-host preflight remains open.** See [RESULTS.md](RESULTS.md).
The USD 25 total cap remains unchanged. The active scope is one API-matched pair,
not the superseded three-model/12-attempt VBench experiment.

The operator subsequently confirmed funding on both services and authorized the
single fal reference to proceed independently. [REFERENCE_RUN.md](REFERENCE_RUN.md)
supersedes the whole-pair sequencing gate for that one API call only. Runpod gates
remain required before renting a GPU; no switch to budget hardware was approved.
The later approved [variant comparison](VARIANT_COMPARISON.md) added one Max and
one Turbo API request; both are complete. There are now three outstanding USD 1
reservations until invoice reconciliation, not USD 3 of confirmed expenditure.

## Launch checklist and ownership

The endpoint, GPU count/type, serving framework, latency target, total budget and
first-pair sequence are documented. Selecting them is not a completed deployment.

| Remaining item | Owner | Completion evidence |
|---|---|---|
| fal.ai account/key and usable credit | Operator supplies access; agent verifies it | Authenticated access and a bounded reference request price |
| Runpod API key for CLI/SSH setup and programmatic lifecycle control | Operator supplies access; agent verifies it | Authenticated control-plane access and working SSH setup; MCP OAuth alone is not a CLI credential |
| One English prompt from the selected H3 collection | Agent | Frozen text/hash, source/author, reuse record and five-second suitability |
| Reproducible self-host deployment and test runner | Agent | Checkpoint/runtime/container pins, host requirements, payload mapping, output/timing capture |
| Whole-pair cost reservation, independent rental deadline and export | Agent | Reviewed bounded execution plan, durable reservation and verified shutdown mechanism |

Use [.env.example](.env.example) as a blank template; store real credentials in
ignored `.env.local` or environment variables. Never paste keys into chat, commit
them, or include them in public reports. Existence of a key is not proof of valid
permissions, balance or working inference. The template itself does not load keys.

The initial comparison is two five-second outputs, fal.ai first and self-host
second. Setup/warmup are separately recorded and charged. Optimization and load
testing remain deferred, even if the budget has room. The API prompt and one-call
scope were frozen under the addendum; the self-host schedule remains unfrozen.

## Requirements for the remaining paired/self-host work

1. The reference is selected: `minimax/h3/text-to-video`, ordinary H3 at 768P.
   Verify the candidate MiniMax H3 Base FL2VA weights, license and workflow.
   The hardware/runtime candidate is 1 x B300 with SGLang Diffusion; exact
   version pins, host allocation, capacity and implementation matching remain open.
   Document matched, different and unknown properties.
   A shared family name is not proof of implementation equivalence.
2. Freeze realistic English requests, permitted input assets, payload mappings,
   output profiles and human acceptance criteria. The H3 discovery collection is
   selected, but the exact request has not been frozen;
   do not fall back to the old VBench scenes. The selected request settings and
   first-test sequence are recorded in [START_HERE.md](START_HERE.md).
3. Pin current prices and published claims. Quote both the API reference and
   self-host work, including setup, failures, storage, fees and closeout.
4. Verify access to both services without exposing credentials. Funding Runpod
   does not establish fal.ai access. Do not assume any prior OAuth/API key works
   for a new provider or interface.
5. Establish an independent bound on GPU rental and a known bounded API price.
   Verify download/export and final cancellation/billing behavior.
6. Freeze the attempt count, short/long profiles, run order and upper-bound
   exposure. Baseline batch/concurrency are 1; any load or optimization test
   needs a separate bounded configuration and allocation.
7. Publish the reviewed executable-plan revision and reserve the entire
   commitment within USD 25 before launch.

The 1:3 interactive target still means request submission through final download:
15 seconds for a planned 5-second clip, 30 seconds for a 10-second clip.
VBench and its 5-second evaluator boundary are not first-stage launch requirements.

The current suite is deliberately a **planning-only contract**: the endpoint and
baseline settings are selected, but requests and paid attempts are not scheduled.
The validator reports reference and candidate selection separately from execution readiness;
it does not independently verify credentials, provider controls or matching.
The separate reference runner implements the API-only addendum, not self-host
deployment. Filling placeholders or passing offline tests is not authorization
to rent hardware or submit additional generations.

## Prior access observations — not a new infrastructure check

### September 17 credential preflight

The operator supplied separate fal.ai and Runpod credentials. Read-only checks
authenticated successfully against fal's pricing API. Its generic endpoint rate
was USD 0.05 per billing second; this is **not** the selected 768P quote and does
not replace the documented resolution-specific rate of USD 0.06/second.
The account-billing read returned HTTP 403 (insufficient permission), so fal
credit availability remains unverified. Do not mistake missing billing scope for
an invalid inference key or assume that funding Runpod also funds fal.

The supplied Runpod key returned HTTP 401 from both the hosted MCP service and
the direct v2 Pod listing. The direct response reported an invalid or expired
token. Replacement/rechecking is required; prior MCP OAuth success does not
validate a newly supplied API key. No generation was submitted, resource created
or credential published during these checks.

Recheck with the read-only helper (requires Python 3 and curl):

```bash
python3 scripts/check_access.py --env-file /absolute/path/to/.env.local
```

`--provider fal` or `--provider runpod` restricts the checks. The helper accepts
`FAL_KEY`/`FAL_API` and `RUNPOD_API_KEY`/`RUNPOD_API`; it never sources the file,
prints key values, follows redirects, retries requests, provisions resources or
submits inference. Keys travel only in HTTPS authorization headers; curl receives
them through stdin rather than process arguments. Raw error bodies, account
identity and resource IDs are suppressed. Balance amounts, when readable, are
private operational data: do not commit the command's output.

Exit code 0 means the selected primary access probes succeeded, **not** that all
launch gates passed. In particular, inspect `fal_balance` separately. A valid key
and passing offline tests do not establish funding or execution readiness.

### Earlier observations

On the earlier September 15–16 inspection, hosted Runpod MCP read-only Pod and
network-volume listings worked and were empty; this was not a balance check.
A separate CLI API key was not configured in the checked locations. MCP OAuth
alone did not provide a CLI key. These are dated observations, not a fresh
verification of current access or balances.

The earlier public-video catalog inspection found no endpoint for the requested
latest H3/LTX/Wan candidates. That observation does not select the new fal.ai
reference or establish that self-hosting is impossible. Current access,
availability and prices must be checked for the selected pair.

## Runpod CLI: documentation and executable disagree

The official [Pod command documentation](https://docs.runpod.io/runpodctl/reference/runpodctl-pod)
lists `--stop-after` and `--terminate-after`. However, the official Darwin arm64
binary from [release v2.14.0](https://github.com/runpod/runpodctl/releases/tag/v2.14.0)
was downloaded and checked directly:

```text
SHA-256: 5818914c30e5a2bfa5d0f0d54a2b2fbeceac7880e785c972475afc34524e764d
runpodctl --version: runpodctl 2.14.0-dd55bcf
runpodctl pod create --help: neither deadline flag is listed
runpodctl create pod --help: neither deadline flag is listed
```

The matching [new-command source](https://github.com/runpod/runpodctl/blob/v2.14.0/cmd/pod/create.go)
and [legacy source](https://github.com/runpod/runpodctl/blob/v2.14.0/cmd/pod/createPod.go)
also do not register these flags. `--wait-timeout` is an observation timeout:
the help explicitly says that the Pod is kept after a timeout. It does not bound
the rental duration. No create command was executed to test this.

This finding is specific to the inspected version and interface, not a claim
that Runpod can never schedule deletion. A separate supported mechanism would
need its own verification before it can satisfy the budget guard. In particular,
a field mentioned in another SDK is not proof that the provider enforces it.

This CLI evidence is retained from the earlier preflight; it was not rerun as
part of the methodology update. Revalidate the chosen launch mechanism before
paid execution. Do not reserve or spend money on an unbounded Pod.
