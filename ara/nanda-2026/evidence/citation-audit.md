# Citation and venue audit

## Current manuscript audit - 2026-09-16

The old audit below is retained as historical context, not the current bibliography.
The revised manuscript has five references: RSI-Exam, PROV-CONSTRAINTS, in-toto,
MLflow tracking, and the ARA repository. NANDA and the ARA arXiv paper are no longer
bibliography entries. Rechecked the following primary pages for the revised claims:

- https://www.w3.org/TR/prov-constraints/ - W3C Recommendation, 30 April 2013;
  editors James Cheney, Paolo Missier, Luc Moreau. Explicit consistency constraints
  exist already; the manuscript does not claim to invent provenance validation.
- https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias -
  in-toto, USENIX Security 2019, Santiago Torres-Arias and four coauthors. Its
  cryptographic supply-chain guarantees are distinct from unsigned package checks.
- https://mlflow.org/docs/latest/ml/tracking/ - tracking of runs, parameters,
  metrics and artifacts. No experimental product-superiority claim is made.
- https://github.com/ARA-Labs/Agent-Native-Research-Artifact - four-layer artifact
  organization. ARA is the companion format, not this paper's research novelty.

The RSI-Exam setting and venue facts were verified in the earlier audit below;
the workshop page was rechecked on 2026-09-16. Author approval, anonymity, and
artifact-link decisions remain external-submission checks, not claims of approval.

## Historical audit of the superseded manuscript

**Checked:** 2026-09-15 America/Los_Angeles

This audit records the primary public pages used to verify the four references in the anonymous IEEE review source and the venue facts that affect release. It verifies bibliographic and public-page metadata, not the paper's local experimental claims.

| Key | Primary page | Verified metadata used in the paper |
| --- | --- | --- |
| `rsiexam` | <https://github.com/aiming-lab/RSI-Exam> | Repository title: *RSI-Exam: Measuring Recursive Self-Improvement on Long-Horizon, Executable Research Tasks*. The official README describes the agent container, fresh hidden-data grading container, 12-hour run setting, and `verifier/reward.json` output. |
| `prov` | <https://www.w3.org/TR/prov-o/> | *PROV-O: The PROV Ontology*, W3C Recommendation, 30 April 2013. The recommendation states that PROV-O represents and interchanges provenance across systems and contexts. |
| `nanda` | <https://arxiv.org/abs/2508.03101> | *Using the NANDA Index Architecture in Practice: An Enterprise Perspective*, Sichao Wang, Ramesh Raskar, Mahesh Lambe, Pradyumna Chari, Rekha Singhal, Shailja Gupta, Rajesh Ranjan, and Ken Huang; arXiv:2508.03101, submitted 5 August 2025. |
| `ara` | <https://arxiv.org/abs/2604.24658> | *The Last Human-Written Paper: Agent-Native Research Artifacts*, Jiachen Liu et al.; arXiv:2604.24658, version 3 dated 19 May 2026. The abstract describes four ARA layers: scientific logic, executable code/specifications, an exploration graph, and claim-grounding evidence. |

## Venue facts

Primary page: <https://projectnanda.org/workshops/ieeetps26/>

Parent-conference cross-check: <https://tps.ieee-cs.org/2026/>

- Track 3 explicitly names manipulation-resistant reputation, provenance and audit trails, verifiable agent metadata, and governance for decentralized networks.
- Short papers may use up to four pages in standard IEEE two-column conference format, including references.
- The listed submission deadline is 2026-09-17 at 23:59 AoE; notification is 2026-09-26 and camera-ready is 2026-09-30.
- The public page says to select the IEEE NANDA track in EasyChair.
- The public page does not state whether review is anonymous or whether an author-controlled artifact link may appear in the review manuscript. This is an absence check, not evidence that either practice is allowed; the working review source therefore remains anonymous and omits the repository link.
- The IEEE TPS 2026 parent homepage lists NANDA as a co-located workshop but provides no additional workshop-specific review policy. The 2025 parent conference's main research track required anonymous submissions, but a prior-year main-track rule cannot be imported as the 2026 workshop rule.

## Freeze rule

Re-check the five reference/venue pages and the 2026 parent-conference page at the final freeze. If any title, version, submission date, format rule, anonymity rule, or artifact-link rule changes, update the manuscript, `venue-rules.md`, and this audit together before rebuilding the PDF.
