# Local review verification

## Reader-first local revision — 2026-09-17

- Full suite: 426 tests in 55.733 seconds, OK with two skips.
- Focused research suite: 20 tests passed; the added regression binds every number and disposition in the worked example to the unmodified synthetic decision log.
- All twelve S/B/V rows still match saved execution; fixture, verifier, manifest and experiment-result files are unchanged.
- Historical retained-case check and pinned historical table generator passed.
- Readable manuscript synchronization and git diff whitespace checks passed.
- Pyright: zero errors, one existing optional jsonschema source warning.
- Three-page IEEE PDF rendered and all pages inspected; two tables legible, no clipping/overlap, fonts embedded/subset.
- This is a local editorial review candidate, not a readability user study. Public PR #40 and its frozen ZIP remain unchanged.

## Previous frozen delivery checks — 2026-09-16

Checked 2026-09-16. This is author-side verification, not independent review or
an official ARA certification.

- Full suite: `python3 -m unittest discover -s tests -t . -q` ran 425 tests in
  57.812 seconds, OK with two skips, after the historical-case additions.
- Focused research suite: decision-audit reproduction, ARA consistency, historical
  result reconciliation, conformance and historical cases: 19 tests passed.
- Primary reproduction compares all twelve case records, actual errors, file
  hashes and source hashes with a fresh run. One failed diagnostic expectation
  remains disclosed. It is not erased by the passing regression.
- Table consistency checks cover all twelve labels and each S/B/V outcome.
- The review PDF is three US Letter pages, using embedded subset fonts.
  Every page was rendered and inspected: no clipping, overlap or broken table.
- `git diff --check` passed after the research/test edits.

Source identity is the content-bound snapshot, not a claim that the base commit
contains all working-tree edits. Original private/external job directories are
not included. The historical working-paper PDF is superseded by the IEEE review
PDF and must not be treated as the current manuscript.

Before external submission: author review and approval, authorship and affiliation,
workshop anonymity/artifact-link policy, and final source freeze. No external
submission or public publication has been performed.

## Historical-case revision checks
- review_cases.py --check --proofpress-root verified the saved extraction and exact imported source selections against the pinned source bytes.
- The portable version omits --proofpress-root and needs no original external run directories. It checks retained evidence, not absent raw experiments.
- Readable manuscript generation preserves title, abstract and reference labels; render_manuscript.py --check passed.
- Revised three-page PDF rendered and every page inspected; all fonts embedded/subset. No clipped text or table overlap.
- RSI repository pyright: zero errors, one pre-existing optional jsonschema source warning. An accidental diagnostic invocation in the separate Proofpress workspace is not this repository's result and no changes were made there.
- Initial clean-copy delivery check found a bundle missing a default HEAD. Explicit branch checkout reproduced all 19 focused tests, the historical generator, snapshot bindings and readable manuscript. Packaging now includes HEAD and instructions specify the branch. This was a packaging issue, not a study-result change.
