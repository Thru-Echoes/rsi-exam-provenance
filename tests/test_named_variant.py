"""Keep the optional named source compatible with the canonical review source."""
import argparse
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "ara/nanda-2026/submission"
spec = importlib.util.spec_from_file_location(
    "named_variant", ROOT / "ara/nanda-2026/src/execution/build_named_variant.py")
named = importlib.util.module_from_spec(spec)
spec.loader.exec_module(named)


class NamedVariantTests(unittest.TestCase):
    def test_canonical_source_generates_both_orders_without_release_claim(self):
        canonical = (SUBMISSION / "main.tex").read_text()
        for first in ("muellerklein", "tang"):
            with self.subTest(first=first), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                (folder / "main.tex").write_text(canonical)
                args = argparse.Namespace(a1_affil="Test University", a1_email="a@example.invalid",
                    a2_affil="Test Institute", a2_email="b@example.invalid", first=first)
                with patch.object(named, "SUBMISSION", folder):
                    result = named.build(args).read_text()
                self.assertNotIn("Anonymous Authors", result)
                self.assertNotIn("withheld for review", result)
                self.assertNotIn("v0.4.0", result)
                self.assertIn("https://github.com/chenmingtang830/proofpress", result)
                self.assertIn("7fad672", result)
                self.assertIn("These authors contributed equally", result)
                self.assertEqual(first == "muellerklein",
                    result.index("Oliver Muellerklein") < result.index("Chenming Tang"))
                self.assertEqual(canonical, (folder / "main.tex").read_text())

    def test_changed_canonical_reference_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "main.tex").write_text(
                (SUBMISSION / "main.tex").read_text().replace(named.ANON_TRACE, "changed reference"))
            with patch.object(named, "SUBMISSION", folder), self.assertRaises(SystemExit):
                named.build(argparse.Namespace())
            self.assertFalse((folder / "main-named.tex").exists())


if __name__ == "__main__":
    unittest.main()
