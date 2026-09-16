# Sources and attribution

The unmodified VBench metadata, prompt README and Apache-2.0 license in `source/`
come from [Vchitect/VBench at fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490](https://github.com/Vchitect/VBench/tree/fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490).

`source/VBench_full_info.json` SHA-256:
`5dd2de80ee43cda750b2b72ea7023657c0b90d3702041c7e4608c65dbe50dccd`.

`suite.json` is a local derivative selecting two unchanged prompts. IDs S01/S02,
sampling, cost limits and acceptance criteria are local additions, not official
VBench requirements or an endorsement. Source indices are zero-based and meaningful
only at the pinned commit; upstream entries have no independent official IDs.

VBench original metric assignments remain in the unmodified metadata. Applying all
six custom-input scorers to both pilot scenes is a separate diagnostic protocol,
not a claim to reproduce those assignments or the official full score.

The selected indices are 262 (human drinking coffee) and 29 (bowl on a kitchen
counter). Version 0.6 replaces the unexecuted S05 / index 823 (`kitchen`) with
S02 / index 29, keeping the new prompt verbatim and preserving the old protocol in
Git history. Index 29's original assignment is `temporal_flickering`; that scorer
is not part of this six-dimension custom-input pilot. No official coverage claim
is inferred from selecting a prompt from that source group.

Model weights are not redistributed by this repository. Their vendors' licenses
and access requirements must be checked before downloading or running them.
Public visibility of locally authored material does not relicense third-party assets.
