# Execution preflight

Checked 2026-09-16. **No generation results; no paid resource was provisioned for
this pilot.** The USD 25 total ceiling and the three-model objective are unchanged.
This note is not a successful GPU deployment or a measured cost report.

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

## Access and launch requirements still open

- Hosted Runpod MCP access works for read-only Pod and network-volume listing.
  These listings were empty at inspection. They are not a billing balance check.
- A separate CLI API key is not configured in the checked environment or normal
  saved configuration locations. OAuth authentication of MCP alone does not give
  the CLI a key. Obtain a key in [Runpod settings](https://console.runpod.io/user/settings)
  and configure it locally; do not paste it into an issue, this repository or chat.
- The exact latest-model profiles, native output durations, runtime/checkpoint
  pins, bounded exposure and artifact export are not yet validated.
- The latest Wan candidate remains the vendor's [Wan 3.0 API](https://www.alibabacloud.com/help/en/model-studio/text-to-video-guide).
  Access to an additional provider is not established by funding Runpod.
  Wan 2.2 open weights are a different candidate and require an explicit scope
  decision, not a silent fallback.

The next execution step requires the missing access and a verified bounded
launch path. Until then, leave the 12 scheduled attempts as `not_run`, retain all
unresolved profile fields, and do not reserve or spend money on an unbounded Pod.
Neither this preflight note nor the offline test suite completes the experiment.
