# Sources and attribution

## Active request selection

The v0.8.1 API-matched pilot uses realistic requests for the chosen H3 endpoint, not
the earlier VBench subset. The selected discovery collection is
[Awesome Video Prompts: MiniMax H3](https://awesomevideoprompts.com/en/models/minimaxh3).
The first English text-only request is frozen in [REFERENCE_RUN.md](REFERENCE_RUN.md),
with source/author and reuse notes. No input media is used, and no explicit longer
duration is specified in its source text. Its fast comedy sequence may challenge
five-second adherence, which remains a review question rather than an assumed pass.
The full unchanged prompt remains private; [the result](results/P01_FAL_5S_001.json)
records its SHA-256 and the serialized payload SHA-256.

Before selection, record the exact source page, retrieval date, attribution and
reuse/asset permissions. Record the relevant customer use case and why the request
is representative; inclusion in a curated collection is not evidence of popularity.
Freeze the final English prompt and input-asset hashes before paid runs, using
the same logical request on the API and self-host sides.

Provider documentation and published performance claims need their own source
URLs, dates and conditions in [CLAIMS.md](CLAIMS.md). A cited provider claim is not
an independently measured result. Do not publish private chat screenshots or quotes.

## Retained VBench provenance — historical, not active

The unmodified metadata, prompt README and Apache-2.0 license in `source/`
come from [Vchitect/VBench at fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490](https://github.com/Vchitect/VBench/tree/fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490).

`source/VBench_full_info.json` SHA-256:
`5dd2de80ee43cda750b2b72ea7023657c0b90d3702041c7e4608c65dbe50dccd`.

The previous v0.6 protocol selected unchanged prompts at zero-based indices 262
(S01, coffee) and 29 (S02, bowl on a kitchen counter), replacing index 823
(S05, kitchen) before any generation. Those local scene IDs, sampling choices
and acceptance rules were not official VBench requirements. The old protocol and
schedule are retained in [Git history](https://github.com/Frozen/video-generation-cost-benchmark/tree/ee78f1f2ec20864139d4c0bda84e37e40938c4e2).

VBench remains deferred since v0.7. Retaining its assets does not schedule a VBench run,
require a 5-second evaluator boundary or imply official benchmark coverage.

Model weights are not redistributed. Check model licenses, service terms and
input-asset permissions before running or publishing artifacts. Public visibility
of locally authored material does not relicense third-party assets.
