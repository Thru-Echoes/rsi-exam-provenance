# Campaign manifest: the instrument against the helper, paired, in three stages

This manifest is committed and pushed before the first comparison-stage trial starts; the pilots it cites ran under
their own committed pre-registrations. Modified-program runs at reduced budgets; nothing here is an official RSI-Exam
result. Counts, never rates; no efficacy or significance claim.

## Question, treatment and estimand

The treatment is the complete instrument package: its loop text, the mounted gate and profile, the gate preview, the
enforced screening and confirmation of keep proposals, the submission-safety refusals, the window marks, the runner's
overhead and the confirmation's wall time inside the common window. The control is the helper package alone. The
question is what rollouts under each package leave behind and score, paired within blocks of two trials of the same
model at the same window, run back to back.

The primary estimand, separately per stage: the within-block difference in the sealed reward of the submission,
instrument minus helper, under the fixed model, reasoning effort, window, harness, commit and procedure of this
manifest. Confirmation time stays inside the common window and is part of the treatment effect. This comparison does
not identify the effect of the statistical gate alone, the effect of confirmation holding the agent's research time
constant, or a common effect across models. At three or four blocks the estimates are observations from this
campaign, not a determination that the instrument improves performance.

## Pilots this design rests on

- Pilot 5 (`docs/shadow-audit/pilots/pilot-5-preregistration.md`, outcomes in `docs/shadow-audit/instrument-ab/pilot-*/endpoints.md`):
  the Haiku smoke (86 s) was stopped by the harness at 89 s with no gate line, the agent having reverted its candidate
  and left an unevaluated edit that the record refused, reward 0.085, $0.41; the Haiku trial (346 s) wrote three gate
  lines, a keep overruled as exploratory, a keep confirmed on ten fresh seeds within the minute, an agent revert after
  the preview, record verified, reward 0.0895, $0.66; the Sonnet trial (1296 s) wrote two gate lines, a keep confirmed
  on eight fresh seeds in 2.3 minutes, record verified, reward 0.330, $0.67; the Opus smoke at the same window wrote
  two gate lines, a keep confirmed on eight fresh seeds in 1.2 minutes and a second keep refused for time, record
  verified, reward 0.550, $4.75; the helper-arm smoke through this runner (pilot 7 in the same note) ran the helper's
  program and mount and its record verified, $0.38.
- Pilot 6 (`docs/shadow-audit/pilots/pilot-6-preregistration.md`): the cycle completed at multiplier 0.045, a keep
  confirmed on eight fresh seeds in 4.6 minutes before the close-out mark with no keep refused for time and no blocked
  gate, so the rule selects 0.045 for the Opus stage; record verified, reward 0.628, $4.96.
- The calibration of the instrument's planning rule at its bounds (`docs/shadow-audit/calibration/check-result.md`):
  criterion met, largest exact upper bound 0.0343 over 120 gated cells.

## Configuration common to every trial

Task `game2048_policy_search`, RSI-Exam commit `bc36dadb405b`; harbor 0.22.0, `claude-code` adapter;
`WebSearch` and `WebFetch` disallowed; output-token limit 400000; one trial per invocation; every started trial is
reported, none is replaced; repository commit fd6efc46e5a5 for the helper (`runbook/provenance.py`, sha256 342bfe5cc15eb8c6),
the gate (`gate/*.py`, copied clean per stage), the two programs and templates (instrument: sha256 665108c66bbe4cb3 and
26b4dec447cb3bb8; helper: d298399c322fcdc8 and 38314bcdada4715f) and the two mount files (560c3da9b2f0a80b, d7d55791dfd558d2).

## Arms

- **I, the instrument:** `runbook/autoresearch-instrument.md` with `runbook/mount-instrument.yaml`: the helper, the
  gate's scripts at `/app/gate`, and a task profile at `/app/profile.json` written per trial by
  `runbook/make_profile.py` with floor 8, cap 16, the estimate-aware planning rule, minimum effect 2.5 percent of the
  parent's public-seed mean, a fresh replication key (readable inside the rollout; committed after the stage).
- **H, the helper:** `runbook/autoresearch-provenance.md` with `runbook/mount-provenance.yaml`, exactly as in the
  helper-overlay campaign.

## Stages, blocks and the drawn order

Blocks of two trials, one per arm, run back to back; the orders within blocks are counterbalanced (as many
instrument-first as helper-first blocks; a three-block stage carries one block's imbalance, stated with its result)
and shuffled once by `draw_order.py` with seed 20260911, and are fixed here. Trials are named `ab-<stage>-<block>-<arm>`.
The files that define a trial (both programs and templates, both mount files, the helper, the profile generator, the
gateway script, the gate's five scripts and `stages.json`) are pinned by digest in `manifest-digests.txt` beside this
manifest, and the runner refuses to start when any differs. A dry run of the runner writes only under the audit root
(a clean gate copy and per-trial profiles) and starts nothing.

| stage | model | reasoning effort | agent timeout multiplier (window the helper is told) | key | blocks | order | per-trial reservation | ceiling |
|---|---|---|---|---|---|---|---|---|
| haiku | claude-haiku-4-5-20251001 | low | 0.008 (340 s) | operator's | 4 | 1-I 1-H 2-H 2-I 3-H 3-I 4-I 4-H | $2.60 | $22.00 |
| sonnet | claude-sonnet-5 | low | 0.030 (1200 s) | operator's | 3 | 1-I 1-H 2-H 2-I 3-I 3-H | $3.00 | $20.00 |
| opus | claude-opus-5 | max | 0.045 (1900 s), by pilot 6's rule | operator's | 3 | 1-I 1-H 2-H 2-I 3-H 3-I | $8.00 | $50.00 |

The stages run in that order; a stage starts only after the previous stage's pipeline has committed its endpoints.
The direction of any endpoint is never a reason to start, skip or stop a stage. Over every trial of this comparison,
pilots included, the runner also applies a campaign-wide admission threshold of $120.00 (`stages.json`, `_campaign.ceiling`; the possible overrun is one block's cost less its reservations). No new
trial starts after 2026-09-13 12:00 UTC unless the operator moves that time; a stage not started by then stays
pre-registered and unrun.

## Endpoints, fixed before the first trial

Decision quality, per trial and comparable across arms: the final-selection regret, the largest sealed reward among
the measured snapshots (the starter and every version) less the sealed reward of the submission, lower being better;
and, with their denominators, the keeps and reverts the sealed seeds disagreed with under the gate's own threshold,
the minimum effect on the sealed scale (2.5 percent of the parent's sealed mean): a keep whose sealed delta against
the parent is below minus that threshold, a revert whose delta is above it, and, counted apart, decisions whose delta
lies within it (in the instrument arm a decision is the gate's last line for the version; in the helper arm the
agent's recorded status). These are measured on the candidates each arm produced; they describe selection within a
package, not judgment on a common candidate set.

Primary, per trial: the sealed reward of the submission (`verifier/reward.json`), paired within its block and
reported as the per-block difference (instrument minus helper), the count of blocks favouring each arm, ties, the mean
difference, and an exact two-sided sign test as a descriptive number (with four blocks it cannot fall below 0.125;
with three, 0.25). A block with two rewards from the harness's verifier has a numeric difference. When exactly one of its trials has a
reward, the other arm's failure to leave a scorable submission is an outcome: the scorable arm is counted as
favoured and the block has no numeric difference. A block with neither reward, or with a trial not started, is
incomplete and enters no count; it stays in the trial table and the mechanism counts. The sign test and the mean use
the blocks with two rewards, zero differences dropped, and the count of such blocks is printed beside them. A
submission the grader scored low for an invalid game, an exhausted budget or an illegal move keeps the reward the
grader gave it. Nothing is imputed, and no failure is classified by the direction of any reward.

Secondary, per trial (`ab_measures.py`): pairs the record recovers; gate lines by disposition, provisional decisions
left open, a blocked gate; keep proposals overruled; keeps refused for safety and for time; unmeasurable candidates;
versions the gate kept that exceed the plan's safety margins by their own safety report (a weakened margin);
confirmations run with their sizes and wall time; minutes to the first evaluate, the first decide and finalize;
whether the agent finished or was stopped; the candidate undecided at the stop, if any; the record's outcome,
whether every decision line and receipt carries the mounted profile's digest, and whether any version the gate kept
exceeds the plan's safety margins by its own safety report (which would mean the margin was weakened inside the
rollout); priced cost. Per stage: the shadow audit
over every verified record under the instrument's own planning rule (estimate-aware, floor 16 and cap 64 as the host's
CPU budget, a fresh host key) with its inputs manifest committed and pushed before evaluation, so both arms are read
under the rule the instrument decided by;
the sealed-suite retrospective over every snapshot, with each arm's decisions read against the sealed seeds (in the
instrument arm the gate's decision, in the helper arm the agent's recorded status): keeps with a negative sealed delta
and reverts with a positive one, per trial, as descriptive counts; spend against the ceiling.

## Stopping rules

- Blocks are atomic: the rules below are judged before a block's first trial and never between its two arms, so a
  block that starts is completed, back to back; a block that could not complete before the calendar cutoff is not
  started.
- Money, per stage and for the campaign: a block starts only while the priced spend plus the reservations for both
  of its trials stays within the stage's ceiling and the campaign's hard ceiling; the last admitted block can carry
  the total past a ceiling by at most its own cost less its reservations, and the report says so if it does.
- Mechanism, per stage: if the first two instrument-arm trials of the stage both end without a record that builds and
  verifies, no later block starts and the stage is reported as stopped by that rule. If an instrument-arm trial ends
  with the gate blocked (the runner refused a policy during a confirmation), its block completes and no later block
  starts.
- Harness: any harbor non-zero exit, missing job directory, or trial that did not end normally or by the harness
  timeout with assistant usage in its session log stops the stage.
- A stop for any other reason is the operator's decision and is reported with its reason.

## Expectations stated before the runs

Under the instrument's bounds, the Haiku-scale improvements the earlier cohorts showed (hundreds of points against
per-seed spreads of thousands) plan more confirmation seeds than the cap and are reverted as exploratory; the Haiku
stage is expected to show the instrument keeping little, and it runs as the protocol's rehearsal and for its mechanism
counts. The Opus-scale improvements (tens of thousands of points) confirmed at the floor in the audit's diagnostic;
the Opus stage is where a confirmed keep is expected to occur. Neither expectation is an endpoint.

## What is not claimed

No rate, no efficacy claim, no significance claim, no comparison across stages or models, no statement about official
results. A stage's blocks are instrumentation: what they show is direction and mechanism counts, reported as such in
`docs/PREFLIGHT.md`.
