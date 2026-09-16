# Experiments

All repository-relative paths below resolve from the root checkout.

## E01 — Development replay
**Verifies:** C01
**Run:** python3 studies/decision-audit/replay_development.py
**Setup:** Ten known development vectors, including a valid baseline; three local components.
**Procedure:** Preserve each case hash, component outcome, producer/verifier stage, and explicit validation reason.
**Expected outcome:** Existing documented outcomes reproduce. Refusal alone does not establish the intended reason.
**Evidence:** studies/decision-audit/development-results.json. Nine full-path refusals include three producer refusals. Missing v4 masks the intended ancestry check in one case. The converter is not schema-only.

## E02 — Historical source reconciliation
**Verifies:** C02
**Run:** python3 ara/nanda-2026/src/execution/build_paper_results.py --check
**Setup:** Committed tables and reports at the result generator's fixed source revision.
**Procedure:** Reconcile all twenty A/B trials and retain source class; separately read dated preflight observations.
**Expected outcome:** 18 verified records, 9 per arm, and two explicit submitted_not_snapshotted outcomes.
**Evidence:** evidence/results/paper-results.json; docs/PREFLIGHT.md. This checks reports, not all original job directories.

## E03 — Historical gate comparison
**Verifies:** C03
**Run:** Same source-reconciliation command as E02.
**Setup:** Four Haiku, three Sonnet, three Opus blocks under the historical manifest.
**Procedure:** Preserve 3/7 direction count and mixed raw/source precision. Do not infer a general effect.
**Expected outcome:** Descriptive evidence does not support the positive efficacy claim.
**Evidence:** evidence/results/paper-results.json and historical reconciliation-status.md. Optional deployment context, not the primary audit study.

## E04 — Prospective confirmation-cap intervention
**Verifies:** C04
**Run:** Not executed; future experiment.
**Setup:** Would require a fixed evidence sequence and controlled total compute.
**Procedure:** Vary cap and remaining-window policy, measure selection and downstream search changes.
**Expected outcome:** No outcome asserted.
**Evidence:** None for causal identification. Excluded from the primary findings.

## E05 — Controlled package checks
**Verifies:** C01, C05, C06
**Run:** python3 studies/decision-audit/run_faults.py
**Setup:** Twelve packages from fixtures/gated; manifest committed at c1bcd7d before first execution, after inspecting source and tests.
**Procedure:** Verify a clean copy first, inject the manifest's change, compare S (structure), B (structure and bindings), and V (full require-complete verification). The producer is not rerun after mutation. Capture changed-file hashes and actual reasons. Unexpected exceptions abort execution.
**Expected outcome:** Nine faults rejected; clean and cache controls accepted; unsigned reward rewrite accepted. Manifest diagnostic expectations remain unchanged after execution.
**Evidence:** studies/decision-audit/fault-results.json and fault-manifest.json. One diagnostic-prefix mismatch is retained: missing snapshot expects file:version:v2 but returns file:artifact:v2:missing_file. This is 9/9 expected refusal outcomes and 8/9 diagnostic-target matches, not a perfect test run. Evaluation code and limitations are indexed in src/artifacts.md.
