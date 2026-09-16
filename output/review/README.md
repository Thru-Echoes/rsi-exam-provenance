# Frozen ARA review bundle

[Download the review ZIP](nanda-2026-ara-review-final.zip?raw=true), then open `START_HERE.md` and `paper.pdf` inside it.

- Paper: **Auditable Keeps: Semantic Verification of Self-Improving Agent Decisions**.
- Frozen scientific/source revision: `c7d433c6c3d160b1fa5e6f173a63df63d116c6af`.
- Archive size: 3,125,966 bytes.
- SHA-256: `048b2ce1b040844d82ec9b0d0159b1cac6173d0082ba850c3c00571865efa7e3`.
- Contents: three-page IEEE PDF, browsable repository-backed ARA, claims/experiments, synthetic fault results, bounded historical case dossier, content manifest, and offline-cloneable Git bundle.

This archive deliberately remains the exact reviewed snapshot. The later PR distribution commit adds this ZIP and index without changing its source revision. Do not treat the archive's earlier revision as a stale or missing manuscript update, and do not recursively repackage the archive into itself.

For online review, start at [ARA manifest](../../ara/nanda-2026/PAPER.md), [review guide](../../ara/nanda-2026/REVIEW.md), and [current PDF](../pdf/nanda-2026-track3-ieee-review.pdf). The older working-paper PDF is superseded.

The recorded full suite ran 425 tests with two skips. The final archive was unpacked and its Git bundle cloned into a clean directory; all 19 focused checks, pinned historical-result check, 136 content bindings, and readable-manuscript synchronization passed. Reproduction commands are inside `START_HERE.md`.

Research limits remain explicit: nine faults are authored synthetic cases, not nine real incidents; retained RSI records lack original snapshots/per-seed evidence; the legacy Harvey illustration uses asymmetric external ledger information and is not a current-verifier evaluation. No official ARA certification or conference submission is implied. The complete source/history is not anonymized.
