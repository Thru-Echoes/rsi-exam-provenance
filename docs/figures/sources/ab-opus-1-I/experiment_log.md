## v0
- parent: none
- status: baseline
- change: inherited starter policy, unchanged
- method tree sha256: 72267d6fb29d7742042559306b4a3440d7b484a7d87f2173ec4e81c1bf676b85
- score: 2060 mean over the public suite (median 1646; mean max tile 168; cpu s per game 0; valid fraction 1; max move s 0)
## v1
- parent: v0
- status: kept
- change: bitboard expectimax depth 2 with nneonneo row heuristic
- method tree sha256: 7599b5b49efcf483d95563390768a7fdcba76948c38805a1d601e7ccd6870c89
- score: 38974.5 mean over the public suite (median 28938; mean max tile 2432; cpu s per game 0.3; valid fraction 1; max move s 0.0004)
- gate: keep, confirmed on fresh seeds (clears; estimate +32800.0, interval [21510.0, 44029.0], minimum effect 51.5, 8 seeds)
- agent proposed: kept
## v2
- parent: v1
- status: reverted
- change: depth-3 expectimax with 1e-4 probability cutoff and transposition cache
- method tree sha256: ab77e396f183474e25763e39c44deff3b6e0564a8cb9f86b47c5484db2a6f8dd
- score: 48115 mean over the public suite (median 41198; mean max tile 2816; cpu s per game 8.9; valid fraction 1; max move s 0.0193)
- gate: not consulted (the agent reverted)
- agent proposed: reverted
- agent note: real +9k but 8-seed noise cannot confirm; superseded by adaptive-depth candidate
## v3
- parent: v1
- status: kept
- change: tiered depth: 2 when >5 empties, 3 when 3-5, 4 when <=2; 4-spawns only at first chance layer
- method tree sha256: db19d6b2c0cbc5034a365187dbe76f6bacb0e34ce2e76e6b49ef0a82fddb0dcf
- score: 89317.5 mean over the public suite (median 80782; mean max tile 5120; cpu s per game 13.5; valid fraction 1; max move s 0.0385)
- gate: keep, confirmed on fresh seeds (clears; estimate +57097.0, interval [28839.5, 88737.0], minimum effect 974.4, 8 seeds)
- agent proposed: kept
