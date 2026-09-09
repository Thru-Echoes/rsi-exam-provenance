# Runbook: running RSI-Exam rollouts and the shadow audit

Operator tooling. Nothing under `gate/` or `profile/` imports anything here.

## Prerequisites

- A Docker daemon whose kernel sets `CONFIG_NFT_FIB_INET`. The task declares `no-network` for
  the agent phase and the verifier, and harbor enforces that with an nftables sidecar it enables
  only when that symbol is present. Docker Desktop's LinuxKit kernel lacks it and is refused at
  environment start; a Lima VM on a stock Ubuntu kernel (colima) works. Confirm directly rather
  than trust harbor's probe, which passes when `/proc/config.gz` is absent:

      docker run --rm --privileged alpine:3.23.4 sh -c \
        "apk add --no-cache nftables >/dev/null && nft add table inet t && \
         nft add chain inet t c '{ type filter hook prerouting priority 0; }' && \
         nft add rule inet t c fib daddr type local accept && echo ok"

- `harbor` 0.22.0 or later, and a checkout of RSI-Exam at commit `bc36dadb405b` with the task
  materials on disk under `tasks/`.
- `RSI_EXAM_ROOT` exported to that checkout.
- For the shadow audit: the evaluation image pulled, and every path the audit touches under a
  directory the Docker VM shares with the host (on colima and Docker Desktop that is your home
  directory by default; a bind mount from anywhere else is empty inside the container):

      docker pull python:3.13-slim
      docker image inspect --format '{{index .RepoDigests 0}}' python:3.13-slim

  The audit records that digest. Smoke-test the container once per machine before the first real
  replay (a scratch copy of the gate and the fixture task under your home directory):

      H=$HOME/rsi-shadow-smoke && rm -rf "$H" && mkdir -p "$H/methods/results" "$H/methods/gate" "$H/methods/versions"
      cp -R gate "$H/gate" && cp -R fixtures/task2048/environment "$H/task"
      cp fixtures/gated_mode/job/artifacts/app/methods/gate/profile.json "$H/methods/gate/profile.json"
      cp -R fixtures/task2048/policy_weak "$H/methods/versions/v1"
      docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
        --pids-limit 256 --memory 4g --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,size=256m \
        -e PYTHONHASHSEED=0 -e PYTHONDONTWRITEBYTECODE=1 -e LC_ALL=C -e TZ=UTC \
        -v "$H/task:/task:ro" -v "$H/gate:/gate:ro" -v "$H/methods:/methods" python:3.13-slim \
        python3 /gate/evaluate_suite.py --profile /methods/gate/profile.json --task-root /task \
        --policy-dir /methods/versions/v1 --suite /task/visible_seeds.json \
        --output /methods/results/v1/visible_result.json && ls -l "$H/methods/results/v1/" && rm -rf "$H"

  Expected: the runner's receipt JSON on stdout, then two files owned by you. Anything else is a
  STOP: the audit cannot run on this machine until it passes.

## Credentials

`$RSI_EXAM_ROOT/.env.gateway`, mode 600, git-ignored by RSI-Exam's own `.gitignore`:

    ANTHROPIC_BASE_URL=https://<gateway host>
    ANTHROPIC_AUTH_TOKEN=<token>

The base URL has no trailing `/v1`. `run_gateway.sh` unsets `ANTHROPIC_API_KEY` and
`CLAUDE_CODE_OAUTH_TOKEN` because both outrank the auth token in the claude-code adapter; a
leftover key would bill the wrong account without any error.

## Running a rollout

    runbook/run_gateway.sh <job-name> <agent-seconds> <multiplier> <k> <effort> [program.md] [template.j2]

Only the agent-execution phase spends. `agent_setup` installs the harness in the container and
takes about three minutes on no tokens; the verifier can take fourteen minutes on a strong policy.
The agent timeout is a ceiling, not a driver: a larger budget does not make a run longer, and an
agent stopped by the timeout leaves whatever is in `main/` at that instant to be graded.

Under a spend ceiling run one trial per invocation (`k` 1, a distinct job name each time) and
price each finished job before starting the next:

    RATES=opus python3 runbook/cost.py $RSI_EXAM_ROOT/jobs/<job-name>

`cost.py` refuses an unknown rate card, an unreadable session file, a malformed usage record, and
a job with no usage records; it never guesses. Start the next trial only while
`verified spend so far + the reservation for one trial <= the ceiling`.

## The provenance overlay and the helper

`autoresearch-provenance.md` is RSI-Exam's own program text with the loop block rewritten so that the
record can be built from what the agent leaves behind: the agent runs `provenance.py`, mounted read-only
at `/app/provenance.py`, instead of copying snapshot directories and appending log entries by hand, and the
helper owns everything under `methods/` except `main/`. `init` snapshots the inherited `main/` as `v0`,
logs it, measures it and prints the run window; `evaluate` copies `main/` to the next `versions/v<N>`,
appends that version's log block (id, parent, status, change, digest, score) and runs the task's
self-check; `decide v<N> kept|reverted` records the decision, a revert restoring the head into `main/`;
`restore v<K>` makes an older snapshot the head; `finalize` settles an undecided candidate and leaves
`main/` equal to the head; `status` shows the versions. The loop also tells the agent its run window and
how to budget it.

A candidate reads as `reverted` until its decision is durable, so an interrupted run never reports an
undecided version as kept. Every stop is repaired by the agent's next command: a snapshot without a log
block is adopted as the pending candidate with the parent recorded before staging, a block without its
status line is set to `reverted`, the head's block is reconciled from the state, an unmeasured candidate
is measured at `decide`, and `finalize` restores the head even when `main/` cannot be hashed. The remaining
windows are a few operations wide (between a snapshot's rename and its log block; between the two renames
of a restore) plus the stretch while the agent edits `main/` before `evaluate`. Snapshots are never
edited: a changed snapshot is refused. One command runs at a time (a lock under `.provenance/`).
`tests/test_provenance_helper.py` stops the helper at every checkpoint and asserts what the record
producer then says and that the next command recovers a complete record.

`mount-provenance.yaml` is RSI-Exam's `infra/prompts/mount.yaml` plus the helper's read-only mount;
`run_gateway.sh` selects it when the program text names `/app/provenance.py` (`MOUNT_YAML` and
`ARB_PROVENANCE_PY` override). A run under the overlay is a modified-program run. Pass the program and the
matching template as the last two arguments.

The replay-configuration generator takes `--planning-rule estimate-aware` to write the profile key that
selects the estimate-aware planning rule for a diagnostic pass of the audit; without the flag the profile
names no rule and the gate plans under the accepted one.

## The instrument overlay

`autoresearch-instrument.md` is the helper overlay with a loop in which a keep is a proposal the gate rules on. It
runs with `mount-instrument.yaml`, which mounts, beside the helper, a directory of the gate's scripts at `/app/gate`
(`ARB_GATE_DIR`; a clean copy of `gate/*.py`) and a task profile at `/app/profile.json` (`ARB_PROFILE`; written per
rollout with `runbook/make_profile.py`, for the instrument with `--floor 8 --max-seeds 16 --planning-rule
estimate-aware`). `run_gateway.sh` selects that mount when the program text names `/app/gate/` and refuses to start
without both variables. With the two mounts the helper measures every version with the gate's runner (a receipt
beside each result, and a safety report with the slowest move, the CPU per game and the policy's size), prints a
gate preview after `evaluate`, and on `decide v<N> kept` runs the gate's screening and, when the plan fits under the
cap and before the close-out mark, its confirmation; only a confirmed candidate becomes the head, and an overruled
proposal is recorded in the block. `decide v<N> reverted` consults no gate. A candidate the runner refused, or over
half of the grader's CPU or per-move limit on the public seeds, cannot be kept, and `finalize` walks back to the last
version within the margins. `init` prints the window's marks and every command the time used.

Limits, stated as they are. The replication key is mounted with the profile and readable by the agent, so a fresh
suite is auditable, not secret. What `init` sees (the mode, the profile's digest, the gate scripts' digest, the
safety fraction, the window) is bound to the rollout, and a command run under a different environment refuses; what
the helper cannot prevent is same-user tampering with files, because policy code and the helper run as the agent's
user: a safety report's slowest-move figure is not bound anywhere else (its CPU figure and size are checked against
the receipt-bound result and the snapshot), a policy can read the confirmation suite, and the gate can be invoked
directly. What makes such a run visible after the fact is the record: every decision line and receipt carries the
profile's digest, the safety reports carry the measured numbers, and the comparison's measures check both. The
contract resolves an open provisional decision only by a confirmation, so a confirmation a stop interrupted is
finished by the next `decide` or `finalize`, and a runner refusal during a confirmation leaves the decision open in
the gate's log, the candidate pending, the head restored into `main/`, and every later command refusing with the
reason. The per-move time is measured in process and underestimates the grader's sandboxed measurement, hence the
margin. A run under this overlay is a modified-program run. `tests/test_instrument.py` drives every path on the
fixture evaluator and verifies the record after each.

## Building and verifying the record

Never write into a job directory. Build every record into an audit root outside the jobs:

    python3 profile/build_capsule.py --job-dir $RSI_EXAM_ROOT/jobs/<job>/<trial> \
        --task-dir $RSI_EXAM_ROOT/tasks/game2048_policy_search --release <release> \
        --capsule-id <id> --model <model> --harness claude-code --output $AUDIT_ROOT/<id>/capsule.json
    python3 profile/verify_capsule.py $AUDIT_ROOT/<id>/capsule.json --artifact-root $RSI_EXAM_ROOT/jobs/<job>/<trial>

## The shadow audit

`gate/shadow_replay.py --help` states the contract. The procedure, per rollout:

1. Write a replay configuration outside the job directory and the repository:
   `python3 runbook/make_profile.py --task-dir <task> --rollout-id <id> --output $AUDIT_ROOT/<id>/profile.json`.
   It is written after the rollout, so it is a replay configuration, not a pre-registration.
2. Write the inputs manifest without evaluating anything, commit it under
   `docs/shadow-audit/<id>/inputs.json`, and push:
   `python3 gate/shadow_replay.py ... --container python:3.13-slim --inputs-only --output docs/shadow-audit/<id>/inputs.json`.
3. Run the audit in a fresh workdir under your home directory, requiring the committed manifest:
   `python3 gate/shadow_replay.py ... --container python:3.13-slim --expect-inputs docs/shadow-audit/<id>/inputs.json --workdir $AUDIT_ROOT/<id>/work --output docs/shadow-audit/<id>/report.json`.
4. Read the exit status. `0`: every pair reached a gate disposition. `1`: the report is complete
   but at least one pair failed, was refused, or was not replayable; read `summary.outcomes` and
   the refusals before using the report. `2`: the run could not proceed. Then commit and push the
   report.

The anchor is the pushed commit that carries the inputs manifest; it says nothing about what
happened inside the rollout. A workdir is used once; an interrupted run is rerun in a fresh
workdir from step 3. The policy runs inside the evaluator's process in a throwaway container,
as in the task's own self-check: the container protects the machine, not the result, against a
policy written to manipulate the evaluator, and every report says so in its `limits`.

## Vocabulary

Shadow audit, never in-rollout gate. Record-recoverable pairs, never the agent's action history.
Disagreement counts are descriptive and directionless. An exploratory outcome means the accepted
planning rule asked for more confirmation seeds than the cap allows; it is a finding about the
rule and the task's per-seed spread, not about the candidate. Tamper-evident from the pushed
manifest onward, never tamper-proof.
