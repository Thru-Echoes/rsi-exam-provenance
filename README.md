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

## In one picture

![Six tries. Alone they chain. With the gate, the bad ones get pruned](docs/figures/with-and-without-tree.svg)

An illustration, not a measured run. Every try an agent makes starts from the version it currently
trusts. Alone, that is always the last thing it kept, so a lucky keep becomes the parent of everything
after it and the mistake compounds. With the gate, a try the fresh games reject is thrown away and the
next try starts again from the last confirmed version, so a bad branch never becomes anyone's parent.
Every ruling is written down with a fingerprint of the code and the games it ran on. Real rollouts,
animated from their own files with a plain-language reading, are in [docs/in-motion.md](docs/in-motion.md).

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

### What the rule buys, and what it costs

![What the agent sees, and what is real](docs/figures/with-and-without-curves.svg)

The same illustration from the other side. The grey line is the score on the practice games, the only
number the agent can see. The coloured line is what the hidden games would say at that moment. Alone,
the two drift apart at every lucky keep, and the agent watches a number climb that is not really
climbing. With the gate they stay together, because a keep only sticks when fresh games agree. The
cost is on the same picture: a rejected try is a real attempt thrown away, and some of those would
have been improvements the eight practice games were simply too few to prove.


## Status

Ten real rollouts of `game2048_policy_search` have run (four on `claude-haiku-4-5`, six on
`claude-opus-5`), and the record builds for five of them; `docs/PREFLIGHT.md` records the real job
layout and what the tooling did with it. The gate, its modules, the converter, the record and the
report are fixture-verified, and `docs/RUN_REPORT.md` records a full run on a demo lineage through
`trace-mcp validate` and a `proofpress evidence import`. A second-model review found that the gate
cannot be trusted inside the agent's container, so Milestone 3 runs it on the host after the
rollout, as a shadow audit over the record's candidate-parent pairs, with policy code isolated in a
container; `docs/ROADMAP.md` has the milestones and the deferred in-container instrument.

## Quick start

```
python3 -m unittest discover -s tests -t .          # 336 tests
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
