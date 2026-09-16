# Local review verification

Checked 2026-09-16. This is author-side verification, not independent review or
an official ARA certification.

- Full suite: `python3 -m unittest discover -s tests -t . -q` ran 423 tests in
  58.517 seconds, OK with two skips.
- Focused research suite: decision-audit reproduction, ARA consistency, historical
  result reconciliation, and conformance: 17 tests passed.
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
