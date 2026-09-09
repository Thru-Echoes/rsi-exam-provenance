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
