| trial | arm | block | agent s | stopped | steps | snapshots | record | pairs | gate lines | gate kept | gate reverted | provisional open | blocked | undecided at stop | keeps overruled | refused: safety | refused: window | unmeasurable | kept over margin | confirmations | confirmation min | first evaluate min | first decide min | finalize | profile bound | sealed reward | no reward because | sealed mean | final-selection regret | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ab-haiku-1-H | H | 1 | 186 | agent finished | 51 | 8 | verified | 7 | 0 | 0 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 0 |  | 0.6 | 0.7 | yes |  | 0.07764052 |  | 3295.25 | 0.0306 | 0.69 |
| ab-haiku-1-I | I | 1 | 150 | agent finished | 39 | 5 | verified | 4 | 2 | 1 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 1 (8 seeds) | 0.0 | 0.7 | 0.8 | yes | yes | 0.14003888 |  | 5554.0 | 0.0434 | 0.55 |
| ab-haiku-2-H | H | 2 | 168 | agent finished | 39 | 6 | verified | 5 | 0 | 0 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 0 |  | 0.6 | 0.7 | yes |  | 0.21636209 |  | 9245.25 | 0.0000 | 0.53 |
| ab-haiku-2-I | I | 2 | 180 | agent finished | 41 | 5 | verified | 4 | 3 | 1 | 1 | 0 |  |  | 1 | 0 | 0 | 0 | 0 | 1 (12 seeds) | 0.0 | 0.6 | 0.7 | yes | yes | 0.1808063 |  | 7335.0 | 0.0000 | 0.67 |
| ab-haiku-3-H | H | 3 | 216 | agent finished | 63 | 9 | verified | 8 | 0 | 0 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 0 |  | 0.5 | 0.5 | yes |  | 0.04347278 |  | 2496.75 | 0.0287 | 0.89 |
| ab-haiku-3-I | I | 3 | 249 | agent finished | 59 | 4 | verified | 3 | 3 | 1 | 1 | 0 |  |  | 1 | 0 | 0 | 0 | 0 | 1 (13 seeds) | 0.0 | 0.8 | 0.9 | yes | yes | 0.09345836 |  | 3931.75 | 0.0268 | 0.93 |
| ab-haiku-4-H | H | 4 | 348 | harness timeout | 63 | 8 | no record |  | 0 | 0 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 0 |  | 0.5 | 0.6 | no |  | 0.15123168 |  | 5932.5 | 0.0108 | 1.03 |
| ab-haiku-4-I | I | 4 | 160 | agent finished | 38 | 5 | verified | 4 | 2 | 0 | 2 | 0 |  |  | 2 | 0 | 0 | 0 | 0 | 0 |  | 0.5 | 0.5 | yes | yes | 0.0 |  | 2473.25 | 0.0732 | 0.55 |

Paired by block (sealed reward of the submission, instrument minus helper). A block with both rewards has a numeric difference; when exactly one trial has a reward from the verifier the other arm's failure is an outcome and the scorable arm is counted as favoured, with no numeric difference; a block with neither, or with a trial not started, is incomplete and enters no count.

| block | instrument trial | helper trial | reward I | reward H | I minus H | block outcome | regret I | regret H |
|---|---|---|---|---|---|---|---|---|
| 1 | ab-haiku-1-I | ab-haiku-1-H | 0.14003888 | 0.07764052 | +0.0624 | favours I | 0.0434 | 0.0306 |
| 2 | ab-haiku-2-I | ab-haiku-2-H | 0.1808063 | 0.21636209 | -0.0356 | favours H | 0.0000 | 0.0000 |
| 3 | ab-haiku-3-I | ab-haiku-3-H | 0.09345836 | 0.04347278 | +0.0500 | favours I | 0.0268 | 0.0287 |
| 4 | ab-haiku-4-I | ab-haiku-4-H | 0.0 | 0.15123168 | -0.1512 | favours H | 0.0732 | 0.0108 |

Blocks: 4; favouring the instrument: 2; favouring the helper: 2; ties: 0; incomplete: 0. Over the 4 blocks with two rewards: mean difference -0.0186; exact two-sided sign test p: 1.000 (n=4) (zero differences dropped). With this many blocks the sign test cannot fall below 0.125 (four blocks) or 0.25 (three); the number describes the direction of these blocks and establishes nothing.

Decisions read against the sealed seeds, both arms (descriptive; the sealed suite is analysis data). In the instrument arm a decision is the gate's (its last line for the version); in the helper arm it is the agent's recorded status. The threshold is the minimum effect on the sealed scale, 2.5 percent of the parent's sealed mean: a keep whose sealed delta is below minus that, and a revert whose delta is above it, are the decisions the sealed seeds disagreed with; a delta within the threshold is indeterminate and counted apart.

| trial | arm | keeps | keeps the sealed seeds disagreed with | reverts | reverts the sealed seeds disagreed with | within the threshold | unmeasured |
|---|---|---|---|---|---|---|---|
| ab-haiku-1-H | H | 3 | 1 | 4 | 2 | 0 | 0 |
| ab-haiku-1-I | I | 1 | 0 | 3 | 2 | 1 | 0 |
| ab-haiku-2-H | H | 3 | 0 | 2 | 0 | 0 | 0 |
| ab-haiku-2-I | I | 1 | 0 | 3 | 1 | 1 | 0 |
| ab-haiku-3-H | H | 3 | 2 | 5 | 3 | 2 | 0 |
| ab-haiku-3-I | I | 1 | 0 | 2 | 2 | 0 | 0 |
| ab-haiku-4-H | H | no sealed report or record | | | | |
| ab-haiku-4-I | I | 0 | 0 | 4 | 3 | 0 | 0 |
