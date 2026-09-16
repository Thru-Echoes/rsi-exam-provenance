# Offline decision audit study

This is the research redesign following review of the initial NANDA draft. Read
`PROTOCOL.md` for the research question, planned controlled evaluation, and limits.
The ARA manuscript has been rewritten around the controlled audit question.

## Completed: retrospective development replay

Run `python3 studies/decision-audit/replay_development.py` from the repository root.
`development-results.json` records the output with source hashes and the base Git
revision. The new study files were uncommitted at execution; their exact bytes are
identified by the recorded hashes. A rerun after committing changes the head field.

Ten existing development cases were replayed: one valid baseline and nine adversarial
documents. All local outcomes matched the existing expectations; the original
conformance suite also passed (four tests). This confirms reproduction of known
development behavior, not performance on unseen errors.

| Check | Valid baseline | Adversarial cases rejected |
| --- | --- | --- |
| Referenced evidence-file SHA-256 only | accept | 0 of 9 |
| Gate log loader | accept | 1 of 9 |
| Converter with contract checks | accept | 7 of 9 |
| Producer plus profile verifier | accept | 9 of 9 |

These checks have different responsibilities. File-digest acceptance means only
that cited primary evidence bytes match; the loader is not a general audit tool.
The converter includes protocol checks and is not a schema-only baseline. Cases
were deliberately developed to expose these distinctions; counts are not general
detection rates and are not a comparison against observability products.

Two cases separate the converter from the complete verification path:
`lower_is_better_orientation` and `replication_reduction`. Their converter outputs
are accepted while the complete path rejects them. Explicit captured reasons are
`interval_not_reproducible` / `estimate_not_reproducible` for the orientation case,
and `protocol:replication_reduction` for reduced confirmation. The research runner
now records validation reasons and lets unexpected exceptions abort execution.

The nine full-path refusals consist of three producer refusals and six verifier
refusals. This distinction changes the interpretation of one case:
`descendant_of_open_provisional` is refused by the producer because `v4` is missing,
before the verifier checks provisional ancestry. Its end-to-end rejection does
NOT demonstrate detection of the fault named by the case. The converter does
explicitly reject unresolved provisional ancestry. Likewise, `aliased_holdout`
produces `holdout:interval_evidence_incomplete` in the verifier. These results
motivate the controlled study's requirement that each injected fault have all
other prerequisites satisfied and that the reported reason match the audit claim.

## Completed: controlled package study

Run `python3 studies/decision-audit/run_faults.py`. The manifest was committed at
`c1bcd7d` before first execution, after inspecting implementation and tests.
The report `fault-results.json` binds the exact runner and fixture bytes.
Nine authored faults are rejected by full verification, versus one by structure
and three by structure plus bindings. Both valid controls pass; a consistently
rewritten unsigned reward also passes. These are twelve synthetic packages from
one base fixture, not a real-world detection-rate estimate.

The missing-snapshot case is refused with `file:artifact:v2:missing_file`, not
the expected `file:version:v2`. Thus nine refusal outcomes match but only eight
diagnostic targets match. `all_expectations_met: false` is intentionally retained.
Unexpected exceptions abort instead of being counted as detections.

Historical real-run reports remain weaker contextual evidence: original job
directories are not all included and are not newly reproduced end to end.

No new agent rollouts or external services are needed for the completed replay.
