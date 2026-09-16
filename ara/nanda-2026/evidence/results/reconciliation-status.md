# Result reconciliation status

**Status:** primary direction and record denominators reconciled; raw Opus receipt binding and secondary analysis still block numerical freeze and public release.

## Canonical evidence currently present

| Stage | Planned blocks | Endpoint table | Record table | Current readable result |
| --- | ---: | --- | --- | --- |
| Haiku | 4 | present | present | 2 instrument-favoring, 2 helper-favoring; mean difference -0.0186 |
| Sonnet | 3 | present | present | 1 instrument-favoring, 2 helper-favoring; mean difference -0.0171 |
| Opus | 3 | missing; pre-probe summary present | present | 0 instrument-favoring, 3 helper-favoring; approximate mean difference -0.144 from rounded inputs |

The generated paper result supports the ten-block primary direction count: 3 instrument-favoring and 7 helper-favoring blocks. It parses the first seven blocks from machine-generated endpoint tables and the final three from a committed pre-probe summary. The Opus values are rounded and not raw-receipt-bound, so their direction is usable in the working paper while their exact numerical values remain provisional.

The complete per-trial record tables contain 20 started trials and 18 verified records: 9/10 in the instrument arm and 9/10 in the helper arm. The two failures are explicit `submitted_not_snapshotted` outcomes.

## Conflicts to resolve

1. **Opus receipt completeness:** the primary summary is committed, but raw reward receipts, endpoint, spend, sealed-summary, and complete secondary tables are absent.
2. **Test count:** older notes cite 369 or 410 tests; generate a fresh receipt from the frozen submission commit.
3. **Causal language:** observations compatible with a confirmation-cap mechanism must not be rewritten as an established cause.
4. **Working-note conflicts:** `15/16` and “every instrument record” are superseded for this paper by the generated 18/20 and 9/10-per-arm result; the older prose should remain visibly historical rather than silently treated as canonical.

## Freeze procedure

1. Recover or regenerate the raw Opus reward receipts and secondary tables from the original job directories using the committed scripts and manifest.
2. Re-run `src/execution/build_paper_results.py`; replace summary-backed Opus rows only when stronger sources are available.
3. Verify trial identities, block assignment, missing-reward handling, record outcomes, and every aggregate against the preregistration.
4. Hash every paper-critical input and output and update `evidence/snapshot-manifest.json` at the frozen commit.
5. Run the full test suite and static analysis; save receipts.
6. Update C03 and the manuscript only from the frozen generated result.
7. Obtain joint approval for claims, authorship, anonymity, license, and public release.
