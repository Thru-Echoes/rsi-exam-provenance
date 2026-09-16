# Code and data artifact index

The implementation remains in the parent repository. This index avoids copying code into the ARA package.

| Role | Repository path | Paper use |
| --- | --- | --- |
| Decision gate | `gate/decide.py` | Applies the keep/revert/confirm-first rule and writes decision lines. |
| Provenance producer | `profile/build_capsule.py` | Builds the portable record from a job directory. |
| Offline verifier | `profile/verify_capsule.py` | Checks schema, digests, lineage, coverage, measurements, and protocol. |
| TRACE converter | `gate/trace_from_decisions.py` | Converts typed decisions to TRACE 0.5.1. |
| Shadow replay | `gate/shadow_replay.py` | Applies the policy post hoc to recovered candidate-parent pairs. |
| Campaign manifest | `docs/campaign/2026-09-instrument-ab/manifest.md` | Preregistered comparison design and endpoint rules. |
| Stage configuration | `docs/campaign/2026-09-instrument-ab/stages.json` | Models, windows, blocks, randomized order, and limits. |
| Fault-injection tests | `tests/test_rsi_exam_provenance.py` | Evidence for C01. |
| Conformance tests | `tests/test_conformance.py` and `tests/conformance/` | Cross-component contract checks. |
| Study narrative | `docs/PREFLIGHT.md` | Cohort observations and study limitations. |
| A/B generated evidence | `docs/shadow-audit/instrument-ab/` | Per-stage records, endpoints, audits, and source reports. |
| Paper result builder | `ara/nanda-2026/src/execution/build_paper_results.py` | Pins source bytes, parses all ten primary blocks and all 20 record outcomes, and writes the canonical paper result. |
| Paper result tests | `tests/test_paper_results.py` | Guards the 3/7 direction count, 18/20 record yield, source-revision refusal, and generated-file drift. |
| Canonical paper result | `ara/nanda-2026/evidence/results/paper-results.json` | Machine-readable primary result, evidence class per row, source hashes, and release blockers. |
| Layout-proof builder | `ara/nanda-2026/src/execution/build_submission_pdf.py` | Renders the working manuscript and generated result table as an anonymous two-column PDF. |
| Working PDF | `output/pdf/nanda-2026-track3-working-paper.pdf` | Visual submission proof; not an official IEEEtran build or approved submission. |

The submission artifact should cite a versioned tag and commit. The generated result already records a digest and evidence class for each input; the final freeze must additionally bind the raw Opus reward receipts if they are recovered. The PDF must be rebuilt in the official IEEE template after anonymity and author metadata are settled.
