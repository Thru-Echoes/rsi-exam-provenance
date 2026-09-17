# Capture, Verify, Govern: Decision Provenance for Agent Artifact Handoffs

Status: framework-first revision for PR #40, 2026-09-17. Four-page IEEE review draft; human approval and submission remain pending. See repository-root output/review/README.md for distribution status and exact source revision.

**Motivation:** A kept version can become the parent of later work. A recipient inherits the consequences of those choices without necessarily having access to the producing runtime. The unit of audit is each version-selection decision and its evidence.

**Question:** How should submitted decisions become checkable evidence, and what must remain separate before downstream reuse?

**Framework:** Capture (TRACE decision record), Verify (domain-specific consistency checks), Govern (evidence-bound claim, separate human review, current scoped context). C09 states the design; C01 implements the RSI verification profile. This is a partial reference instantiation, not a receipt-enforced end-to-end deployment.

**Result:** In twelve authored fixture packages, full verification rejects all nine faults; six survive structure-plus-binding checks. Both valid controls pass. A consistently rewritten unsigned reward also passes, exposing the authenticity boundary. Eight of nine faults match the frozen diagnostic target; one prefix mismatch is retained.

**Scope:** Internal characterization, not a held-out benchmark, efficacy result, or runtime attestation.

**Integration demonstration:** C10/E07 freshly checks conversion and evidence intake against a pinned Proofpress source. Three decisions become three evidence items, no claims or admissions; a verifier-rejected mean error is still importable as evidence. An explicit candidate remains outside governed context. The adapter does not import a complete verifier receipt or authorize reuse.

**Evidence levels:** Framework design; Verify-layer characterization; local intake demonstration; retained real-case motivation. None implies validation of human governance or a networked deployment.

Read:
- [Manuscript](submission/manuscript.md) and [IEEE source](submission/main.tex).
- [Claims](logic/claims.md), [experiments](logic/experiments.md), [related work](logic/related_work.md).
- [Code and reproduction](src/artifacts.md), [environment](src/environment.md).
- [Evidence index](evidence/README.md), [review guide](REVIEW.md).
- [Exploration history](trace/exploration_tree.yaml).

The ARA is repository-backed: paths outside this directory resolve from the repository root. Keep the repository with the artifact when reproducing. The prior reward-centered draft is preserved in Git at a1c2354.

## Historical case supplement
[C07/C08](logic/claims.md) and [E06](logic/experiments.md) distinguish retained real-run inspection from controlled fixture execution. See repository-root studies/handoff-case-review/README.md. Historical source extraction is portable; original model runs and missing snapshots are not reproduced.

The manuscript uses C07 only as motivation; C08 (Harvey) and historical reward/development results remain companion material. [Framework revision rationale](evidence/framework-review-2026-09-17.md) records the new hierarchy and implementation gaps. The twelve-package Verify experiment and its outcomes are unchanged; E07 is a separate new integration demonstration.
