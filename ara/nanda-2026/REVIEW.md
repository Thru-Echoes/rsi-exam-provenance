# Human review guide

Status: framework-first revision, 2026-09-17, for existing PR #40. Four-page IEEE
draft titled **Capture, Verify, Govern: Decision Provenance for Agent Artifact
Handoffs**. Human approval, authorship and external submission remain pending.

## Read in this order

1. The PDF or submission/manuscript.md: the framework is the main contribution;
   RSI is its first verification instantiation, not the whole framework.
2. logic/claims.md: C09 is design, C01 implementation, C05/C06 Verify results,
   C10 the new intake demonstration. These evidence levels must not be pooled.
3. studies/framework-boundary/README.md and results.json from repository root:
   see what actually crosses each interface and what is not implemented.
4. studies/decision-audit/fault-results.json and the retained-case dossier.

## What is newly supported

E07 freshly checks the existing converter and a pinned Proofpress revision in
disposable local repositories. Three decisions become three evidence items, no
claims, no admissions and empty context. An explicit candidate also remains
outside governed context. The existing numerical fault is rejected by the full
RSI checker but remains first-importable as evidence. No production changes,
hosted writes, simulated human approval or model runs were used.

## What remains unchanged

E05 still contains twelve synthetic packages: nine authored faults, two valid
controls and one unsigned reward-rewrite control. S/B/V reject 1/3/9 faults; the
controls pass. Eight of nine diagnostic targets match, with the missing-snapshot
prefix mismatch retained. No verifier code or historical result was changed.

C07 is a retained real-run illustration with missing original snapshots and
measurements. C08/Harvey, reward A/B, cohort summaries and development diagnostics
remain companion-only context. They do not validate the complete framework.

## Questions for a critical reviewer

- Is the separation useful beyond the familiar observation that logs are not proof?
  The concrete contribution is the executable profile and explicit intake boundary,
  not a claim that separation of concerns is new.
- Does the paper make its partial implementation clear? TRACE import does not
  consume a complete verifier receipt or require verification before intake.
- Are the author-selected cases sufficient for a workshop characterization?
  They cannot estimate real-world detection rates or cross-domain generalization.
- Does the manuscript distinguish a system resolver in RSI from authorized human
  admission in Proofpress, without claiming the latter was exercised?
- Is the framework claim proportionate to evidence that stops at an unadmitted
  candidate, with no measurement of human-review quality or downstream benefit?

## Human decisions before submission

Confirm claims, author order, affiliations, contribution/IP/COI declarations,
artifact-link/anonymity rules and submission authority. The PDF retains an anonymous
author block, but named implementations and public history may identify contributors.
The complete ARA is not anonymized. No official ARA Seal, independent peer review,
merge, deployment or conference submission is implied.

See evidence/framework-review-2026-09-17.md for the rationale and
evidence/review-verification.md for execution receipts. Earlier editorial decisions
remain in Git and the dated reader-review note, not current contribution guidance.
