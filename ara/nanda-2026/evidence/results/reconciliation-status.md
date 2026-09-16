# Result reconciliation status

**Status:** blocking for numerical freeze and public release.

## Canonical evidence currently present

| Stage | Planned blocks | Endpoint table | Record table | Current readable result |
| --- | ---: | --- | --- | --- |
| Haiku | 4 | present | present | 2 instrument-favoring, 2 helper-favoring; mean difference -0.0186 |
| Sonnet | 3 | present | present | 1 instrument-favoring, 2 helper-favoring; mean difference -0.0171 |
| Opus | 3 | missing | present | six verified records; no canonical block result in this branch |

The committed endpoint tables therefore support a seven-block subtotal of 3 instrument-favoring and 4 helper-favoring blocks. A narrative handoff reports a ten-block total of 3 and 7. That total is plausible but is not canonical until the Opus endpoint table is generated, committed, and bound into the manifest.

## Conflicts to resolve

1. **A/B denominator:** ten planned blocks exist, but only seven have endpoint tables on the pinned branch.
2. **Record yield:** working notes contain `15/16`, “every instrument record,” and source tables that imply different denominators/outcomes. Recompute from the complete per-trial inventory and state the population being counted.
3. **Test count:** older notes cite 369 tests; the current source tree has a different test count. Generate a fresh receipt from the frozen submission commit.
4. **Opus completeness:** records are present, but endpoints, spend, sealed summaries, and complete secondary tables are absent.
5. **Causal language:** observations compatible with a confirmation-cap mechanism must not be rewritten as an established cause.

## Freeze procedure

1. Recover or regenerate the Opus endpoint and secondary tables from the original job directories using the committed scripts and manifest.
2. Build one all-stage machine-readable result file from the source tables.
3. Verify trial identities, block assignment, missing-reward handling, record outcomes, and every aggregate against the preregistration.
4. Hash every paper-critical input and output and update `evidence/snapshot-manifest.json` at the frozen commit.
5. Run the full test suite and required static analysis; save receipts.
6. Update C03 and the manuscript only from the frozen result file.
7. Obtain joint approval for claims, authorship, anonymity, license, and public release.
