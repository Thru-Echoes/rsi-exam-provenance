# Shadow audit over the helper-overlay campaign cohort

Descriptive and directionless. Pairs are what each record recovers, not the agent's action history. An exploratory outcome means the accepted planning rule asked for more confirmation seeds than the cap (64) allows. Comparable pairs have both a gate disposition and a recorded keep or revert.

| rollout | versions | pairs | with disposition | record-backed comparable | agree | disagree | task-starter pairs | confirmed | exploratory | screening below | evaluation failed | not replayable | other failures | median planned | cpu s | audit kind | exit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| campaign-H1-hoG9P2f | 10 | 9 | 9 | 9 | 5 | 4 | 0 | 0 | 6 | 3 | 0 | 0 | 0 | 5897 | 83 | screening-and-feasibility | 0 |
| campaign-H2-R8sDt8Y | 10 | 9 | 9 | 9 | 5 | 4 | 0 | 0 | 8 | 1 | 0 | 0 | 0 | 13467 | 97 | screening-and-feasibility | 0 |
| campaign-H3-RbhgqQB | 9 | 8 | 8 | 8 | 6 | 2 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 8993 | 3 | screening-and-feasibility | 0 |
| campaign-H4-LWzeis7 | 7 | 6 | 6 | 6 | 3 | 3 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 3981 | 7 | screening-and-feasibility | 0 |
| campaign-H6-3qz6CEn | 13 | 12 | 12 | 12 | 6 | 6 | 0 | 0 | 11 | 1 | 0 | 0 | 0 | 10565 | 8 | screening-and-feasibility | 0 |
| campaign-O1-zvdgNzq | 2 | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 16443551 | 251 | screening-and-feasibility | 0 |
| campaign-O2-Fjweu3m | 3 | 2 | 2 | 2 | 0 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 964903 | 394 | screening-and-feasibility | 0 |
| campaign-S1-qXiB758 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |  | 0 | screening-and-feasibility | 1 |
| campaign-S2-xZPTJeM | 2 | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 62699 | 156 | screening-and-feasibility | 0 |
| campaign-S3-Lhwt3ro | 3 | 2 | 2 | 2 | 0 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 422826 | 260 | screening-and-feasibility | 0 |

Per-pair screening lines, for the sizing question:

| rollout | parent | candidate | recorded | outcome | estimate | interval | min_effect | screening sd | planned |
|---|---|---|---|---|---|---|---|---|---|
| campaign-H1-hoG9P2f | v0 | v1 | kept | exploratory | 1621.5 | 786.5 to 2457.0 | 51.5 | 1524 | 9483 |
| campaign-H1-hoG9P2f | v1 | v2 | kept | exploratory | 2225.0 | 947.0 to 3433.0 | 92.0 | 2266 | 6560 |
| campaign-H1-hoG9P2f | v2 | v3 | reverted | screening_below | -2347.0 | -3260.0 to -1446.5 | 147.7 |  |  |
| campaign-H1-hoG9P2f | v2 | v4 | kept | exploratory | 1402.5 | 559.5 to 2319.5 | 147.7 | 1628 | 1316 |
| campaign-H1-hoG9P2f | v4 | v5 | reverted | screening_below | -1896.0 | -3113.0 to -806.0 | 182.7 |  |  |
| campaign-H1-hoG9P2f | v4 | v6 | submitted | exploratory | 760.0 | -2155.0 to 3495.0 | 182.7 | 5135 | 8546 |
| campaign-H1-hoG9P2f | v6 | v7 | reverted | screening_below | -2200.0 | -4198.5 to -249.0 | 201.7 |  |  |
| campaign-H1-hoG9P2f | v6 | v8 | reverted | exploratory | -439.5 | -2676.5 to 1824.0 | 201.7 | 4139 | 4557 |
| campaign-H1-hoG9P2f | v6 | v9 | reverted | exploratory | -1883.0 | -4348.0 to 472.0 | 201.7 | 4436 | 5234 |
| campaign-H2-R8sDt8Y | v0 | v1 | kept | exploratory | 1867.5 | 1021.5 to 2746.5 | 51.5 | 1570 | 10056 |
| campaign-H2-R8sDt8Y | v1 | v2 | kept | exploratory | 4262.5 | 1447.5 to 7250.0 | 98.2 | 5226 | 30657 |
| campaign-H2-R8sDt8Y | v2 | v3 | reverted | screening_below | -7390.0 | -10497.5 to -4593.0 | 204.8 |  |  |
| campaign-H2-R8sDt8Y | v2 | v4 | kept | exploratory | 613.5 | -3330.0 to 4654.0 | 204.8 | 7196 | 13369 |
| campaign-H2-R8sDt8Y | v4 | v5 | reverted | exploratory | -1326.0 | -5605.5 to 2875.0 | 220.1 | 7806 | 13616 |
| campaign-H2-R8sDt8Y | v4 | v6 | reverted | exploratory | -13.5 | -3975.0 to 3629.0 | 220.1 | 6955 | 10807 |
| campaign-H2-R8sDt8Y | v4 | v7 | reverted | exploratory | -579.0 | -4029.0 to 2513.0 | 220.1 | 5911 | 7807 |
| campaign-H2-R8sDt8Y | v4 | v8 | submitted | exploratory | 229.5 | -3964.5 to 4494.0 | 220.1 | 7792 | 13566 |
| campaign-H2-R8sDt8Y | v8 | v9 | reverted | exploratory | -436.5 | -6857.0 to 4604.5 | 225.8 | 10523 | 23499 |
| campaign-H3-RbhgqQB | v0 | v1 | reverted | exploratory | -45.0 | -572.0 to 540.5 | 51.5 | 1007 | 4140 |
| campaign-H3-RbhgqQB | v0 | v2 | kept | exploratory | 727.0 | 18.5 to 1514.5 | 51.5 | 1385 | 7824 |
| campaign-H3-RbhgqQB | v2 | v3 | reverted | exploratory | -97.5 | -1196.0 to 1194.5 | 69.7 | 2209 | 10878 |
| campaign-H3-RbhgqQB | v2 | v4 | submitted | exploratory | 3348.5 | 1124.0 to 5559.5 | 69.7 | 4084 | 37177 |
| campaign-H3-RbhgqQB | v4 | v5 | reverted | exploratory | -577.0 | -3464.5 to 2443.0 | 153.4 | 5483 | 13827 |
| campaign-H3-RbhgqQB | v4 | v6 | reverted | exploratory | -443.0 | -2332.5 to 1473.5 | 153.4 | 3452 | 5483 |
| campaign-H3-RbhgqQB | v4 | v7 | reverted | exploratory | -741.0 | -3088.0 to 1843.0 | 153.4 | 4427 | 9015 |
| campaign-H3-RbhgqQB | v4 | v8 | reverted | exploratory | -535.0 | -2858.0 to 1933.5 | 153.4 | 4416 | 8972 |
| campaign-H4-LWzeis7 | v0 | v1 | kept | exploratory | 1050.0 | 496.5 to 1528.5 | 51.5 | 966 | 3809 |
| campaign-H4-LWzeis7 | v1 | v2 | kept | exploratory | 990.5 | 201.5 to 1817.0 | 77.8 | 1523 | 4153 |
| campaign-H4-LWzeis7 | v2 | v3 | submitted | exploratory | 494.0 | -260.0 to 1010.0 | 102.5 | 1172 | 1415 |
| campaign-H4-LWzeis7 | v3 | v4 | reverted | exploratory | -783.5 | -1536.0 to 59.5 | 114.9 | 1454 | 1734 |
| campaign-H4-LWzeis7 | v3 | v5 | reverted | exploratory | -576.0 | -2008.0 to 822.0 | 114.9 | 2577 | 5448 |
| campaign-H4-LWzeis7 | v3 | v6 | reverted | exploratory | -699.5 | -2006.5 to 448.5 | 114.9 | 2274 | 4243 |
| campaign-H6-3qz6CEn | v0 | v1 | kept | exploratory | 2520.0 | 1325.0 to 3652.5 | 51.5 | 2130 | 18512 |
| campaign-H6-3qz6CEn | v1 | v2 | reverted | exploratory | 163.0 | -1639.0 to 1911.5 | 114.5 | 3304 | 9012 |
| campaign-H6-3qz6CEn | v1 | v3 | kept | exploratory | 1006.5 | -613.0 to 2810.5 | 114.5 | 3172 | 8305 |
| campaign-H6-3qz6CEn | v3 | v4 | reverted | exploratory | -992.5 | -3139.5 to 849.5 | 139.7 | 3732 | 7726 |
| campaign-H6-3qz6CEn | v3 | v5 | kept | exploratory | 161.5 | -1671.5 to 1964.0 | 139.7 | 3331 | 6155 |
| campaign-H6-3qz6CEn | v5 | v6 | kept | exploratory | 4037.5 | 1097.0 to 7102.0 | 143.7 | 5497 | 15835 |
| campaign-H6-3qz6CEn | v6 | v7 | reverted | screening_below | -3691.0 | -6770.0 to -504.0 | 244.6 |  |  |
| campaign-H6-3qz6CEn | v6 | v8 | reverted | exploratory | -4202.0 | -8124.5 to 86.5 | 244.6 | 7643 | 10565 |
| campaign-H6-3qz6CEn | v6 | v9 | kept | exploratory | 1364.0 | -3128.0 to 5777.5 | 244.6 | 8005 | 11588 |
| campaign-H6-3qz6CEn | v9 | v10 | submitted | exploratory | 378.5 | -6488.5 to 8386.0 | 278.7 | 13917 | 26981 |
| campaign-H6-3qz6CEn | v10 | v11 | reverted | exploratory | -3107.5 | -7535.5 to 694.5 | 288.2 | 7866 | 8062 |
| campaign-H6-3qz6CEn | v10 | v12 | reverted | exploratory | -3495.5 | -10012.0 to 1122.0 | 288.2 | 10200 | 13556 |
| campaign-O1-zvdgNzq | v0 | v1 | submitted | exploratory | 149197.0 | 114661.5 to 182565.5 | 51.5 | 63482 | 16443551 |
| campaign-O2-Fjweu3m | v0 | v1 | kept | exploratory | 48304.5 | 36042.5 to 59678.5 | 51.5 | 21701 | 1921601 |
| campaign-O2-Fjweu3m | v1 | v2 | submitted | exploratory | 17195.5 | -2246.5 to 35952.5 | 1259.1 | 34668 | 8205 |
| campaign-S1-qXiB758 | v0 | v1 | submitted | evaluation_failed |  |  |  |  |  |
| campaign-S2-xZPTJeM | v0 | v1 | submitted | exploratory | 11548.5 | 9274.0 to 13482.5 | 51.5 | 3920 | 62699 |
| campaign-S3-Lhwt3ro | v0 | v1 | kept | exploratory | 29041.0 | 21754.0 to 37332.5 | 51.5 | 14316 | 836281 |
| campaign-S3-Lhwt3ro | v1 | v2 | submitted | exploratory | 2487.0 | -9256.5 to 15126.5 | 777.5 | 22880 | 9372 |
