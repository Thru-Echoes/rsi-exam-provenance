# Deviations from the manifest, stage haiku

| trial | what happened | spend | how it was handled |
|---|---|---|---|
| ab-haiku-4-I, first attempt (started 00:46 UTC, 2026-09-10) | the harness's container setup step (the package installation that precedes the agent's first call) hung for more than two hours; the host had no sleep event and its network was reachable when checked; the agent was never started and no request reached the API | $0 | the container was stopped from the operator's session at about 03:00 UTC, the harness exited, the job directory (no agent session, no usage) was moved out of the jobs tree, and block 4 was re-run under the runner's resume mode with a fresh per-trial profile; blocks 1 to 3 were not touched |

The manifest names harness failures as stage stops and leaves any other stop to the operator with its reason; this is
that report. The re-run trial is the one reported as ab-haiku-4-I in the tables.
