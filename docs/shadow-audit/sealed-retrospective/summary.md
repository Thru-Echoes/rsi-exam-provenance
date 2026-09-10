# Sealed-suite retrospective over the development cohort

Every snapshot of every real rollout scored on the task's published sixteen sealed seeds with the grader's own reward mapping, beside what the agent recorded and what the shadow audit decided for the same pair. Descriptive: the sign of a paired delta over sixteen seeds describes these snapshots on these seeds; the sealed suite is analysis data here and is never used to tune the rule.

## Per rollout

### opus-batch-k5-8NhhboZ

Submission on the sealed seeds: unmeasured (wall_clock_exceeded); the verifier's reward.json said 0.01127715. Snapshots measured: 1 of 2.

No record for this rollout; snapshots scored individually: v0 mean 2473.2 reward 0.0000, submission unmeasured (wall_clock_exceeded)

### opus-batch-k5-F7E69wm

Submission on the sealed seeds: mean 106197.5, reward 0.60627434; the verifier's reward.json said 0.60627434. Snapshots measured: 3 of 4.

| version | recorded | parent | visible score | sealed mean | reward | sealed delta vs parent (mean, +/- seeds) | audit outcome | audit disposition |
|---|---|---|---|---|---|---|---|---|
| v0 | baseline |  |  | 2473.2 | 0.0000 |  |  |  |
| v1 | submitted | v0 |  | 106197.5 | 0.6063 | 103724.2 (16+/0-) | exploratory | revert |
| v2 | reverted | v1 | 0.0 |  |  | unmeasured | evaluation_failed |  |

### opus-batch-k5-FHQNNyJ

Submission on the sealed seeds: mean 2473.2, reward 0.00000000; the verifier's reward.json said 0.00000000. Snapshots measured: 2 of 2.

| version | recorded | parent | visible score | sealed mean | reward | sealed delta vs parent (mean, +/- seeds) | audit outcome | audit disposition |
|---|---|---|---|---|---|---|---|---|
| v0 | submitted |  |  | 2473.2 | 0.0000 |  |  |  |

### opus-batch-k5-jTbv9e3

Submission on the sealed seeds: unmeasured (wall_clock_exceeded); the verifier's reward.json said 0.64613965. Snapshots measured: 0 of 4.

No record for this rollout; snapshots scored individually: v1a unmeasured (wall_clock_exceeded), v2 unmeasured (wall_clock_exceeded), v3 unmeasured (wall_clock_exceeded), submission unmeasured (wall_clock_exceeded)

### opus-batch-k5-ucAjUAW

Submission on the sealed seeds: mean 149056.0, reward 0.64482207; the verifier's reward.json said 0.64482207. Snapshots measured: 2 of 2.

No record for this rollout; snapshots scored individually: v1 mean 149056.0 reward 0.6448, submission mean 149056.0 reward 0.6448

### opus-cal-01-sMUjv7Q

Submission on the sealed seeds: mean 2473.2, reward 0.00000000; the verifier's reward.json said 0.00000000. Snapshots measured: 1 of 1.

No record for this rollout; snapshots scored individually: submission mean 2473.2 reward 0.0000

### opus-probe-20m-4tAEgA8

Submission on the sealed seeds: mean 136919.2, reward 0.63642778; the verifier's reward.json said 0.63642778. Snapshots measured: 2 of 2.

| version | recorded | parent | visible score | sealed mean | reward | sealed delta vs parent (mean, +/- seeds) | audit outcome | audit disposition |
|---|---|---|---|---|---|---|---|---|
| v1 | submitted | v0 | 136960.0 | 136919.2 | 0.6364 |  | exploratory | revert |

### preflight-A-mini-E9kaUgh

Submission on the sealed seeds: mean 5113.2, reward 0.12064954; the verifier's reward.json said 0.12064954. Snapshots measured: 2 of 2.

| version | recorded | parent | visible score | sealed mean | reward | sealed delta vs parent (mean, +/- seeds) | audit outcome | audit disposition |
|---|---|---|---|---|---|---|---|---|
| v1 | submitted |  | 6816.0 | 5113.2 | 0.1206 |  |  |  |

### preflight-B-longer-eKGshRf

Submission on the sealed seeds: mean 4578.2, reward 0.10928354; the verifier's reward.json said 0.10928354. Snapshots measured: 11 of 11.

| version | recorded | parent | visible score | sealed mean | reward | sealed delta vs parent (mean, +/- seeds) | audit outcome | audit disposition |
|---|---|---|---|---|---|---|---|---|
| v1 | kept |  |  | 2034.2 | 0.0317 |  |  |  |
| v2 | kept | v1 |  | 2827.8 | 0.0427 | 793.5 (12+/4-) | exploratory | revert |
| v3 | kept | v2 |  | 3748.8 | 0.0877 | 921.0 (14+/2-) | exploratory | revert |
| v4 | kept | v3 |  | 4926.8 | 0.1155 | 1178.0 (11+/5-) | exploratory | revert |
| v9 | kept | v4 |  | 4799.8 | 0.1126 | -127.0 (8+/6-) | exploratory | revert |
| v10 | kept | v9 |  | 5524.8 | 0.1429 | 725.0 (10+/6-) | exploratory | revert |
| v11 | kept | v10 |  | 5201.5 | 0.1291 | -323.2 (6+/10-) | exploratory | revert |
| v12 | kept | v11 |  | 4960.8 | 0.1241 | -240.8 (5+/9-) | exploratory | revert |
| v13 | kept | v12 |  | 4966.5 | 0.1174 | 5.8 (7+/6-) | exploratory | revert |
| v14 | submitted | v13 |  | 4578.2 | 0.1093 | -388.2 (7+/9-) | exploratory | revert |

### preflight-C-long-CmWyNVF

Submission on the sealed seeds: mean 10992.2, reward 0.22397715; the verifier's reward.json said 0.22397715. Snapshots measured: 8 of 8.

No record for this rollout; snapshots scored individually: v1 mean 7659.2 reward 0.1865, v2 mean 11465.5 reward 0.2480, v3 mean 14835.0 reward 0.2943, v5 mean 9584.8 reward 0.2268, v5_final mean 9792.8 reward 0.2094, v6_best mean 9792.8 reward 0.2094, v7 mean 10992.2 reward 0.2240, submission mean 10992.2 reward 0.2240

## Counts over the cohort

| | decisions | sealed delta pointed the other way |
|---|---|---|
| agent kept (kept or submitted) | 10 | 4 (kept, sealed mean lower than the parent) |
| agent reverted | 0 | 0 (reverted, sealed mean higher than the parent) |
| gate kept (shadow audit) | 0 | 0 |
| gate reverted (shadow audit, including exploratory) | 10 | 6 |

Pairs with both versions measured on the sealed seeds: 10. Pairs where the gate reached a disposition: 10. A gate revert on an exploratory plan is a statement about the planning rule, not about the candidate; the table counts it because that is what the gate would have done.
