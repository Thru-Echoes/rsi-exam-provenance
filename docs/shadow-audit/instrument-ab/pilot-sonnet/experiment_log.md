## v0
- parent: none
- status: baseline
- change: inherited starter policy, unchanged
- method tree sha256: 72267d6fb29d7742042559306b4a3440d7b484a7d87f2173ec4e81c1bf676b85
- score: 2060 mean over the public suite (median 1646; mean max tile 168; cpu s per game 0; valid fraction 1; max move s 0.0001)
## v1
- parent: v0
- status: kept
- change: expectimax with monotonicity/smoothness/empty/corner heuristic
- method tree sha256: 65cf34fe6bc45114f1222e496bba862035ce24efa8729abbd0f0476c2ba714e8
- score: 15177.5 mean over the public suite (median 12536; mean max tile 1024; cpu s per game 12; valid fraction 1; max move s 0.091)
- gate: keep, confirmed on fresh seeds (clears; estimate +15833.0, interval [11162.0, 20545.5], minimum effect 51.5, 8 seeds)
- agent proposed: kept
