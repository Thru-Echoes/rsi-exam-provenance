# Auditing Keep-or-Revert Decisions in Self-Improving Agents

Status: reader-first handoff revision for PR #40, 2026-09-17. Human review is pending; this is not an approved or submitted paper. See repository-root output/review/README.md for the dated archive and exact source revision.

**Motivation:** A kept version can become the parent of later work. A recipient inherits the consequences of those choices without necessarily having access to the producing runtime. The unit of audit is each version-selection decision and its evidence.

**Question:** Which decision inconsistencies can an offline recipient detect beyond document structure and file binding?

**Result:** In twelve authored fixture packages, full verification rejects all nine faults; six survive structure-plus-binding checks. Both valid controls pass. A consistently rewritten unsigned reward also passes, exposing the authenticity boundary. Eight of nine faults match the frozen diagnostic target; one prefix mismatch is retained.

**Scope:** Internal characterization, not a held-out benchmark, efficacy result, or runtime attestation.

Capture, consistency checking, and authorization to reuse are separate responsibilities. This paper characterizes checking; networked handoff is a use case, not a measured network deployment.

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
