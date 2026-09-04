# RSI-Exam experiment provenance profile

Profile identifier: proofpress/rsi-exam-trajectory/v2

This profile is an interpretation layer over what an RSI-Exam rollout already
produces. It is passive and black-box at rollout time: it does not gate the
agent, replace the harness, or require any tool inside the container. A
record is built after the rollout from the harbor job directory and can be
verified offline by anyone holding that directory.

TRACE is optional enrichment. A record must be producible from the harness
artifacts plus the public task directory, with no TRACE anywhere; when a
TRACE session accompanied the rollout, its share-safe export binds into the
record and its decision events attach to versions.

## Source mapping

| Experiment fact | Primary source (harness-preserved) | Optional TRACE enrichment |
| --- | --- | --- |
| Rollout identity | Job directory name, `task.toml` | `rollout.trace_session_ids` |
| Saved method version | `methods/versions/v<N>` snapshot directory | `trace_event_ids` on the version |
| Kept or reverted | The version's line in `methods/experiment_log.md` | Decision events explaining why |
| Visible score | Score named on that log line, or a saved result file | — |
| Final submission | The snapshot whose tree digest equals `methods/main/` | — |
| Hidden evaluation | `verifier/reward.json` (and `score_details.json`) | — |
| Full transcript | `agent/trajectory.json` (ATIF), bound by digest | — |

The record never carries prompts, reasoning, transcripts, tool payloads, or
hidden targets: the schema is closed (unknown fields are rejected
everywhere) and every string is capped. Transcript content stays in the
ATIF file, which is bound by digest but not copied.

## Required bindings

Every version has a snapshot-directory identity (`v<N>`), an ordinal, parent
ids, a disposition from the protocol's own vocabulary (`baseline`, `kept`,
`reverted`, `submitted`), a reference to the experiment-log line that names
it, and a canonical tree digest of its directory. The
canonical tree digest is: one line `<sha256><two spaces><posix relpath>` per
regular file, relpaths byte-sorted, lines concatenated and hashed with
SHA-256; symlinks are rejected. Occurrence identity is the directory name,
never the content digest, because reverts legitimately repeat bytes.

Exactly one version is `submitted`; the final submission and the hidden
evaluation bind to it. The hidden reward file and the experiment log are
bound by file digest; each version's artifact locator must be exactly
`<versions_root>/<version_id>`; the frozen task and grader are bound by tree
digests of the task directory and its `tests/`.

## Governance boundary

Importing a record creates source events and evidence receipts. It does not
create a claim or admission. A later claim may be proposed for a bounded
statement about exact result binding or coverage. The normal Proofpress
deterministic checks, policy recommendation, and explicit human review
remain the admission boundary.

## Coverage and limitations

Coverage is anchored on the harness-preserved snapshot directories:
`complete` means the recorded versions and the `versions/v<N>` directories
match one to one; `partial` and `unverifiable` are first-class outcomes, and
a consumer can refuse anything short of `complete`. Completeness is always
relative to the directories supplied at verification: an experiment whose
snapshot, log entry, and trajectory evidence were all removed beforehand is
undetectable from what remains, which is exactly why the upstream proposal
asks for an issuer-published denominator. The bound trajectory is checked
by digest, not reconciled event by event.

The experiment log and snapshots are written by the agent and preserved by
the harness, and reward files are unsigned. The record is therefore
tamper-evident relative to the supplied job directory: version-to-score
bindings are self-consistent, not issuer-authenticated. It does not prove
semantic quality of the method, truth of the score, authorship, or that the
agent captured anything outside the methods tree. Two upstream additions
would strengthen it: the submitted tree digest inside `reward.json`, and a
published digest per job directory.

## CLI

Build a record from a job directory, then verify it:

    python3 profile/build_capsule.py \
      --job-dir JOB_DIR --task-dir TASK_DIR \
      --release "0.1@bc36dadb405b" --capsule-id ROLLOUT_ID

    python3 profile/verify_capsule.py \
      JOB_DIR/capsule.json --require-complete --json

The output keeps integrity and coverage as separate fields. A successful
integrity check with `partial` or `unverifiable` coverage is not a complete
provenance verdict, and `--require-complete` makes that distinction the exit
code.
