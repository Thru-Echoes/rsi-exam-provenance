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

### The gate in motion

Three captured rollouts, rendered from their own files by `docs/figures/make_instrument_animation.py`:
every row is a recorded event, the plain line under each ruling is rendered from the recorded fields,
and the gate's own line is printed beneath it. Nothing in the figures is invented.

First, a rollout from before the instrument, under the exam's own program: the agent kept nine of nine
candidates, and the sealed seeds, scored afterwards, say four of those keeps made the policy worse. The
record could report it only after the grade.

![Before the instrument: the agent decided alone; the record could only report afterwards](docs/figures/instrument-before.svg)

Then the first Opus trial of the pre-registered comparison (one trial of it, no claim): in one 32-minute
window the agent wrote three candidates, the gate confirmed two of them on fresh seeds, one on top of the
other, the agent reverted the third itself after the preview, and finalize submitted the confirmed head,
which scored 0.551 on the exam's sealed seeds. The hidden-seed column joins the figure once the sealed
retrospective of that stage has run.

![Under the instrument at Opus scale: two keeps confirmed on fresh seeds in one window](docs/figures/instrument-opus.svg)

Last, the instrument's Haiku pilot, the rollout the reading below walks through number by number.

![Under the instrument: every keep is measured before it sticks](docs/figures/instrument-now.svg)

**What you are looking at, in plain words.** An AI agent gets a short time window to improve a small
program that plays the game 2048. The better the program plays, the higher its score. When the window
closes, the exam grades whatever program the agent left in place, on 16 hidden games the agent never sees.

- **Version, parent.** Each attempt the agent saves is a version (v1, v2, v3). The parent is the version it
  started from. "v2, parent v0" means the agent went back to the starting program and tried a different idea.
- **Score on the public seeds.** The agent tests each version on the same 8 practice games. "2,222 on the
  public seeds (parent 2,060)" means the new version averaged 2,222 points over those 8 games and its parent
  averaged 2,060. Higher is better.
- **Keep, revert.** A keep makes the new version the starting point for everything that follows. A revert
  throws it away and goes back to the parent. A keep is the decision that compounds: every later edit builds
  on it.
- **Why a keep can be wrong.** 2048 is a game of luck as well as skill: the same program can score 1,000 or
  5,000 depending on which tiles appear. Eight practice games are few, and they are the same eight every
  time, so a version can look better by luck, and an agent that keeps testing on the same games drifts toward
  tweaks that happen to suit those games.
- **What the gate does with a keep.** First it looks at the 8 game-by-game differences and asks whether the
  improvement is clearly bigger than the luck. If it might be, it runs a confirmation: fresh games nobody has
  used before, both versions play them, and the keep stands only if the new version still wins by at least a
  minimum margin. When the practice games say it would take thousands of games to tell (the "2,046 fresh
  seeds, cap 16" line), the gate says no rather than guess.
- **"interval -578 to 1,072".** The range of average improvement that the 8 practice games are consistent
  with. When that range includes zero, the practice games cannot tell whether the version is better at all.
- **"+1,364 · 13 up, 3 down".** The hidden 16 games, scored afterwards and never used during the run: the
  new version beat its parent on 13 of them and lost on 3, by 1,364 points on average. This column is the
  answer key. "This keep made it worse" means the parent would have scored higher on the hidden games;
  "this revert lost a real gain" means the discarded version would have.

**Why this matters.** Before the instrument, the agent kept whatever looked better on the practice games; in
the rollout shown in the overview, four of its nine keeps made the program worse on the hidden games, and
the final submission scored below a version it had three keeps earlier. The record could show this
afterwards, when the grade was already in. Now a keep only sticks if it survives fresh games, so the agent's
work compounds on real improvements rather than lucky ones, a regression cannot quietly become the new
baseline, the program that gets submitted has passed a safety check (legal moves, time per move, file size)
so it cannot score zero on a technicality, and every ruling is written down with digests, so anyone can check
afterwards which version was measured on which games with what result.

**The honest trade-off.** Measuring costs time (a confirmation runs both versions on fresh games, one to four
minutes for a strong program), and the rule is deliberately cautious: it will sometimes discard a real
improvement it could not tell from luck, as it did twice in the Haiku pilot shown last. Whether the trade is worth it is
the question the pre-registered A/B answers: same model, same window, gate on against gate off, judged by the
hidden-game score of what each one submits.

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
