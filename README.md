# Video generation cost benchmark

Reproducible, budget-capped pilot for **MiniMax H3, LTX and Wan** using unchanged
official VBench prompts. [Методика тестирования на русском](METHODOLOGY.md).

**Status: preflight, no generation results yet. Total spending ceiling: USD 25,
including setup, failed attempts, generation, evaluation and storage.**

The pilot targets two scenes × two durations (approximately 5 and 10 seconds) ×
three models: **12 attempts**, four per model. All videos are reused for cost,
latency, manual review and six VBench scorer checks. This is not an official VBench
score, a leaderboard submission, or a statistically reliable quality ranking.

## Latest does not mean latest open weights

Checked against primary sources on 2026-09-15:

| Family | Candidate | Release/access distinction |
|---|---|---|
| H3 | MiniMax H3, Base FL2VA for text-to-video | [Official open release](https://www.minimax.io/news/minimax-h3-open-source); exact checkpoint revision is not frozen yet. |
| LTX | LTX-2.5 distilled | [Official checkpoint](https://huggingface.co/Lightricks/LTX-2.5); fast open-weight configuration, not a claim about every LTX-2.5 API tier. |
| Wan | Wan 3.0 video | [Current vendor API documentation](https://www.alibabacloud.com/help/en/model-studio/text-to-video-guide). Open T2V weights found in the [official organization](https://huggingface.co/Wan-AI) remain in the Wan 2.2 family. These are not interchangeable. |

The interpretation of "latest" for Wan needs to be resolved before paid execution.
Do not replace Wan 3.0 with Wan 2.2, H3 with Hailuo 2.x, or LTX-2.5 with an older
release simply because an endpoint is cheaper or already available.

On 2026-09-15 the connected Runpod live public-video catalog returned 20 entries,
with no H3, LTX-2.5 or Wan 3.0 entry. This is a catalog observation, not a claim
that self-hosting is impossible. No paid requests were made for this inspection.
Model access, exact profiles, runtime pins and teardown must pass preflight.
The [execution preflight](PREFLIGHT.md) records a verified CLI/documentation
discrepancy: the tested Runpod CLI 2.14.0 has no automatic stop/termination flags.
Do not treat a documentation example or a local ledger as an enforced lease limit.

## Files

- [METHODOLOGY.md](METHODOLOGY.md): preregistered design, costs, quality and stopping rules.
- [suite.json](suite.json): exact prompts, planned attempts and unresolved profiles.
- [pilot-plan.csv](pilot-plan.csv): the 12 scheduled attempts, all initially `not_run`.
- [SOURCE.md](SOURCE.md): upstream attribution and verification.
- [PREFLIGHT.md](PREFLIGHT.md): verified launch blockers and the next access steps.
- [scripts/validate.py](scripts/validate.py): source, schedule and publication checks.
- [scripts/budget.py](scripts/budget.py): fail-closed reservation ledger; not a provider spending cap.
- [tests/test_budget.py](tests/test_budget.py): boundary and failure tests.

Run offline checks (no GPU, credentials or paid APIs required):

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
git diff --check
```

## Before any paid run

Freeze all model profiles, confirm access, quote an upper bound including tax and
storage, configure an independent provider-side stop/termination deadline, verify
artifact export, and reserve the entire exposure in the local ledger. A reservation
alone cannot stop a provider from charging. If bounded execution cannot be established,
**do not provision a billable resource**.

Ledger amounts round exposure upward to cents; keep precise provider billing as the
authoritative cost record. Never settle a request to zero because a poll timed out:
its reservation remains outstanding until its final state and charges are verified.
`validate.py --ready` checks that preflight evidence fields have been filled; it cannot
independently prove that a provider will enforce the declared limit.

Do not commit credentials, account identifiers, raw billing exports, payment details,
signed URLs or private logs. Publish only reviewed, redacted evidence and intentional
video artifacts. Upstream materials retain their original [license](source/LICENSE).
