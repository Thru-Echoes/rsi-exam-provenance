# 2048 Policy Improvement Log

## Baseline
- **v0**: Greedy heuristic (UP, LEFT, RIGHT, DOWN order)
  - Mean score: 2060
  - Median score: 1646
  - Mean max tile: 168
  - Notes: Simple baseline, tries moves in fixed order

## Iteration 1
- **v1**: Heuristic board evaluation (KEPT - FINAL)
  - Mean score: 6816 (+231% vs v0)
  - Median score: 6978 (+324% vs v0)
  - Mean max tile: 560
  - Heuristics: empty cells, monotonicity, smoothness, merge potential
  - Weights: empty=2.7, mono=1.0, smooth=0.1, merge=1.5
  - Notes: Significant improvement across the board. All games valid.

## Iteration 2 (Attempted)
- **v2**: Adjusted weights (higher smooth/merge/empty)
  - Mean score: 6762.5 (-53.5 vs v1)
  - Median score: 6388.0 (-590 vs v1)
  - Notes: Worse performance, reverted to v1
