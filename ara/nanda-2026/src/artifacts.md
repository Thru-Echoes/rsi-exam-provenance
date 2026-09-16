# Executable artifact index

Repository-backed ARA: paths here resolve from the root checkout. No paid rollout
or hosted service is needed for the primary controlled experiment.

| Role | Path |
| --- | --- |
| Frozen case definitions | studies/decision-audit/fault-manifest.json |
| Research protocol | studies/decision-audit/PROTOCOL.md |
| Controlled runner | studies/decision-audit/run_faults.py |
| Exact controlled outputs | studies/decision-audit/fault-results.json |
| Development replay and outputs | studies/decision-audit/replay_development.py and development-results.json |
| Producer and verifier | profile/build_capsule.py and profile/verify_capsule.py |
| Synthetic source package | fixtures/gated/ |
| Decision contract | docs/decision-log-contract.md |
| Historical integration receipt | docs/RUN_REPORT.md |
| Historical cohort source | docs/PREFLIGHT.md and docs/shadow-audit/instrument-ab/ |
| Historical result generator | ara/nanda-2026/src/execution/build_paper_results.py |
| Current IEEE manuscript | ara/nanda-2026/submission/main.tex |
| Readable manuscript | ara/nanda-2026/submission/manuscript.md |
| Current PDF | output/pdf/nanda-2026-track3-ieee-review.pdf |

The earlier build_submission_pdf.py and nanda-2026-track3-working-paper.pdf are
historical layout proofs. They do not generate the current research manuscript.
Use submission/README.md for the current build.
