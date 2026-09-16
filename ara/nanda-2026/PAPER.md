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

Self-improving agents repeatedly decide whether an observed change should become the parent of later work. The choice is consequential, but a conventional rollout may preserve neither the evidence used for it nor a machine-checkable link from that evidence to the submitted artifact. We present a decision-provenance layer that records candidate-parent comparisons, binds artifacts and measurements by digest, and verifies lineage, coverage, recomputed statistics, and protocol conformance offline. We study it in reduced-window, modified-program RSI-Exam rollouts. The evidence supports the integrity and auditability contribution and exposes incomplete or unstable native provenance in the observed cohorts. It does not support a claim that the tested decision gate improves sealed reward: across ten blocked comparisons, three favor the instrument and seven favor the helper. The first seven block results come from machine-generated endpoint tables; the three Opus results come from a committed pre-probe summary rounded to three decimals, while raw Opus reward receipts and secondary tables remain a release blocker. The artifact therefore treats efficacy as refuted under the tested conditions and a proposed confirmation-limit mechanism as a hypothesis, not a causal result.

## 1. Problem

An agent can improve a visible score while making a decision that does not survive fresh or sealed evaluation. If the rollout stores only a final method and an informal experiment log, an auditor cannot reliably reconstruct which exact candidate was compared with which parent, which evidence authorized the keep, or whether the recorded interval follows from the bound result files.

The paper's unit of analysis is a **keep-or-revert decision**, not an entire trajectory and not a model-generated explanation. A decision changes the ancestry of subsequent work: the selected candidate becomes a new parent, while a rejected candidate is excluded from that lineage. In a decentralized agent network, an incorrect or unverifiable keep can propagate beyond one process because another agent may discover, retrieve, and reuse the resulting artifact.

The contribution is therefore a record and verifier for the decision boundary. It makes three separable questions inspectable: what the agent proposed, what evidence the resolver used, and which exact artifact later work inherited. This fits Track 3's concern with provenance, audit trails, verifiable metadata, and accountability. The evaluation is single-agent; it is not itself a decentralized or multi-agent network experiment. It does not attempt to solve identity, reputation aggregation, or Sybil resistance.

## 2. System

The system has four distinct layers:

1. The RSI-Exam provenance implementation creates decision records, artifact digests, lineage links, and offline verification results.
2. TRACE expresses the runtime decision history: the agent proposes and the gate resolves.
3. ProofPress can import selected TRACE evidence for later human governance; import is compatibility, not approval, adoption, or independent verification.
4. ARA packages the paper's claims, experiments, negative results, source pointers, and research trajectory for machine and human review.

The layers deliberately do not collapse into one another. TRACE records a runtime decision; the portable record binds files and measurements; ProofPress governs later reuse; and ARA exposes the research argument and its evidence graph. The ARA directory does not replace any of those layers.

### 2.1 Record contract

For each submitted version, the record identifies the task and rollout, the version and its parent, the candidate and parent artifact digests, the evidence files used for comparison, the decision state, and the submitted artifact. The verifier recomputes digests and statistics from the exported job directory, checks that the declared ancestry is coherent, and reports integrity, coverage, and protocol outcomes separately. This separation matters: a record can be internally intact but incomplete, or complete but protocol-invalid.

The contract is tamper-evident relative to the supplied export. It is not an oracle for scientific truth and does not authenticate who produced a file. Those require external identity, attestation, or replication mechanisms.

## 3. Claims

- **C01 — supported:** the implementation can bind rollout artifacts, evidence, decisions, and lineage into a record whose internal consistency and protocol conformance can be checked offline.
- **C02 — supported in observed cohorts:** native agent-authored provenance is incomplete or structurally unstable in the examined reduced-window rollouts, while the instrumented path produces machine-checkable records or explicit refusals.
- **C03 — refuted under tested conditions:** the tested decision instrument improves final sealed reward relative to the helper comparator. The generated ten-block direction count is 3 versus 7. Opus values are summary-backed and rounded, so they support direction only until raw receipts are bound.
- **C04 — hypothesis:** confirmation planning limits may reject or delay some later candidates and thereby alter downstream search. The current evidence is mechanistically compatible with this explanation but is not a causal test.

The formal claim cards, conditions, dependencies, and falsification criteria are in [`logic/claims.md`](logic/claims.md).

## 4. Evaluation design

The comparison uses blocked pairs: one instrument-arm rollout and one helper-arm rollout under the same stage configuration. The instrument arm routes keep decisions through the statistical gate; the helper arm receives provenance bookkeeping without that gate. The primary endpoint is the within-block difference in final sealed reward. Secondary endpoints cover record outcomes, recovered candidate-parent pairs, gate dispositions, agent stop conditions, and descriptive comparisons with sealed snapshots. Exact configurations, randomized order, and missing-reward rules were fixed in the campaign manifest before the stages ran.

All runs are reduced-window, modified-program runs on one RSI-Exam task. They are not official RSI-Exam results. Counts describe these rollouts and do not establish a population rate.

## 5. Current evidence state

The generated result file pins every input to repository revision `727b9b821d7814d7467a29c1e740ce92eea7e219` and refuses a working-tree source that differs from that revision. It reports:

- Haiku: instrument favored in 2 blocks, helper favored in 2; mean within-block sealed-reward difference -0.0186.
- Sonnet: instrument favored in 1 block, helper favored in 2; mean difference -0.0171.
- Opus: helper favored in all 3 blocks; the approximate mean difference from rounded inputs is -0.144.
- Record production: 18 verified records from 20 started trials, split 9/10 in each arm. The two visible refusals are unsnapshotted submissions, one in each arm.

Thus the ten observed primary comparisons favor the instrument in 3 blocks and the helper in 7. We do not run or report an inferential efficacy test: the study is small, uses one task, and was not sized for a population effect. The Opus values are drawn from a committed pre-probe summary rather than a generated endpoint table and are rounded to three decimals. They are sufficient to recover block direction but not a final numerical freeze. The source hierarchy and remaining gaps are recorded in [`evidence/results/reconciliation-status.md`](evidence/results/reconciliation-status.md).

## 6. Interpretation

The negative efficacy result does not erase the systems contribution. A decision-provenance system can be useful precisely when it makes an unfavorable result auditable, refuses incomplete records, and prevents a narrative summary from outranking the underlying evidence. Here, the provenance workflow caught two different classes of incompleteness: decision-record refusals caused by a submitted version without a corresponding snapshot, and a paper-analysis gap in which an aggregate Opus summary existed without the raw receipts and secondary tables needed for release.

The strongest defensible contribution is therefore the record/verifier contract and the evidence-precedence workflow. The gate is an evaluated policy that supplies a useful stress test; it is not the paper's success criterion.

For decentralized agent systems, the implication is narrower than a global reputation score but more directly testable: an artifact consumer can demand a locally verifiable decision record before accepting a claimed improvement into its own lineage. A network can then attach reputation or policy to explicit verifier outcomes instead of to prose assertions. The record does not make reputation manipulation-resistant by itself, but it provides the inspectable event on which such a mechanism can operate.

## 7. Limitations and non-claims

- Digests make the record tamper-evident relative to supplied files; they do not prevent modification or establish that the contents are correct.
- Offline recomputation checks that results follow from bound evidence; it does not make author-run evidence independent.
- ProofPress import demonstrates schema compatibility, not adoption, verification, approval, or governed reuse.
- The interval describes a measured effect on evaluated seeds; it is not the probability that a decision is correct and is not a statement about sealed reward.
- The study uses one task, small stage sizes, modified programs, and reduced windows. It supports neither a general model ranking nor an official RSI-Exam performance claim.
- Causal explanations for the observed reward pattern remain hypotheses until directly tested.
- The study does not evaluate malicious record producers, key compromise, collusion, Sybil behavior, or cross-organization identity.
- Opus primary values are rounded summaries until raw receipts are recovered and bound; secondary Opus analysis is not reported.

## 8. Related work

W3C PROV provides a general vocabulary for entities, activities, agents, derivation, and provenance interchange. Our record is a task-specific executable profile: it binds the files and measurements needed to re-evaluate a keep decision and adds protocol checks that a generic provenance graph does not define. NANDA's enterprise-agent work foregrounds discovery, authentication, metadata, and interoperability across agent ecosystems; this paper focuses on the narrower handoff where one agent's claimed improvement may become another agent's inherited artifact. RSI-Exam supplies the long-horizon self-improvement setting and sealed evaluation boundary. TRACE supplies typed runtime decision events, while ARA supplies the research-facing claim, evidence, and trajectory package. ProofPress is used only as an optional downstream governance adapter.

## 9. Reproducibility and release

The companion artifact pins the source revision and hashes each paper-critical input in the generated JSON result. Code remains in this repository and is indexed from [`src/artifacts.md`](src/artifacts.md). The all-stage result can be rebuilt with the command in [`src/environment.md`](src/environment.md); `--check` fails if committed outputs drift. Before submission, the artifact must be regenerated from the frozen paper tag, structurally validated, semantically reviewed, anonymity-checked, and jointly approved. No ARA Hub publication is authorized by this draft.

## 10. Open decisions

The following remain pending: title, final Track 3 framing, authorship order and contributions, anonymity mode, artifact license, public-release timing, and whether the raw Opus receipts can be recovered before the freeze. The public CFP does not state an anonymity or artifact-link policy, so the working PDF remains anonymous and the ARA remains unpublished pending organizer or authenticated-submission guidance. The primary A/B denominator (10 blocks), direction count (3/7), and record-yield denominator (18/20, split 9/10 per arm) are now mechanically reconciled from pinned committed sources.

## References

1. Aiming Lab, “RSI-Exam,” repository and benchmark materials, 2026. <https://github.com/aiming-lab/RSI-Exam>
2. K. DeLong et al., “NANDA: An Enterprise Perspective on Agentic AI,” arXiv:2508.03101, 2025. <https://arxiv.org/abs/2508.03101>
3. W3C Provenance Working Group, “PROV-O: The PROV Ontology,” W3C Recommendation, 2013. <https://www.w3.org/TR/prov-o/>
4. J. Liu et al., “The Last Human-Written Paper: Agent-Native Research Artifacts,” arXiv:2604.24658, 2026. <https://arxiv.org/abs/2604.24658>
5. ARA Labs, “Agent-Native Research Artifact,” 2026. <https://github.com/ARA-Labs/Agent-Native-Research-Artifact>
