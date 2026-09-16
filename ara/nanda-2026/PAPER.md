# Auditable Keeps: Semantic Verification of Self-Improving Agent Decisions

Status: human-review draft, 2026-09-16. Author approval and public submission are pending.

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
