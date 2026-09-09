# Shadow audit over the helper-backed pilot records (demonstration, not anchored)

Descriptive and directionless. Pairs are what each record recovers, not the agent's action history. An exploratory outcome means the accepted planning rule asked for more confirmation seeds than the cap (64) allows. Comparable pairs have both a gate disposition and a recorded keep or revert.

| rollout | versions | pairs | with disposition | record-backed comparable | agree | disagree | task-starter pairs | confirmed | exploratory | screening below | evaluation failed | not replayable | other failures | median planned | cpu s | audit kind | exit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pilot-haiku-C0-mQDrhf8 | 4 | 3 | 3 | 3 | 1 | 2 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 13192 | 0 | screening-and-feasibility | 2 |
| pilot-haiku-C1-Lm65CUp | 19 | 18 | 18 | 18 | 14 | 4 | 0 | 1 | 12 | 5 | 0 | 0 | 0 | 7462 | 7 | confirmation-and-screening | 2 |
| pilot-haiku-C2-fhidLPm | 12 | 11 | 11 | 11 | 7 | 4 | 0 | 0 | 7 | 4 | 0 | 0 | 0 | 6664 | 8 | screening-and-feasibility | 2 |
| pilot-haiku-C3-CwwaZkP | 15 | 14 | 14 | 14 | 8 | 6 | 0 | 0 | 8 | 6 | 0 | 0 | 0 | 8235 | 6 | screening-and-feasibility | 0 |

Per-pair screening lines, for the sizing question:

| rollout | parent | candidate | recorded | outcome | estimate | interval | min_effect | screening sd | planned |
|---|---|---|---|---|---|---|---|---|---|
| pilot-haiku-C0-mQDrhf8 | v0 | v1 | kept | exploratory | 1717.5 | 538.5 to 3027.0 | 51.5 | 2240 | 20481 |
| pilot-haiku-C0-mQDrhf8 | v1 | v2 | reverted | exploratory | -44.0 | -924.5 to 1040.5 | 94.4 | 1805 | 3952 |
| pilot-haiku-C0-mQDrhf8 | v1 | v3 | submitted | exploratory | 502.5 | -1242.0 to 2389.5 | 94.4 | 3297 | 13192 |
| pilot-haiku-C1-Lm65CUp | v0 | v1 | kept | exploratory | 1991.0 | 1068.0 to 2969.5 | 51.5 | 1724 | 12123 |
| pilot-haiku-C1-Lm65CUp | v1 | v2 | kept | exploratory | 1945.5 | 406.5 to 3844.0 | 101.3 | 3176 | 10645 |
| pilot-haiku-C1-Lm65CUp | v2 | v3 | reverted | confirmed_revert | 0.0 | 0.0 to 0.0 | 149.9 | 0 | 16 |
| pilot-haiku-C1-Lm65CUp | v2 | v4 | reverted | screening_below | -1529.0 | -2946.5 to -270.0 | 149.9 |  |  |
| pilot-haiku-C1-Lm65CUp | v2 | v5 | reverted | screening_below | -2646.5 | -4468.5 to -993.0 | 149.9 |  |  |
| pilot-haiku-C1-Lm65CUp | v2 | v6 | reverted | exploratory | -1432.5 | -3049.5 to 135.5 | 149.9 | 2959 | 4216 |
| pilot-haiku-C1-Lm65CUp | v2 | v7 | reverted | exploratory | -1621.5 | -3896.0 to 454.5 | 149.9 | 3936 | 7462 |
| pilot-haiku-C1-Lm65CUp | v2 | v8 | reverted | exploratory | -1207.0 | -2992.5 to 536.0 | 149.9 | 3195 | 4917 |
| pilot-haiku-C1-Lm65CUp | v2 | v9 | reverted | exploratory | -1949.0 | -4168.5 to 15.5 | 149.9 | 3883 | 7260 |
| pilot-haiku-C1-Lm65CUp | v2 | v10 | kept | exploratory | 384.5 | -1347.5 to 2423.5 | 149.9 | 3594 | 6220 |
| pilot-haiku-C1-Lm65CUp | v10 | v11 | reverted | exploratory | -862.0 | -3418.5 to 1393.0 | 159.5 | 4369 | 8119 |
| pilot-haiku-C1-Lm65CUp | v10 | v12 | reverted | screening_below | -2923.5 | -5797.5 to -139.5 | 159.5 |  |  |
| pilot-haiku-C1-Lm65CUp | v10 | v13 | reverted | exploratory | -1363.5 | -3582.5 to 957.5 | 159.5 | 4231 | 7615 |
| pilot-haiku-C1-Lm65CUp | v10 | v14 | reverted | exploratory | -722.5 | -2167.5 to 0.0 | 159.5 | 2044 | 1776 |
| pilot-haiku-C1-Lm65CUp | v10 | v15 | submitted | exploratory | 130.0 | -2472.5 to 2661.5 | 159.5 | 4750 | 9594 |
| pilot-haiku-C1-Lm65CUp | v15 | v16 | reverted | exploratory | -433.5 | -3363.5 to 2405.0 | 162.8 | 5408 | 11947 |
| pilot-haiku-C1-Lm65CUp | v15 | v17 | reverted | screening_below | -1317.5 | -2504.5 to -334.0 | 162.8 |  |  |
| pilot-haiku-C1-Lm65CUp | v15 | v18 | reverted | screening_below | -1938.5 | -3140.5 to -772.5 | 162.8 |  |  |
| pilot-haiku-C2-fhidLPm | v0 | v1 | kept | exploratory | 2496.0 | 1202.0 to 3771.0 | 51.5 | 2331 | 22164 |
| pilot-haiku-C2-fhidLPm | v1 | v2 | reverted | screening_below | -1893.0 | -3122.5 to -690.0 | 113.9 |  |  |
| pilot-haiku-C2-fhidLPm | v1 | v3 | kept | exploratory | 1705.5 | 600.0 to 2834.5 | 113.9 | 2005 | 3353 |
| pilot-haiku-C2-fhidLPm | v3 | v4 | kept | exploratory | 109.0 | -2114.5 to 2429.5 | 156.5 | 4088 | 7382 |
| pilot-haiku-C2-fhidLPm | v4 | v5 | reverted | screening_below | -3544.0 | -5484.0 to -1717.0 | 159.3 |  |  |
| pilot-haiku-C2-fhidLPm | v4 | v6 | reverted | exploratory | -185.5 | -1711.0 to 1301.5 | 159.3 | 2771 | 3277 |
| pilot-haiku-C2-fhidLPm | v4 | v7 | reverted | exploratory | -514.5 | -2669.5 to 1672.5 | 159.3 | 3952 | 6664 |
| pilot-haiku-C2-fhidLPm | v4 | v8 | submitted | exploratory | 991.0 | -1620.5 to 3449.5 | 159.3 | 4672 | 9314 |
| pilot-haiku-C2-fhidLPm | v8 | v9 | reverted | screening_below | -3414.0 | -5031.5 to -1936.0 | 184.0 |  |  |
| pilot-haiku-C2-fhidLPm | v8 | v10 | reverted | screening_below | -2626.5 | -4889.5 to -577.5 | 184.0 |  |  |
| pilot-haiku-C2-fhidLPm | v8 | v11 | reverted | exploratory | -1939.0 | -4168.5 to 181.0 | 184.0 | 3978 | 5058 |
| pilot-haiku-C3-CwwaZkP | v0 | v1 | kept | exploratory | 1015.0 | 446.5 to 1521.5 | 51.5 | 977 | 3893 |
| pilot-haiku-C3-CwwaZkP | v1 | v2 | kept | exploratory | 619.0 | 78.0 to 1262.0 | 76.9 | 1113 | 2268 |
| pilot-haiku-C3-CwwaZkP | v2 | v3 | kept | exploratory | 1111.0 | -55.0 to 2283.5 | 92.4 | 2177 | 6013 |
| pilot-haiku-C3-CwwaZkP | v3 | v4 | kept | exploratory | 445.0 | -2427.0 to 3685.5 | 120.1 | 5695 | 24324 |
| pilot-haiku-C3-CwwaZkP | v4 | v5 | kept | exploratory | 744.5 | -1431.0 to 2558.5 | 131.2 | 3674 | 8482 |
| pilot-haiku-C3-CwwaZkP | v5 | v6 | reverted | screening_below | -2019.0 | -3697.5 to -464.5 | 149.9 |  |  |
| pilot-haiku-C3-CwwaZkP | v5 | v7 | reverted | exploratory | -1767.0 | -3826.5 to 571.5 | 149.9 | 4071 | 7988 |
| pilot-haiku-C3-CwwaZkP | v5 | v8 | reverted | screening_below | -3350.0 | -4866.0 to -1780.0 | 149.9 |  |  |
| pilot-haiku-C3-CwwaZkP | v5 | v9 | reverted | exploratory | -839.0 | -3303.5 to 1888.5 | 149.9 | 4747 | 10857 |
| pilot-haiku-C3-CwwaZkP | v5 | v10 | submitted | exploratory | 1390.0 | -1058.0 to 4487.5 | 149.9 | 5152 | 12790 |
| pilot-haiku-C3-CwwaZkP | v10 | v11 | reverted | screening_below | -2904.5 | -5610.0 to -588.0 | 184.6 |  |  |
| pilot-haiku-C3-CwwaZkP | v10 | v12 | reverted | screening_below | -2934.5 | -5241.5 to -957.0 | 184.6 |  |  |
| pilot-haiku-C3-CwwaZkP | v10 | v13 | reverted | screening_below | -2913.0 | -5364.0 to -583.5 | 184.6 |  |  |
| pilot-haiku-C3-CwwaZkP | v10 | v14 | reverted | screening_below | -1724.5 | -3148.0 to -315.0 | 184.6 |  |  |
