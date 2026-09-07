# Preflight: the real job layout

The first engineering task in Milestone 1 is to run `game2048_policy_search` for real, observe the
job directory RSI-Exam actually publishes, and record it here. This document is that observation.

Nothing here is a score. Every run below used a reduced model and a reduced time budget, so the
numbers describe the harness and the tooling, not the exam. The gate did not run inside any
container: mounting it, the trusted driver, and the program overlay that calls it are Milestone 3.
What ran is the published task, unmodified, plus the post-rollout tooling on the result.

## What was run

| | |
| --- | --- |
| Task | `game2048_policy_search`, RSI-Exam repository commit `bc36dadb405b` |
| Harness | `harbor` 0.22.0, `claude-code` adapter |
| Agent model | `claude-haiku-4-5`, not the exam's pinned model |
| Program overlay | `infra/prompts/autoresearch.md` with `infra/prompts/mount.yaml` |
| Container runtime | Docker Engine 28.5.2 in a Lima VM, Ubuntu kernel 6.8.0, 6 CPU / 16 GB |

## The container runtime has to enforce `no-network`

`game2048_policy_search` declares `network_mode = "no-network"` for the agent phase and again for
the verifier environment. harbor only advertises that capability when its nftables egress-control
sidecar is usable, and it gates the sidecar behind a kernel probe for `CONFIG_NFT_FIB_INET`
(`harbor/environments/docker/docker.py`, `_egress_control_kernel_support` and
`_requires_egress_control`). When the probe fails, `harbor/environments/base.py` raises

```
ValueError: network_mode='no-network' is not supported by EnvironmentType.DOCKER environment.
```

This is a hard refusal at environment start, before any model tokens are spent, and it applies to
the no-agent run as well, because the verifier environment carries the same declaration. Any
non-public policy on any phase triggers the requirement, so there is no partial path.

A Docker Desktop 4.51.0 LinuxKit kernel (6.12.54) does not set `CONFIG_NFT_FIB_INET` and is
refused. A Lima VM on a stock Ubuntu 6.8 kernel is accepted and runs the task as published.

One caveat about the probe: it exits successfully when `/proc/config.gz` is absent, which is the
normal case on Ubuntu, so a passing probe is not by itself evidence of support. Confirm the
capability directly instead, by loading a rule that needs it:

```
nft add table inet t
nft add chain inet t c '{ type filter hook prerouting priority 0; }'
nft add rule inet t c fib daddr type local accept
```

The LinuxKit kernel does ship `/proc/config.gz`, which is why that path failed loudly rather than
passing the probe and then failing at runtime.

## The job directory

```
jobs/<job-name>/
  config.json  lock.json  result.json  job.log
  <task>__<trial-id>/
    agent/claude-code.txt          full harness transcript
    agent/trajectory.json          normalized ATIF trajectory
    agent/sessions/projects/-app/  the harness's own session records, with per-message token usage
    agent/setup/
    artifacts/app/methods/         main/, versions/, experiment_log.md
    artifacts/logs/artifacts/
    artifacts/manifest.json        what was copied out, and whether each source was empty
    verifier/reward.json           mean_score, median_score, reward, valid_fraction
    verifier/score_details.json    per-seed sealed results
    verifier/reward.txt  verifier/test-stdout.txt
    config.json  lock.json  result.json  trial.log
```

`result.json` carries a start and finish timestamp for each phase separately:
`environment_setup`, `agent_setup`, `agent_execution`, `verifier`. Only `agent_execution` spends
model budget. `agent_setup` installs the harness inside the container and took about four minutes
in every run here, on no tokens at all.

`lock.json` records harbor's own digest of the task directory. It is an independent pin, but it is
built by a different construction than the record's `freeze.task_digest`, so the two are not
numerically comparable; treating either as a check on the other requires reimplementing the other's
scheme.

### `__pycache__` is present, and the grader skips it

Bytecode caches do appear inside a submitted method tree once the agent imports its policy. A real
submission carried both:

```
artifacts/app/methods/main/__pycache__/policy.cpython-313.pyc
artifacts/app/methods/versions/v1/__pycache__/policy.cpython-313.pyc
```

The task's grader skips them rather than rejecting them. `tests/policy_sandbox.py` `_stage_policy`
iterates the source tree and continues on any path with `__pycache__` in its parts or a `.pyc` or
`.pyo` suffix, before the later check that raises `policy source may contain only Python files` for
any other non-Python file. It separately refuses symlinks, a tree over 10 MB, and a missing regular
`policy.py`. The run scored normally, with `valid_fraction` 1.0.

Both halves of this repository's stance are therefore confirmed against a real rollout rather than
assumed: excluding `__pycache__`, `*.pyc` and `*.pyo` from a method-tree digest matches what the
grader stages, and the separate rule that a non-Python file under `main/` is fatal is real and is
enforced at staging time.

The exclusion is load-bearing, and the same rollout shows what it prevents. The agent submitted
`v1`, so `main/policy.py` and `versions/v1/policy.py` are byte-identical, but their cache files are
not, because CPython embeds the originating source path in the cache. Over those two directories:

| digest | `main/` | `versions/v1/` | same? |
| --- | --- | --- | --- |
| cache-free `method_tree_sha256` | `3e1eae5a…` | `3e1eae5a…` | yes |
| naive whole-tree digest | `9f143bff…` | `36878453…` | no |

A digest that included bytecode caches would report that the submitted tree matches no snapshot.
The record producer fails closed on exactly that condition, so it would refuse to build a record at
all, for a rollout that is in fact perfectly well formed.

### `visible_result.json` does not survive

The task's `selfcheck.py` sets `ROOT` to its own parent directory, which the environment Dockerfile
places at `/app`, and writes `ROOT/visible_result.json` at the end of every run. The task manifest
declares `artifacts = ["/app/methods"]`, so only the methods tree is copied out. The visible-split
result the agent judged its own versions on is written to `/app/visible_result.json`, overwritten in
place by the next `selfcheck.py` invocation, and destroyed with the container. No job directory from
any run here contains a file by that name.

A published rollout therefore carries the sealed per-seed detail in `verifier/score_details.json`
and no record at all of the visible measurements behind the agent's decisions, so scores quoted in
an experiment log cannot be checked against the evidence that produced them.

This is the concrete reason for the rule that evidence lives under `methods/results/<version>/`.
That path is inside `/app/methods`, the one directory the manifest captures. A gate writing its
result files, confirmation results and receipts there survives into the job directory; anything
relying on the task's own default output does not.

### The sealed suite publishes per-seed results

`verifier/score_details.json` carries all sixteen sealed seeds individually, each with `seed`,
`raw_metric`, `moves`, `max_tile`, `error`, and a per-seed pair of `baseline` and `frontier`
anchors. Paired per-seed deltas against a sealed run are therefore available from the published
artifact, not only from a visible split.

Its `reward_mapping` reads: *per-seed log interpolation baseline→0 and frontier→0.6; log-space soft
cap above frontier, asymptotic to 1.0*. Reward 0.6 marks the frontier anchor, not 1.0.

## Results

The no-agent run establishes the baseline: it runs the real verifier against the untouched starter
policy and spends nothing.

| | Baseline (no agent) | 3-minute budget | 10-minute budget | 20-minute budget |
| --- | --- | --- | --- | --- |
| Sealed mean score | 2473.25 | 5113.25 | 4578.25 | 10992.25 |
| Sealed median score | 1828.0 | 5358.0 | 4688.0 | 8690.0 |
| Sealed reward | 0.0 | 0.1206 | 0.1093 | 0.2240 |
| Valid fraction | 1.0 | 1.0 | 1.0 | 1.0 |
| Agent execution | none | 79.6 s | 500.9 s | 473.9 s |
| Versions snapshotted | none | 1 | 10 | 7 |
| Record built | not applicable | yes | no, see below | no, see below |

The starter policy reproduces its per-seed baseline anchor exactly on all sixteen seeds: mean raw
2473.25 against mean baseline anchor 2473.25, reward 0.0. The anchors were computed from this same
policy, and the sealed evaluation is deterministic, as the task states.

A larger time budget did not produce a longer run. The 20-minute configuration stopped after 7.9
minutes of agent execution, marginally sooner than the 10-minute configuration's 8.3 minutes. The
budget is a ceiling, not a driver: `harbor`'s agent timeout can stop an agent early but cannot keep
one working, and the mounted `budget.py` only reports progress into the transcript. `ARB_OUTPUT_TOKEN_LIMIT`
is advisory for the same reason. Buying a longer rollout therefore means changing the agent — a
different model, a higher reasoning effort, or `-k` repeats — not raising the timeout.

Each row is a single trial. These tasks are stochastic and `harbor` exposes `-k` for repeats
precisely because one trial is a sample, not a measurement. Nothing here supports a claim that one
budget beats another.

The 10-minute run is worth reading anyway: its agent reached a higher score on its own visible split
than the 3-minute run did (8729 against 6816) while scoring lower on the sealed set. A gain measured
on the split the agent already tuned against need not transfer, which is the effect the gate exists
to measure.

## What the tooling did with a real rollout

On the 3-minute rollout the producer built a record and the offline verifier accepted it:

```
integrity=pass coverage=complete (relative to the supplied versions directory)
```

with `json`, `schema`, `semantics` and `files` all passing. The decision report reads the same
record and correctly reports `decisions: 0` with *No decision log was recorded for this rollout*,
which is right: the gate does not run inside the container until Milestone 3.

Three rollouts produced three different experiment-log shapes, and the record producer read only
one of them. These are defects fixture data could not have surfaced, because a fixture's log is
written to match the parser.

The reader is a pair: `get_log_reference` takes the first line naming a version, and `get_status`
classifies from that same line, accepting only the lowercased substrings `revert`, `kept` or `keep`.
Every failure below follows from those two properties.

**Vocabulary coupling.** The 10-minute run's agent wrote a markdown table with a `Kept?` column
holding `YES` or `NO`. All ten snapshotted versions raise `log_unclassifiable`. `autoresearch.md`
asks the agent to record whether a version was kept or reverted as a concept; it does not mandate
either word.

**The single-line assumption.** The 20-minute run's agent wrote one markdown section per version, so
the first line naming `v1` is the heading `## v1` and its disposition sits ten lines below as
`Status: kept (4.3x improvement from baseline)`. `v1`, `v2`, `v3` and `v5` all raise
`log_unclassifiable` while stating in plain words that they were kept.

**Snapshots the log never names.** The same run wrote `versions/v5_final` and `versions/v6_best`,
directory names appearing nowhere in its log, so both raise `log_missing_version`.

**A silent misclassification, which is worse than any refusal.** In that run the first line naming
`v7` is `Status: kept (best before v7)` — a line belonging to `v6`'s section that mentions `v7` only
in passing. The token matches, the line contains `kept`, and `v7` is therefore recorded as kept on
the strength of another version's status line. That is a wrong record rather than a refused one, and
no check in the current pipeline would catch it. A version's disposition must be read from a line
the version owns, not merely from the first line its identifier appears on.

Of the three rollouts, only the 3-minute one produced a record, and it did so because its agent
happened to write `(KEPT - FINAL)` on the same line as the version id. That is a coincidence of
phrasing, not a property the program text requires.

**Snapshot coverage is reported against the versions directory, not the log.** The 10-minute run
names nineteen versions in its log and snapshotted ten. `v5`–`v8` and `v15`–`v18` were logged and
never written, so the agent did not follow the program's instruction to snapshot every logged
version. The producer enumerates the versions directory rather than the log, so it cannot detect
this, and a record built from such a run would silently omit exactly the reverted experiments that
make a keep-or-revert chain evidence of anything. The verifier's wording is already accurate —
coverage is complete *relative to the supplied versions directory* — but that phrase reads as a
stronger claim than it makes.

## Limits of this observation

- One task, one harness, one agent model, one trial per configuration.
- A reduced model and a reduced budget. No number here is comparable to a published result.
- No gate ran inside a container, so no rollout here exercises gated mode end to end.
- The log-reader defects above are recorded, not fixed.
- One rollout in three yielded a record, so the record producer has not been exercised
  end to end on the majority of real logs.
