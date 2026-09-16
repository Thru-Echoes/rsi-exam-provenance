# Related work: comparison of guarantees

Primary pages checked 2026-09-16. Relations below are author analysis, not measured
head-to-head comparisons.

| Source | Established function | Relation to this paper |
| --- | --- | --- |
| [PROV-CONSTRAINTS](https://www.w3.org/TR/prov-constraints/) | Consistency constraints and reasoning over provenance histories | extends at application level: executable paired-score recomputation and keep/confirmation semantics; provenance validation itself is prior art |
| [in-toto, USENIX Security 2019](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias) | Cryptographic verification of software supply chains | complementary: authenticating production is stronger than our unsigned boundary; no composition implemented |
| [MLflow tracking](https://mlflow.org/docs/latest/ml/tracking/) | Stores experiment parameters, metrics, and artifacts | complementary storage; no comparative product experiment or impossibility claim |
| [RSI-Exam](https://github.com/aiming-lab/RSI-Exam) | Executable agent self-improvement task environment | application context; reduced-window historical runs are not official benchmark results |
| [ARA](https://github.com/ARA-Labs/Agent-Native-Research-Artifact) | Layered claims, experiments, code, evidence, exploration history | packaging method, not the paper's research contribution |
| TRACE and ProofPress | Typed decision representation and downstream evidence import | implementation case: docs/RUN_REPORT.md records exact historical release pins, projected fields, and the absence of admission |

The novelty claim is deliberately narrow: an executable decision profile and
an empirical characterization of its additional checks in this task. No first-ever
claim, survey-completeness claim, universal dominance, or security equivalence is made.
