# Milestone 3 handoff: the plan review of 2026-09-08, its evidence, and what to do next

This document hands Milestone 3 to an executing session and to the operator. It records what a
critical review of the merged plan of 2026-09-07 found, how each finding was verified, what a
second-model adversarial review added, which decisions are the operator's, and how the corrected
plan (`docs/superpowers/plans/2026-09-08-milestone-3-dev-plan.md`) is meant to be executed by a
smaller model. Read this first; then the plan; then, only if a step needs it, the earlier plan,
which is superseded and carries a banner saying so.

## 1. Where the project stands

- `main` at `19f064a`: 274 tests pass, pyright is clean. Milestones 1 and 2 (the gate, the
  runner, receipts, the restore helper, the record, the verifier, the conformance matrix, the
  report, the TRACE converter, the ProofPress import) are built and fixture-verified.
- Ten real rollouts of `game2048_policy_search` exist outside the repository: four
  `claude-haiku-4-5` preflight trials and six `claude-opus-5` trials through a gateway. Four of
  them build a record. The refusals are two missing logs (the agent was stopped before writing
  one), a log with a table header and no rows, two snapshot names outside `^v[0-9]+$` (`v1a`,
  `v5_final`), and a log that names the inherited starter policy `v0` as a parent when `v0` was
  never snapshotted.
- A second-model review on 2026-09-07 withdrew the in-container gate design in its strong form
  (a driver sharing the agent's container is not a trust boundary; a suite derived from a key the
  agent can read is not a holdout). The operator accepted that withdrawal, and accepted the four
  lineage decisions of the plan that followed (suffixed ids in the record only; ordinals from
  declaration order; `unsnapshotted_parent_ids`; a missing log stays a refusal), rejecting the
  alternative of dropping an unsnapshotted parent silently.
- The plan of 2026-09-07 (`docs/superpowers/plans/2026-09-07-opus-records-shadow-replay-campaign.md`)
  is merged. It was never executed. This review replaces it.

## 2. What the review did

Every claim below was checked by running something, in a scratch copy of `main`, never in the
repository or a job directory.

1. **The plan's own code, verbatim.** Every code block of the 2026-09-07 plan was extracted from
   the plan text and applied to a scratch copy of `main`, and its commands and tests were run.
2. **The plan's expectations against the real rollouts.** The producer was run over all ten job
   directories before and after the plan's group A.
3. **The shadow replay on a real rollout.** The plan's `gate/shadow_replay.py` was run, as
   written, over the Opus rollout `opus-batch-k5/F7E69wm` under the plan's own profile values.
4. **The sizing rule at real scales.** The gate's confirmation planning rule was evaluated for the
   per-seed spreads real policies show, and a diagnostic simulator was written and run.
5. **The container path.** The evaluation runner was run inside a hardened `python:3.13-slim`
   container on this machine's Docker daemon (colima).
6. **Five second-model passes** (`gpt-5.6-sol`): three analyst lenses (executor readiness,
   statistics and endpoints, the record's threat model and claims) and two adversarial passes
   (one arguing the corrections overreach, one constructing failure scenarios for a smaller
   executor), then a confirmation pass over the corrected plan. Their raw outputs are kept in the
   operator's dated review notes; the ledger of dispositions is section 5.

## 3. Findings about the 2026-09-07 plan

### 3.1 What held

- Groups B and C (the runbook scripts, the program overlay, the profile generator, the shadow
  replay) work exactly as written: their ten tests pass and pyright is clean. `runbook/cost.py`
  reproduces the recorded spend of a real job.
- Group A's Task 2 (the unsnapshotted parent) works exactly as written: five tests pass, and the
  Opus rollout `opus-probe-20m/4tAEgA8` builds and verifies (`v1`, ordinal 2, `parent_ids []`,
  `unsnapshotted_parent_ids ["v0"]`, `submitted`).
- The design assumption behind declaration-order ordinals holds: all three golden fixtures
  rebuild byte for byte after Task 1's edits, when each is rebuilt with its own capsule id.

### 3.2 What was wrong, with the evidence

| Finding | Evidence | Consequence for a literal executor |
| --- | --- | --- |
| Task 1's golden check rebuilds `fixtures/gated` with `--capsule-id fixture-rollout-001`; the golden was built with `fixture-gated-001`. | `cmp` reports a difference on the unmodified tree too. | STOP condition 3 fires for a reason unrelated to the change. |
| Task 1's test asserts the reader classifies `v3` of the `jTbv9e3` log as `submitted`. | The row reads `**kept (submitted)**`; the reader returns `kept` because `kept` is checked before `submitted` and the table's status column is headed `verdict`, which the header pattern does not match. Confirmed by running the reader. | One of the five new tests fails; the executor has no fix path. |
| Task 1 breaks two existing tests it never mentions. | `UnnameableSnapshotsAreRefused` uses `v6_best` as a name outside the scheme; the widened pattern accepts it and the producer refuses it as `log_missing_version:v6_best` instead. | The suite fails after Task 1 with three failures, not the plan's `OK`. |
| Task 8 expects `preflight-C-long/CmWyNVF` to build because "its log declares `v5_final`". | The log declares `v0` to `v7` and never names `v5_final` or `v6_best`; `docs/PREFLIGHT.md` already said so. After group A the producer refuses it as `log_missing_version:v5_final`. | The plan's target of six records of ten is five. |
| The overlay's first step copies `main/` to `versions/v0`. | The image copies only `environment/methods` into `/app/methods`, which holds `main/policy.py`; `versions/` does not exist. | The literal command fails until the agent creates the directory. |
| The profile values make the shadow replay uninformative. | See section 3.3. | The disagreement table would measure the cap, not the agent. |
| Task 0 deletes and rewrites `capsule.json` inside every real job directory. | The loop begins `rm -f "$J/capsule.json"` and the producer's default output is the job directory. | The evidence the plan baselines is modified by the baseline. |
| The replay turns an evaluation failure into a gate `revert` and counts it as agreement, aborts the whole run on one gate refusal, runs agent-written policy code on the operator's machine as the operator's user, and reports no sizing, no coverage denominator and no input digests. | Read from the plan's code; the real replay below shows the synthetic agreement. | A misleading report, and hours of evaluation lost to one refusal. |

### 3.3 The sizing finding

The gate plans a confirmation as the smallest `n` with `z * s / sqrt(n) < min_effect / 2` (`s`
the sample standard deviation of the eight screening deltas, `z` 1.645 at level 0.9), at least
the floor; when the plan exceeds the cap the plan is exploratory and the gate reverts on the
screening line without confirming. That last rule was reviewed and accepted in Milestone 1: an
under-planned confirmation never keeps. The plan fixed `min_effect` at 2.5 percent of the parent's
visible mean, floor 4 and cap 16.

Planned sizes under that rule, level 0.9:

| Pair | Parent visible mean | Delta spread | Minimum effect | Planned seeds |
| --- | --- | --- | --- | --- |
| The worked example in the documents | 4,120 | 565 | 103 | 327 |
| Starter to a strong policy, assumed spread | 2,060 | 30,000 | 51.5 | about 3.7 million |
| Strong to strong, assumed spread | 100,000 | 40,000 | 2,500 | 2,771 |
| Strong to strong, assumed spread | 100,000 | 15,000 | 2,500 | 390 |

The real rollout confirmed the assumed scale. Under the plan's profile, the shadow replay over
`opus-batch-k5/F7E69wm` produced, for the pair `v0` to `v1`: estimate +83,474; interval
+56,528.5 to +109,760.0; verdict `clears`; spread 48,737; planned 9,692,228 seeds; disposition
`revert` because the plan was exploratory. The agent kept `v1` and submitted it, so the replay
counted a disagreement. For the pair `v1` to `v2`, the candidate exhausted the runner's CPU budget
(1,800 s over eight games); the plan's code recorded a `revert` and counted an agreement with the
agent's recorded revert, though no gate decision existed. The old report therefore read
"1 agree, 1 disagree", and neither number meant what a reader would take it to mean.

The exploratory outcome is a fact about the accepted rule on this task: 2048 scores are heavy
tailed and per-seed spreads of tens of thousands are normal for strong policies, so any minimum
effect anchored to the parent's mean is small relative to the spread, and the rule plans for a
precision the cap cannot buy regardless of how large the observed effect is. A rule that planned
against the observed effect (`max(min_effect, estimate - min_effect)`) would plan the floor for the
pair above. That is a change to the decision-log contract, and the adversarial passes argued, with
reason, that choosing it after seeing these rollouts and inside a provenance milestone is
post-selection and scope creep. The corrected plan therefore audits under the accepted rule and
reports exploratory outcomes as findings; the rule change is a separate proposal (section 6).

Diagnostic simulations (synthetic paired deltas, 200 trials per cell, 1,000 bootstrap resamples,
floor 16, cap 64; not evidence about any rollout) illustrate both rules at the strong-to-strong
scale (minimum effect 2,500, spread 15,000):

| Rule | Distribution | True effect (× minimum) | P(exploratory) | P(final keep) |
| --- | --- | --- | --- | --- |
| accepted | normal | 0 | 0.905 | 0.000 |
| accepted | normal | 10 | 0.990 | 0.010 |
| accepted | heavy tailed | 10 | 0.930 | 0.070 |
| estimate-aware | normal | 0 | 0.825 | 0.000 |
| estimate-aware | normal | 5 | 0.230 | 0.635 |
| estimate-aware | normal | 10 | 0.000 | 1.000 |
| estimate-aware | heavy tailed | 10 | 0.025 | 0.960 |

At the starter scale (minimum effect 51.5, spread 30,000) the accepted rule keeps nothing even at
a true effect two thousand times the minimum (every cell exploratory); the estimate-aware rule
plans the floor and keeps in essentially every trial. The binomial standard error at 200 trials
is at most 0.035, so these are shapes, not calibrated rates.

### 3.4 What the shadow replay needed beyond the plan

From the review passes, adopted in the corrected plan: the record is verified before pairs are
taken from it and every staged snapshot's digest must equal the record's; failures never become
dispositions and never enter the agree or disagree counts; a report is checkpointed after every
pair and a refusal on one pair does not abort the run; the outcome names why the gate ended where
it did (screening below, exploratory, confirmed keep, confirmed revert, evaluation failed, gate
refused, infrastructure failed, not replayable); coverage states what the record did and did not
recover and separates record-backed pairs from task-starter reconstructions; a workdir is used
once; policy code runs in a throwaway container with no network, a read-only root, all
capabilities dropped and the operator's uid, and the run refuses a directory the Docker VM does
not share (on colima that is anything outside the home directory); an inputs manifest is written
and pushed before any evaluation and enforced at run time, and the report then carries that
manifest's exact bytes, its digest and the pushed commit; every locator in a manifest or report
is relative and every refusal message has the run's own paths replaced by tokens, so the files can
be committed; a refusal after some stages completed keeps the completed stages in the pair's row;
every report states its limits.

The container path was run for real: the runner produced a receipt inside `python:3.13-slim`
(Python 3.13.15) that the host read, with the image's digest recorded, from a working directory
under the home directory; the same mount from `/private/tmp` was empty inside the container, which
is why the plan pins the audit root to the home directory and why the replay checks the mounts.

## 4. The corrected plan, in one page

Six groups, one branch and pull request each, in order. Counts are what test discovery reported
on the assembled scratch tree (336 tests, pyright clean).

| Group | What | Tests after |
| --- | --- | --- |
| A | Record lineage: suffixed ids, declaration-order ordinals, `unsnapshotted_parent_ids`; Task 1 corrected (the `v3` expectation, the two existing tests, the golden ids); five of ten records. | 285 |
| B | Documents describe the design being built: roadmap Milestone 3 and a deferred Milestone 4, README status, overview, two prose sentences of the contract. | 285 |
| C | Runbook: gateway script, fail-loud cost script with tests, program overlay (creates `versions/` first), replay-configuration generator (floor 16, cap 64 as a CPU budget, private file, reserved audit field). | 301 |
| D | `gate/shadow_replay.py` (22 tests) and `gate/calibrate.py` (13 tests). | 336 |
| E | The development cohort: records into an audit root, raw inventory, inputs manifests pushed first, six replays in the container by immutable image digest, the operator's dispositions of any failures, tables, diagnostics at the observed scale, the preflight record. | 336 |
| F | The prospective cohort: a campaign manifest pushed first, four `claude-opus-5` trials planned and started one at a time under a spend guard, their records and replays, the report over trials started. Notion and the shared page are operator steps. | 336 |

Follow-ups deliberately outside the plan: the planning-rule change with a pre-registered
calibration; a separate referee process for evaluation; a parity test of the Python-only
projection against the grader's staging; the cooperative in-container instrument (Milestone 4);
a validated resume for the audit.

## 5. The adversarial review: results and dispositions

Five passes, each returning REVISE, converging on five themes. Numbers of findings: executor
readiness 19; statistics 12; record and claims 12; overreach 12; failure scenarios 14.

**Theme 1: isolation of policy code.** All passes: container execution must be mandatory for real
rollouts, hardened, pinned by digest, and the host path fixture-only. Adopted. Two passes asked
for a separate referee process so the policy never shares the evaluator's process. Not adopted for
Milestone 3: it is a redesign of the evaluator, which today imports the policy exactly as the
task's own self-check does. The threat model is stated in every report and document instead: the
container protects the machine, not the result, against a policy written to manipulate the
evaluator. The overreach pass and the scenario pass both accepted this as long as the wording
never claims otherwise; the wording never does.

**Theme 2: failures are not dispositions.** All passes. Adopted in full: no gate disposition and
a null agreement for evaluation failures, refusals, infrastructure failures and unstageable
snapshots; the configured failure policy appears as metadata only; the hypothetical "would
disagree" count that a first revision carried was removed at the overreach pass's objection.
Exit status 0, 1, 2 as the scenario and overreach passes asked, so a report with failures cannot
be tabulated by accident.

**Theme 3: the record as the source of pairs.** Verified before use; digests matched; the
task-starter reconstruction of an unsnapshotted `v0` allowed only when it is the version's only
declared parent, counted separately; coverage lists every version the record could not pair and
why; the endpoint is named "disagreement among record-covered pairs". Adopted. The scenario pass
added a raw inventory of every rollout's snapshots before record construction, so the one snapshot
with a non-Python file (`jTbv9e3/v3/result.txt`) is on record although its rollout has no record.
Adopted.

**Theme 4: anchoring.** A report that carries its own input digests is self-description. Adopted:
the audit writes an inputs manifest before any evaluation; the manifest is committed and pushed
first; the run refuses unless its own manifest matches; the report and its digest are committed
after. The anchor starts at that first pushed commit and says nothing about what happened inside
the rollout, and the documents say so. An HMAC-chained ledger was not adopted; the pushed
repository is the retained copy.

**Theme 5: the sizing rule.** The statistics pass and both adversarial passes: do not change the
rule inside this milestone, do not choose values from a pilot on the rollouts the audit then
reports, calibrate before deciding, state a precommitted criterion. Adopted: the audit runs once
under the accepted rule with the configuration pushed first; exploratory outcomes are findings;
the estimate-aware rule is a separate proposal with a stated calibration protocol; the simulator
ships as a diagnostic. The minimum-effect fraction stays at 2.5 percent (the plan of record's
choice, with its rationale); floor 16 is the documented rule; cap 64 is a CPU budget.

**Other adopted items.** One trial per invocation with a spend guard that reserves the cost of one
trial (the earlier plan's single four-repeat command could not be stopped); a campaign manifest
that names the trials, includes every start, defines its counts mechanically and makes no
comparative claim; a fail-loud cost script; documents aligned before real runs, with the
withdrawn design's phrases removed from everything this plan writes; "replay configuration"
rather than "pre-registration" for a profile written after a rollout; the reserved audit-key
field filled with the digest of a documented literal rather than a discarded random key; the
job-directory test comparing a manifest of paths, kinds and digests; the named comparison on the
illegal-moves submission worded as an evaluation failure with no gate disposition; explicit branch
and merge choreography; test counts from discovery, never arithmetic.

**Not adopted, with reasons.** A validated `--resume` (a workdir is used once instead; an
interrupted run is rerun fresh). A single-policy determinism check (removed as unrepresentative;
the assumption is stated). A parity test against the grader's own staging (a follow-up; until then
projected pairs are excluded from the primary audit by default). Five thousand simulation trials
per cell at the gate's five thousand resamples (hours of pure Python per cell; smaller defaults
with the binomial standard error reported). A contract version bump for a rule that is not being
changed here.

**Confirmation pass.** See section 9; it was run over the assembled plan and this document.

## 6. Decisions that are the operator's

Each is recorded in the project's TRACE log as a proposal by the assistant and stays proposed
until the operator resolves it.

1. **Supersede the 2026-09-07 plan** with the corrected plan and this handoff (TRACE
   `evt_003` of the review session). Recommendation: accept; the earlier plan fails its own
   first task as written.
2. **Defer the planning-rule change out of Milestone 3** (`evt_005`, revising the original
   proposal `evt_004` to change the rule). Recommendation: accept the deferral; decide the rule
   itself after the audit's tables and a pre-registered calibration exist. The proposal itself
   stays open: plan against `max(min_effect, estimate - min_effect)`, with an optional profile key
   naming the rule; its first task is a calibration with a precommitted false-keep criterion at
   true effects 0 and one minimum effect, under every declared distribution, both caps, and
   candidate selection over reused seeds, reported with a one-sided Monte Carlo bound.
3. **Replay configuration values**: floor 16 and cap 64 in place of the accepted floor 4 and cap
   16 (`evt_006`). Recommendation: accept; floor 16 is what the documents state and cap 64 is a
   CPU budget the operator's machine can pay.
4. **The campaign's spend.** The guard reserves ten dollars per trial against a seventy-dollar
   ceiling with about forty-one dollars already spent, so it may stop the campaign after three of
   the four trials. Raising the ceiling is the operator's call and needs no code change.

## 7. How to execute

- A fresh session with a smaller model (a Sonnet-class or Haiku-class executor) and the
  `superpowers:executing-plans` discipline on
  `docs/superpowers/plans/2026-09-08-milestone-3-dev-plan.md`, one group at a time, stopping at
  every pull request for the operator to merge.
- Before starting: `RSI_EXAM_ROOT` exported to the RSI-Exam checkout; `AUDIT_ROOT` exported to a
  directory under the home directory; the Docker daemon up (`colima start`) with the context
  `colima`; `python:3.13-slim` pulled. The plan's Task 0 checks the first two and Task 10 the rest.
- Groups A to D need no money and no browser. Group E needs hours of CPU and the container. Group
  F spends gateway money under the guard and ends with two operator-only steps (the shared page and
  the Notion page).
- The STOP conditions are the contract between the executor and the operator: an executor that
  stops on one has done its job.

## 8. Roadmap beyond this plan

- **Milestone 4 (undecided):** the cooperative in-container instrument, with the mechanical
  fixes the 2026-09-07 review named, and the narrowed claim of internal consistency.
- **The planning rule:** the proposal in section 6, gated by calibration.
- **Evaluation isolation:** a referee process that owns game state, seeds and scoring, with the
  policy receiving observations and returning moves over a narrow protocol.
- **Upstream (unchanged):** the asks in `docs/overview.md` section 8: the submitted method's
  digest in `reward.json`, a published digest per job directory, per-seed visible results
  preserved per snapshot, and a fix or note for the only-Python trap.
- **A comparative study:** only with RSI-Exam's interest and a preregistered design.

## 9. Confirmation pass

Run over the assembled plan and this document after every disposition above was applied. Its
verdict and the items it left open are recorded here so the executing session knows what the plan
does not claim to have settled.

**Verdict: REVISE, on one blocker that was real and is fixed.** The pass found that committing
the inputs manifest moves the repository's commit, so a run that enforced the committed manifest
would have refused its own inputs on the recorded commit. The manifest comparison now ignores the
commit and the checkout's cleanliness (the digest of every gate source file is what pins the
code), the run copies the committed manifest's exact bytes into its workdir and reports their
digest, and a test commits a different commit and a dirty flag into a manifest and expects the run
to accept it. The pass also found absolute machine paths in committed manifests and reports (now
relative locators and redacted refusal messages, with a test that the temporary directory's path
appears nowhere in a report), a refusal after screening that discarded the completed screening
line (now kept, with a test), an inventory that would have written `opus` or `preflight` as the
model (now an explicit mapping that stops on an unknown job family), a campaign section titled for
four trials when the guard may start three (now planned and started counts with the denominator
stated), a calibration mixture whose true mean was not the nominal effect (now reported and used),
a "repeat the earlier task" instruction for the prospective cohort (now complete commands scoped
to it), a STOP condition that said both stop and continue (now a batch that continues and tables
that wait for the operator's written dispositions), and no literal branch-creation commands (now
at the head of every group).

Of the thirty-eight objections it traced, it marked twenty-one resolved, fourteen partial and
three not resolved before these fixes. What remains open after them, by choice and stated in the
plan's follow-ups: the policy still runs inside the evaluator's process (a referee redesign);
determinism is assumed, not tested per policy; the task-starter reconstruction is checked against
the manifest, not against a binding the record carries; projected pairs stay out of the primary
audit until a parity test exists; the spend reservation is an allowance from observed costs, not a
hard cap, and the manifest says so; the replay configuration's cap has a default rather than being
demanded on every real invocation, and the minimum-effect fraction is a constant. The pass agreed
that the group A changes, the five-of-ten yield, the documentation alignment, the retention of the
accepted planning rule, the failure semantics, the outcome and summary vocabulary, and the test
totals are internally consistent and executable.

## 10. What this review did not do

- It did not execute the corrected plan against the repository. The code was run in a scratch
  copy; the repository changes are for the executing session to make, group by group, with the
  operator merging each pull request.
- It did not run the shadow audit inside the container over a real rollout; the container path
  was proven on the fixture policy, and the host path on the real rollout.
- It did not resolve any of the operator's decisions in section 6.
- It did not update the shared page or the Notion page; nothing here is public.
