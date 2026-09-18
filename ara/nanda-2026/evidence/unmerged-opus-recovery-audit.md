# Unmerged Opus recovery audit

**Checked:** 2026-09-15 America/Los_Angeles

This note inventories evidence-shaped files on a later remote branch so a future source review can recover missing Opus material without silently mixing branch states. Nothing listed here is admitted into the paper result, the ARA claim set, or the snapshot manifest as experimental evidence.

## Branch boundary

- Remote branch: `origin/docs/instrument-ab`
- Audited tip: `d4d1f0140f4c6b52a16f26983ab5a10f601a6c1d`
- The branch is five commits ahead of `origin/main`: `1619c6f`, `55cbcc7`, `cac99cc`, `f744aea`, and `d4d1f01`.
- These commits are not merged into the working paper branch. Their files therefore remain recovery candidates, not sources that can override the committed evidence precedence chain.

## Located reports

The branch contains a shadow-replay `report.json` for all six Opus A/B rollouts:

| Block | Arm | Report |
| --- | --- | --- |
| 1 | helper | `docs/shadow-audit/instrument-ab/opus/ab-opus-1-H-gZWCHaL/report.json` |
| 1 | instrument | `docs/shadow-audit/instrument-ab/opus/ab-opus-1-I-UaXracv/report.json` |
| 2 | helper | `docs/shadow-audit/instrument-ab/opus/ab-opus-2-H-4xm8dnr/report.json` |
| 2 | instrument | `docs/shadow-audit/instrument-ab/opus/ab-opus-2-I-YMmhjjX/report.json` |
| 3 | helper | `docs/shadow-audit/instrument-ab/opus/ab-opus-3-H-rwXkAdi/report.json` |
| 3 | instrument | `docs/shadow-audit/instrument-ab/opus/ab-opus-3-I-Dek7ANT/report.json` |

Each is a replay/audit report with coverage, pair, disposition, and resource-summary fields. None exposes the paper's primary hidden-evaluation receipt.

Only three sealed-retrospective reports are present:

- `docs/shadow-audit/instrument-ab/opus/sealed/ab-opus-1-H-gZWCHaL/report.json`
- `docs/shadow-audit/instrument-ab/opus/sealed/ab-opus-1-I-UaXracv/report.json`
- `docs/shadow-audit/instrument-ab/opus/sealed/ab-opus-2-H-4xm8dnr/report.json`

No sealed report is present there for block 2 instrument or either block 3 arm. No Opus spend table or complete primary-endpoint table is present.

The three available retrospective reports do carry source-precision rewards for a snapshot named `submission`: block 1 helper `0.60840837`, block 1 instrument `0.5510569`, and block 2 helper `0.60200514`. The first two agree with the capsule-bound primary rewards already admitted on this branch. The block 2 helper value agrees, after rounding, with the committed pre-probe summary. This is useful corroboration, but it is not a replacement for `verifier/reward.json`: the report itself states that it used the environment's same-process evaluator under a pooled CPU budget rather than the grader's sandboxed process and per-move limit. It also comes from an unmerged branch state. The block 2 helper report therefore remains a recovery candidate until source review and admission, not a primary endpoint receipt.

## Admission rule

Do not cherry-pick individual reports into the paper evidence tree merely because their filenames match the campaign. Before admission, Richard and Oliver should review the producing commits and confirm the intended branch state; the reports must then be checked against their input manifests, profile hashes, rollout IDs, completeness flags, and any corresponding raw job outputs. Primary hidden rewards still require their verifier receipts or an equivalently digest-bound capsule. Any admitted source must be regenerated through `build_paper_results.py`, tested, and added to `snapshot-manifest.json` with an explicit evidence role.

Until that review happens, the paper keeps Opus block 1's two committed capsule-bound rewards and labels block 2--3 values as rounded pre-probe summary inputs.
