# Decision audit study: protocol draft

Status: research redesign in progress, 2026-09-16. This protocol is written after
inspection of the existing implementation and development vectors. It is not a
preregistration or an independent evaluation. The existing paper/PDF is the prior
review draft and has not yet been replaced by results from this study.

## Research question

Given an exported job directory and its decision record, which artifact,
measurement, and decision-state inconsistencies can a downstream consumer detect
offline, beyond checking document structure or file digests?

The unit of analysis is a supplied evidence package and an explicit audit question.
The target is consistency relative to supplied files, not runtime truth or global
completeness. An attacker who rewrites every artifact consistently may remain
undetectable without an external commitment or witness.

## Audit questions

1. Does the submitted method correspond to a recorded snapshot under the grader's
   source-file identity rules?
2. Do the evidence references identify the declared parent and candidate results?
3. Can the reported statistic and interval be recomputed with the declared
   orientation, algorithm, and seed?
4. Does a final disposition follow the declared decision protocol, including
   provisional decisions and their confirmations?
5. Is coverage complete relative to the supplied snapshot directory, and are
   missing required artifacts explicitly reported?

## Evidence tracks

### D: retrospective development replay

Run every committed `tests/conformance/vectors/*.json` case. Include the valid
baseline. These cases were used in development and are deliberately selected to
exercise checks; results describe known capability boundaries, not an unbiased
detection rate. Record every input hash and implementation revision.

Report the gate loader, converter, and full producer/verifier separately. The
converter already checks contract semantics: it must NOT be labeled a generic
schema-only baseline. Add a narrowly specified evidence-file-digest check, which
only resolves cited evidence files inside the fixture's methods directory and
compares their SHA-256 values. Its `accept` means those referenced bytes match,
not that the record is valid. It does not inspect evidence roles or rule state.

External TRACE and ProofPress expected outcomes are not measured here. Historical
fixture handoff in `docs/RUN_REPORT.md` is a separate interoperability case, not
evidence that all external implementations were rerun on this matrix.

### F: controlled fault injection (not yet executed)

Freeze a case manifest before inspecting new outputs. Define fault families from
the audit questions: submitted-version mismatch, missing evidence, mismatched
parent/candidate evidence, inconsistent orientation/statistic, unresolved
confirmation, and missing snapshot. Include clean packages and benign bytecode
cache variation. Distinguish raw corruption (stale digests) from semantic
inconsistency after updating affected digests. A coherent rewrite of all evidence
is an explicit out-of-scope control, not an expected rejection.

Use available real packages where all required source files can be redistributed;
otherwise label fixture cases synthetic. Enumerate eligible packages and exclusions
before running. Do not infer raw-file availability from a capsule or summary alone.
Author-designed cases remain author-designed even if fixed before execution.

Compare the same packages under explicit format checks, digest checks, and full
verification. For baseline checks that cannot answer a question, use
`not_assessed`, not rejection or successful verification of the question.

Report per-family outcomes, clean-case false rejections, explicit missing-evidence
outcomes, and operational errors. Do not count a crash as successful detection.
Retain failing cases; fixes require a new implementation version and a separately
reported rerun. Measure elapsed time and package size if making cost claims.

### R: real-run feasibility and failure cases

Use the existing cohort inventories and record tables with their recorded producer
versions. Select representative source-backed cases: visible results not exported,
cache-sensitive version identity, and log/snapshot ambiguity. Historical parser
failures must not be described as current verifier failures. Different cohorts are
not a randomized provenance intervention; their record yields are descriptive.

## Paper argument and decision rules

Introduction: a concrete handoff failure and the questions a recipient cannot
answer. Method: record semantics, verification rules, trust assumptions, and one
worked decision. Evaluation: D capability matrix, F controlled checks, R real-run
cases. Discussion: limitations and the cost of enforcing decision policy.

The reward A/B is a secondary deployment observation. Three instrument-favoring
blocks and seven helper-favoring blocks do not establish a general efficacy
refutation. Missing Opus receipts limit any retained reward analysis but do not
prevent a separately supported audit-consistency study.

Before rewriting the paper as a completed study: execute F, verify the raw sources
for retained R cases, and compare related work at the level of actual guarantees.
ARA organizes claims and evidence; its formatting is not evidence of novelty.
