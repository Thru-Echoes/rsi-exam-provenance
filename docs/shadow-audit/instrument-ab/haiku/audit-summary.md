# Shadow audit over the instrument A/B, stage haiku

Descriptive and directionless. Pairs are what each record recovers, not the agent's action history. An exploratory outcome means the planning rule the replay configuration names asked for more confirmation seeds than its cap allows. Comparable pairs have both a gate disposition and a recorded keep or revert.

| rollout | versions | pairs | with disposition | record-backed comparable | agree | disagree | task-starter pairs | confirmed | exploratory | screening below | evaluation failed | not replayable | other failures | median planned | cpu s | audit kind | exit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ab-haiku-1-H-qoHjD7m | 8 | 7 | 7 | 7 | 4 | 3 | 0 | 1 | 4 | 2 | 0 | 0 | 0 | 236 | 3 | confirmation-and-screening | 0 |
| ab-haiku-1-I-CvxwUxa | 5 | 4 | 4 | 4 | 4 | 0 | 0 | 1 | 3 | 0 | 0 | 0 | 0 | 3823 | 2 | confirmation-and-screening | 0 |
| ab-haiku-2-H-2gcMB53 | 6 | 5 | 5 | 5 | 4 | 1 | 0 | 2 | 3 | 0 | 0 | 0 | 0 | 72 | 12 | confirmation-and-screening | 0 |
| ab-haiku-2-I-bsKugMw | 5 | 4 | 4 | 4 | 3 | 1 | 0 | 2 | 2 | 0 | 0 | 0 | 0 | 69 | 3 | confirmation-and-screening | 0 |
| ab-haiku-3-H-Lt8T7Cp | 9 | 8 | 8 | 8 | 5 | 3 | 0 | 1 | 5 | 2 | 0 | 0 | 0 | 1141 | 2 | confirmation-and-screening | 0 |
| ab-haiku-3-I-A7qtpdG | 4 | 3 | 3 | 3 | 3 | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 21 | 1 | confirmation-and-screening | 0 |
| ab-haiku-4-I-exmA3Kq | 5 | 4 | 4 | 4 | 4 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 0 | 19 | 1 | confirmation-and-screening | 0 |

Per-pair screening lines:

| rollout | parent | candidate | recorded | outcome | estimate | interval | min_effect | screening sd | planned |
|---|---|---|---|---|---|---|---|---|---|
| ab-haiku-1-H-qoHjD7m | v0 | v1 | kept | confirmed_revert | 594.5 | -38.5 to 1222.5 | 51.5 | 1177 | 51 |
| ab-haiku-1-H-qoHjD7m | v1 | v2 | kept | exploratory | 509.5 | -477.5 to 1721.0 | 66.4 | 2069 | 236 |
| ab-haiku-1-H-qoHjD7m | v2 | v3 | reverted | exploratory | -432.0 | -1645.0 to 663.0 | 79.1 | 2117 | 7750 |
| ab-haiku-1-H-qoHjD7m | v2 | v4 | submitted | exploratory | 730.5 | -244.5 to 1927.0 | 79.1 | 2030 | 106 |
| ab-haiku-1-H-qoHjD7m | v4 | v5 | reverted | screening_below | -1050.5 | -2009.0 to -179.5 | 97.4 |  |  |
| ab-haiku-1-H-qoHjD7m | v4 | v6 | reverted | screening_below | -1185.0 | -2080.0 to -281.5 | 97.4 |  |  |
| ab-haiku-1-H-qoHjD7m | v4 | v7 | reverted | exploratory | -291.0 | -1644.5 to 1096.5 | 97.4 | 2540 | 7368 |
| ab-haiku-1-I-CvxwUxa | v0 | v1 | reverted | exploratory | -152.5 | -1163.0 to 827.5 | 51.5 | 1795 | 13155 |
| ab-haiku-1-I-CvxwUxa | v0 | v2 | submitted | confirmed_keep | 5576.5 | 3531.5 to 7648.0 | 51.5 | 3616 | 16 |
| ab-haiku-1-I-CvxwUxa | v2 | v3 | reverted | exploratory | -885.5 | -2187.5 to 413.0 | 190.9 | 2347 | 1637 |
| ab-haiku-1-I-CvxwUxa | v2 | v4 | reverted | exploratory | -129.0 | -2426.0 to 2439.5 | 190.9 | 4499 | 6010 |
| ab-haiku-2-H-2gcMB53 | v0 | v1 | kept | confirmed_keep | 2574.0 | 1323.5 to 3785.5 | 51.5 | 2232 | 16 |
| ab-haiku-2-H-2gcMB53 | v1 | v2 | reverted | exploratory | -223.0 | -1409.0 to 998.0 | 115.9 | 2222 | 3981 |
| ab-haiku-2-H-2gcMB53 | v1 | v3 | kept | confirmed_keep | 3013.0 | 862.0 to 5196.5 | 115.9 | 4017 | 21 |
| ab-haiku-2-H-2gcMB53 | v3 | v4 | submitted | exploratory | 1628.5 | -237.5 to 3740.5 | 191.2 | 3691 | 72 |
| ab-haiku-2-H-2gcMB53 | v4 | v5 | reverted | exploratory | -2789.0 | -5517.0 to 239.0 | 231.9 | 5352 | 5766 |
| ab-haiku-2-I-bsKugMw | v0 | v1 | reverted | confirmed_keep | 752.5 | -167.5 to 1533.5 | 51.5 | 1536 | 52 |
| ab-haiku-2-I-bsKugMw | v0 | v2 | submitted | confirmed_keep | 4423.5 | 2118.0 to 6969.0 | 51.5 | 4487 | 16 |
| ab-haiku-2-I-bsKugMw | v2 | v3 | reverted | exploratory | -240.5 | -1731.5 to 1180.0 | 162.1 | 2747 | 3109 |
| ab-haiku-2-I-bsKugMw | v2 | v4 | reverted | exploratory | 1598.0 | -641.0 to 3948.5 | 162.1 | 4045 | 86 |
| ab-haiku-3-H-Lt8T7Cp | v0 | v1 | kept | exploratory | 195.5 | -354.0 to 795.5 | 51.5 | 1052 | 578 |
| ab-haiku-3-H-Lt8T7Cp | v1 | v2 | kept | confirmed_revert | 1355.5 | 644.0 to 2079.5 | 56.4 | 1314 | 16 |
| ab-haiku-3-H-Lt8T7Cp | v2 | v3 | submitted | exploratory | 115.0 | -253.5 to 582.0 | 90.3 | 769 | 786 |
| ab-haiku-3-H-Lt8T7Cp | v3 | v4 | reverted | exploratory | -382.0 | -1495.5 to 788.5 | 93.2 | 2050 | 5244 |
| ab-haiku-3-H-Lt8T7Cp | v3 | v5 | reverted | exploratory | -438.5 | -1036.5 to 182.5 | 93.2 | 1095 | 1496 |
| ab-haiku-3-H-Lt8T7Cp | v3 | v6 | reverted | screening_below | -389.0 | -753.0 to -57.5 | 93.2 |  |  |
| ab-haiku-3-H-Lt8T7Cp | v3 | v7 | reverted | exploratory | -764.5 | -2014.0 to 569.5 | 93.2 | 2338 | 6819 |
| ab-haiku-3-H-Lt8T7Cp | v3 | v8 | reverted | screening_below | -591.5 | -1245.0 to -1.0 | 93.2 |  |  |
| ab-haiku-3-I-A7qtpdG | v0 | v1 | reverted | confirmed_revert | 1767.0 | 417.5 to 3022.0 | 51.5 | 2343 | 21 |
| ab-haiku-3-I-A7qtpdG | v0 | v2 | submitted | confirmed_keep | 1874.0 | 817.5 to 2998.5 | 51.5 | 1970 | 16 |
| ab-haiku-3-I-A7qtpdG | v2 | v3 | reverted | exploratory | 5.5 | -1495.0 to 1599.0 | 98.4 | 2858 | 9142 |
| ab-haiku-4-I-exmA3Kq | v0 | v1 | reverted | exploratory | -232.5 | -615.0 to 181.0 | 51.5 | 738 | 2225 |
| ab-haiku-4-I-exmA3Kq | v0 | v2 | reverted | confirmed_revert | 1259.5 | 426.0 to 2109.0 | 51.5 | 1569 | 19 |
| ab-haiku-4-I-exmA3Kq | v0 | v3 | reverted | confirmed_revert | 2063.5 | 580.5 to 3538.5 | 51.5 | 2710 | 20 |
| ab-haiku-4-I-exmA3Kq | v0 | v4 | reverted | confirmed_revert | 1259.5 | 426.0 to 2109.0 | 51.5 | 1569 | 19 |
