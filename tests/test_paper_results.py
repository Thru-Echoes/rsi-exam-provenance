"""Tests for the NANDA paper's source-bound result generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ara" / "nanda-2026" / "src" / "execution" / "build_paper_results.py"
SPEC = importlib.util.spec_from_file_location("build_paper_results", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PaperResultsTests(unittest.TestCase):
    def setUp(self):
        self.result = MODULE.build(
            "727b9b821d7814d7467a29c1e740ce92eea7e219",
            verify_revision=True,
        )

    def test_primary_block_counts_are_recomputed(self):
        summary = self.result["primary_summary"]
        self.assertEqual(summary["blocks"], 10)
        self.assertEqual(summary["favors_instrument"], 3)
        self.assertEqual(summary["favors_helper"], 7)
        self.assertEqual(summary["ties"], 0)
        self.assertEqual(summary["by_stage"]["opus"]["mean_precision"],
                         "approximate_from_rounded_inputs")

    def test_record_yield_uses_all_started_trials(self):
        record_yield = self.result["record_yield"]
        self.assertEqual(record_yield["trials"], 20)
        self.assertEqual(record_yield["verified_records"], 18)
        self.assertEqual(record_yield["arms"]["instrument"],
                         {"trials": 10, "verified_records": 9})
        self.assertEqual(record_yield["arms"]["helper"],
                         {"trials": 10, "verified_records": 9})
        self.assertEqual(
            {failure["rollout"] for failure in record_yield["failures"]},
            {"ab-haiku-4-H-CkZZrtb", "ab-sonnet-1-I-xtakhda"},
        )

    def test_markdown_carries_the_claim_boundary(self):
        rendered = MODULE.render_markdown(self.result)
        self.assertIn("no rate, efficacy, or significance claim", rendered)
        self.assertIn("Opus comes from a committed pre-probe summary", rendered)
        self.assertIn("18 verified records from 20 started trials", rendered)


if __name__ == "__main__":
    unittest.main()
