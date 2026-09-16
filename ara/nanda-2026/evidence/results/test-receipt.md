# Verification receipt — working paper branch

**Run date:** 2026-09-15 America/Los_Angeles

**Branch:** `codex/nanda-2026-ara`

**Source base:** `727b9b821d7814d7467a29c1e740ce92eea7e219`

## Unit tests

**Command:** `python3 -m unittest discover -s tests -t .`

**Result:** 420 tests ran in 60.038 seconds; 2 skipped; 0 failures; 0 errors.

## Static analysis

**Command:** `npx --yes pyright`

**Result:** 0 errors, 1 warning. The warning states that optional test import `jsonschema` could not be resolved from source at `tests/test_rsi_exam_provenance.py:104`. The command exited successfully.

## ARA structural and cross-layer checks

**Command:** `python3 -m unittest tests.test_nanda_ara tests.test_paper_results -v`

**Result:** Covered by the 420-test full-suite run. Required layers and files are present; claim and experiment cards contain their required fields; claim-to-experiment links are bidirectional; exploration nodes are unique, typed, and source-bounded; the Markdown and IEEEtran manuscripts carry the generated claim boundary; the review source is anonymous and contains no author-controlled artifact link; the result generator reproduces the 3/7 direction count and 18/20 record yield; generated files match.

The working epistemic review is `level2_report.json`: tier `Sound`, mean 4.0, no critical findings, one major evidence-completeness finding. These are local ARA-compatible checks, not an official ARA Seal result; the official `ara` CLI was not installed or run.

## Layout proof

The working anonymous PDF was generated with the bundled ReportLab runtime, reported as two US-letter pages, rendered to PNG, and visually inspected page by page for clipping, overlap, table legibility, references, page numbers, and column flow. It is an IEEE-style layout proof, not an official IEEEtran build.

## IEEEtran review PDF

**Build:** `SOURCE_DATE_EPOCH=1789526400 tectonic --outdir output/pdf --keep-logs ara/nanda-2026/submission/main.tex`

**Result:** The anonymous IEEEtran review PDF is 3 US-letter pages. All fonts reported by `pdffonts` are embedded and subset. `pdfinfo` reports no encryption, forms, JavaScript, or suspect content. The TeX log contains no overfull boxes, underfull boxes, LaTeX errors, or emergency stops. Poppler text extraction finds the title, anonymous author marker, Sections II--V, References, and the total row `10 / 3 / 7`.

The final PDF was rendered at 150 DPI and visually inspected page by page. No clipping, overlap, illegible table content, orphaned heading, or broken reference flow was observed. Two independent builds with the fixed source epoch and the checked-in output all produced SHA-256 `eafc09e3e50dd7cc7343118fa773aa929826cc033f10c1fad274543528fd9c63`.

This is a working-branch receipt, not the submission freeze receipt. Refresh it after Opus source reconciliation and from the final tagged commit.
