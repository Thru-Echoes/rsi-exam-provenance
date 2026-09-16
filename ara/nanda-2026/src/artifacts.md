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

The submission artifact should cite a versioned tag and commit and include a machine-generated manifest for every paper-critical source.
