# 2048 Policy Improvement Experiment Log

## v0 - Baseline
Parent: N/A
Change: Baseline weak policy - just tries UP, LEFT, RIGHT, DOWN in order
Metrics: mean_score=2060, median_score=1646, mean_max_tile=168
Status: baseline

## v1
Parent: v0
Change: Added multi-heuristic evaluation with heuristics:
- Empty cell count (bonus for open spaces)
- Monotonicity (prefer organized boards)
- Distance-to-corner (prefer concentrated tiles)
- Merge potential (adjacent equal tiles)
- Lookahead moves available

Metrics: mean_score=8838.5, median_score=6294, mean_max_tile=~300
Status: kept (4.3x improvement from baseline)

## v2
Parent: v1
Change: Added lookahead for available future moves
Metrics: mean_score=10134.0, median_score=6270
Status: kept (modest improvement, 4.9x from baseline)

## v3
Parent: v2
Change: Added max_tile_score heuristic with log2 scaling for max tiles
Metrics: mean_score=10414.5, median_score=6930
Status: kept (5.1x from baseline)

## v4
Parent: v3
Change: Added gradient_score heuristic (tiles organized by value)
Metrics: mean_score=9958.0, median_score=8770
Status: reverted (mean score regressed)

## v5
Parent: v3
Change: Conservative weight tuning (empty: 105, mono: 12, dist: 0.12, merge: 60, moves: 22, max_tile: 1.1)
Metrics: mean_score=13544.5, median_score=13842
Status: kept (6.6x from baseline)

## v6 - Best (prior)
Parent: v5
Change: Same weights as v5 (confirmed stable)
Metrics: mean_score=13544.5, median_score=13842
Status: kept (best before v7)

## v7 - Final Best
Parent: v3
Change: More aggressive weight tuning
- empty: 110 (was 100)
- monotonicity: 14 (was 10)
- distances: 0.14 (was 0.1)
- merged_potential: 65 (was 50)
- lookahead_moves: 24 (was 20)
- max_tile: 1.1 (unchanged)

Metrics: mean_score=14667.5, median_score=13588
Status: final submission (7.1x improvement from baseline, 1.08x from v5)

## Strategy Notes

The policy uses a greedy heuristic-based approach:
1. For each legal move, evaluate the resulting board
2. Score boards using weighted combination of six heuristics
3. Pick the move with the highest-scoring resulting board

Key insights:
- Empty cell count is critical (bonus for flexibility)
- Monotonicity helps organize tiles for merging
- Merge potential (adjacent equal tiles) drives scoring
- Max tile score rewards progress toward larger tiles
- Move availability looks ahead one step

Weight tuning was done systematically through experimentation on public seeds.
The improvement trajectory suggests the heuristics capture important aspects
of good play, with weights calibrated for the balance between exploration
(keeping moves available, empty cells) and exploitation (creating merges,
building large tiles).
