"""Tests for gate/restore.py: restoring main/ from a snapshot without nesting."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import restore  # noqa: E402
import treedigest  # noqa: E402
from tests.gate_fixtures import write_tree  # noqa: E402


class TestRestore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_tree(self.methods / "main", "def choose_move(board):\n    return 'LEFT'\n")
        (self.methods / "main" / "extra.py").write_text("z = 3\n", encoding="utf-8")
        write_tree(self.methods / "versions" / "v1", "def choose_move(board):\n    return 'UP'\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_restore_replaces_main_with_the_snapshot_and_returns_its_digest(self) -> None:
        expected = treedigest.method_tree_sha256(self.methods / "versions" / "v1")
        self.assertEqual(restore.main(["--methods", str(self.methods), "--version", "v1"]), 0)
        self.assertEqual(treedigest.method_tree_sha256(self.methods / "main"), expected)
        self.assertFalse((self.methods / "main" / "extra.py").exists())
        self.assertFalse((self.methods / "main" / "v1").exists(), "the snapshot must not be nested inside main/")
        self.assertFalse((self.methods / "main.restoring").exists())

    def test_caches_are_not_copied_and_a_stale_staging_dir_is_removed(self) -> None:
        (self.methods / "versions" / "v1" / "__pycache__").mkdir()
        (self.methods / "versions" / "v1" / "__pycache__" / "policy.cpython-312.pyc").write_bytes(b"\x00")
        (self.methods / "main.restoring").mkdir()
        (self.methods / "main.restoring" / "junk.py").write_text("j = 1\n", encoding="utf-8")
        self.assertEqual(restore.restore(self.methods, "v1"), treedigest.method_tree_sha256(self.methods / "versions" / "v1"))
        self.assertFalse((self.methods / "main" / "__pycache__").exists())
        self.assertFalse((self.methods / "main" / "junk.py").exists())

    def test_missing_or_invalid_snapshots_are_refused_and_main_is_untouched(self) -> None:
        before = treedigest.method_tree_sha256(self.methods / "main")
        self.assertEqual(restore.main(["--methods", str(self.methods), "--version", "v9"]), 2)
        (self.methods / "versions" / "v1" / "notes.json").write_text("{}", encoding="utf-8")
        self.assertEqual(restore.main(["--methods", str(self.methods), "--version", "v1"]), 2)
        self.assertEqual(treedigest.method_tree_sha256(self.methods / "main"), before)


class TestRestoreVersionArgument(unittest.TestCase):
    def test_version_must_be_a_single_path_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            methods = Path(tmp) / "methods"
            write_tree(methods / "main", "x = 1\n")
            write_tree(Path(tmp) / "outside", "def choose_move(board):\n    return 'UP'\n")
            for bad in ("../../outside", "v1/..", "", "."):
                with self.subTest(version=bad):
                    self.assertEqual(restore.main(["--methods", str(methods), "--version", bad]), 2)
            self.assertEqual((methods / "main" / "policy.py").read_text(encoding="utf-8"), "x = 1\n")


if __name__ == "__main__":
    unittest.main()
