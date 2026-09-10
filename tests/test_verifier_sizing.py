"""The verifier's disposition rule follows the gate's sizing rule: an exploratory screening reverts.

A gated screening whose confirmation plan exceeds the profile's cap is reverted by the gate on the screening
line, records the plan, and derives no suite (docs/decision-log-contract.md, "Confirmation size"). The verifier
re-applies that rule and checks the plan's flag against its own numbers. These are unit tests over the rule
functions; ``tests/test_instrument.py`` exercises the same path end to end on a real record.

Run: python3 -m unittest tests.test_verifier_sizing
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


vc = load("verify_capsule_for_sizing_tests", REPO / "profile" / "verify_capsule.py")


def screening(**overrides) -> dict:
    entry = {
        "log_line": 1, "kind": "screening", "version_id": "v2", "replicates": None,
        "verdict": "clears", "disposition": "revert", "confirm_policy": "always",
        "interval": {"lower": 216.5, "upper": 2875.5, "level": 0.9}, "min_effect": 51.5, "sample_size": 8,
        "sizing": {"rule": "estimate-aware", "size": 8, "planned": 30, "floor": 4, "cap": 8, "exploratory": True,
                   "screening_sd": 1200.0, "z": 1.645},
        "suite": None, "evidence": [], "holdout": None,
    }
    entry.update(overrides)
    return entry


def rules_errors(*entries: dict) -> list[str]:
    data = {"versions": [{"version_id": "v2", "parent_ids": ["v1"], "status": "reverted", "decisions": list(entries)}]}
    errors: list[str] = []
    vc._check_decision_rules(data, errors)
    return errors


class ExploratoryScreeningsRevert(unittest.TestCase):
    def test_an_exploratory_plan_reverts_whatever_the_verdict(self):
        self.assertEqual(vc.expected_disposition(screening(verdict="clears")), "revert")
        self.assertEqual(vc.expected_disposition(screening(verdict="inconclusive")), "revert")
        self.assertEqual(rules_errors(screening()), [])

    def test_a_plan_under_the_cap_stays_provisional(self):
        entry = screening(disposition="provisional",
                          sizing={"rule": "estimate-aware", "size": 5, "planned": 5, "floor": 4, "cap": 8,
                                  "exploratory": False, "screening_sd": 300.0, "z": 1.645},
                          suite={"locator": "results/v2/replication/seeds.json", "sha256": "0" * 64, "derivation": {}})
        self.assertEqual(vc.expected_disposition(entry), "provisional")
        self.assertEqual(rules_errors(entry), [])

    def test_a_replay_line_without_sizing_keeps_the_older_rule(self):
        entry = screening(disposition="keep", confirm_policy="inconclusive", sizing=None)
        self.assertEqual(vc.expected_disposition(entry), "keep")

    def test_the_flag_must_follow_from_the_plans_numbers(self):
        # exploratory claims the cap bound, but size equals planned
        wrong = screening(sizing={"rule": "x", "size": 8, "planned": 8, "floor": 4, "cap": 8, "exploratory": True,
                                  "screening_sd": 1.0, "z": 1.645})
        self.assertIn("decision:sizing_inconsistent:v2:1", rules_errors(wrong))
        # not exploratory, but the cap binds
        wrong = screening(disposition="provisional",
                          sizing={"rule": "x", "size": 8, "planned": 30, "floor": 4, "cap": 8, "exploratory": False,
                                  "screening_sd": 1.0, "z": 1.645})
        self.assertIn("decision:sizing_inconsistent:v2:1", rules_errors(wrong))

    def test_an_exploratory_line_derives_no_suite(self):
        wrong = screening(suite={"locator": "results/v2/replication/seeds.json", "sha256": "0" * 64, "derivation": {}})
        self.assertIn("decision:sizing_inconsistent:v2:1", rules_errors(wrong))


if __name__ == "__main__":
    unittest.main()
