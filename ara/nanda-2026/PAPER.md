# Auditing Keep-or-Revert Decisions in Self-Improving Agents

Status: reader-first local review candidate, 2026-09-17. The public PR #40 ZIP remains the previous frozen draft. This revision is not yet pushed or submitted.

**Question:** Which decision inconsistencies can an offline recipient detect beyond document structure and file binding?

**Result:** In twelve authored fixture packages, full verification rejects all nine faults; six survive structure-plus-binding checks. Both valid controls pass. A consistently rewritten unsigned reward also passes, exposing the authenticity boundary. Eight of nine faults match the frozen diagnostic target; one prefix mismatch is retained.

**Scope:** Internal characterization, not a held-out benchmark, efficacy result, or runtime attestation.

Read:
- [Manuscript](submission/manuscript.md) and [IEEE source](submission/main.tex).
- [Claims](logic/claims.md), [experiments](logic/experiments.md), [related work](logic/related_work.md).
- [Code and reproduction](src/artifacts.md), [environment](src/environment.md).
- [Evidence index](evidence/README.md), [review guide](REVIEW.md).
- [Exploration history](trace/exploration_tree.yaml).

The ARA is repository-backed: paths outside this directory resolve from the repository root. Keep the repository with the artifact when reproducing. The prior reward-centered draft is preserved in Git at a1c2354.

## Historical case supplement
[C07/C08](logic/claims.md) and [E06](logic/experiments.md) distinguish retained real-run inspection from controlled fixture execution. See repository-root studies/handoff-case-review/README.md. Historical source extraction is portable; original model runs and missing snapshots are not reproduced.

The manuscript now uses C07 only as motivation; C08 (Harvey) and historical reward/development results remain companion material. [Reader-review rationale](evidence/reader-review-2026-09-17.md) explains the structural revision. The primary experiment and all outcomes are unchanged.
