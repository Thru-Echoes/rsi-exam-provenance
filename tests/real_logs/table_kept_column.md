# 2048 Policy Experiment Log

| Version | Parent | Change | Mean Score | Median | Max Tile | Kept? |
|---------|--------|--------|-----------|--------|----------|-------|
| baseline | - | Starting weak policy | 2060.0 | 1646 | 168 | - |
| v1 | baseline | Heuristic: empty cells + monotonicity + smoothness | 2308.5 | 2052 | 216 | YES |
| v2 | v1 | Improved: corner preference + better monotonicity | 3218.5 | 2880 | 240 | YES |
| v3 | v2 | Depth-2 lookahead: evaluate next move options | 4385.0 | 4376 | 288 | YES |
| v4 | v3 | Depth-3 lookahead: three-move horizon | 4636.0 | 4146 | 352 | YES |
| v5 | v4 | Tuned weights + mergeability metric | 1936.0 | 1886 | 184 | NO (reverted) |
| v6 | v4 | Depth-4 lookahead | 3337.0 | 2718 | 224 | NO (reverted) |
| v7 | v4 | Added isolation penalty | 3583.5 | 3980 | 224 | NO (reverted) |
| v8 | v4 | Adaptive position scoring | 4503.0 | 4858 | 304 | NO (reverted) |
| v9 | v4 | Adaptive strategy switching based on board state | 5699.5 | 6134 | 400 | YES |
| v10 | v9 | Refined strategy with max connectivity metric | 5921.5 | 5030 | 464 | YES |
| v11 | v10 | Added merge potential heuristic | 5939.5 | 5544 | 448 | YES |
| v12 | v11 | Increased merge potential weights | 6148.5 | 5296 | 448 | YES |
| v13 | v12 | Further increased merge potential weights | 6639.5 | 5962 | 480 | YES |
| v14 | v13 | Much higher merge potential weights (3.0-2.0) | 8729.0 | 9730 | 704 | YES |
| v15 | v14 | Even higher merge weights (4.0-3.0) | 6402.5 | 4396 | 416 | NO |
| v15b | v14 | Mid-range merge weights (3.5-2.5) | 7167.0 | 6806 | 512 | NO |
| v16 | v14 | Changed merge formula (val*4) | 5224.5 | 5176 | 384 | NO |
| v17 | v14 | Increased lookahead bonus 0.4→0.5 | 6197.0 | 4954 | 416 | NO |
| v18 | v14 | Reduced merge weights (2.5-1.5) | 5000.5 | 4886 | 384 | NO |

**Final version: v14**
- Mean score: 8729.0
- Median score: 9730.0
- Max tile: 704
- Strategy: Adaptive weights + merge potential heuristic + depth-3 lookahead
- 4.2x improvement over baseline (2060 → 8729)
