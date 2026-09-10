# Calibration of the estimate-aware planning rule at the instrument's bounds

Written and committed before the runs (2026-09-09). Synthetic paired deltas; not evidence about any rollout. The
gate's own bootstrap and planning code run at the sample sizes the instrument sees (`gate/calibrate.py`).

**Question.** Under the estimate-aware rule with the instrument's bounds (floor 8, cap 16, level 0.9, eight screening
seeds, minimum effect 51.5 in score units, 2.5 percent of the starter's public-seed mean), how often does the gate
finally keep a candidate whose true effect is zero or exactly the minimum effect (a false keep), and how often does it
keep a real improvement, across the spreads the real rollouts showed?

**Cells.** Rule `estimate-aware`; floor and cap (8, 16) and, for comparison with the replay configurations, (16, 64);
distributions `normal`, `skewed`, `heavy`; selection best-of-1 and best-of-3 (the optimistic selection an agent
performs on reused public seeds); 2000 trials per cell, seed 20260910, 2000 bootstrap resamples. Haiku scale:
standard deviation 1000, 2500 and 5000 (the development and campaign cohorts' screening spreads ran from about
1700 to 5300), true effects 0, 1, 2, 5 and 20 times the minimum effect. Opus scale: standard deviation 50000 (the two
large Opus improvements had spreads near 49000 and 62000 with estimates near 1600 times the minimum effect), true
effects 0, 1, 100, 1000 and 2000 times the minimum effect. Rare-catastrophe mixtures at the Haiku scale (spread 1000,
each delta replaced with probability 0.1 by a collapse of minus 900, and separately minus 9000), both bound pairs,
best-of-1, at the same true effects, because the real failures seen so far (illegal moves, an exhausted budget) are
collapses on some seeds rather than spread. The accepted rule (`current`) at the Haiku scale, spread 2500, both bound
pairs, best-of-1, as the reference the audit tables already describe.

**What is reported beside the criterion.** The keep probability at every true effect in every cell, so the rule's
power at worthwhile effects (5 and 20 minimum effects at the Haiku scale; 100 and 1000 at the Opus scale) is on the
record; the plan expects it to be small at the Haiku scale (the instrument keeps little there) and large at the Opus
scale, and it is reported, not gated, because a power requirement is the operator's decision.

**Criterion, fixed before the runs.** For every best-of-1 and best-of-3 cell at true effects 0 and 1 times the
minimum effect, the false-keep probability is at most 0.10 and its exact one-sided 95 percent binomial upper bound
(the same bound for every count, including zero) is at most 0.125. Each bound is marginal to its cell; no simultaneous
coverage across cells is claimed. The criterion is per keep proposal: an agent may propose repeatedly and select on
reused public seeds beyond three candidates, so no rollout-level false-keep control is claimed. The 200-trial sample
run during the plan's own verification is exploratory and is not part of this result. If the criterion is not met
the profile is not changed by this plan; the operator decides.

**Profile lock.** Floor 8, cap 16, level 0.9, eight screening seeds, the minimum-effect fraction 0.025 and the
estimate-aware rule are final for every comparison trial once these runs start; a change to any of them invalidates
this calibration and needs a new pre-registration and run before another trial.

**What is reported.** Every table the tool prints, its JSON sidecar, and the criterion check's table, all committed.
Nothing here is a rate observed on any rollout, and nothing here tunes the rule to the rollouts: the sealed
retrospective is never an input.
