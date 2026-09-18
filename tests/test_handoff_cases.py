"""Regression checks for bounded retained-record inspection."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "studies/handoff-case-review/review_cases.py"
spec = importlib.util.spec_from_file_location("handoff_review", PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class HandoffCaseTests(unittest.TestCase):
    def test_saved_report_reproduces(self):
        expected = json.loads(PATH.with_name("case-results.json").read_text())
        self.assertEqual(expected, module.inspect(None))

    def test_boundaries_and_branch(self):
        report = module.inspect(None)
        rsi = report["rsi_case"]
        self.assertTrue(rsi["log_binding_matches"])
        self.assertTrue(rsi["v3_branches_from_v1"])
        self.assertTrue(rsi["v2_is_reverted_without_gate_decision"])
        self.assertEqual(9140.5, rsi["v2_reported_mean_gain_over_v1"])
        self.assertFalse(rsi["can_recompute_per_seed_statistics"])
        self.assertFalse(rsi["can_verify_original_snapshot_bytes"])
        harvey = report["harvey_case"]
        self.assertEqual((3, 0), (harvey["ordinary_unsafe_count"], harvey["proofpress_unsafe_count"]))
        self.assertEqual(9, harvey["full_pilot_stress_pairs"])
        self.assertFalse(harvey["runtime_reproduction"])
        self.assertFalse(harvey["same_implementation_as_rsi"])
