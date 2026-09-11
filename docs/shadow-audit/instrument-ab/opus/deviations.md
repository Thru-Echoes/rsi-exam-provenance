# Deviations from the manifest, stage opus

| step | what happened | how it was handled |
|---|---|---|
| shadow replays | the step had finished one of the six rollouts after about thirty-five minutes, and the stage's own probe of why every block favoured the helper arm (`docs/shadow-audit/pilots/pilot-8-preregistration.md`) needed the machine's CPUs to itself, because a trial's gate reasons about wall-clock time and a concurrent replay would inflate it | the pipeline was paused from the operator's session at 21:47 UTC on 2026-09-10 between rollouts, the probe's two Opus trials ran, and the replays were restarted afterwards from the beginning of the step. No trial of the stage is affected: the replays read finished job directories and can run at any time. The stage's primary endpoint, the grader's reward of each submission, does not depend on them. |

The manifest leaves stops for reasons other than money, mechanism and harness to the operator with the
reason stated; this is that report.

| shadow replays, the repair | the replay of one instrument rollout was mid-write when the step was paused, so its report carried `complete: false`; a rerun refuses to overwrite an existing report, by design, so the partial one had to be removed first. The repair removed that rollout's whole directory rather than its report alone, which also removed the inputs manifest the step iterates over, and the next pass finished over five of the six rollouts while still printing its DONE line | the manifest was restored from the commit that anchored it, the rollout was replayed on its own against the same anchor, and the repair now removes only the report and refuses to finish unless the report count matches the rollout count |
