"""Reproduce the primary study, including its disclosed failed expectation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DecisionAuditReproductionTests(unittest.TestCase):
    def test_exact_recorded_cases_reproduce(self):
        saved = json.loads((ROOT / "studies/decision-audit/fault-results.json").read_text())
        run = subprocess.run([sys.executable, "studies/decision-audit/run_faults.py"],
                             cwd=ROOT, text=True, capture_output=True, check=True)
        actual = json.loads(run.stdout)
        for field in ("cases", "fixture_sha256", "manifest", "source_sha256",
                      "all_expectations_met"):
            self.assertEqual(saved[field], actual[field], field)
        for path, expected in saved["source_sha256"].items():
            self.assertEqual(expected, hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), path)
        faults = [case for case in actual["cases"] if case["kind"] == "fault"]
        self.assertEqual(9, len(faults))
        self.assertEqual(9, sum(c["outcomes"]["full"] == "reject" for c in faults))
        self.assertEqual(6, sum(c["outcomes"]["bindings"] == "accept" for c in faults))
        self.assertEqual(["missing_snapshot"], [c["id"] for c in faults if not c["expectation_met"]])
        self.assertFalse(actual["all_expectations_met"])


if __name__ == "__main__":
    unittest.main()
