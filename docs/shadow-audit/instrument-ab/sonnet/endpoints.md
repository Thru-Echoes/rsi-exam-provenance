| trial | arm | block | agent s | stopped | steps | snapshots | record | pairs | gate lines | gate kept | gate reverted | provisional open | blocked | undecided at stop | keeps overruled | refused: safety | refused: window | unmeasurable | kept over margin | confirmations | confirmation min | first evaluate min | first decide min | finalize | profile bound | sealed reward | no reward because | sealed mean | final-selection regret | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ab-sonnet-1-H | H | 1 | 1298 | harness timeout | 23 | 3 | verified | 2 | 0 | 0 | 0 | 0 |  | v2 | 0 | 0 | 0 | 0 | 0 | 0 |  | 2.6 | 20.9 | no |  | 0.38678773 |  | 26403.0 | 0.0000 | 0.79 |
| ab-sonnet-1-I | I | 1 | 777 | agent finished | 35 | 2 | no record |  | 0 | 0 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 0 |  | 2.4 | 10.5 | yes |  | 0.3327198 |  | 20127.25 | 0.0000 | 1.00 |
| ab-sonnet-2-H | H | 2 | 832 | agent finished | 54 | 4 | verified | 3 | 0 | 0 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 0 |  | 0.3 | 0.7 | yes |  | 0.4697557 |  | 46706.5 | 0.0000 | 1.25 |
| ab-sonnet-2-I | I | 2 | 816 | agent finished | 33 | 3 | verified | 2 | 2 | 1 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 1 (8 seeds) | 1.6 | 1.7 | 3.2 | yes | yes | 0.4350452 |  | 35002.75 |  | 1.38 |
| ab-sonnet-3-H | H | 3 | 1268 | agent finished | 25 | 4 | verified | 3 | 0 | 0 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 0 |  | 2.4 | 17.4 | yes |  | 0.4235464 |  | 36052.75 |  | 0.78 |
| ab-sonnet-3-I | I | 3 | 674 | agent finished | 33 | 2 | verified | 1 | 2 | 1 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 1 (8 seeds) | 3.9 | 2.3 | 8.9 | yes | yes | 0.46113606 |  | 42735.5 |  | 0.88 |

Paired by block (sealed reward of the submission, instrument minus helper). A block with both rewards has a numeric difference; when exactly one trial has a reward from the verifier the other arm's failure is an outcome and the scorable arm is counted as favoured, with no numeric difference; a block with neither, or with a trial not started, is incomplete and enters no count.

| block | instrument trial | helper trial | reward I | reward H | I minus H | block outcome | regret I | regret H |
|---|---|---|---|---|---|---|---|---|
| 1 | ab-sonnet-1-I | ab-sonnet-1-H | 0.3327198 | 0.38678773 | -0.0541 | favours H | 0.0000 | 0.0000 |
| 2 | ab-sonnet-2-I | ab-sonnet-2-H | 0.4350452 | 0.4697557 | -0.0347 | favours H |  | 0.0000 |
| 3 | ab-sonnet-3-I | ab-sonnet-3-H | 0.46113606 | 0.4235464 | +0.0376 | favours I |  |  |

Blocks: 3; favouring the instrument: 1; favouring the helper: 2; ties: 0; incomplete: 0. Over the 3 blocks with two rewards: mean difference -0.0171; exact two-sided sign test p: 1.000 (n=3) (zero differences dropped). With this many blocks the sign test cannot fall below 0.125 (four blocks) or 0.25 (three); the number describes the direction of these blocks and establishes nothing.

Decisions read against the sealed seeds, both arms (descriptive; the sealed suite is analysis data). In the instrument arm a decision is the gate's (its last line for the version); in the helper arm it is the agent's recorded status. The threshold is the minimum effect on the sealed scale, 2.5 percent of the parent's sealed mean: a keep whose sealed delta is below minus that, and a revert whose delta is above it, are the decisions the sealed seeds disagreed with; a delta within the threshold is indeterminate and counted apart.

| trial | arm | keeps | keeps the sealed seeds disagreed with | reverts | reverts the sealed seeds disagreed with | within the threshold | unmeasured |
|---|---|---|---|---|---|---|---|
| ab-sonnet-1-H | H | 1 | 0 | 0 | 0 | 0 | 1 |
| ab-sonnet-1-I | I | no sealed report or record | | | | |
| ab-sonnet-2-H | H | 1 | 0 | 0 | 0 | 0 | 2 |
| ab-sonnet-2-I | I | no sealed report or record | | | | |
| ab-sonnet-3-H | H | no sealed report or record | | | | |
| ab-sonnet-3-I | I | no sealed report or record | | | | |
