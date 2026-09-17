# Execution preflight

Version 0.7, September 17, 2026. **No paid pilot runs or generation results.**
The USD 25 total cap remains unchanged. The active scope is one API-matched pair,
not the superseded three-model/12-attempt VBench experiment.

## Current requirements before any paid run

1. Select the exact fal.ai endpoint/variant and corresponding self-host weights,
   license and workflow. Document matched, different and unknown properties.
   A shared family name is not proof of implementation equivalence.
2. Freeze realistic English requests, permitted input assets, payload mappings,
   output profiles and human acceptance criteria. The endpoint and requests
   have not been selected; do not fall back to the old VBench scenes.
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

The current suite is deliberately a **planning-only contract**, with no selected
endpoint, requests or scheduled attempts. The validator reports not ready;
it does not independently verify credentials, provider controls or matching.
The repository does not yet contain an execution runner. Filling placeholders
or passing offline tests must not be mistaken for execution authorization.

## Prior access observations — not a new infrastructure check

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
