# Verification receipt — scaffold branch

**Run date:** 2026-09-15 America/Los_Angeles

**Branch:** `codex/nanda-2026-ara`

**Source base:** `727b9b821d7814d7467a29c1e740ce92eea7e219`

## Unit tests

**Command:** `python3 -m unittest discover -s tests -t .`

**Result:** 410 tests ran in 57.167 seconds; 2 skipped; 0 failures; 0 errors.

## Static analysis

**Command:** `npx --yes pyright`

**Result:** 0 errors, 1 warning. The warning states that optional test import `jsonschema` could not be resolved from source at `tests/test_rsi_exam_provenance.py:104`. The command exited successfully.

## ARA scaffold checks

The required directories and files were present and non-trivial; required frontmatter and layer-index fields were present; JSON and YAML parsed; claim quotations matched their cited repository line ranges; exploration-tree node types and required fields passed the ARA Level 1 structural rules used by this draft; and `git diff --check` passed.

This is a scaffold receipt, not the submission freeze receipt. Refresh it after source reconciliation and from the final tagged commit.
