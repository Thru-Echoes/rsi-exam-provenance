"""Tests for gate/task_profile.py: the per-rollout task profile."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import task_profile  # noqa: E402
from tests.gate_fixtures import profile_document  # noqa: E402

VALID = profile_document()


def mutate(**changes):
    doc = copy.deepcopy(VALID)
    for dotted, value in changes.items():
        target = doc
        parts = dotted.split("__")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    return doc


class TestCheckProfile(unittest.TestCase):
    def test_valid_profile_passes_and_is_returned(self) -> None:
        self.assertEqual(task_profile.check_profile(copy.deepcopy(VALID)), VALID)

    def test_each_rule_is_enforced(self) -> None:
        bad = [
            mutate(schema="other/v1"),
            mutate(task=""),
            mutate(direction="up"),
            mutate(min_effect={"kind": "absolute", "value": 0}),
            mutate(min_effect={"kind": "absolute", "value": -1.0}),
            mutate(min_effect={"kind": "fraction_of_parent_visible_mean", "fraction": 1.0}),
            mutate(min_effect={"kind": "fraction_of_parent_visible_mean", "fraction": 0.0}),
            mutate(min_effect={"kind": "relative_to_parent_mean", "fraction": 0.1}),
            mutate(level=1.0),
            mutate(level=0.0),
            mutate(resamples=999),
            mutate(resamples=True),
            mutate(bootstrap_seed="20260902"),
            mutate(confirm_policy="inconclusive"),
            mutate(confirm_policy="sometimes"),
            mutate(confirmation__floor=1),
            mutate(confirmation__max_seeds=3),
            mutate(confirmation__max_moves=0),
            mutate(confirmation__cpu_seconds_per_game=0),
            mutate(confirmation={"floor": 4, "max_seeds": 8, "max_moves": 300}),
            mutate(visible_suite_sha256="short"),
            mutate(replication_key="11" * 31),
            mutate(replication_key="ZZ" * 32),
            mutate(audit_key_sha256="short"),
            mutate(evaluator={}),
            mutate(evaluator={"evaluate.py": "a" * 64}),
            mutate(evaluator={"evaluate.py": "a" * 64, "game2048.py": "b" * 64, "extra.py": "c" * 64}),
            mutate(evaluator={"evaluate.py": "not-hex", "game2048.py": "b" * 64}),
        ]
        for doc in bad:
            with self.subTest(doc=doc):
                with self.assertRaises(task_profile.ProfileError):
                    task_profile.check_profile(doc)
        with self.assertRaises(task_profile.ProfileError):
            task_profile.check_profile(["not", "an", "object"])

    def test_the_planning_rule_key_is_optional_and_checked(self) -> None:
        profile = copy.deepcopy(VALID)
        self.assertEqual(task_profile.resolve_planning_rule(task_profile.check_profile(profile)), "min-effect")
        profile["confirmation"]["planning_rule"] = "estimate-aware"
        self.assertEqual(task_profile.resolve_planning_rule(task_profile.check_profile(profile)), "estimate-aware")
        profile["confirmation"]["planning_rule"] = "guess"
        with self.assertRaises(task_profile.ProfileError):
            task_profile.check_profile(profile)
        self.assertEqual(task_profile.PLANNING_RULES, ("min-effect", "estimate-aware"))

    def test_absolute_min_effect_is_accepted(self) -> None:
        doc = mutate(min_effect={"kind": "absolute", "value": 120.0})
        self.assertEqual(task_profile.check_profile(doc)["min_effect"]["value"], 120.0)


class TestLoadAndResolve(unittest.TestCase):
    def test_load_returns_profile_and_file_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            text = json.dumps(VALID, indent=2, sort_keys=True) + "\n"
            path.write_text(text, encoding="utf-8")
            profile, digest = task_profile.load_profile(path)
            self.assertEqual(profile, VALID)
            self.assertEqual(digest, hashlib.sha256(text.encode("utf-8")).hexdigest())
            with self.assertRaises(task_profile.ProfileError):
                task_profile.load_profile(Path(tmp) / "missing.json")
            (Path(tmp) / "bad.json").write_text("{not json", encoding="utf-8")
            with self.assertRaises(task_profile.ProfileError):
                task_profile.load_profile(Path(tmp) / "bad.json")

    def test_resolve_min_effect(self) -> None:
        scores = {1: 4000.0, 2: 4240.0}
        self.assertAlmostEqual(task_profile.resolve_min_effect(VALID, scores), 0.025 * 4120.0)
        absolute = mutate(min_effect={"kind": "absolute", "value": 120.0})
        self.assertEqual(task_profile.resolve_min_effect(absolute, scores), 120.0)
        with self.assertRaises(task_profile.ProfileError):
            task_profile.resolve_min_effect(VALID, {1: 0.0, 2: 0.0})
        with self.assertRaises(task_profile.ProfileError):
            task_profile.resolve_min_effect(VALID, {1: -10.0, 2: 5.0})
        with self.assertRaises(task_profile.ProfileError):
            task_profile.resolve_min_effect(VALID, {})


if __name__ == "__main__":
    unittest.main()
