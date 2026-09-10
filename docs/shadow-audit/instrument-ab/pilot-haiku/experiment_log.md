## v0
- parent: none
- status: baseline
- change: inherited starter policy, unchanged
- method tree sha256: 72267d6fb29d7742042559306b4a3440d7b484a7d87f2173ec4e81c1bf676b85
- score: 2060 mean over the public suite (median 1646; mean max tile 168; cpu s per game 0; valid fraction 1; max move s 0)
## v1
- parent: v0
- status: reverted
- change: v1: heuristic-based move evaluator
- method tree sha256: fa1b9a1890a234afeb4b99bc0170eb9c7be77d1353a86e6ca16163979dcea657
- score: 2222 mean over the public suite (median 1930; mean max tile 224; cpu s per game 0; valid fraction 1; max move s 0.0002)
- gate: revert at screening (inconclusive; exploratory: the plan needs 2046 fresh seeds and the cap is 16; estimate +162.0, interval [-578.5, 1072.5], minimum effect 51.5, 8 seeds)
- agent proposed: kept (overruled)
## v2
- parent: v0
- status: kept
- change: v2: lookahead with revised heuristics
- method tree sha256: e6936d289a7bb5db8ab12091e0ff9752be8a75cd9789ad066411ca564fc8428e
- score: 4838.5 mean over the public suite (median 4462; mean max tile 320; cpu s per game 0.1; valid fraction 1; max move s 0.0004)
- gate: keep, confirmed on fresh seeds (clears; estimate +2503.2, interval [947.2, 4118.0], minimum effect 51.5, 10 seeds)
- agent proposed: kept
## v3
- parent: v2
- status: reverted
- change: v3: refined heuristics and monotonicity
- method tree sha256: dee5c3bb8d600add0d90ef15e43ea73e06f37c9beded04372f33c61e483617de
- score: 5938 mean over the public suite (median 6218; mean max tile 464; cpu s per game 0.1; valid fraction 1; max move s 0.0023)
- gate: not consulted (the agent reverted)
- agent proposed: reverted
- agent note: noisy improvement, interval includes zero
