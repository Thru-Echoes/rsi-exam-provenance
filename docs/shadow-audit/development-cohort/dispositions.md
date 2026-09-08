# Dispositions of the pairs that did not reach a gate disposition

Two runs exited 1. Both failures are evaluations the runner refused because the candidate policy exhausted
the pooled CPU budget on the eight visible seeds; neither pair has a gate disposition, and neither enters
the agree or disagree counts.

| rollout | pair | outcome | disposition for the tables |
| --- | --- | --- | --- |
| opus-batch-k5-8NhhboZ-pair | v0 to v1 (the submitted policy that returned illegal moves on the sealed suite) | evaluation_failed: v1 cpu_budget_exhausted | stays in the tables as a failure count; reported as "no gate disposition because the candidate could not be measured" |
| opus-batch-k5-F7E69wm | v1 to v2 (the deep-search candidate the agent itself reverted as too slow) | evaluation_failed: v2 cpu_budget_exhausted | stays in the tables as a failure count |

Nothing is excluded. Drafted for the operator from the reports; the operator's review of this pull request is
the confirmation.
