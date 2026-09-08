"""The calibration simulator: the gate rule on synthetic deltas, with both planning rules.

Run: python3 -m unittest tests.test_calibrate
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))

import calibrate  # noqa: E402

SCRIPT = REPO / "gate" / "calibrate.py"


class PlanningEffect(unittest.TestCase):
    def test_the_current_rule_ignores_the_estimate(self):
        self.assertEqual(calibrate.planning_effect("current", 100.0, 5000.0), 100.0)

    def test_the_estimate_aware_rule_is_never_below_the_minimum_effect(self):
        self.assertEqual(calibrate.planning_effect("estimate-aware", 100.0, 150.0), 100.0)
        self.assertEqual(calibrate.planning_effect("estimate-aware", 100.0, 5000.0), 4900.0)
        self.assertEqual(calibrate.planning_effect("estimate-aware", 100.0, -300.0), 100.0)


class Simulation(unittest.TestCase):
    def cell(self, **overrides: Any) -> dict[str, Any]:
        params: dict[str, Any] = dict(distribution="normal", effect_multiple=0.0, min_effect=50.0, sd=100.0, level=0.9,
                      resamples=200, floor=4, cap=16, trials=40, screening_seeds=8, rule="current",
                      rng=random.Random(7))
        params.update(overrides)
        return calibrate.simulate(**params)

    def test_every_probability_is_a_fraction_of_the_trials(self):
        row = self.cell()
        for key in ("coverage", "p_clears", "p_below", "p_inconclusive", "p_exploratory", "p_keep"):
            self.assertGreaterEqual(row[key], 0.0, key)
            self.assertLessEqual(row[key], 1.0, key)
        self.assertAlmostEqual(row["p_clears"] + row["p_below"] + row["p_inconclusive"], 1.0)
        self.assertEqual(row["false_keep"], row["p_keep"])

    def test_a_large_true_effect_is_kept_more_often_than_no_effect(self):
        none = self.cell(effect_multiple=0.0)
        large = self.cell(effect_multiple=10.0, rng=random.Random(7))
        self.assertGreater(large["p_keep"], none["p_keep"])
        self.assertIsNone(large["false_keep"])

    def test_the_estimate_aware_rule_plans_no_more_than_the_current_one(self):
        current = self.cell(effect_multiple=10.0, cap=10_000, rng=random.Random(3))
        aware = self.cell(effect_multiple=10.0, cap=10_000, rule="estimate-aware", rng=random.Random(3))
        self.assertLessEqual(aware["median_planned"], current["median_planned"])

    def test_the_same_seed_gives_the_same_row(self):
        self.assertEqual(self.cell(rng=random.Random(11)), self.cell(rng=random.Random(11)))

    def test_a_margin_factor_of_one_plans_fewer_seeds_than_two(self):
        loose = self.cell(effect_multiple=2.0, cap=10_000, margin_factor=1.0, rng=random.Random(5))
        strict = self.cell(effect_multiple=2.0, cap=10_000, margin_factor=2.0, rng=random.Random(5))
        self.assertLess(loose["median_planned"], strict["median_planned"])

    def test_selecting_the_best_of_many_screens_inflates_clears_at_zero_effect(self):
        honest = self.cell(trials=120, resamples=150, rng=random.Random(9))
        selected = self.cell(trials=120, resamples=150, select_best_of=8, rng=random.Random(9))
        self.assertGreater(selected["p_clears"], honest["p_clears"])
        self.assertLess(selected["lower_coverage"], honest["lower_coverage"])

    def test_a_catastrophe_mixture_reports_and_uses_its_true_mean(self):
        row = self.cell(effect_multiple=2.0, catastrophe_prob=0.5, catastrophe_delta=-1000.0)
        self.assertAlmostEqual(row["true_mean"], 0.5 * 100.0 + 0.5 * -1000.0)
        # The mixture's mean is under the minimum effect, so a keep here is a false keep.
        self.assertEqual(row["false_keep"], row["p_keep"])

    def test_catastrophes_replace_draws(self):
        sample = calibrate.draw(random.Random(2), "normal", 10.0, 0.0, 2000, catastrophe_prob=0.5,
                                catastrophe_delta=-99999.0)
        share = sum(1 for v in sample if v == -99999.0) / len(sample)
        self.assertAlmostEqual(share, 0.5, delta=0.05)

    def test_every_distribution_draws_with_the_requested_spread(self):
        rng = random.Random(1)
        for distribution in calibrate.DISTRIBUTIONS:
            sample = calibrate.draw(rng, distribution, 100.0, 500.0, 4000)
            mean = sum(sample) / len(sample)
            self.assertAlmostEqual(mean, 500.0, delta=15.0, msg=distribution)


class CommandLine(unittest.TestCase):
    def test_a_table_is_written_and_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "table.md"
            proc = subprocess.run([sys.executable, str(SCRIPT), "--min-effect", "50", "--sd", "100", "--trials", "5",
                                   "--resamples", "100", "--floor", "4", "--cap", "8", "--effects", "0,5",
                                   "--distributions", "normal,heavy", "--output", str(out)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertEqual(text, proc.stdout)
            self.assertEqual(text.count("\n| normal |"), 2)
            self.assertEqual(text.count("\n| heavy |"), 2)
            self.assertIn("not evidence about any rollout", text)
            sidecar = json.loads((Path(tmp) / "table.json").read_text(encoding="utf-8"))
            self.assertEqual(len(sidecar["rows"]), 4)
            self.assertEqual(sidecar["params"]["rule"], "current")
            self.assertIn("lower_coverage", sidecar["rows"][0])

    def test_bad_inputs_are_refused(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--min-effect", "0", "--sd", "100"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("refused", proc.stderr)


if __name__ == "__main__":
    unittest.main()
