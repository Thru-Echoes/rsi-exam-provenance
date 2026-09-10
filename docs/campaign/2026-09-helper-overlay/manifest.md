# Campaign manifest: the helper-backed overlay across three models

This manifest is committed and pushed before any trial it names starts. It replaces the six-trial `claude-opus-5`
campaign of 2026-09-08 (`docs/campaign/2026-09-opus-overlay/manifest.md`), which the operator stopped after four
trials: all four were stopped by the harness timeout with only `v0` snapshotted, sealed reward 0.0, zero auditable
pairs, and the cause is not established. That campaign is reported as it was, beside this one.

## Purpose

To observe, as counts, what rollouts under the helper-backed provenance overlay leave behind (a verified record and
auditable candidate-parent pairs) across three models, and to run the shadow audit over every verified record with its
inputs manifest committed and pushed before evaluation. No rate, reliability or efficacy claim. Nothing here is an
official RSI-Exam result: every run is a modified-program run under a reduced agent budget.

## Pilots this design rests on (2026-09-09, the operator's own key)

- Pilot 1, six `claude-haiku-4-5` trials at 345.6 s: the exam's program yielded records in 0 of 3 trials, the earlier
  wording-only overlay in 1 of 3. Both arms edited the policy within a minute; every refusal was a bookkeeping race
  (a snapshot without its log line, reverted candidates never snapshotted, `main/` mid-edit at the stop).
- Pilot 2, the helper-backed overlay on Haiku, three trials plus two smokes at multiplier 0.002 (86.4 s configured, 89 s
  observed): records built and verified in
  5 of 5; 18, 11 and 14 auditable pairs in the three trials; every snapshot with its log block; no undecided candidate
  at any stop; three trials finishing on their own after `finalize`; $0.31 to $1.49 per rollout. A demonstration
  shadow audit over four of these records (not anchored) recovered 46 pairs, all comparable: 30 agree and 16 disagree
  with the agent's dispositions, 1 confirmed revert, 30 exploratory, 15 screening-below, 21 CPU seconds in total.
- Pilots 3 and 4, `claude-opus-5` at reasoning effort `max` under the helper: one 345.6 s trial ran `init` first and
  wrote an expectimax candidate but had no time for a first `evaluate` (record refused, `submitted_not_snapshotted`;
  the unsnapshotted candidate scored 0.650 on the sealed seeds); two 1296 s trials initialized first, evaluated and
  kept a candidate through the helper, and scored 0.585 and 0.598, both records verified, $7.67 for the pair. One
  agent wrapped `decide` in a shell timeout and killed the helper while it re-measured a candidate it was reverting;
  the helper no longer re-measures reverted candidates and the loop forbids wrapping its commands in a timeout.
- The four Opus trials under the wording-only overlay and the six 21.6-minute trials under the exam's program (the
  4.4-minute calibration probe excluded) are context, not a comparison: same model, effort and budget, different days,
  no randomization; the cause of the difference is not established.

## Configuration common to every trial

Task `game2048_policy_search`, RSI-Exam commit `bc36dadb405b`; harbor 0.22.0, `claude-code` adapter; program
`runbook/autoresearch-provenance.md` and template `runbook/autoresearch-provenance.j2`, compose overlay
`runbook/mount-provenance.yaml` mounting `runbook/provenance.py` at `/app/provenance.py`, all at the commit this
manifest is committed in; `WebSearch` and `WebFetch` disallowed; one trial per invocation; every started trial is
reported, none is replaced.

## Arms

| arm | model | reasoning effort | agent timeout multiplier | trials | key | per-trial reservation |
|---|---|---|---|---|---|---|
| H | claude-haiku-4-5-20251001 | low | 0.008 (345.6 s) | 6 | operator's | $2.60 (largest pilot trial $1.49 times 1.7 = $2.53, rounded up to ten cents) |
| S | claude-sonnet-5 | low | 0.008 (345.6 s) | 3 | operator's | $6.00 for the first trial (S1); then S1's priced cost times 1.7, rounded up to the cent |
| O | claude-opus-5 (as `anthropic/claude-opus-5` through the gateway) | max | 0.030 (1296 s) | up to 2 | collaborator's gateway | $11.00 (above the largest earlier trial, $10.71) |

Order of the nine operator-key trials, drawn once before the first trial with `random.Random(20260909).shuffle` over
`["H1","H2","H3","H4","H5","H6","S1","S2","S3"]`: H3, S1, H6, H4, H1, H5, S2, S3, H2. The gateway trials run after them, because they run
on a different key and rate card. The gateway's fixed $100.00 ceiling (verified spend $77.83 before this campaign) admits
the first Opus trial under the $11.00 reservation ($88.83); the second is admitted only if the first costs at most
$11.17, so arm O holds one or two trials as the guard decides, and the count is reported.

The runner (`run-campaign.sh` beside this manifest) fixes the remaining settings: the helper is told a run window of
340 s for arms H and S and 1200 s for arm O (the harness's own stops are 345.6 s and 1296 s); the output-token limit
is 400000; the runner refuses to start when any named job directory already exists, when the RSI-Exam checkout is not
at `bc36dadb405b`, or when another runner holds its lock. The runner starts trials only; records, inputs manifests,
the audit and the tables are the runbook's later steps, run after every trial has ended.

## Endpoints, fixed before the first trial

Primary, per trial: the number of auditable pairs the record recovers (versions with a snapshotted parent whose
status is kept, reverted, or the submitted head); a refused record recovers zero pairs. Secondary: the record builds and verifies (yes or no, with the
refusal reason); minutes to `init`, to the first `evaluate` and to the first `decide`; snapshots; whether the agent
finished or was stopped; whether `finalize` ran; infrastructure actions (a C compiler, a training script, weight
files); priced cost (`runbook/cost.py`, rate cards `haiku`, `sonnet`, `opus`); the verifier's sealed reward as an
incidental number.

## The audit, and the rule it reports under

The shadow audit runs over every verified record with its inputs manifest committed and pushed before evaluation,
under the accepted planning rule (the smallest confirmation suite that resolves the minimum effect, capped at 64
seeds); its tables are the primary result, with exploratory outcomes reported as a finding about the rule and the
task's per-seed spread. A second pass under the estimate-aware planning rule (the confirmation planned against the
larger of the minimum effect and the screening estimate less the minimum effect) is reported beside it as a labelled
diagnostic: it was not pre-registered before the earlier cohorts were seen, it decides nothing, and the rule change
itself remains a separate decision with its own calibration. Both passes use the same records, replay configurations
and evaluation image.

## Stopping rules

- Per arm: if the first two trials of an arm in the drawn order (H3 and H6; S1 and S2) both end with at most one
  snapshot directory, which is no pair before any record is built, the arm's remaining trials are skipped and the arm
  is reported as stopped by that rule.
- Money, operator's key: ceiling $30.00 across arms H and S together; a trial starts only while priced spend plus its
  reservation stays within the ceiling. Money, gateway: ceiling $100.00 with the $11.00 reservation. A ceiling is an
  admission threshold: the last admitted trial can carry the total past it by at most its own cost less its
  reservation, and the report says so if it does. The money rule is checked before the per-arm rule, and the reported
  reason is the rule that fired.
- Any harbor non-zero exit, missing job directory, or trial that did not end normally or by the harness timeout with
  assistant usage in its session log stops the whole campaign, including the gateway arm, for inspection.
- A stop for any other reason is the operator's decision and is reported with its reason.

## What is reported

For every started trial: the per-trial table of the endpoints above; the record's outcome; the audit's report with its
committed inputs manifest and anchor commit; spend against each ceiling; the stopping rule that ended each arm. This
campaign and the stopped one both appear in `docs/PREFLIGHT.md`.
