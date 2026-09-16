# Evidence package

This directory records what the paper may cite and what remains unresolved.

| File | Role | Status |
| --- | --- | --- |
| `snapshot-manifest.json` | Pins paper-critical source files at scaffold creation | draft |
| `results/reconciliation-status.md` | Lists contradictions and release blockers | active |
| `results/test-receipt.md` | Scaffold-branch unit-test and static-analysis receipt | present; refresh at freeze |
| `results/paper-results.json` | Canonical machine-readable all-stage result | pending |
| `tables/` | Filed paper tables with source metadata and screenshots | pending manuscript numbering |
| `figures/` | Filed paper figures with source metadata and screenshots | pending manuscript numbering |

Evidence precedence is: raw job outputs and verifier receipts; generated per-trial tables; preregistered manifest and committed endpoint tables; narrative handoffs; working notes.

Do not copy secrets, private traces, operator home paths, or unpublished raw data into this directory. Do not treat a narrative count as canonical when a source table is missing.
