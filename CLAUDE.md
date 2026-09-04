# rsi-exam-provenance: working rules for agentic sessions

## What this repository is

A decision gate and a provenance record for [RSI-Exam](https://github.com/aiming-lab/RSI-Exam)
rollouts. The gate turns each keep-or-revert decision an agent makes into a measured decision
(paired per-seed deltas, a bootstrap interval, a rule), records it in an append-only log, and the
post-rollout tooling binds every version, decision, and result file into an offline-verifiable
record. A converter turns the decision log into a TRACE session document that ProofPress can
import as evidence. Nothing in RSI-Exam's harness, prompt, task containers, or grader changes for
official runs.

Start with `README.md`, then `docs/overview.md` (the exam, the gate's rule, the components, and
the limits, with figures), `docs/decision-log-contract.md` (the contract every component
implements), `docs/profile-v2.md` (the provenance record), `docs/ROADMAP.md` (status and
milestones), and `docs/RUN_REPORT.md` (the last verified end-to-end run on fixture data).

## Layout

```
gate/decide.py                 the decision gate (gated mode with a task profile; replay mode)
gate/treedigest.py             cache-free, Python-only method-tree digests
gate/task_profile.py           the per-rollout task profile (rsi-exam-gate-profile/v1)
gate/seeds.py                  fresh confirmation suites (rsi-exam-gate/hmac-seeds/1) and the planning rule
gate/evaluate_suite.py         the evaluation runner that writes receipts (rsi-exam-gate-receipt/v1)
gate/restore.py                put a snapshot back into main/ without nesting it
gate/trace_from_decisions.py   decision log -> TRACE 0.5.0 session document
profile/schema.json            the provenance record's JSON Schema (profile v2)
profile/build_capsule.py       job directory -> provenance record
profile/verify_capsule.py      offline verifier for a record
fixtures/valid/                a harbor-shaped job directory with its golden record
fixtures/task2048/             the 2048 task's evaluator, engine, seed file, and starter policy at the pinned revision (MIT; see NOTICE), plus a variant policy
tests/                         unittest suites (run: python3 -m unittest discover -s tests -t .)
docs/                          overview, contract, profile, roadmap, run report
docs/figures/                  the SVG figures and make_figures.py, which regenerates them
report/                        the decision-evidence report generator (planned)
```

## Rules that hold everywhere in this repository

- **Standard library only** in `gate/`, `profile/`, and their tests. The RSI-Exam sandbox has no
  network and nothing installed, and the verifier must run anywhere.
- **Fail loud.** A missing result file, a seed-set mismatch, a malformed log line, a digest
  mismatch, or a contract violation raises or returns a named error. Nothing warns and proceeds.
- **Evidence never lives in the policy tree.** Result files, confirmation results, and receipts go
  under `methods/results/<version>/`, never inside `methods/versions/<version>/` or
  `methods/main/`. The RSI-Exam grader rejects any non-Python file under `main/` and scores the
  submission 0.0; a snapshot that carries a result file zeroes the submission the moment it is
  restored. The gate refuses such locators.
- **Digests of a method exclude bytecode caches** (`__pycache__/`, `*.pyc`, `*.pyo`), as the
  grader does; those bytes drift on every import.
- **Vocabulary.** Tamper-evident, never tamper-proof, immutable, trustless, notarized, or
  independent. An interval describes the measured visible-split effect that motivated a decision;
  it is never the probability the decision was right and never a statement about the sealed
  reward. A verdict (`clears`, `below`, `inconclusive`) is the statistics; a disposition (`keep`,
  `revert`, `provisional`) is the action; keep them separate in code and prose.
- **The log and the TRACE document carry numbers, identifiers, locators, and digests only.** No
  prompts, reasoning, transcripts, or tool payloads.
- **Nothing here changes an official RSI-Exam run.** A rollout that runs the gate adds one step
  to the program text and is recorded as a modified-program run. The post-rollout tooling works
  on any rollout.

## Git

- Work on a branch; open a pull request; never push to `main` directly.
- Commit messages and pull-request text are self-contained: what changed and why, in durable
  terms. No session narrative, no tool or assistant attribution footers, no internal labels.
- Before pushing: `python3 -m unittest discover -s tests -t .` must pass and `pyright` (basic
  mode, `pyrightconfig.json`) must be clean on changed files.

## TRACE

TRACE project name: "rsi-exam-provenance"

When the TRACE MCP server is available, start a session for multi-step work, propose decisions
before acting, log one contribution per artifact with `direction` and `execution`, and never
fabricate or retroactively alter events. A sparse honest record beats a dense fabricated one.

## Related projects

- RSI-Exam: https://github.com/aiming-lab/RSI-Exam and the task materials at
  https://huggingface.co/datasets/RSI-Exam/RSI-Exam (this repository pins repository commit
  `bc36dadb405b` and dataset revision `956025d7ecf6`).
- TRACE (decision-level provenance protocol and MCP server): https://github.com/Thru-Echoes/TRACE
- ProofPress (evidence import of TRACE documents, `proofpress evidence import`):
  https://github.com/chenmingtang830/proofpress
