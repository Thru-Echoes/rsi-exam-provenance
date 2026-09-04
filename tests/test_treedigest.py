"""Tests for gate/treedigest.py: cache-free method-tree digests under the grader's rules."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import treedigest  # noqa: E402


def _load_producer():
    spec = importlib.util.spec_from_file_location("rsi_exam_producer", REPO / "profile" / "build_capsule.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMethodTreeDigest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "v3"
        (self.root / "sub").mkdir(parents=True)
        (self.root / "policy.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "sub" / "helper.py").write_text("y = 2\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_digest_is_sha256_over_sorted_file_lines(self) -> None:
        lines = ""
        for rel in ("policy.py", "sub/helper.py"):
            lines += f"{hashlib.sha256((self.root / rel).read_bytes()).hexdigest()}  {rel}\n"
        self.assertEqual(treedigest.method_tree_sha256(self.root), hashlib.sha256(lines.encode("utf-8")).hexdigest())
        self.assertEqual(treedigest.method_files(self.root), ["policy.py", "sub/helper.py"])

    def test_bytecode_caches_do_not_change_the_digest(self) -> None:
        before = treedigest.method_tree_sha256(self.root)
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "policy.cpython-312.pyc").write_bytes(b"\x00\x01")
        (self.root / "sub" / "helper.pyo").write_bytes(b"\x02")
        (self.root / "sub" / "__pycache__").mkdir()
        (self.root / "sub" / "__pycache__" / "helper.cpython-313.pyc").write_bytes(b"\x03")
        self.assertEqual(treedigest.method_tree_sha256(self.root), before)

    def test_a_source_change_changes_the_digest(self) -> None:
        before = treedigest.method_tree_sha256(self.root)
        (self.root / "policy.py").write_text("x = 2\n", encoding="utf-8")
        self.assertNotEqual(treedigest.method_tree_sha256(self.root), before)

    def test_matches_the_producer_full_tree_digest_when_there_are_no_caches(self) -> None:
        producer = _load_producer()
        self.assertEqual(treedigest.method_tree_sha256(self.root), producer.tree_digest(self.root))

    def test_non_python_files_are_refused_as_the_grader_refuses_them(self) -> None:
        for name in ("notes.json", "weights", "sub/data.txt"):
            with self.subTest(name=name):
                target = self.root / name
                target.write_text("x", encoding="utf-8")
                with self.assertRaises(treedigest.TreeDigestError):
                    treedigest.method_tree_sha256(self.root)
                target.unlink()
        self.assertEqual(treedigest.method_files(self.root), ["policy.py", "sub/helper.py"])

    def test_symlinks_are_refused_even_under_excluded_names(self) -> None:
        os.symlink(self.root / "policy.py", self.root / "link.py")
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(self.root)
        (self.root / "link.py").unlink()
        os.symlink(self.root / "policy.py", self.root / "cache.pyc")
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(self.root)

    def test_missing_and_empty_trees_are_refused(self) -> None:
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(self.root / "missing")
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(empty)
        only_cache = Path(self.tmp.name) / "only_cache"
        (only_cache / "__pycache__").mkdir(parents=True)
        (only_cache / "__pycache__" / "a.pyc").write_bytes(b"\x00")
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(only_cache)


if __name__ == "__main__":
    unittest.main()
