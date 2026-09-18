# Capture, Verify, Govern — human review

Framework-first review revision, 2026-09-17. Open paper.pdf in the ZIP root, or
output/pdf/nanda-2026-track3-ieee-review.pdf in the repository. CONTENTS.json pins
the exact source revision and bundle branch. Earlier ZIPs are historical drafts.

This is an author-side, AI-assisted research draft, not author approval, submission,
an official ARA Seal or independent review. The PDF keeps an anonymous author
block; named implementations and source/history are NOT anonymized.

## Review in this order

1. Read the four-page IEEE PDF: framework, RSI instantiation, Verify characterization,
   intake demonstration, and limitations.
2. Read source/ara/nanda-2026/REVIEW.md and logic/claims.md. C09 is framework design;
   C05/C06 are Verify results; C10 is an integration demonstration, not full governance.
3. Inspect source/studies/framework-boundary/ and source/studies/decision-audit/.
4. Read source/studies/handoff-case-review/ for historical evidence limits.

## Reproduce the portable RSI checks

The full offline ZIP contains a browsable source snapshot plus repository.bundle
with the history needed for pinned historical-table reproduction:

```sh
git clone --branch codex/nanda-framework-review repository.bundle reproduction
cd reproduction
python3 studies/handoff-case-review/review_cases.py --check
python3 -m unittest tests.test_handoff_cases tests.test_decision_audit tests.test_nanda_ara tests.test_paper_results tests.test_conformance -q
python3 ara/nanda-2026/src/execution/build_paper_results.py --source-revision 727b9b821d7814d7467a29c1e740ce92eea7e219 --check
python3 ara/nanda-2026/src/execution/check_review_snapshot.py --check
```

These checks use Python standard library and Git. The E07 receipt is checked for
source bindings here; this does NOT re-execute the external Proofpress component.

## Re-execute the new integration demonstration

Obtain the public Proofpress commit specified in studies/framework-boundary/README.md,
and use Python >=3.11 with its cryptography dependency installed:

```sh
python studies/framework-boundary/run_demo.py --proofpress-root /path/to/proofpress --check
```

The script exports the pinned commit, ignores local checkout changes, uses
disposable local repositories and performs no network/provider calls or approvals.
The external Proofpress source/dependencies are not included in this ZIP. Obtaining
them may need network access; the actual demonstration does not.

PDF rebuilding requires Tectonic; Markdown synchronization requires Pandoc.
Neither is needed to inspect the included PDF or reproduce the primary Verify study.

## Evidence limits and human decisions

Nine faults are authored synthetic cases, not nine real incidents. One expected
diagnostic prefix remains mismatched. Import is not domain verification; a
synthetic candidate remains unadmitted. No complete human-approved agent handoff,
independent test set, reviewer-benefit study or new model rollout is claimed.

Authors must review the framework's novelty and scope, confirm attribution and
venue policy, approve a specific revision, and separately authorize submission.
The ZIP manifest is an integrity inventory, not an authenticity certificate.
