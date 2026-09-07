"""The record producer's experiment-log reader, against logs it did not author.

The fixtures under ``tests/real_logs/`` are verbatim experiment logs from three real
``game2048_policy_search`` rollouts. They are the point of this suite: a log written to match the
parser proves nothing about the parser, and every defect these tests guard against survived a full
green suite of fixture-based tests because every fixture log was written that way.

The three shapes, all produced by the same program text and the same agent model:

- ``prose_inline_disposition.md``  a list item carrying its disposition on the same line
- ``table_kept_column.md``         a markdown table with a ``Kept?`` column of ``YES``/``NO``
- ``sectioned_status_line.md``     one heading per version with a ``Status:`` line below it

Run: ``python3 -m unittest discover -s tests -t .``
"""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOGS = Path(__file__).resolve().parent / "real_logs"


def load_producer():
    """Import build_capsule by path; ``profile`` shadows a standard-library module."""
    spec = importlib.util.spec_from_file_location(
        "build_capsule_under_test", REPO / "profile" / "build_capsule.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bc = load_producer()


def read(name: str) -> list[str]:
    return (LOGS / name).read_text(encoding="utf-8").splitlines()


def materialize(case: unittest.TestCase) -> tuple[Path, Path]:
    """Copy the golden fixture into a temporary directory. Side effect: creates that copy."""
    temp = tempfile.TemporaryDirectory()
    case.addCleanup(temp.cleanup)
    root = Path(temp.name)
    shutil.copytree(REPO / "fixtures/valid", root, dirs_exist_ok=True)
    return root / "job", root / "task"


def status_of(lines: list[str], version_id: str) -> str:
    line_no, block = bc.get_version_blocks(lines)[version_id]
    return bc.get_status(block, version_id, bc.get_table_status(lines, line_no - 1))


class DispositionIsReadFromALineTheVersionOwns(unittest.TestCase):
    """The regression that matters most: a wrong record rather than a refused one."""

    def test_a_passing_mention_does_not_donate_its_disposition(self):
        # In this log v6's own status line reads "Status: kept (best before v7)". That line is the
        # first in the file to contain the token v7, and it contains the word "kept". A reader that
        # classifies a version from the first line naming it therefore recorded v7 as kept on the
        # strength of v6's status, while v7's real status -- "final submission" -- was never read.
        lines = read("sectioned_status_line.md")
        self.assertIn("Status: kept (best before v7)", "\n".join(lines))
        self.assertEqual(status_of(lines, "v7"), "submitted")
        self.assertEqual(status_of(lines, "v6"), "kept")

    def test_end_to_end_a_donated_disposition_does_not_reach_the_record(self):
        # The same defect stated against the public API, so this guard survives any refactor of the
        # reader's internals. v1's own line mentions v2 in passing while carrying v1's disposition,
        # "kept". A reader keyed on first mention hands that word to v2, and the record then reports
        # a reverted version as kept. v2 is deliberately not the submitted version: the submitted
        # one has its status overwritten later, which would mask the defect.
        job, task = materialize(self)
        log = job / "artifacts/app/methods/experiment_log.md"
        log.write_text(
            "# Experiment log\n\n"
            "- v1 (parent: none): corner-priority move order. score: 1180. kept,"
            " later superseded by v2\n"
            "- v2 (parent: v1): depth-2 lookahead, exceeded the per-move budget."
            " score: 940. reverted\n"
            "- v3 (parent: v1): tuned corner weights on the public suite. score: 1560. kept\n",
            encoding="utf-8")
        capsule = bc.build_capsule(job, task, "0.1@bc36dadb405b", "fixture-rollout-001",
                                   None, None, [])
        status = {v["version_id"]: v["status"] for v in capsule["versions"]}
        self.assertEqual(status["v1"], "kept")
        self.assertEqual(status["v2"], "reverted")

    def test_a_mention_line_declares_nothing(self):
        self.assertIsNone(bc.get_declaration("Status: kept (best before v7)"))
        self.assertIsNone(bc.get_declaration("  - Mean score: 6816 (+231% vs v0)"))

    def test_headings_list_items_and_table_rows_declare(self):
        self.assertEqual(bc.get_declaration("## v1"), "v1")
        self.assertEqual(bc.get_declaration("## v7 - Final Best"), "v7")
        self.assertEqual(bc.get_declaration("- **v1**: Heuristic board evaluation"), "v1")
        self.assertEqual(bc.get_declaration("| v9 | v4 | Adaptive strategy | 5699.5 | YES |"), "v9")
        self.assertIsNone(bc.get_declaration("| Version | Parent | Change | Kept? |"))
        self.assertIsNone(bc.get_declaration("|---------|--------|--------|-------|"))


class EveryRealLogShapeClassifies(unittest.TestCase):
    """Each shape below refused to classify, or misclassified, under a single-line reader."""

    def test_prose_with_the_disposition_inline(self):
        lines = read("prose_inline_disposition.md")
        self.assertEqual(status_of(lines, "v1"), "kept")
        self.assertEqual(status_of(lines, "v2"), "reverted")

    def test_table_with_a_kept_column(self):
        # The disposition is YES or NO in a column the header names; neither word is a keyword.
        lines = read("table_kept_column.md")
        for version_id in ("v1", "v2", "v3", "v4", "v9", "v10", "v11", "v12", "v13", "v14"):
            self.assertEqual(status_of(lines, version_id), "kept", version_id)
        self.assertEqual(status_of(lines, "v5"), "reverted")
        self.assertEqual(status_of(lines, "v8"), "reverted")

    def test_sections_with_the_disposition_below_the_heading(self):
        lines = read("sectioned_status_line.md")
        expected = {"v0": "baseline", "v1": "kept", "v2": "kept", "v3": "kept",
                    "v4": "reverted", "v5": "kept", "v6": "kept", "v7": "submitted"}
        self.assertEqual({v: status_of(lines, v) for v in expected}, expected)

    def test_an_unclassifiable_block_still_raises(self):
        block = ["## v3", "Change: tried something", "Metrics: mean_score=10"]
        with self.assertRaises(bc.ProducerError) as caught:
            bc.get_status(block, "v3")
        self.assertIn("log_unclassifiable:v3", str(caught.exception))


class LineageIsNotInventedFromProse(unittest.TestCase):
    def test_a_score_comparison_is_not_a_parent(self):
        # "+231% vs v0" cites v0 to explain a delta; it does not declare v0 as a parent.
        lines = read("prose_inline_disposition.md")
        _, block = bc.get_version_blocks(lines)["v1"]
        self.assertIn("vs v0", "\n".join(block))
        self.assertEqual(bc.get_block_parents(block, "v1"), [])

    def test_a_labelled_parent_line_is_read(self):
        lines = read("sectioned_status_line.md")
        _, block = bc.get_version_blocks(lines)["v2"]
        self.assertEqual(bc.get_block_parents(block, "v2"), ["v1"])

    def test_a_table_parent_column_is_read(self):
        lines = read("table_kept_column.md")
        _, block = bc.get_version_blocks(lines)["v9"]
        self.assertEqual(bc.get_block_parents(block, "v9"), ["v4"])


class VisibleScoreComesFromTheBlock(unittest.TestCase):
    def test_a_score_below_the_declaration_is_found(self):
        lines = read("sectioned_status_line.md")
        _, block = bc.get_version_blocks(lines)["v1"]
        visible = bc.get_block_visible(block)
        assert visible is not None
        self.assertEqual(visible["score"], 8838.5)
        self.assertEqual(visible["recorded_in"], "experiment_log")

    def test_a_block_with_no_score_records_none(self):
        self.assertIsNone(bc.get_block_visible(["## v1", "Change: nothing measured"]))


class BlocksAreBoundedAndDeterministic(unittest.TestCase):
    def test_a_block_stops_at_the_next_declaration(self):
        lines = read("sectioned_status_line.md")
        _, block = bc.get_version_blocks(lines)["v1"]
        self.assertTrue(block[0].startswith("## v1"))
        self.assertNotIn("## v2", "\n".join(block))

    def test_a_redeclared_version_keeps_its_first_block(self):
        lines = ["## v1", "Status: kept", "## v2", "Status: reverted", "## v1", "Status: reverted"]
        line_no, block = bc.get_version_blocks(lines)["v1"]
        self.assertEqual(line_no, 1)
        self.assertEqual(bc.get_status(block, "v1"), "kept")


class UnnameableSnapshotsAreRefused(unittest.TestCase):
    """A snapshot the producer cannot name is refused, never dropped without a word."""

    def test_a_directory_outside_the_version_naming_scheme_raises(self):
        # A real rollout wrote versions/v5_final and versions/v6_best beside its numbered
        # snapshots. Those names fall outside ^v[0-9]+$, so they were filtered out before any
        # check ran and the record simply omitted them while reporting itself complete.
        with tempfile.TemporaryDirectory() as tmp:
            versions = Path(tmp) / "versions"
            (versions / "v1").mkdir(parents=True)
            (versions / "v6_best").mkdir()
            offenders = sorted(child.name for child in versions.iterdir()
                               if child.is_dir() and not bc.VERSION_DIR.fullmatch(child.name))
            self.assertEqual(offenders, ["v6_best"])

    def test_the_producer_refuses_such_a_job_directory(self):
        # End to end on the golden fixture, so the refusal is proved against a job directory that
        # is otherwise complete and would build a record.
        job, task = materialize(self)
        (job / "artifacts/app/methods/versions/v6_best").mkdir()
        with self.assertRaises(bc.ProducerError) as caught:
            bc.build_capsule(job, task, "0.1@bc36dadb405b", "fixture-rollout-001",
                             None, None, [])
        self.assertIn("unrecognized_snapshot:v6_best", str(caught.exception))

    def test_the_same_fixture_builds_without_it(self):
        job, task = materialize(self)
        capsule = bc.build_capsule(job, task, "0.1@bc36dadb405b", "fixture-rollout-001",
                                   None, None, [])
        self.assertTrue(capsule["versions"])



if __name__ == "__main__":
    unittest.main()
