# Claims

Epistemic attribution: paper framing and these revised claim cards are ai-suggested;
executions E01, E05 and E07 are ai-executed. Historical sources remain attributed to
their repository authors. These labels do not represent human approval.

Manuscript mapping (framework revision, 2026-09-17): C09 is the framework design; C01 is its domain-specific verification implementation; C05/C06 characterize Verify; C10 demonstrates the intake boundary. C07 motivates Capture. C02/C03/C04/C08 remain companion context or hypotheses. These distinct evidence levels must not be pooled as validation of the whole framework.

## C01 — Executable decision consistency
**Statement:** The profile implements offline checks for declared artifact identity, paired-measurement reproduction, protocol state, and supplied-directory coverage.
**Conditions:** Intended verifier and complete required files; internal consistency only, with no runtime witnessing.
**Sources:** [input] profile/verify_capsule.py; docs/decision-log-contract.md; docs/profile-v3.md.
**Status:** supported within implemented and exercised checks.
**Falsification criteria:** A claimed check is absent, or a case satisfying its prerequisites violates it without the stated failure. This does not require rejecting a fully consistent rewrite.
**Proof:** [E01], [E05].
**Evidence basis:** implementation inspection, development replay, and controlled fixtures; no formal soundness proof.
**Dependencies:** none.
**Tags:** consistency, executable-profile.

## C02 — Historical capture feasibility and missing evidence
**Statement:** Committed real-run reports document missing visible measurements, version-identification pitfalls, and 18 verified records from 20 started A/B trials.
**Conditions:** Historical versions and cohorts only; raw job directories are not all available in this artifact.
**Sources:** [result] docs/PREFLIGHT.md; docs/shadow-audit/instrument-ab/{haiku,sonnet,opus}/records.md; evidence/results/paper-results.json.
**Status:** supported as a report of committed observations.
**Falsification criteria:** A retained observation contradicts its cited source or the all-started-trial denominator does not reconcile.
**Proof:** [E02].
**Evidence basis:** historical reports and generated table reconciliation, not fresh end-to-end reproduction or a causal capture-effect estimate.
**Dependencies:** none.
**Tags:** historical, feasibility.

## C03 — Gate efficacy
**Statement:** The tested statistical instrument improves sealed reward over the helper.
**Conditions:** Original blocked comparison, small stages, one task, and mixed source precision.
**Sources:** [result] evidence/results/paper-results.json; docs/campaign/2026-09-instrument-ab/manifest.md.
**Status:** unsupported; prior 'refuted' label withdrawn as too strong.
**Falsification criteria:** A prospectively adequate comparison could support or reject a specified effect. The current 3 instrument-favoring and 7 helper-favoring blocks do not establish a general effect.
**Proof:** [E03].
**Evidence basis:** descriptive secondary context only. Later Opus raw receipts remain incomplete.
**Dependencies:** none.
**Tags:** historical, unsupported-efficacy.

## C04 — Confirmation limits influence search
**Statement:** Confirmation limits may alter downstream candidate selection under a finite compute budget.
**Conditions:** Requires separating rule effects from model behavior, policy cost, and remaining time.
**Sources:** [input] docs/campaign/2026-09-instrument-ab/manifest.md; docs/shadow-audit/pilots/pilot-8-preregistration.md.
**Status:** hypothesis, not a finding of the new audit study.
**Falsification criteria:** A controlled cap intervention with fixed evidence and compute could contradict the proposed effect on selection.
**Proof:** [E04] is unexecuted.
**Evidence basis:** historical mechanism observations only.
**Dependencies:** none.
**Tags:** hypothesis, future-work.

## C05 — Additional checks beyond file bindings
**Statement:** On the twelve frozen authored packages, full verification rejects nine faults; six pass both structural and file-binding checks. Two valid controls pass.
**Conditions:** Synthetic gated fixture; shared checking components; cases designed after source inspection. All nine outcome expectations match, but only eight diagnostic targets match.
**Sources:** [result] studies/decision-audit/fault-results.json; [input] studies/decision-audit/fault-manifest.json.
**Status:** supported on the enumerated cases.
**Falsification criteria:** Reproduction with matching source hashes changes an outcome, or an attributed failure comes from a different prerequisite or operational crash.
**Proof:** [E05].
**Evidence basis:** direct controlled execution and per-case diagnostic records. No population detection rate.
**Dependencies:** C01.
**Tags:** controlled-characterization, primary-result.

## C06 — Unsigned reward rewrite remains accepted
**Statement:** Rewriting the unsigned reward file and matching capsule reward to 0.5, then refreshing the reward digest, passes complete verification.
**Conditions:** Exact boundary_control case; remaining files unchanged. The verifier does not recompute the hidden reward from score_details.
**Sources:** [result] studies/decision-audit/fault-results.json case reward_rewrite; [input] profile/verify_capsule.py _check_reward.
**Status:** supported on the tested rewrite.
**Falsification criteria:** The unchanged verifier rejects this package, or the report does not contain the declared changed-file bindings.
**Proof:** [E05].
**Evidence basis:** accepted adversarial boundary control, not proof that all consistent rewrites pass.
**Dependencies:** C01.
**Tags:** authenticity-boundary, negative-control.

## C07 — Partial real-run evidence is inspectable, not fully replayable
**Statement:** The retained Opus block 1 capsule/log reconstruct v1-to-v2 revert and v1-to-v3 submission, with a matching log binding; absent results and snapshots prevent full replay.
**Conditions:** Only the retained export is inspected; reported means and dispositions are declarations.
**Sources:** studies/handoff-case-review/case-results.json; docs/figures/sources/ab-opus-1-I/.
**Status:** supported retained-record inspection, not current verifier success on a real run.
**Falsification criteria:** Source hashes differ, lineage extraction disagrees, or claimed missing evidence is present in the inspected export.
**Proof:** [E06].
**Evidence basis:** Original retained capsule and log plus deterministic inventory.
**Dependencies:** none.
**Tags:** historical-case, incomplete-evidence.

## C08 — Reuse eligibility is separate from decision consistency
**Statement:** A legacy Harvey-derived license stress report records 3/3 unsafe ordinary continuations versus 0/3 gated continuations; this illustrates a separate expiry-based admission boundary.
**Conditions:** Retrospectively selected subgroup; full pilot 4/9 versus 0/9. Only the gated arm has external ledger state. Older implementation, controlled perturbations, no model rerun here.
**Sources:** studies/handoff-case-review/harvey-source-projection.json and case-results.json.
**Status:** historical illustrative observation, not causal attribution or RSI-verifier generalization.
**Falsification criteria:** Exact pinned result projection does not support counts or treatment asymmetry.
**Proof:** [E06].
**Evidence basis:** Public pinned historical result/protocol projection, not original raw runs.
**Dependencies:** none.
**Tags:** historical-case, reuse-boundary, information-asymmetry.

## C09 — Capture, verify and govern are separate responsibilities
**Statement:** The proposed handoff framework distinguishes a submitted decision record, a package-bound domain-check result, and an explicitly scoped claim whose reuse requires separate authority.
**Conditions:** This is a design proposal, not a general theorem or an empirically validated end-to-end workflow. The present TRACE adapter does not enforce a verifier-receipt binding.
**Sources:** [design] submission/main.tex section II; logic/solution/architecture.md; docs/decision-log-contract.md; [implementation] gate/trace_from_decisions.py.
**Status:** proposed architecture with partial reference instantiation.
**Falsification criteria:** An alleged implemented boundary has no corresponding operation, or the documented statuses are silently promoted by the tested path. General usefulness remains an open empirical question.
**Proof:** [E07] illustrates non-equivalence at intake only; it is not proof of the framework's effectiveness.
**Evidence basis:** interface inspection and a local synthetic demonstration; no human-approval or multi-agent evaluation.
**Dependencies:** C01, C10.
**Tags:** framework-design, partial-instantiation, authority-separation.

## C10 — TRACE intake neither repeats verification nor grants reuse
**Statement:** A pinned local demo imports three TRACE decisions into three source records and three evidence items with no claims, admissions or governed context. The existing one-point numerical fault is refused by the RSI verifier yet accepted by conversion and first-time evidence import. An explicit synthetic claim proposal remains unadmitted and absent from governed context.
**Conditions:** One synthetic lineage; Proofpress 7fad672321ae00d7c7af350e7b26000846b37895; TRACE wire 0.5.1. Changed normalized content under an already imported identity fails closed. Fault import uses a fresh receiver, not an overwrite. No human is simulated as approving.
**Sources:** [result] studies/framework-boundary/results.json; [input] studies/framework-boundary/run_demo.py; Proofpress docs/TRACE_ADAPTER.md and src/proofpress/kernel/operations.py at the pinned revision.
**Status:** supported local integration demonstration, not governance effectiveness or full TRACE schema conformance.
**Falsification criteria:** Reproduction changes counts or boundary outcomes, the wrong estimate is accepted by full verification, or a candidate becomes governed context without admission.
**Proof:** [E07].
**Evidence basis:** fresh isolated execution, source/runner digests and read-back of empty context. Unsupported wire version, malformed interval and restamped identity are refused; repeat import is idempotent.
**Dependencies:** C01.
**Tags:** integration-demonstration, evidence-only, no-self-approval.
