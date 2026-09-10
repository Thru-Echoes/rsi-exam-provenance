# Shadow audit over the instrument A/B, stage sonnet

Descriptive and directionless. Pairs are what each record recovers, not the agent's action history. An exploratory outcome means the planning rule the replay configuration names asked for more confirmation seeds than its cap allows. Comparable pairs have both a gate disposition and a recorded keep or revert.

| rollout | versions | pairs | with disposition | record-backed comparable | agree | disagree | task-starter pairs | confirmed | exploratory | screening below | evaluation failed | not replayable | other failures | median planned | cpu s | audit kind | exit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ab-sonnet-1-H-SeA7iww | 3 | 2 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 16 | 52 | confirmation-and-screening | 1 |
| ab-sonnet-2-H-C2M2YpQ | 4 | 3 | 2 | 2 | 1 | 1 | 0 | 2 | 0 | 0 | 1 | 0 | 0 | 16 | 4924 | confirmation-and-screening | 1 |
| ab-sonnet-2-I-SdrMhjg | 3 | 2 | 2 | 2 | 2 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 291 | 898 | confirmation-and-screening | 0 |
| ab-sonnet-3-H-bWAJ7UE | 4 | 3 | 2 | 2 | 1 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 743 | 120 | confirmation-and-screening | 1 |
| ab-sonnet-3-I-jWw94xB | 2 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 16 | 1048 | confirmation-and-screening | 0 |

Per-pair screening lines:

| rollout | parent | candidate | recorded | outcome | estimate | interval | min_effect | screening sd | planned |
|---|---|---|---|---|---|---|---|---|---|
| ab-sonnet-1-H-SeA7iww | v0 | v1 | reverted | evaluation_failed |  |  |  |  |  |
| ab-sonnet-1-H-SeA7iww | v0 | v2 | submitted | confirmed_keep | 19170.0 | 10446.0 to 28774.5 | 51.5 | 17011 | 16 |
| ab-sonnet-2-H-C2M2YpQ | v0 | v1 | reverted | evaluation_failed |  |  |  |  |  |
| ab-sonnet-2-H-C2M2YpQ | v0 | v2 | reverted | confirmed_keep | 40414.0 | 28083.0 to 51973.0 | 51.5 | 21579 | 16 |
| ab-sonnet-2-H-C2M2YpQ | v0 | v3 | submitted | confirmed_keep | 35819.5 | 28979.5 to 42984.5 | 51.5 | 12748 | 16 |
| ab-sonnet-2-I-SdrMhjg | v0 | v1 | submitted | confirmed_keep | 29125.0 | 18459.0 to 40200.5 | 51.5 | 19961 | 16 |
| ab-sonnet-2-I-SdrMhjg | v1 | v2 | reverted | exploratory | 5007.5 | -11924.5 to 21946.0 | 779.6 | 30553 | 566 |
| ab-sonnet-3-H-bWAJ7UE | v0 | v1 | reverted | evaluation_failed |  |  |  |  |  |
| ab-sonnet-3-H-bWAJ7UE | v0 | v2 | kept | confirmed_keep | 23978.5 | 18270.5 to 29497.5 | 51.5 | 10262 | 16 |
| ab-sonnet-3-H-bWAJ7UE | v2 | v3 | submitted | exploratory | 2324.5 | -8397.5 to 12796.5 | 651.0 | 19503 | 1470 |
| ab-sonnet-3-I-jWw94xB | v0 | v1 | submitted | confirmed_keep | 53777.0 | 39105.5 to 67063.0 | 51.5 | 25687 | 16 |
