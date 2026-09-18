# Local review verification

## PR #42 integration — 2026-09-18 UTC

- Preserved Figure 1 from `8628b0834b55b2fa1edd1d61c81941e6e9d62292` and
  integrated the Proofpress version, governance-boundary and named-generator fixes
  from local correction `b596c18`. E07 uses a source pin, not a package release.
- Full suite: 429 tests in 59.214 seconds, OK with two skips. After final prose
  compression, the 12 named-generator/ARA checks passed again. Retained-export
  inspection and Markdown synchronization also passed.
- Rebuilt four US-letter pages with Tectonic and inspected all four rendered
  pages. Figure 1 is now on page 1. No clipping or overlap observed; margins and
  text sizes are unchanged. No experiment results or verifier code changed.
- Refreshed source bindings; prior ZIP archives remain explicitly historical.
- This remains an anonymous review draft. Actual AI-use disclosure and final
  author metadata require confirmation before conference upload. No new model
  rollout, independent Case R replay, or external Proofpress execution occurred.

## Framework-first revision — 2026-09-17

- Full repository suite: 427 tests in 58.408 seconds, OK with two skips.
- Focused research suite: 21 tests in 1.153 seconds, all passing. The added test
  binds the new integration receipt to its inputs and runner and preserves its
  no-approval/no-downstream-run boundary; it does not execute external Proofpress.
- E07 freshly executed, then rerun by the same author-side runner
  with --check: exact pinned receipt reproduced. Python 3.11.13, cryptography
  46.0.7; Proofpress 7fad672321ae00d7c7af350e7b26000846b37895. This is not an
  independent evaluator. Only disposable local fixture repositories were written.
- Retained-case check, historical table reproduction and Markdown synchronization
  passed. Pyright: zero errors, one existing optional jsonschema source warning.
- Four-page IEEE PDF including references, rendered and all pages inspected.
  Three legible tables, no clipping or overlap, all fonts embedded/subset; no
  margin or type-size reduction. The author block stays anonymous, not a guarantee
  that named systems or the public ARA hide authorship.
- Existing gate, converter, verifier, fixtures and twelve-package study/results
  remain byte-identical to the prior public source. The new runner exercises
  existing implementations, not a fix that makes the study pass.
- Source snapshot and final clean-clone receipt are recorded after the source
  freeze in output/review/README.md. Earlier verification sections below describe
  earlier revisions and do not supply the current test counts.
- No model rollout, paid inference, human approval, hosted service mutation or
  conference submission occurred. Framework effectiveness is not established.

## Handoff framing and distribution revision — 2026-09-17

- Full repository suite: 426 tests in 61.426 seconds, OK with two skips.
- Final focused research suite: 20 tests passed in 1.241 seconds. Retained-case
  inspection, pinned historical table reproduction and readable-manuscript
  synchronization also passed. All PDF fonts are embedded and subset.
- The final handoff text keeps the existing twelve-case experiment, fixture,
  verifier and result files unchanged. The reviewer-facing boundaries are also
  checked by the focused ARA tests.
- Three-page IEEE PDF rebuilt, rendered and all pages inspected. Both tables and
  references fit; no clipping or overlap. No font size or margin was reduced.
- Capture, consistency checking and admission are distinguished. No network
  experiment, outcome improvement or execution authenticity is claimed.
- The prior reader-first local revision and this handoff revision are prepared
  together for the existing PR #40. A new dated archive preserves the earlier
  frozen ZIP unchanged. Exact distribution pins and clean-clone results belong
  in output/review/README.md, outside the scientific source freeze.
- No new model rollout, paid inference, or independent human evaluation occurred.

## Reader-first local revision — 2026-09-17

- Full suite: 426 tests in 55.733 seconds, OK with two skips.
- Focused research suite: 20 tests passed; the added regression binds every number and disposition in the worked example to the unmodified synthetic decision log.
- All twelve S/B/V rows still match saved execution; fixture, verifier, manifest and experiment-result files are unchanged.
- Historical retained-case check and pinned historical table generator passed.
- Readable manuscript synchronization and git diff whitespace checks passed.
- Pyright: zero errors, one existing optional jsonschema source warning.
- Three-page IEEE PDF rendered and all pages inspected; two tables legible, no clipping/overlap, fonts embedded/subset.
- At this earlier checkpoint it was a local editorial candidate, not a readability
  user study. Public PR #40 had not yet been synchronized; the handoff revision
  above supersedes that distribution status.

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
conference submission has been performed. Review materials are shared in PR #40.

## Historical-case revision checks
- review_cases.py --check --proofpress-root verified the saved extraction and exact imported source selections against the pinned source bytes.
- The portable version omits --proofpress-root and needs no original external run directories. It checks retained evidence, not absent raw experiments.
- Readable manuscript generation preserves title, abstract and reference labels; render_manuscript.py --check passed.
- Revised three-page PDF rendered and every page inspected; all fonts embedded/subset. No clipped text or table overlap.
- RSI repository pyright: zero errors, one pre-existing optional jsonschema source warning. An accidental diagnostic invocation in the separate Proofpress workspace is not this repository's result and no changes were made there.
- Initial clean-copy delivery check found a bundle missing a default HEAD. Explicit branch checkout reproduced all 19 focused tests, the historical generator, snapshot bindings and readable manuscript. Packaging now includes HEAD and instructions specify the branch. This was a packaging issue, not a study-result change.
