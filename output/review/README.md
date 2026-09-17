# Frozen ARA review bundle

## Current framework-first revision — 2026-09-17

Paper: **Capture, Verify, Govern: Decision Provenance for Agent Artifact Handoffs**.
Four IEEE pages including references. Framework design is the main contribution;
RSI-Exam instantiates Verify. The unchanged 12-package characterization supports
C05/C06. C10/E07 adds a pinned local conversion/intake demonstration, not a complete
human-approved agent handoff. See [ARA manifest](../../ara/nanda-2026/PAPER.md)
and [review guide](../../ara/nanda-2026/REVIEW.md).

The previous public source was c3d94b6790055fe60783137f5c2eaa4aed620ea8.
The earlier local-only distribution commit 8e8136054ab016ecf493404edfb921d082c0a7e3
and its archive are preserved in the original checkout. This revision starts from
the public source in a separate worktree; no unpublished binary/history is overwritten.

Source freeze precedes distribution packaging. The current PDF and ARA source are
the review authority; final archive names, hashes and clean-clone results are added
here in the distribution record. Never interpret a historical ZIP as this paper.

Review materials go to existing PR #40, not merge, deployment or conference submission.
The anonymous author block is not full anonymization of named systems or public history.

## Previous frozen delivery — 2026-09-16 (superseded)

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
