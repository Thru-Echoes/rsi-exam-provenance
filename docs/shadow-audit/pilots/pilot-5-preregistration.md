# Pilot 5: the instrument overlay on Haiku and Sonnet, operator's key

Written before the trials started (2026-09-09).

**Question.** Inside the agent's container, does the instrument run as the tests say: `init` reports the gate
mounted and measures the starter with the gate's runner, `evaluate` prints a gate preview, a keep the agent proposes
reaches the gate (a line in `decisions.jsonl`), a confirmation that starts finishes before the close-out mark, the
record builds and verifies with the gate's decisions in it? How long do a screening and a confirmation take for
policies of each model's strength?

**Trials.** Through `docs/campaign/2026-09-instrument-ab/run-ab.sh`, stages `pilot-haiku-smoke`
(`claude-haiku-4-5-20251001`, reasoning effort `low`, agent timeout multiplier 0.002, 86.4 s; the helper told 80 s),
`pilot-haiku` (the same model and effort at multiplier 0.008, 345.6 s; the helper told 340 s) and `pilot-sonnet`
(`claude-sonnet-5`, effort `low`, multiplier 0.030, 1296 s; the helper told 1200 s), one instrument-arm trial each,
program `runbook/autoresearch-instrument.md`, mount `runbook/mount-instrument.yaml`, profile floor 8, cap 16,
estimate-aware rule, minimum effect 2.5 percent, at the commit of this note. Jobs `ab-pilot-haiku-smoke-1-I`,
`ab-pilot-haiku-1-I`, `ab-pilot-sonnet-1-I`.

**Measures per trial** (`ab_measures.py`, from the job directory and the record): the gate mounted at init; gate
lines by disposition; keeps overruled, refused for safety, refused for time; confirmations with their sizes and wall
time; minutes to the first evaluate and the first decide; whether finalize ran; the record's outcome; the sealed
reward as an incidental number; priced cost.

**Reading it.** The smoke trial must show `the gate is mounted` from `init`, a receipt beside the starter's result,
and a record that builds and verifies; anything else stops the pilot for inspection before any longer trial (the
plan's STOP condition 8). The Haiku and Sonnet trials show whether the loop leads the agent to propose keeps through
the gate and what a confirmation costs in wall clock at each strength; a trial in which the agent proposes no keep at
all is reported as such, not replaced. No number here is a rate.

**The rule that fixes the Sonnet stage's window, stated before the trial.** If at least one confirmation settled
before the close-out mark and no keep was refused for time, the Sonnet stage runs at multiplier 0.030 (the helper told
1200 s). If a keep was refused for time or a confirmation was held by the wall clock, the Sonnet stage runs at
multiplier 0.045 (1944 s; the helper told 1900 s) with its reservation raised to $4.00 and its threshold to $26.00. If
no confirmation opened (no keep proposed, or every keep exploratory), the stage runs at 0.030 and the pilot is reported
as it was.

**Money and stopping.** Ceilings $1.00, $3.00 and $4.00 with reservations $0.60, $2.60 and $3.00, enforced by the
runner; stop on any harbor non-zero exit, missing job directory, or trial that did not end normally or by the
harness timeout with assistant usage in its session log. Every started trial is reported.

## Outcome (from the committed endpoints under `docs/shadow-audit/instrument-ab/pilot-*/`)

- Smoke (`ab-pilot-haiku-smoke-1-I`, 86.4 s, $0.41): `init` reported the gate mounted with the profile and gate digests; the
  runner published results, receipts and safety reports for v0 and v1 inside the container; `evaluate` printed the gate
  preview; the agent reverted v1 with a note (no gate line); the harness stopped the run with an unevaluated edit in `main/`
  (record `submitted_not_snapshotted`, the known window). The runner refused the Haiku trial's first start under its money
  rule because its stage glob counted the smoke's spend; fixed before the trial ran.
- Haiku (`ab-pilot-haiku-1-I`, 345.6 s, $0.66, the agent finished on its own after 159 s and 28 steps): 3 gate lines; the
  first keep overruled at screening as exploratory (estimate +162, 2046 seeds planned against a cap of 16); the second
  confirmed on 10 fresh seeds in about a second (estimate +2503, interval [947, 4118]) and made the head; the third
  candidate reverted by the agent after the preview said a keep would be exploratory; finalize ran; record verified;
  sealed reward 0.0895. On the sealed seeds both reverts discarded better candidates (v1 +270, v3 +1140 against the head);
  final-selection regret 0.031.
- Sonnet (`ab-pilot-sonnet-1-I`, 1296 s, $0.67, the agent finished on its own after 480 s and 25 steps): 2 gate lines; one
  candidate (expectimax with heuristics, 12 cpu s per public game) screened clear and was confirmed on 8 fresh seeds in
  2.3 min (estimate +15833, interval [11162, 20546]); first evaluate at minute 2.8, first decide at 4.8, finalize at 7.9;
  record verified; sealed reward 0.330 with all 16 seeds up; regret 0.
- The Sonnet window rule: a confirmation settled before the close-out mark and no keep was refused for time, so the Sonnet
  stage runs at multiplier 0.030. Single trials; no rate.

## Pilot 6 smoke: one Opus trial at the earlier Opus window

Written 2026-09-09 21:40 UTC, before the trial started.

**Question.** At the window every earlier Opus trial on this task used (multiplier 0.030, 1296 s; the helper told
1200 s), does an Opus agent under the instrument propose a keep early enough for a confirmation to fit before the
close-out mark, and what does a confirmation of eight fresh seeds cost in wall clock for a policy of Opus's strength
(about 30 CPU seconds per game in the helper campaign)? This trial is a smoke, not the Opus pilot: `pilot-opus`
(multiplier 0.045, two trials) still fixes the Opus stage's window by its own rule, which this trial neither replaces
nor pre-empts.

**Trial.** Stage `pilot-opus-smoke`: `claude-opus-5`, reasoning effort `max`, multiplier 0.030, one instrument-arm
trial, job `ab-pilot-opus-smoke-1-I`, the same program, mount, profile settings and key as the other pilots, at the
commit of this section. Ceiling $8.00, reservation $6.00, enforced by the runner.

**Reading it.** Reported like the other pilots: the measures table, the gate lines, whether a confirmation opened and
settled, keeps refused for time, and the sealed reward as an incidental number beside the helper-only Opus trials at
the same window (0.585 and 0.521 in the campaign; 0.598 and 0.585 in pilot 4). One trial establishes no rate. The time
budget at this window, stated in advance: the first-candidate mark is at 400 s and the close-out mark 180 s before the
end, so a confirmation of eight seeds at 30 CPU seconds per game (about 6.2 min with the runner's slack) fits only for a
keep proposed before about the eleventh minute; a keep refused for time is the expected failure mode at this window and
is reported, not retried.

### Outcome of the Opus smoke (from `docs/shadow-audit/instrument-ab/pilot-opus-smoke/`)

`ab-pilot-opus-smoke-1-I`: the agent ran 1036 s of the 1200 s told and finished on its own; first evaluate at 8.7
min, first decide at 10.3 min. v1 (a bitboard expectimax, 41,720 on the public seeds against the starter's 2,060, 6.4
CPU s per game) screened `clears` and was confirmed on 8 fresh seeds in 1.2 min: kept. v2 (a deeper endgame search,
91,864 on the public seeds, 18.8 CPU s per game) was proposed after the point where an 8-seed confirmation (about 3.9
min with the runner's slack) still fit before the close-out mark: refused for time, `main/` restored to v1. finalize
ran; the record verifies; sealed reward 0.5504, cost $4.75. On the sealed seeds v1 beat the starter on 16 of 16
(+66,417); v2 had a higher mean than v1 (+10,288, 9 up and 7 down) but a lower reward (0.5297), so on the primary
endpoint the refusal cost nothing, while the sealed-mean rule counts it as a revert the sealed seeds disagreed with.
The time budget stated in advance held: at this window the second candidate's confirmation did not fit, which is why
the Opus pilot runs at multiplier 0.045.

## Pilot 7 smoke: the helper arm through the A/B runner

Written 2026-09-09 23:15 UTC, before the trial started.

**Question.** The A/B runner has executed only instrument-arm trials so far. Does its helper-arm path run as the
stages need it to: the helper program and mount selected, no gate or profile exported, the job named by block and
arm, the trial priced and admitted by the same rules, and the record built and verified afterwards?

**Trial.** Stage `pilot-haiku-smoke-H`: the Haiku smoke's settings (`claude-haiku-4-5-20251001`, effort `low`,
multiplier 0.002, the helper told 80 s) with the order `1-H`, one trial, job `ab-pilot-haiku-smoke-H-1-H`, at the
commit of this section. Ceiling $1.00, reservation $0.60.

**Reading it.** The stage log must show the helper program and mount for arm H and no profile line; the job
directory must exist with assistant usage; the records step must build and verify a record or refuse it for a reason
the helper's known windows explain (an unevaluated edit or an undecided candidate at the stop). Any other outcome
stops the pilots for inspection before the Opus pilot starts. One trial establishes nothing about the arm's scores.
