# Shadow audit over the development cohort

Descriptive and directionless. Pairs are what each record recovers, not the agent's action history. An exploratory outcome means the accepted planning rule asked for more confirmation seeds than the cap (64) allows. Comparable pairs have both a gate disposition and a recorded keep or revert.

| rollout | versions | pairs | with disposition | record-backed comparable | agree | disagree | task-starter pairs | confirmed | exploratory | screening below | evaluation failed | not replayable | other failures | median planned | cpu s | audit kind | exit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| opus-batch-k5-8NhhboZ-pair |  | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |  | 0 | screening-and-feasibility | 1 |
| opus-batch-k5-F7E69wm | 3 | 2 | 1 | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 9692228 | 552 | screening-and-feasibility | 1 |
| opus-batch-k5-FHQNNyJ | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  | 0 | screening-and-feasibility | 0 |
| opus-probe-20m-4tAEgA8 | 1 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 15515437 | 342 | screening-and-feasibility | 0 |
| preflight-A-mini-E9kaUgh | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  | 0 | screening-and-feasibility | 0 |
| preflight-B-longer-eKGshRf | 10 | 9 | 9 | 9 | 0 | 9 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 6177 | 24 | screening-and-feasibility | 0 |

Per-pair screening lines, for the sizing question:

| rollout | parent | candidate | recorded | outcome | estimate | interval | min_effect | screening sd | planned |
|---|---|---|---|---|---|---|---|---|---|
| opus-batch-k5-8NhhboZ-pair | v0 | v1 |  | evaluation_failed |  |  |  |  |  |
| opus-batch-k5-F7E69wm | v0 | v1 | submitted | exploratory | 83474.0 | 56528.5 to 109760.0 | 51.5 | 48737 | 9692228 |
| opus-batch-k5-F7E69wm | v1 | v2 | reverted | evaluation_failed |  |  |  |  |  |
| opus-probe-20m-4tAEgA8 | v0 | v1 | submitted | exploratory | 109152.5 | 75879.0 to 142174.5 | 51.5 | 61664 | 15515437 |
| preflight-B-longer-eKGshRf | v1 | v2 | kept | exploratory | 910.0 | -399.0 to 2304.5 | 57.7 | 2471 | 19845 |
| preflight-B-longer-eKGshRf | v2 | v3 | kept | exploratory | 1166.5 | 108.0 to 2148.5 | 80.5 | 1833 | 5619 |
| preflight-B-longer-eKGshRf | v3 | v4 | kept | exploratory | 251.0 | -1131.5 to 1703.0 | 109.6 | 2619 | 6177 |
| preflight-B-longer-eKGshRf | v4 | v9 | kept | exploratory | 1063.5 | 135.5 to 1976.5 | 115.9 | 1711 | 2360 |
| preflight-B-longer-eKGshRf | v9 | v10 | kept | exploratory | 222.0 | -2522.0 to 3269.5 | 142.5 | 5298 | 14962 |
| preflight-B-longer-eKGshRf | v10 | v11 | kept | exploratory | 18.0 | -2879.5 to 2961.5 | 148.0 | 5141 | 13050 |
| preflight-B-longer-eKGshRf | v11 | v12 | kept | exploratory | 209.0 | -1531.5 to 1942.5 | 148.5 | 3239 | 5151 |
| preflight-B-longer-eKGshRf | v12 | v13 | kept | exploratory | 491.0 | -650.0 to 1732.0 | 153.7 | 2178 | 2173 |
| preflight-B-longer-eKGshRf | v13 | v14 | submitted | exploratory | 2089.5 | -838.0 to 4729.5 | 166.0 | 5122 | 10306 |
