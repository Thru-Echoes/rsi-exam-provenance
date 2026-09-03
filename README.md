# rsi-exam-provenance

A decision gate and a verifiable provenance record for [RSI-Exam](https://github.com/aiming-lab/RSI-Exam) rollouts.

RSI-Exam lets an agent improve a weak method for up to twelve hours, logging every version it
keeps or reverts and snapshotting each one, and then scores the final version on sealed seeds.
Every keep-or-revert decision the agent makes rests on one visible number. This repository adds:

- **A decision gate** (`gate/decide.py`, standard library only). It pairs the parent's and the
  candidate's per-seed scores, computes a bootstrap interval on the mean difference, applies a
  keep / revert / confirm-first rule, and appends one line to an append-only decision log. A
  candidate that screens well is frozen and confirmed on fresh seeds before it is kept.
- **A provenance record** (`profile/`). The producer binds every snapshot, the experiment log, the
  submitted version, the reward file, and each version's decisions by digest; the verifier checks
  the record offline: digests, lineage, coverage, recomputed intervals, and whether the gate's
  rules were followed. Integrity failures, protocol failures, and coverage downgrades are reported
  separately.
- **A TRACE converter** (`gate/trace_from_decisions.py`). The decision log becomes a TRACE 0.5.0
  session document: one decision event per line, the agent as proposer and the gate as resolver,
  and a `confidence` block per decision that ProofPress's evidence adapter imports unchanged.

Nothing in RSI-Exam's harness, prompt, task containers, or grader changes for official runs. A
rollout that runs the gate adds one step to the program text and is recorded as a modified-program
run; the record and verifier work on any rollout.

## Status

Fixture-verified, no real rollout yet. The gate and converter have 31 tests, the profile has a
38-case conformance suite, and `docs/RUN_REPORT.md` records a full run on a demo lineage: gate
decisions, `trace-mcp validate` passing, a byte-equal typed TRACE round-trip, and a successful
`proofpress evidence import`. Next: the task profile and confirmation policy flag, deterministic
fresh-seed derivation, evaluation receipts, the verifier's decision checks, the decision-evidence
report, then the first real rollout on `game2048_policy_search`.

## Quick start

```
python3 -m unittest discover -s tests -t .          # 70 tests
python3 gate/decide.py --help
python3 gate/trace_from_decisions.py --help
python3 profile/build_capsule.py --job-dir fixtures/valid/job --task-dir fixtures/valid/task \
    --release "0.1@bc36dadb405b" --capsule-id fixture-rollout-001 --output /tmp/capsule.json
python3 profile/verify_capsule.py /tmp/capsule.json --artifact-root fixtures/valid/job --require-complete
```

The gate expects the task's per-seed result files under `methods/results/<version>/` (never inside
a snapshot or `main/`: the grader rejects non-Python files there). See
`docs/decision-log-contract.md` for the log line, the rule, and the TRACE mapping, and
`docs/profile-v2.md` for the record.

## Upstream

This is an evaluation-pipeline contribution on RSI-Exam's advisor path: a machine-checkable record
of why each version was kept, so an auditor's question ("did the score move for a real reason?")
becomes a checked table over bound versions, scores, and decisions. Two additions on RSI-Exam's
side would strengthen it: the submitted method's digest inside `reward.json`, and a published digest
per released job directory. A third is a fix or a note for the trap where the task instruction
(save results under `versions/vN/`) and the program's revert command together can place a
non-Python file in `main/`.

## Derivation pins

RSI-Exam repository `aiming-lab/RSI-Exam` @ `bc36dadb405b` (MIT); dataset `RSI-Exam/RSI-Exam` @
`956025d7ecf6` on Hugging Face; ATIF v1.8 trajectories; TRACE schema 0.5.0.

## License

Apache-2.0. See `LICENSE`.
