# rsi-exam-provenance

A decision gate and a verifiable provenance record for [RSI-Exam](https://github.com/aiming-lab/RSI-Exam) rollouts.

RSI-Exam lets an agent improve a weak method for up to twelve hours, logging every version it
keeps or reverts and snapshotting each one, and then scores the final version on sealed seeds.
Every keep-or-revert decision the agent makes rests on one visible number over eight reused
seeds, and a version kept on a lucky number becomes the parent of everything after it. Nothing in
the job directory records why a keep was made or how sure the measurement was. This repository
adds:

- **A decision gate** (`gate/decide.py`, standard library only). It pairs the parent's and the
  candidate's per-seed scores, computes a bootstrap interval on the mean difference, applies a
  keep / revert / confirm-first rule, and appends one line to an append-only decision log. A
  candidate that screens well is frozen and confirmed on fresh seeds before it is kept.
- **A provenance record** (`profile/`). The producer binds every snapshot, the experiment log, the
  submitted version, the reward file, and each version's decisions by digest; the verifier checks
  the record offline: digests, lineage, coverage, recomputed intervals, and whether the gate's
  rules were followed. Integrity failures, protocol failures, and coverage downgrades are reported
  separately.
- **A TRACE converter** (`gate/trace_from_decisions.py`). The decision log becomes a TRACE 0.5.1
  session document: one decision event per line, the agent as proposer and the gate as resolver,
  and a `confidence` block per decision that ProofPress's evidence adapter imports unchanged.

Nothing in RSI-Exam's harness, prompt, task containers, or grader changes for official runs. A
rollout that runs the gate adds one step to the program text and is recorded as a modified-program
run; the record and verifier work on any rollout.

## How it attaches to a rollout

![What this repository adds and how it attaches to a rollout](docs/figures/components.svg)

Inside the loop, on gated rollouts only, the gate reads two per-seed result files and writes one
line per decision. After any rollout, the producer builds the record from the job directory, the
verifier checks it offline, the converter writes the TRACE document, and ProofPress imports it.
The gate writes numbers and digests only: no prompts, transcripts, or reasoning. Result files
live under `methods/results/<version>/`, never inside a snapshot or `main/`, because the grader
rejects any non-Python file there and scores the submission 0.0.

## The gate's rule

![The gate rule: screen on the visible seeds, freeze, confirm on fresh seeds](docs/figures/gate-rule.svg)

The interval on the eight visible seeds is screening evidence, because those seeds are reused for
every candidate across the whole search. An interval entirely below zero reverts. Anything else
freezes the candidate (its method digest is recorded), derives fresh seeds from that digest, and
confirms parent against candidate on 16 or more seeds the search never touched; only a
confirmation that clears the task's positive minimum effect keeps. The verdict (`clears`, `below`,
`inconclusive`) is the statistics and the disposition (`keep`, `revert`, `provisional`) is the
action; they are recorded separately, so a revert on inconclusive evidence is never read as proof
the change hurt. The interval is never the probability the decision was right and never a
statement about the sealed reward.

## Status

Fixture-verified, no real rollout yet. The gate, its modules, and the converter have 110 tests, the
profile has a 38-case conformance suite, and `docs/RUN_REPORT.md` records a full run on a demo
lineage: gate decisions, `trace-mcp validate` passing, a byte-equal typed TRACE round-trip, and a
successful `proofpress evidence import`. What comes next, milestone by milestone, is in
`docs/ROADMAP.md`: the verifier's decision checks and cache-free digests, the decision-evidence
report, then the first real rollout on `game2048_policy_search`. A gated rollout waits for
Milestone 3, which mounts the gate and its profile into the container and adds the trusted driver
and the program overlay that call it.

## Quick start

```
python3 -m unittest discover -s tests -t .          # 148 tests
python3 gate/decide.py --help
python3 gate/trace_from_decisions.py --help
python3 gate/shadow_replay.py --help
python3 gate/calibrate.py --help
python3 profile/build_capsule.py --job-dir fixtures/valid/job --task-dir fixtures/valid/task \
    --release "0.1@bc36dadb405b" --capsule-id fixture-rollout-001 --output /tmp/capsule.json
python3 profile/verify_capsule.py /tmp/capsule.json --artifact-root fixtures/valid/job --require-complete
```

The gate expects the task's per-seed result files under `methods/results/<version>/` (never inside
a snapshot or `main/`: the grader rejects non-Python files there).

## Documentation

- `docs/overview.md`: the exam in the detail that matters (protocol, visible versus sealed
  evaluation, the reward mapping, the 2048 task, the grader facts, contribution tracks), the
  problem, every component and what it attaches to, the gate's rule with a worked example, a
  gated rollout step by step, the evaluation ladder, the upstream offer and asks, how it fits
  ProofPress and TRACE, limits, and a glossary. Five figures.
- `docs/decision-log-contract.md`: the contract every component implements: the log line and its
  rules, the bootstrap algorithm, the TRACE `confidence` block and event mapping, the record's
  per-version decisions, and the verifier codes.
- `docs/profile-v3.md`: the provenance record's profile text.
- `docs/ROADMAP.md`: status, milestones, how the three repositories fit, the version-pin path,
  and the changes to propose in ProofPress.
- `docs/RUN_REPORT.md`: the last verified end-to-end run on fixture data, commands and outputs.
- `CLAUDE.md`: the working rules for agentic sessions in this repository.

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
`956025d7ecf6` on Hugging Face; ATIF v1.8 trajectories; TRACE schema 0.5.1 (release `v0.5.1`,
commit `a97d4e81fb3b4ec5134e992882d28a6cf97fac04`).

## License

Apache-2.0. See `LICENSE`.
