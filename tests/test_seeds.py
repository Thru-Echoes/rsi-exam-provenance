"""Tests for gate/seeds.py: deterministic fresh suites and the confirmation-size planning rule."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import seeds  # noqa: E402

KEY = "00" * 32
DIGEST = "a" * 64
DELTAS = [1310.0, 820.0, 410.0, 200.0, 60.0, -190.0, -300.0, -230.0]


class TestDerive(unittest.TestCase):
    def test_known_vectors(self) -> None:
        self.assertEqual(seeds.derive_seeds(key_hex=KEY, rollout_id="demo-rollout", candidate_digest=DIGEST,
                                            look_index=1, size=3, exclude=set()),
                         [976793988, 1809094229, 1101487377])
        self.assertEqual(seeds.derive_seeds(key_hex=KEY, rollout_id="demo-rollout", candidate_digest=DIGEST,
                                            look_index=1, size=3, exclude={976793988}),
                         [1809094229, 1101487377, 456647843])
        self.assertEqual(seeds.derive_seeds(key_hex=KEY, rollout_id="demo-rollout", candidate_digest=DIGEST,
                                            look_index=2, size=3, exclude=set()),
                         [1836097249, 1878888563, 1379785594])

    def test_inputs_change_the_suite_and_values_are_positive_31_bit(self) -> None:
        base = seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=16, exclude=set())
        self.assertEqual(len(set(base)), 16)
        self.assertTrue(all(1 <= s < 2 ** 31 for s in base))
        other_key = seeds.derive_seeds(key_hex="01" * 32, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=16, exclude=set())
        other_digest = seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest="b" * 64, look_index=1, size=16, exclude=set())
        other_rollout = seeds.derive_seeds(key_hex=KEY, rollout_id="r2", candidate_digest=DIGEST, look_index=1, size=16, exclude=set())
        for variant in (other_key, other_digest, other_rollout):
            self.assertNotEqual(variant, base)

    def test_exclusion_is_respected_and_bad_arguments_are_refused(self) -> None:
        first = seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=8, exclude=set())
        again = seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=8, exclude=set(first))
        self.assertFalse(set(first) & set(again))
        with self.assertRaises(seeds.SeedsError):
            seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=0, size=8, exclude=set())
        with self.assertRaises(seeds.SeedsError):
            seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=0, exclude=set())
        with self.assertRaises(seeds.SeedsError):
            seeds.derive_seeds(key_hex="zz", rollout_id="r", candidate_digest=DIGEST, look_index=1, size=1, exclude=set())


class TestSizing(unittest.TestCase):
    def test_worked_example_plans_327_and_is_exploratory_under_the_cap(self) -> None:
        out = seeds.confirmation_size(DELTAS, min_effect=103.0, level=0.9, floor=16, cap=64)
        self.assertEqual((out["size"], out["planned"], out["floor"], out["cap"], out["exploratory"]), (64, 327, 16, 64, True))
        self.assertAlmostEqual(out["screening_sd"], 565.4833583505606, places=6)
        self.assertAlmostEqual(out["z"], 1.6448536269514715, places=6)
        self.assertEqual(out["rule"], seeds.SIZING_RULE)
        self.assertEqual(seeds.confirmation_size(DELTAS, min_effect=103.0, level=0.9, floor=16, cap=32)["size"], 32)

    def test_the_estimate_aware_rule_plans_against_the_larger_effect(self) -> None:
        # mean 1000, sd about 300: the accepted rule resolves a minimum effect of 50 and needs ~1560 seeds;
        # the estimate-aware rule plans against 950 and needs the floor.
        wide = [1000.0 + d for d in (-450.0, -300.0, -150.0, -50.0, 50.0, 150.0, 300.0, 450.0)]
        accepted = seeds.confirmation_size(wide, min_effect=50.0, level=0.9, floor=16, cap=64)
        aware = seeds.confirmation_size(wide, min_effect=50.0, level=0.9, floor=16, cap=64, rule="estimate-aware")
        self.assertTrue(accepted["exploratory"])
        self.assertNotIn("planning_rule", accepted)
        self.assertEqual(accepted["rule"], seeds.SIZING_RULE)
        self.assertEqual((aware["planned"], aware["size"], aware["exploratory"]), (16, 16, False))
        self.assertEqual((aware["planning_rule"], aware["planning_effect"], aware["screening_mean"]), ("estimate-aware", 950.0, 1000.0))
        self.assertEqual(aware["rule"], seeds.ESTIMATE_AWARE_RULE)
        self.assertEqual(aware["screening_sd"], accepted["screening_sd"])
        # a candidate whose screening mean is below twice the minimum effect plans exactly as the accepted rule does
        low = [20.0 + d for d in (-45.0, -30.0, -15.0, -5.0, 5.0, 15.0, 30.0, 45.0)]
        same = seeds.confirmation_size(low, min_effect=50.0, level=0.9, floor=16, cap=64, rule="estimate-aware")
        self.assertEqual(same["planning_effect"], 50.0)
        self.assertEqual(same["planned"], seeds.confirmation_size(low, min_effect=50.0, level=0.9, floor=16, cap=64)["planned"])
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(wide, min_effect=50.0, level=0.9, floor=16, cap=64, rule="guess")
        self.assertEqual(seeds.PLANNING_RULES, ("min-effect", "estimate-aware"))

    def test_floor_applies_when_the_deltas_are_tight_or_constant(self) -> None:
        out = seeds.confirmation_size([0.0] * 8, min_effect=103.0, level=0.9, floor=16, cap=64)
        self.assertEqual((out["size"], out["planned"], out["exploratory"]), (16, 16, False))
        out = seeds.confirmation_size(DELTAS, min_effect=412.0, level=0.9, floor=16, cap=64)
        self.assertEqual((out["planned"], out["exploratory"]), (21, False))
        out = seeds.confirmation_size(DELTAS, min_effect=700.0, level=0.9, floor=4, cap=8)
        self.assertEqual((out["planned"], out["size"], out["exploratory"]), (8, 8, False))
        self.assertEqual(seeds.confirmation_size([5.0], min_effect=1.0, level=0.9, floor=4, cap=8)["size"], 4)

    def test_bad_arguments_are_refused(self) -> None:
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(DELTAS, min_effect=0.0, level=0.9, floor=16, cap=64)
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(DELTAS, min_effect=1.0, level=0.9, floor=1, cap=64)
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(DELTAS, min_effect=1.0, level=0.9, floor=16, cap=8)
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(DELTAS, min_effect=1.0, level=1.0, floor=16, cap=64)


class TestSuiteFiles(unittest.TestCase):
    def test_write_read_and_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results" / "v3" / "replication" / "seeds.json"
            digest = seeds.write_suite(path, [5, 3, 9], max_moves=300)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(digest, hashlib.sha256(text.encode("utf-8")).hexdigest())
            self.assertEqual(json.loads(text), {"max_moves": 300, "seeds": [5, 3, 9]})
            self.assertEqual(seeds.read_suite(path), ([5, 3, 9], 300))
            with self.assertRaises(seeds.SeedsError):
                seeds.write_suite(path, [1], max_moves=300)
            self.assertEqual(seeds.read_suite(path), ([5, 3, 9], 300))
            bad = Path(tmp) / "bad.json"
            bad.write_text('{"seeds": [1, 1]}', encoding="utf-8")
            with self.assertRaises(seeds.SeedsError):
                seeds.read_suite(bad)
            bad.write_text('{"max_moves": 5}', encoding="utf-8")
            with self.assertRaises(seeds.SeedsError):
                seeds.read_suite(bad)

    def test_cli_writes_a_suite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suite.json"
            code = seeds.main(["--key-hex", KEY, "--rollout", "demo-rollout", "--candidate-digest", DIGEST,
                               "--look-index", "1", "--size", "3", "--max-moves", "10000",
                               "--exclude", "976793988", "--output", str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["seeds"], [1809094229, 1101487377, 456647843])
            self.assertEqual(seeds.main(["--key-hex", KEY, "--rollout", "r", "--candidate-digest", DIGEST,
                                         "--look-index", "1", "--size", "3", "--output", str(out)]), 2)


if __name__ == "__main__":
    unittest.main()
