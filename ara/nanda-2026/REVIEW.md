# Human review guide

Status: revised systems-paper draft. The central question now has a direct
controlled evaluation. This is an author-designed, fixture-based short paper;
acceptance by a venue is not assured.

## Read first
1. submission/manuscript.md or the IEEE PDF.
2. logic/claims.md, especially C05 (incremental checks) and C06 (accepted rewrite).
3. studies/decision-audit/fault-results.json from the repository root.
4. logic/related_work.md for the narrow novelty claim.

## Main findings
Nine authored faults are rejected by full verification, versus one by structure
and three by structure plus bindings. Six therefore require additional checks.
Both valid controls pass. An unsigned reward rewritten consistently with its
declaration passes. Eight of nine diagnostic targets match; the missing-snapshot
case retains an incorrect expected prefix alongside the actual correct-family
refusal. The evaluation does not tune the implementation to pass the new cases.

## What changed after human critique
The previous draft centered an auditability claim on a reward experiment. It also
overstated the statistical conclusion as efficacy refutation. That framing and
the earlier self-review score are superseded. The new primary evidence directly
compares checking configurations. The reward campaign is historical context only.
ARA PAPER.md is now a short manifest; the full manuscript has its own location.

## Scientific limits to review
- Are these task-specific semantics a useful enough systems contribution? Prior
  work already covers provenance constraints and cryptographic artifact chains.
- The experiment uses one synthetic base and faults selected after source inspection.
  It characterizes checks; it cannot estimate real-world detection rates.
- No fresh independent implementation comparison, human audit study, or network
  experiment was performed.
- Original historical job directories are not all included. Their observations
  are explicitly reported as historical, not newly reproduced.
- Historical fixture import into ProofPress is not verification or approval.

## Author decisions before external submission
Confirm author order, affiliations, contribution statement, final claims, and
submission authority. Resolve the workshop's anonymity and artifact-link policy.
The anonymous review PDF and full repository-backed ARA are ready for joint review;
no public upload is part of this delivery.

## Tooling labels
The automated local checks are reproducibility and consistency checks. Any local
semantic review is self-review, not an official ARA Seal or independent peer review.
The old level2_report.json was superseded because its positive coherence assessment
did not identify the mismatch between the previous contribution and evaluation.

## Current revision: real cases with explicit evidence ceilings
Read studies/handoff-case-review/README.md from repository root after the manuscript.
C07 and C08 / E06 add retained-source inspection, not two additional verifier trials.
The real RSI capsule/log reconstruct a branch and expose missing evidence; original result and snapshot bytes are unavailable here. H5 remains report-only.
The Harvey license subgroup is selected retrospectively and treatment has extra ledger-state information. It illustrates reuse eligibility, not current-system effectiveness.
The core contribution and primary controlled results remain C05/C06. Two passing controls do not establish a population false-positive rate.
