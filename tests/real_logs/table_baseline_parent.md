# Experiment log — 2048 policy

## How I judge generalization
The metric is the mean raw merge score over a seed suite; hidden seeds come from the same
generator, so the *only* difference between public and sealed is RNG noise. Per-game score
variance in 2048 is huge (sd ~ 40% of the mean), so 8 public seeds give a standard error of
~15% — far too noisy to tune on. Therefore:
* **Tuning set** = seeds 1000..1000+k (arbitrary integers, same distribution as any sealed seed).
* **Held-out set** = seeds 900000..900000+k, consulted rarely and never tuned on.
* The 8 public seeds are reported for comparability but treated as just another small sample.
* A change is kept only if the gain exceeds ~1 standard error on the tuning set, and I prefer
  changes that are structural (search depth, evaluation shape) over weight fiddling, since
  those are the ones that transfer.
Because the policy must be deterministic and clock-free, CPU control is done with a *node
budget* (a pure function of the board), so the sealed run costs the same as the visible one.

| ver | parent | change | measurement | kept |
|-----|--------|--------|-------------|------|
| v0 | - | baseline: first legal of UP,LEFT,RIGHT,DOWN | (weak, ~1-2k) | - |
| v1 | v0 | full rewrite: 64-bit nibble bitboard + 65536-entry row tables (move/spread/heur), nneonneo-style eval (empty/merges/monotonicity/sum), expectimax with iterative deepening under a deterministic node budget (SOFT=900, HARD=6000), transposition table | single probe seed 12345: score 136960, tile 8192, 5826 moves, 66.2s CPU (budget 225s) | kept |
| v1 | v0 | (same, measured) | **public 8 seeds: mean 111212.5 (se 20477), median 106782, mean max tile 5696 (4x8192, 3x4096, 1x512), mean 4822 moves, mean CPU 65.9s / max 103.9s vs 225s budget, 0 errors** | kept |

### Notes on v1
* Score is essentially a function of survival: for a merge tree, d(score) = d(sum_t t*(log2 t - 1)),
  so final score = P(final board) - 4*(#4-spawns).  With the 10000-move cap the total spawned
  value is at most ~22000, giving a hard ceiling near 265k; empirically score ~= 25 * moves
  survived.  So the objective is survival + concentration, which is exactly what the
  empty/merge/monotonicity evaluation rewards.  No need for a greedy score term.
* CPU headroom remains (66s used of 225s per game).  Raising SOFT_NODES is the obvious next
  lever, but it is the one change that can *zero* the run if the pooled budget is exhausted,
  so it needs a measured CPU check before adoption rather than a blind bump.
* Weakest slice: seed 232003 collapsed early (512 tile, 10672).  Early-game collapses are the
  main remaining loss mode.

### Held-out confirmation (v1, never tuned on)
Seeds 900000..900007: mean **133892** (se 12748), median 142658, mean max tile 7168
(6x8192, 2x4096), mean 5666 moves, mean CPU 73.3s / max 99.2s, 0 errors.
Public 8 = 111212, held-out 8 = 133892 -> the two samples agree inside one standard error, and
nothing in v1 was fitted to any seed (the weights are literature values, the node budget is a
board-only function), so the sealed estimate is the pooled 16-game mean ~122.5k.

### Decision on the remaining CPU headroom (not adopted)
Mean CPU is 70s against a 225s-per-game pooled budget, so ~2-3x more search is affordable in
principle. I did **not** raise SOFT_NODES: exhausting the pooled budget kills the process and
scores every unplayed game zero, and I had no wall-clock left to measure the CPU cost of a
bigger budget on a real suite (better play -> longer games -> superlinear CPU growth). Trading a
validated 2.2x safety margin for an unvalidated single-digit-percent score gain is the wrong
side of that bet. Next step for a future run: SOFT_NODES=1500/HARD=10000, adopt only if measured
mean CPU stays under ~150s/game.
