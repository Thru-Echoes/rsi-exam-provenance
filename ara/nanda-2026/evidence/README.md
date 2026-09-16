# Evidence package

This directory records what the paper may cite and what remains unresolved.

| File | Role | Status |
| --- | --- | --- |
| `snapshot-manifest.json` | Pins paper-critical source and generated files | active; refresh at final freeze |
| `results/reconciliation-status.md` | Lists contradictions and release blockers | active |
| `results/test-receipt.md` | Scaffold-branch unit-test and static-analysis receipt | present; refresh at freeze |
| `results/paper-results.json` | Canonical machine-readable all-stage primary result and record yield | present; Opus raw-receipt binding pending |
| `results/paper-results.md` | Human-readable rendering of the generated result | present; generated, do not hand-edit |
| `venue-rules.md` | Checked public CFP requirements and unresolved anonymity/artifact-link question | present; re-check before submission |
| `../../../output/pdf/nanda-2026-track3-working-paper.pdf` | Anonymous two-column manuscript layout proof | present; not official IEEEtran and not approved for submission |
| `../level2_report.json` | Local ARA-compatible semantic review | present; not an official ARA Seal |
| `tables/` | Filed paper tables with source metadata and screenshots | pending manuscript numbering |
| `figures/` | Filed paper figures with source metadata and screenshots | pending manuscript numbering |

Evidence precedence is: raw job outputs and verifier receipts; generated per-trial tables; preregistered manifest and committed endpoint tables; committed pre-probe summaries; narrative handoffs; working notes. The generated result preserves the evidence class of every primary row rather than flattening these sources into equal-strength observations.

Do not copy secrets, private traces, operator home paths, or unpublished raw data into this directory. A committed summary may recover a bounded direction count when a table is missing, but it must remain labelled and cannot support precision or secondary analyses that it does not contain.
