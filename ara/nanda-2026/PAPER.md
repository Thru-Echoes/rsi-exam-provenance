---
title: "Auditable Keeps: Offline-Verifiable Decision Provenance for Self-Improving Agents"
authors:
  - "Richard Tang"
  - "Oliver (full name and order pending joint confirmation)"
year: 2026
status: draft-not-approved
---

# Auditable Keeps: Offline-Verifiable Decision Provenance for Self-Improving Agents

**Draft status:** working paper scaffold for the IEEE TPS 2026 NANDA workshop, Track 3. The title, claim boundary, result table, authorship order, and release decision remain subject to joint approval. This file is not a submission.

## Layer Index

| Layer | Location | Count/status |
| --- | --- | --- |
| Problem | `logic/problem.md` | 3 observations, 3 gaps, 1 key insight |
| Claims | `logic/claims.md` | 4 claims |
| Concepts | `logic/concepts.md` | 8 concepts |
| Experiments | `logic/experiments.md` | 4 experiments/analyses |
| Solution | `logic/solution/` | architecture, contract, constraints |
| Implementation | `src/` | environment plus external-artifact index |
| Trace | `trace/exploration_tree.yaml` | 9 source-bounded nodes |
| Evidence | `evidence/` | draft manifest and unresolved-result ledger |

## Abstract

Self-improving agents repeatedly choose whether an observed change should become the parent of later work. The choice is consequential, but a conventional rollout may preserve neither the evidence used for the choice nor a machine-checkable link from that evidence to the submitted artifact. We present a decision-provenance layer that records candidate-parent comparisons, binds artifacts and measurements by digest, and verifies lineage, coverage, recomputed statistics, and protocol conformance offline. We study it in reduced-window, modified-program RSI-Exam rollouts. The current evidence supports the integrity and auditability contribution and exposes incomplete or unstable native provenance in the observed cohorts. It does not support a claim that the decision gate improves sealed reward: the available comparison-stage summaries favor the instrument in three of seven currently reconciled blocks and the helper in four, while the final three Opus blocks are not yet represented by committed endpoint tables. The artifact therefore treats efficacy as a falsified claim under the tested conditions and treats a proposed mechanism involving confirmation limits as a hypothesis, not a causal result.

## 1. Problem

An agent can improve a visible score while making a decision that does not survive fresh or sealed evaluation. If the rollout stores only a final method and an informal experiment log, an auditor cannot reliably reconstruct which exact candidate was compared with which parent, which evidence authorized the keep, or whether the recorded interval follows from the bound result files.

The paper's unit of analysis is a **keep-or-revert decision**, not an entire trajectory and not a model-generated explanation. The contribution is a record and verifier for that unit.

## 2. System

The system has three distinct layers:

1. The RSI-Exam provenance implementation creates decision records, artifact digests, lineage links, and offline verification results.
2. TRACE expresses the runtime decision history: the agent proposes and the gate resolves.
3. ProofPress can import selected TRACE evidence for later human governance; import is compatibility, not approval or verification.

The ARA directory is the paper-facing claims, evidence, and exploration package. It does not replace any of those layers.

## 3. Claims

- **C01 — supported:** the implementation can bind rollout artifacts, evidence, decisions, and lineage into a record whose internal consistency and protocol conformance can be checked offline.
- **C02 — supported in observed cohorts:** native agent-authored provenance is incomplete or structurally unstable in the examined reduced-window rollouts, while the instrumented path produces machine-checkable records or explicit refusals.
- **C03 — refuted under tested conditions:** the tested decision instrument improves final sealed reward relative to the helper comparator. The currently reconciled seven blocks do not show improvement, and the remaining stage cannot be included until its committed endpoint table is present.
- **C04 — hypothesis:** confirmation planning limits may reject or delay some later candidates and thereby alter downstream search. The current evidence is mechanistically compatible with this explanation but is not a causal test.

The formal claim cards, conditions, dependencies, and falsification criteria are in [`logic/claims.md`](logic/claims.md).

## 4. Evaluation design

The comparison uses blocked pairs: one instrument-arm rollout and one helper-arm rollout under the same stage configuration. The primary endpoint is the within-block difference in final sealed reward. Secondary endpoints cover record outcomes, recovered candidate-parent pairs, gate dispositions, agent stop conditions, and descriptive comparisons with sealed snapshots. Exact configurations were fixed in the campaign manifest before the stages ran.

All runs are reduced-window, modified-program runs on one RSI-Exam task. They are not official RSI-Exam results. Counts describe these rollouts and do not establish a population rate.

## 5. Current evidence state

Committed endpoint tables currently cover four Haiku blocks and three Sonnet blocks. They report:

- Haiku: instrument favored in 2 blocks, helper favored in 2; mean within-block sealed-reward difference -0.0186.
- Sonnet: instrument favored in 1 block, helper favored in 2; mean difference -0.0171.
- Opus: six records are committed and marked verified, but the branch does not contain the stage endpoint, spend, or complete secondary-result tables required for the paper analysis.

Thus the reconciled comparison contains seven blocks: 3 favor the instrument and 4 favor the helper. A separate handoff summary reports a ten-block total of 3 versus 7, but that value is not elevated into the paper result until the missing Opus endpoint sources are committed and checked. Record-yield summaries also disagree across working notes; the source-level reconciliation is tracked in [`evidence/results/reconciliation-status.md`](evidence/results/reconciliation-status.md).

## 6. Interpretation

The negative efficacy result does not erase the main systems contribution. A decision-provenance system can be useful precisely when it makes an unfavorable result auditable, refuses incomplete records, and prevents a narrative summary from outranking the underlying evidence.

The strongest defensible contribution is therefore the record/verifier contract and the evidence-precedence workflow. The gate is an evaluated policy that supplies a useful stress test; it is not the paper's success criterion.

## 7. Limitations and non-claims

- Digests make the record tamper-evident relative to supplied files; they do not prevent modification or establish that the contents are correct.
- Offline recomputation checks that results follow from bound evidence; it does not make author-run evidence independent.
- ProofPress import demonstrates schema compatibility, not adoption, verification, approval, or governed reuse.
- The interval describes a measured effect on evaluated seeds; it is not the probability that a decision is correct and is not a statement about sealed reward.
- The study uses one task, small stage sizes, modified programs, and reduced windows. It supports neither a general model ranking nor an official RSI-Exam performance claim.
- Causal explanations for the observed reward pattern remain hypotheses until directly tested.

## 8. Reproducibility and release

The companion artifact pins the repository commit and the hashes of paper-critical source tables in [`evidence/snapshot-manifest.json`](evidence/snapshot-manifest.json). Code remains in this repository and is indexed from [`src/artifacts.md`](src/artifacts.md). Before submission, the artifact must be regenerated from the frozen paper tag, structurally validated, semantically reviewed, anonymity-checked, and jointly approved. No ARA Hub publication is authorized by this draft.

## 9. Open decisions

The following remain pending: title, final Track 3 framing, claim statuses after source reconciliation, canonical A/B denominator, record-yield denominator, authorship order and contributions, anonymity mode, artifact license, and public-release timing.
