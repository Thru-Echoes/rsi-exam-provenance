# Result reconciliation status

**Status:** primary direction and record denominators reconciled; Opus block 1 is reward-receipt-bound, while block 2--3 receipt binding and secondary analysis still block numerical freeze and public release.

## Canonical evidence currently present

| Stage | Planned blocks | Endpoint table | Record table | Current readable result |
| --- | ---: | --- | --- | --- |
| Haiku | 4 | present | present | 2 instrument-favoring, 2 helper-favoring; mean difference -0.0186 |
| Sonnet | 3 | present | present | 1 instrument-favoring, 2 helper-favoring; mean difference -0.0171 |
| Opus | 3 | missing; block 1 capsules and pre-probe summary present | present | 0 instrument-favoring, 3 helper-favoring; approximate mean difference -0.1441 from mixed-precision inputs |

The generated paper result supports the ten-block primary direction count: 3 instrument-favoring and 7 helper-favoring blocks. It parses seven blocks from machine-generated endpoint tables, Opus block 1 from committed capsules that bind each `verifier/reward.json` by SHA-256, and Opus blocks 2 and 3 from a committed pre-probe summary. The latter two values are rounded and not raw-receipt-bound, so the stage direction is usable in the working paper while its aggregate numerical value remains provisional.

The complete per-trial record tables contain 20 started trials and 18 verified records: 9/10 in the instrument arm and 9/10 in the helper arm. The two failures are explicit `submitted_not_snapshotted` outcomes.

## Conflicts to resolve

1. **Opus receipt completeness:** block 1 reward values and receipt digests are committed in capsules, but block 2--3 raw reward receipts, the endpoint table, spend, sealed-summary, and complete secondary tables are absent from the merged tree. A later unmerged remote branch contains all six shadow-replay reports and three sealed-retrospective reports; these are recovery candidates, not admitted paper evidence.
2. **Test count:** older notes cite 369 or 410 tests; generate a fresh receipt from the frozen submission commit.
3. **Causal language:** observations compatible with a confirmation-cap mechanism must not be rewritten as an established cause.
4. **Working-note conflicts:** `15/16` and “every instrument record” are superseded for this paper by the generated 18/20 and 9/10-per-arm result; the older prose should remain visibly historical rather than silently treated as canonical.

## Freeze procedure

1. Recover or regenerate the block 2--3 raw Opus reward receipts and secondary tables from the original job directories using the committed scripts and manifest; separately review the later unmerged branch inventoried in `../unmerged-opus-recovery-audit.md` before admitting any of its reports.
2. Re-run `src/execution/build_paper_results.py`; replace summary-backed Opus rows only when stronger sources are available.
3. Verify trial identities, block assignment, missing-reward handling, record outcomes, and every aggregate against the preregistration.
4. Hash every paper-critical input and output and update `evidence/snapshot-manifest.json` at the frozen commit.
5. Run the full test suite and static analysis; save receipts.
6. Update C03 and the manuscript only from the frozen generated result.
7. Obtain joint approval for claims, authorship, anonymity, license, and public release.
