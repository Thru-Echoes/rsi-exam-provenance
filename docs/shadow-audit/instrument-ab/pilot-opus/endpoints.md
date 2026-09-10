| trial | arm | block | agent s | stopped | steps | snapshots | record | pairs | gate lines | gate kept | gate reverted | provisional open | blocked | undecided at stop | keeps overruled | refused: safety | refused: window | unmeasurable | kept over margin | confirmations | confirmation min | first evaluate min | first decide min | finalize | profile bound | sealed reward | no reward because | sealed mean | final-selection regret | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ab-pilot-opus-1-I | I | 1 | 1545 | agent finished | 26 | 2 | verified | 1 | 2 | 1 | 0 | 0 |  |  | 0 | 0 | 0 | 0 | 0 | 1 (8 seeds) | 4.6 | 20.3 | 25.0 | yes | yes | 0.62840033 |  | 136673.5 | -0.6284 | 4.96 |

Paired by block (sealed reward of the submission, instrument minus helper). A block with both rewards has a numeric difference; when exactly one trial has a reward from the verifier the other arm's failure is an outcome and the scorable arm is counted as favoured, with no numeric difference; a block with neither, or with a trial not started, is incomplete and enters no count.

| block | instrument trial | helper trial | reward I | reward H | I minus H | block outcome | regret I | regret H |
|---|---|---|---|---|---|---|---|---|
| 1 | ab-pilot-opus-1-I | not started | 0.62840033 |  |  | incomplete: a trial did not start | -0.6284 |  |

Blocks: 1; favouring the instrument: 0; favouring the helper: 0; ties: 0; incomplete: 1. Over the 0 blocks with two rewards: mean difference none; exact two-sided sign test p: no non-zero differences (zero differences dropped). With this many blocks the sign test cannot fall below 0.125 (four blocks) or 0.25 (three); the number describes the direction of these blocks and establishes nothing.

Decisions read against the sealed seeds, both arms (descriptive; the sealed suite is analysis data). In the instrument arm a decision is the gate's (its last line for the version); in the helper arm it is the agent's recorded status. The threshold is the minimum effect on the sealed scale, 2.5 percent of the parent's sealed mean: a keep whose sealed delta is below minus that, and a revert whose delta is above it, are the decisions the sealed seeds disagreed with; a delta within the threshold is indeterminate and counted apart.

| trial | arm | keeps | keeps the sealed seeds disagreed with | reverts | reverts the sealed seeds disagreed with | within the threshold | unmeasured |
|---|---|---|---|---|---|---|---|
| ab-pilot-opus-1-I | I | 0 | 0 | 0 | 0 | 0 | 1 |
