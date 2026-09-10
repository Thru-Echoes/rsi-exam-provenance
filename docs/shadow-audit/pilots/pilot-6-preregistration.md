# Pilot 6: the instrument overlay on claude-opus-5 at a window that can hold a confirmation

Written before the trial started (2026-09-09, 23:20 UTC).

**Question.** A strong Opus policy costs about 30 CPU seconds per public-seed game (campaign O1 v1 31.3 s, O2 v2
29.8 s), so a screening of eight seeds is about four minutes and a confirmation of eight seeds, parent and candidate at
once, about the same. At agent timeout multiplier 0.045 (1944 s; the helper told 1900 s), does a full cycle (a
candidate written, evaluated, proposed, screened and confirmed) complete before the close-out mark? How long do the
screening and the confirmation take? The Opus smoke at multiplier 0.030 (`docs/shadow-audit/pilots/pilot-5-preregistration.md`,
its last two sections) already showed one cycle completing in 1.2 minutes for a 6.4 CPU-second policy and a second
candidate at 18.8 CPU seconds per game refused for time; this pilot asks the same question at the window the Opus
stage would use.

**Trial.** Stage `pilot-opus` of `docs/campaign/2026-09-instrument-ab/stages.json`: `claude-opus-5`, reasoning
effort `max`, multiplier 0.045, operator's key, one instrument-arm trial (`LIMIT=1`), job `ab-pilot-opus-1-I`; the
same profile values as the Haiku and Sonnet pilot. A second trial at multiplier 0.060 (2592 s; the helper told 2500 s)
runs only under the rule below.

**Measures.** As pilot 5, plus the confirmation's wall time against the window.

**The rule that fixes the A/B's Opus window, stated before the trial.** If at least one keep proposal opened a
confirmation and that confirmation produced a settled confirmation line before the close-out mark, with no keep
refused for time and no blocked gate, the Opus stage runs at multiplier 0.045. If a keep was refused because its
confirmation would run past the close-out mark, or a confirmation was blocked by the wall clock, the Opus stage runs
at multiplier 0.060, and one more pilot trial at that multiplier confirms it first. If no confirmation opened (no keep
proposed, or every keep exploratory), a second pilot trial runs at 0.060; the Opus stage then runs at 0.060 whatever
that trial shows, and both pilot trials are reported as they were, so the stage's window is always one a pilot has run.

**Money and stopping.** Admission threshold $24.00, reservation $8.00 per trial, so the second trial is admitted
while the first cost at most $16.00 (earlier full-window Opus trials cost $2.70 to $4.97; a longer window costs more
tokens); if the first trial cost more than that, the second is not started and the Opus stage runs at the window
the first trial's outcome selects, with that said; the runner's rules; every started trial reported.

## Outcome (from `docs/shadow-audit/instrument-ab/pilot-opus/endpoints.md`)

`ab-pilot-opus-1-I`: the agent ran 1545 s of the 1900 s told and finished on its own; first evaluate at 20.3 min and
first decide at 25.0 min of the runner's clock (the agent spent the first twenty minutes on one rewrite). v1, a bitboard
expectimax at 31.4 CPU s per game, scored 104,352 on the public seeds against the starter's 2,060; the screening
cleared (+111,416, interval 75,465 to 153,610 over 8 seeds) and the confirmation on 8 fresh seeds settled in 4.6 min
before the close-out mark: kept. No keep refused for time, no blocked gate, finalize ran, the record verifies. Exam
reward 0.6284 (valid fraction 0.875: two of the sixteen sealed games were invalid under the grader although all eight
public-seed games and the confirmation's games were valid, a limit of a safety check on eight seeds). Cost $4.96.
The pre-registered rule selects multiplier 0.045 (the helper told 1900 s) for the Opus stage, and no second pilot trial
runs. The sealed retrospective could not measure v1 (an invalid game under the runner's in-process evaluator), so the
endpoints' final-selection regret is not defined for this trial and the retrospective's stated limit on strong
policies applies; the primary endpoint comes from the grader and is unaffected.
