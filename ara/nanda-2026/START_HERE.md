# Auditable Keeps — human review bundle

This is an author-side, AI-assisted research draft. No official ARA Seal, independent peer review, author approval, or public submission is implied. The PDF is anonymous; the complete source/history is NOT anonymized.

## Review in this order

1. Open paper.pdf (three-page IEEE manuscript) in the ZIP root.
2. Read source/ara/nanda-2026/REVIEW.md and logic/claims.md: C05/C06 are the primary results; C07/C08 are historical illustrations with weaker evidence.
3. Inspect source/studies/decision-audit/fault-results.json and source/studies/handoff-case-review/README.md.
4. Review the evidence inventory before interpreting the real cases. Original RSI measurements/snapshots and Harvey raw runs are not included; nothing in this bundle recreates them.

## Reproduce without network or provider credentials

The ZIP contains a browsable source snapshot and repository.bundle with the Git history needed for the pinned historical-table check. From the unpacked ZIP directory:

```sh
git clone --branch codex/nanda-2026-ara repository.bundle reproduction
cd reproduction
python3 studies/handoff-case-review/review_cases.py --check
python3 -m unittest tests.test_handoff_cases tests.test_decision_audit tests.test_nanda_ara tests.test_paper_results tests.test_conformance -q
python3 ara/nanda-2026/src/execution/build_paper_results.py --source-revision 727b9b821d7814d7467a29c1e740ce92eea7e219 --check
python3 ara/nanda-2026/src/execution/check_review_snapshot.py --check
```

Tested with Python 3.14.6 and Git. PDF rebuilding additionally requires Tectonic; readable Markdown regeneration requires Pandoc. Those optional tools may download dependencies on first use. Core evidence reproduction uses Python standard library only. An optional original Proofpress checkout enables extra source-projection comparison; it is not required for the portable checks above.

Nine synthetic faults are rejected by full checks, versus one and three by weaker checks. One of nine expected diagnostic prefixes remains mismatched. A passing regression reproduces that disclosed mismatch; it does not turn it into a successful diagnostic expectation. Two valid controls and one coherent unsigned rewrite pass.

## Human decisions still open

- Are the narrow system contribution and historical evidence boundaries convincing?
- Does the Harvey illustration clarify the trust boundary or distract from the main result?
- Confirm author order, affiliations, contribution/IP/COI declarations and venue anonymity/artifact policy.
- Approve a specific frozen version and authorize release separately. This delivery does not publish or submit.

The ZIP content manifest records hashes and source revision; it is an integrity inventory, not an authenticity certificate. The full repository also preserves older drafts and reports, clearly superseded by this review manuscript.
