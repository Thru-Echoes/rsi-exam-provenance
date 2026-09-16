# Human-review delivery requirements

This audit concerns a human-reviewable submission draft, not author approval or
external submission. The limitations are scientific boundaries, not missing
positive results that may be filled in by assumption.

| Requirement | Authoritative evidence |
| --- | --- |
| One coherent research question through conclusion | submission/main.tex: offline incremental decision checks; historical reward comparison is secondary |
| Executable contribution | profile/verify_capsule.py and docs/decision-log-contract.md |
| Direct evaluation and internal baselines | studies/decision-audit/run_faults.py, frozen fault-manifest.json, all twelve cases in fault-results.json |
| Honest uncertainty and negative controls | manuscript reports author-selected synthetic cases, accepted unsigned rewrite, and 8/9 diagnostic matches |
| ARA organization and traceability | PAPER.md, logic/claims.md, logic/experiments.md, src/artifacts.md, trace/exploration_tree.yaml, evidence/README.md |
| Reproduction of primary claims | tests.test_decision_audit compares fresh outcomes and hashes; tests.test_nanda_ara checks all table rows |
| Historical source boundaries | fixed-revision build_paper_results.py and historical reconciliation reports; no fresh end-to-end rollout claim |
| Correct short-paper format | three-page IEEEtran PDF, all pages visually inspected and fonts embedded; review-verification.md |
| Review handoff | REVIEW.md identifies reading order and author decisions; Notion latest-status section synchronized and fetched back |
| Integrity of delivered sources | check_review_snapshot.py --check validates exact content, not authenticity |

Not claimed: independent peer review, official ARA certification, general fault
detection rates, improved agent reward, signed execution, or network-scale trust.
No new paid rollout, public push, Hub upload, or EasyChair submission was performed.

Before external submission, humans must resolve authorship, affiliation, IP/COI,
review anonymity/artifact-link rules, approve the frozen claims, and authorize
release. An additional real-rollout audit or independent evaluation would strengthen
the evidence, but the present draft explicitly reports its narrower study design.
