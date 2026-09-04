"""Tests for gate/decide.py: the paired bootstrap gate in replay mode and in gated mode."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import decide  # noqa: E402
import seeds as seedsmod  # noqa: E402
import treedigest  # noqa: E402
from tests.gate_fixtures import (DELTAS_BELOW, DELTAS_CLEAR, DELTAS_INCONCLUSIVE, PARENT, SEEDS,  # noqa: E402
                                 VISIBLE_SUITE_SHA, write_profile, write_receipt, write_result, write_tree)

UP = "def choose_move(board):\n    return 'UP'\n"
LEFT = "def choose_move(board):\n    return 'LEFT'\n"
RIGHT = "def choose_move(board):\n    return 'RIGHT'\n"
DOWN = "def choose_move(board):\n    return 'DOWN'\n"
GATED_KEYS = ("confirm_policy", "profile_sha256", "look_index", "parent_method_tree_sha256",
              "candidate_method_tree_sha256", "sizing", "suite")
ABSOLUTE_700 = {"kind": "absolute", "value": 700.0}
FRACTION_MIN_EFFECT = 0.025 * sum(PARENT) / len(PARENT)  # 103.0 on the PARENT visible scores


def shifted(base: Sequence[float], deltas: Sequence[float]) -> list[float]:
    return [b + d for b, d in zip(base, deltas)]


def bound_receipt_fields(overrides: dict[str, Any], **defaults: Any) -> dict[str, Any]:
    """Split receipt keyword arguments into the four fields the gate binds and the rest of the document.

    Mutates ``overrides`` in place: what it leaves behind goes into the receipt verbatim.
    """
    for key in list(defaults):
        if key in overrides:
            defaults[key] = overrides.pop(key)
    return defaults


def run_gate(argv: list[str]) -> tuple[int, str]:
    """Call the gate in process; return its exit code and what it refused with."""
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = decide.main(argv)
    return code, err.getvalue()


def gate_main(argv: list[str]) -> int:
    """The gate's exit code, with the appended line and any refusal kept off the test output."""
    return run_gate(argv)[0]


class TestStatistics(unittest.TestCase):
    def test_paired_deltas_align_by_seed(self) -> None:
        parent = dict(zip(SEEDS, PARENT))
        candidate = {s: p + d for s, p, d in zip(SEEDS, PARENT, DELTAS_INCONCLUSIVE)}
        self.assertEqual(decide.paired_deltas(parent, candidate), [float(d) for d in DELTAS_INCONCLUSIVE])

    def test_direction_lower_negates(self) -> None:
        parent = dict(zip(SEEDS, PARENT))
        candidate = {s: p + d for s, p, d in zip(SEEDS, PARENT, DELTAS_INCONCLUSIVE)}
        self.assertEqual(decide.paired_deltas(parent, candidate, "lower"), [-float(d) for d in DELTAS_INCONCLUSIVE])

    def test_paired_deltas_reject_seed_mismatch(self) -> None:
        parent = dict(zip(SEEDS, PARENT))
        candidate = dict(zip(SEEDS[:-1] + [999], PARENT))
        with self.assertRaises(decide.GateError):
            decide.paired_deltas(parent, candidate)

    def test_bootstrap_interval_is_deterministic_and_inconclusive(self) -> None:
        low, high = decide.bootstrap_interval([float(d) for d in DELTAS_INCONCLUSIVE], level=0.9, resamples=5000,
                                              seed=20260902)
        self.assertEqual((round(low, 1), round(high, 1)), (-30.0, 583.8))
        self.assertEqual(decide.get_verdict((low, high), 0.0), "inconclusive")

    def test_verdict_clears_and_below(self) -> None:
        low, high = decide.bootstrap_interval([float(d) for d in DELTAS_CLEAR], level=0.9, resamples=5000, seed=20260902)
        self.assertEqual(decide.get_verdict((low, high), 0.0), "clears")
        low, high = decide.bootstrap_interval([float(d) for d in DELTAS_BELOW], level=0.9, resamples=5000, seed=20260902)
        self.assertEqual(decide.get_verdict((low, high), 0.0), "below")

    def test_min_effect_can_turn_a_clear_into_a_straddle(self) -> None:
        self.assertEqual(decide.get_verdict((10.0, 40.0), 20.0), "inconclusive")

    def test_negative_min_effect_is_refused(self) -> None:
        with self.assertRaises(decide.GateError):
            decide.get_verdict((10.0, 40.0), -1.0)

    def test_disposition_follows_verdict_and_holdout(self) -> None:
        self.assertEqual(decide.get_disposition("clears", None), "keep")
        self.assertEqual(decide.get_disposition("below", None), "revert")
        self.assertEqual(decide.get_disposition("inconclusive", None), "provisional")
        self.assertEqual(decide.get_disposition("clears", "inconclusive"), "provisional")
        self.assertEqual(decide.get_disposition("clears", "clears"), "keep")

    def test_disposition_under_always_makes_every_non_revert_provisional(self) -> None:
        self.assertEqual(decide.get_disposition("clears", None, "always"), "provisional")
        self.assertEqual(decide.get_disposition("inconclusive", None, "always"), "provisional")
        self.assertEqual(decide.get_disposition("below", None, "always"), "revert")
        with self.assertRaises(decide.GateError):
            decide.get_disposition("clears", None, "sometimes")


class TestCli(unittest.TestCase):
    """Replay mode: explicit locators, the weaker screening-only rule, nothing frozen."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_result(self.methods / "results" / "v6" / "visible_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "visible_result.json", shifted(PARENT, DELTAS_INCONCLUSIVE))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_gate(self, *extra: str) -> int:
        return gate_main(["--methods", str(self.methods), "--version", "v7", "--parent", "v6",
                          "--confirm", "inconclusive", *extra])

    def lines(self) -> list[dict[str, Any]]:
        return [json.loads(x) for x in (self.methods / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_appends_one_line_in_the_contract_shape(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        lines = self.lines()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line["schema"], "rsi-exam-decision-log/v1")
        self.assertEqual(line["line"], 1)
        self.assertEqual((line["version_id"], line["parent_id"], line["replicates"]), ("v7", "v6", None))
        self.assertEqual(line["verdict"], "inconclusive")
        self.assertEqual(line["disposition"], "provisional")
        self.assertEqual(line["sample_size"], 8)
        self.assertEqual(line["direction"], "higher")
        self.assertEqual(line["interval"]["level"], 0.9)
        self.assertLessEqual(line["interval"]["lower"], line["estimate"])
        self.assertLessEqual(line["estimate"], line["interval"]["upper"])
        self.assertEqual(line["method"], {"name": "percentile_bootstrap", "algorithm": "rsi-exam-gate/percentile-bootstrap/1",
                                          "resamples": 5000, "seed": 20260902})
        self.assertEqual([e["role"] for e in line["evidence"]], ["parent", "candidate"])
        self.assertEqual([e["locator"] for e in line["evidence"]],
                         ["results/v6/visible_result.json", "results/v7/visible_result.json"])
        for ref in line["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
            self.assertEqual(line["evidence_digests"][ref["role"]], "sha256:" + ref["sha256"])
        self.assertTrue(line["timestamp"].endswith("+00:00"))
        self.assertIsNone(line["holdout"])
        # every gated key is present on every line; in replay mode only the policy is stated
        for key in GATED_KEYS:
            self.assertIn(key, line)
        self.assertEqual(line["confirm_policy"], "inconclusive")
        self.assertIsNone(line["profile_sha256"])
        self.assertIsNone(line["look_index"])
        self.assertIsNone(line["parent_method_tree_sha256"])
        self.assertIsNone(line["candidate_method_tree_sha256"])
        self.assertIsNone(line["sizing"])
        self.assertIsNone(line["suite"])

    def test_refuses_to_stack_on_an_unreplicated_provisional(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v8" / "visible_result.json",
                     [p + d + 20 for p, d in zip(PARENT, DELTAS_INCONCLUSIVE)])
        code = gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v7",
                            "--confirm", "inconclusive"])
        self.assertEqual(code, 3)
        self.assertEqual(len(self.lines()), 1)

    def test_refuses_a_second_open_provisional_on_another_parent(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v8" / "visible_result.json", shifted(PARENT, DELTAS_INCONCLUSIVE))
        code = gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6",
                            "--confirm", "inconclusive"])
        self.assertEqual(code, 3)
        self.assertEqual(len(self.lines()), 1)

    def test_a_clear_keep_on_another_parent_is_allowed_while_one_provisional_is_open(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v8" / "visible_result.json", shifted(PARENT, DELTAS_CLEAR))
        code = gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6",
                            "--confirm", "inconclusive"])
        self.assertEqual(code, 0)
        self.assertEqual(self.lines()[1]["disposition"], "keep")

    def test_replication_resolves_the_provisional(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "replication" / "candidate_result.json",
                     shifted(PARENT, DELTAS_CLEAR))
        self.assertEqual(self.run_gate("--replicates", "v7"), 0)
        lines = self.lines()
        self.assertEqual(lines[1]["replicates"], "v7")
        self.assertEqual(lines[1]["disposition"], "keep")
        self.assertEqual(lines[1]["line"], 2)
        self.assertEqual(lines[1]["evidence"][0]["locator"], "results/v7/replication/parent_result.json")
        self.assertIsNone(lines[1]["suite"])
        # the provisional is now resolved, so building on v7 is allowed
        write_result(self.methods / "results" / "v8" / "visible_result.json",
                     [p + d + 600 for p, d in zip(PARENT, DELTAS_CLEAR)])
        self.assertEqual(gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v7",
                                      "--confirm", "inconclusive"]), 0)

    def test_replication_without_an_open_provisional_is_refused(self) -> None:
        write_result(self.methods / "results" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "replication" / "candidate_result.json", PARENT)
        self.assertEqual(self.run_gate("--replicates", "v7"), 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_replication_with_wrong_parent_is_refused(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "replication" / "candidate_result.json", PARENT)
        code = gate_main(["--methods", str(self.methods), "--version", "v7", "--parent", "v5",
                            "--replicates", "v7", "--confirm", "inconclusive"])
        self.assertEqual(code, 2)
        self.assertEqual(len(self.lines()), 1)

    def test_replication_with_non_clearing_holdout_reverts(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "replication" / "candidate_result.json",
                     shifted(PARENT, DELTAS_CLEAR))
        write_result(self.methods / "results" / "v7" / "holdout" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "holdout" / "candidate_result.json",
                     shifted(PARENT, DELTAS_INCONCLUSIVE))
        code = self.run_gate("--replicates", "v7",
                             "--holdout-parent-result", "results/v7/holdout/parent_result.json",
                             "--holdout-candidate-result", "results/v7/holdout/candidate_result.json")
        self.assertEqual(code, 0)
        lines = self.lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual((lines[1]["verdict"], lines[1]["holdout"]["verdict"], lines[1]["disposition"]),
                         ("clears", "inconclusive", "revert"))
        # the provisional is resolved, so a new line on v6 may open a fresh provisional
        write_result(self.methods / "results" / "v8" / "visible_result.json", shifted(PARENT, DELTAS_INCONCLUSIVE))
        self.assertEqual(gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6",
                                      "--confirm", "inconclusive"]), 0)

    def test_holdout_forces_provisional_and_is_recorded(self) -> None:
        write_result(self.methods / "results" / "v7" / "visible_result.json", shifted(PARENT, DELTAS_CLEAR))
        write_result(self.methods / "results" / "v7" / "holdout" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "holdout" / "candidate_result.json",
                     shifted(PARENT, DELTAS_INCONCLUSIVE))
        code = self.run_gate("--holdout-parent-result", "results/v7/holdout/parent_result.json",
                             "--holdout-candidate-result", "results/v7/holdout/candidate_result.json")
        self.assertEqual(code, 0)
        line = self.lines()[0]
        self.assertEqual(line["verdict"], "clears")
        self.assertEqual(line["disposition"], "provisional")
        self.assertEqual(line["holdout"]["verdict"], "inconclusive")
        self.assertEqual([e["role"] for e in line["holdout"]["evidence"]], ["holdout-parent", "holdout-candidate"])
        self.assertEqual(set(line["holdout"]["evidence_digests"]), {"holdout-parent", "holdout-candidate"})

    def test_missing_result_file_fails_loud(self) -> None:
        code = gate_main(["--methods", str(self.methods), "--version", "v9", "--parent", "v6",
                            "--confirm", "inconclusive"])
        self.assertEqual(code, 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_negative_min_effect_flag_is_refused(self) -> None:
        self.assertEqual(self.run_gate("--min-effect", "-5"), 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_locator_escaping_methods_is_refused(self) -> None:
        self.assertEqual(self.run_gate("--parent-result", "../outside.json"), 2)
        self.assertEqual(self.run_gate("--parent-result", "results\\v6\\visible_result.json"), 2)
        self.assertEqual(self.run_gate("--parent-result", "results/%2e%2e/v6.json"), 2)

    def test_evidence_inside_the_policy_tree_is_refused(self) -> None:
        write_result(self.methods / "versions" / "v6" / "visible_result.json", PARENT)
        self.assertEqual(self.run_gate("--parent-result", "versions/v6/visible_result.json"), 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_corrupt_log_is_refused(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        log = self.methods / "decisions.jsonl"
        log.write_text(log.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        write_result(self.methods / "results" / "v8" / "visible_result.json", shifted(PARENT, DELTAS_CLEAR))
        self.assertEqual(gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6",
                                      "--confirm", "inconclusive"]), 2)


class TestReplayModeFlags(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_result(self.methods / "results" / "v6" / "visible_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "visible_result.json", shifted(PARENT, DELTAS_CLEAR))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_confirm_policy_must_be_stated(self) -> None:
        code = gate_main(["--methods", str(self.methods), "--version", "v7", "--parent", "v6"])
        self.assertEqual(code, 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_always_needs_a_profile(self) -> None:
        code = gate_main(["--methods", str(self.methods), "--version", "v7", "--parent", "v6",
                            "--confirm", "always"])
        self.assertEqual(code, 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())


class GatedCase(unittest.TestCase):
    """A methods directory with v1 (parent) and v2 (candidate) snapshots, main/ matching v2, and a profile."""

    profile_overrides: dict[str, Any] = {}
    candidate_deltas: Sequence[float] = DELTAS_INCONCLUSIVE

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_tree(self.methods / "versions" / "v1", UP)
        write_tree(self.methods / "versions" / "v2", LEFT)
        write_tree(self.methods / "main", LEFT)
        self.profile = self.methods / "gate" / "profile.json"
        self.profile_sha = write_profile(self.profile, **self.profile_overrides)
        self.write_visible("v1", PARENT)
        self.write_visible("v2", shifted(PARENT, self.candidate_deltas))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def digest(self, version: str) -> str:
        return treedigest.method_tree_sha256(self.methods / "versions" / version)

    def visible_path(self, version: str) -> Path:
        return self.methods / "results" / version / "visible_result.json"

    def write_visible(self, version: str, scores: Sequence[float], **receipt_overrides: Any) -> Path:
        """A visible result for one version with the runner receipt the gated screening requires."""
        path = self.visible_path(version)
        write_result(path, scores)
        self.write_visible_receipt(version, **receipt_overrides)
        return path

    def write_visible_receipt(self, version: str, **overrides: Any) -> None:
        bound = bound_receipt_fields(overrides, profile_sha=self.profile_sha, policy_digest=self.digest(version),
                                     suite_sha=VISIBLE_SUITE_SHA, games=len(SEEDS))
        write_receipt(self.visible_path(version), **bound, **overrides)

    def reprofile(self, **overrides: Any) -> None:
        """Rewrite the profile in place and re-bind both visible receipts to its new digest."""
        self.profile_sha = write_profile(self.profile, **overrides)
        for version in ("v1", "v2"):
            self.write_visible_receipt(version)

    def gate(self, version: str, parent: str, *extra: str, profile: Path | None = None) -> int:
        code, _ = self.gate_with_stderr(version, parent, *extra, profile=profile)
        return code

    def gate_with_stderr(self, version: str, parent: str, *extra: str, profile: Path | None = None) -> tuple[int, str]:
        return run_gate(["--methods", str(self.methods), "--version", version, "--parent", parent,
                         "--profile", str(profile or self.profile), *extra])

    def lines(self) -> list[dict[str, Any]]:
        log = self.methods / "decisions.jsonl"
        if not log.exists():
            return []
        return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]

    def suite_file(self, version: str) -> Path:
        return self.methods / "results" / version / "replication" / "seeds.json"


class TestGatedScreening(GatedCase):
    def test_fixed_flags_are_refused_in_gated_mode(self) -> None:
        for extra in (("--confirm", "always"), ("--confirm", "inconclusive"), ("--direction", "lower"),
                      ("--min-effect", "5"), ("--level", "0.8"), ("--resamples", "5000"), ("--seed", "1"),
                      ("--unit", "x"), ("--parent-result", "results/v1/visible_result.json"),
                      ("--candidate-result", "results/v2/visible_result.json"),
                      ("--holdout-parent-result", "results/v1/h.json",
                       "--holdout-candidate-result", "results/v2/h.json")):
            with self.subTest(extra=extra):
                code, err = self.gate_with_stderr("v2", "v1", *extra)
                self.assertEqual(code, 2)
                self.assertIn("fixed by the profile", err)
        self.assertEqual(self.lines(), [])

    def test_an_under_planned_confirmation_reverts_and_records_its_plan(self) -> None:
        self.assertEqual(self.gate("v2", "v1"), 0)
        line = self.lines()[0]
        self.assertEqual((line["verdict"], line["disposition"], line["confirm_policy"]),
                         ("inconclusive", "revert", "always"))
        self.assertAlmostEqual(line["min_effect"], FRACTION_MIN_EFFECT)
        self.assertEqual(line["profile_sha256"], self.profile_sha)
        self.assertEqual(line["parent_method_tree_sha256"], self.digest("v1"))
        self.assertEqual(line["candidate_method_tree_sha256"], self.digest("v2"))
        sizing = line["sizing"]
        self.assertEqual(set(sizing), {"rule", "size", "planned", "floor", "cap", "exploratory", "screening_sd", "z"})
        self.assertEqual((sizing["planned"], sizing["size"], sizing["floor"], sizing["cap"], sizing["exploratory"]),
                         (327, 8, 4, 8, True))
        self.assertEqual(sizing["rule"], seedsmod.SIZING_RULE)
        self.assertIsNone(line["suite"])
        self.assertIsNone(line["look_index"])
        self.assertFalse(self.suite_file("v2").exists())
        self.assertEqual([e["role"] for e in line["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])
        self.assertEqual([e["locator"] for e in line["evidence"]],
                         ["results/v1/visible_result.json", "results/v2/visible_result.json",
                          "results/v1/visible_result.receipt.json", "results/v2/visible_result.receipt.json"])
        for ref in line["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
            self.assertEqual(line["evidence_digests"][ref["role"]], "sha256:" + ref["sha256"])

    def test_a_plan_that_fits_the_cap_opens_a_provisional_with_a_fresh_suite(self) -> None:
        self.reprofile(min_effect=ABSOLUTE_700)
        self.assertEqual(self.gate("v2", "v1"), 0)
        line = self.lines()[0]
        self.assertEqual((line["verdict"], line["disposition"]), ("inconclusive", "provisional"))
        self.assertEqual(line["min_effect"], 700.0)
        self.assertEqual((line["sizing"]["planned"], line["sizing"]["size"], line["sizing"]["exploratory"]),
                         (8, 8, False))
        self.assertEqual(line["look_index"], 1)
        suite = line["suite"]
        self.assertEqual(set(suite), {"locator", "sha256", "derivation"})
        self.assertEqual(suite["locator"], "results/v2/replication/seeds.json")
        path = self.suite_file("v2")
        self.assertEqual(decide.sha256_of(path), suite["sha256"])
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["max_moves"], 300)
        self.assertEqual(len(document["seeds"]), 8)
        self.assertEqual(len(set(document["seeds"])), 8)
        self.assertFalse(set(document["seeds"]) & set(SEEDS))
        self.assertEqual(suite["derivation"],
                         {"algorithm": seedsmod.SEEDS_ALGORITHM, "rollout_id": "demo-rollout",
                          "candidate_method_tree_sha256": self.digest("v2"), "look_index": 1, "size": 8,
                          "max_moves": 300})
        self.assertEqual(document["seeds"],
                         seedsmod.derive_seeds(key_hex="11" * 32, rollout_id="demo-rollout",
                                               candidate_digest=self.digest("v2"), look_index=1, size=8,
                                               exclude=set(SEEDS)))

    def test_constant_clear_deltas_plan_the_floor(self) -> None:
        write_result(self.visible_path("v2"), [p + 500 for p in PARENT])
        self.write_visible_receipt("v2")
        self.assertEqual(self.gate("v2", "v1"), 0)
        line = self.lines()[0]
        self.assertEqual((line["interval"]["lower"], line["interval"]["upper"]), (500.0, 500.0))
        self.assertEqual((line["verdict"], line["disposition"]), ("clears", "provisional"))
        self.assertEqual(line["sizing"]["screening_sd"], 0.0)
        self.assertEqual((line["sizing"]["planned"], line["sizing"]["size"], line["sizing"]["exploratory"]),
                         (4, 4, False))
        self.assertEqual(line["suite"]["derivation"]["size"], 4)
        document = json.loads(self.suite_file("v2").read_text(encoding="utf-8"))
        self.assertEqual(len(document["seeds"]), 4)
        self.assertFalse(set(document["seeds"]) & set(SEEDS))

    def test_below_reverts_with_no_plan_and_no_suite(self) -> None:
        write_result(self.visible_path("v2"), shifted(PARENT, DELTAS_BELOW))
        self.write_visible_receipt("v2")
        self.assertEqual(self.gate("v2", "v1"), 0)
        line = self.lines()[0]
        self.assertEqual((line["verdict"], line["disposition"]), ("below", "revert"))
        self.assertIsNone(line["sizing"])
        self.assertIsNone(line["suite"])
        self.assertIsNone(line["look_index"])
        self.assertFalse((self.methods / "results" / "v2" / "replication").exists())

    def test_a_missing_visible_receipt_is_refused(self) -> None:
        self.visible_path("v2").with_name("visible_result.receipt.json").unlink()
        code, err = self.gate_with_stderr("v2", "v1")
        self.assertEqual(code, 2)
        self.assertIn("receipt not found", err)
        self.assertEqual(self.lines(), [])

    def test_each_bound_receipt_field_is_compared(self) -> None:
        for field, value in (("policy_digest", "0" * 64), ("suite_sha", "0" * 64), ("profile_sha", "0" * 64),
                             ("games", 3), ("metric", "other"), ("max_moves", 10000),
                             ("cpu_budget_per_game", 5), ("result_sha256", "0" * 64),
                             ("evaluator", {"evaluate.py": "0" * 64, "game2048.py": "b" * 64})):
            with self.subTest(field=field):
                self.write_visible_receipt("v2", **{field: value})
                code, err = self.gate_with_stderr("v2", "v1")
                self.assertEqual(code, 2)
                self.assertIn("candidate receipt", err)
                self.write_visible_receipt("v2")
        self.assertEqual(self.lines(), [])

    def test_receipts_from_different_python_minors_are_refused(self) -> None:
        self.write_visible_receipt("v1", python="3.11.9")
        code, err = self.gate_with_stderr("v2", "v1")
        self.assertEqual(code, 2)
        self.assertIn("different Python versions", err)
        self.assertEqual(self.lines(), [])

    def test_main_must_match_the_candidate_snapshot(self) -> None:
        self.reprofile(min_effect=ABSOLUTE_700)
        write_tree(self.methods / "main", DOWN)
        code, err = self.gate_with_stderr("v2", "v1")
        self.assertEqual(code, 2)
        self.assertIn("main/ does not match versions/v2", err)
        self.assertEqual(self.lines(), [])
        self.assertFalse(self.suite_file("v2").exists())

    def test_missing_snapshots_are_refused(self) -> None:
        self.assertEqual(self.gate("v3", "v1"), 2)
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        self.assertEqual(self.gate("v3", "v9"), 2)
        self.assertEqual(self.lines(), [])

    def test_a_replay_line_and_a_gated_line_never_share_one_log(self) -> None:
        replay = ["--methods", str(self.methods), "--version", "v2", "--parent", "v1", "--confirm", "inconclusive"]
        self.assertEqual(gate_main(replay), 0)
        code, err = self.gate_with_stderr("v2", "v1")
        self.assertEqual(code, 2)
        self.assertIn("one profile per log", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_gated_line_refuses_a_later_replay_line_and_a_second_profile(self) -> None:
        write_result(self.visible_path("v2"), shifted(PARENT, DELTAS_BELOW))
        self.write_visible_receipt("v2")
        self.assertEqual(self.gate("v2", "v1"), 0)
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        write_result(self.visible_path("v3"), shifted(PARENT, DELTAS_CLEAR))
        code, err = run_gate(["--methods", str(self.methods), "--version", "v3", "--parent", "v1",
                              "--confirm", "inconclusive"])
        self.assertEqual(code, 2)
        self.assertIn("written in gated mode", err)
        other = self.methods / "gate" / "other.json"
        write_profile(other, rollout_id="another-rollout")
        code, err = self.gate_with_stderr("v3", "v1", profile=other)
        self.assertEqual(code, 2)
        self.assertIn("one profile per log", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_second_provisional_is_refused_and_writes_no_suite(self) -> None:
        self.reprofile(min_effect=ABSOLUTE_700)
        self.assertEqual(self.gate("v2", "v1"), 0)
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        write_result(self.visible_path("v3"), shifted(PARENT, DELTAS_INCONCLUSIVE))
        self.write_visible_receipt("v3")
        code, err = self.gate_with_stderr("v3", "v1")
        self.assertEqual(code, 3)
        self.assertIn("one open provisional decision", err)
        self.assertFalse(self.suite_file("v3").exists())
        # and building on the open provisional's own version is refused too
        code, err = self.gate_with_stderr("v3", "v2")
        self.assertEqual(code, 3)
        self.assertIn("unreplicated provisional decision", err)
        self.assertEqual(len(self.lines()), 1)
        self.assertFalse(self.suite_file("v3").exists())


class TestGatedConfirmation(GatedCase):
    """Line 1 is a provisional with an eight-seed suite; every test resolves or refuses it."""

    profile_overrides = {"min_effect": ABSOLUTE_700}

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.gate("v2", "v1"), 0)
        self.line1 = self.lines()[0]
        self.assertEqual(self.line1["disposition"], "provisional")
        self.suite_seeds, _ = seedsmod.read_suite(self.suite_file("v2"))
        self.assertEqual(len(self.suite_seeds), 8)
        self.base = self.methods / "results" / "v2" / "replication"

    def confirmation_path(self, role: str) -> Path:
        return self.base / f"{role}_result.json"

    def write_confirmation(self, parent_scores: Sequence[float], candidate_scores: Sequence[float],
                           seeds: Sequence[int] | None = None) -> None:
        chosen = list(seeds if seeds is not None else self.suite_seeds)
        write_result(self.confirmation_path("parent"), parent_scores, chosen)
        write_result(self.confirmation_path("candidate"), candidate_scores, chosen)
        self.write_confirmation_receipt("parent")
        self.write_confirmation_receipt("candidate")

    def write_confirmation_receipt(self, role: str, **overrides: Any) -> None:
        version = "v1" if role == "parent" else "v2"
        bound = bound_receipt_fields(overrides, profile_sha=self.profile_sha, policy_digest=self.digest(version),
                                     suite_sha=self.line1["suite"]["sha256"], games=len(self.suite_seeds))
        write_receipt(self.confirmation_path(role), **bound, **overrides)

    def replicate(self, *extra: str) -> tuple[int, str]:
        return self.gate_with_stderr("v2", "v1", "--replicates", "v2", *extra)

    def test_a_clearing_confirmation_keeps_and_repeats_the_frozen_record(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        self.assertEqual(self.replicate()[0], 0)
        line1, line2 = self.lines()
        self.assertEqual((line2["replicates"], line2["verdict"], line2["disposition"]), ("v2", "clears", "keep"))
        self.assertEqual(line2["sample_size"], 8)
        self.assertEqual((line2["interval"]["lower"], line2["interval"]["upper"]), (800.0, 800.0))
        for key in ("suite", "sizing", "look_index", "profile_sha256", "parent_method_tree_sha256",
                    "candidate_method_tree_sha256", "min_effect"):
            self.assertEqual(line2[key], line1[key], key)
        self.assertEqual(line2["confirm_policy"], "always")
        self.assertEqual([e["role"] for e in line2["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])
        self.assertEqual([e["locator"] for e in line2["evidence"]],
                         ["results/v2/replication/parent_result.json",
                          "results/v2/replication/candidate_result.json",
                          "results/v2/replication/parent_result.receipt.json",
                          "results/v2/replication/candidate_result.receipt.json"])
        for ref in line2["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
            self.assertEqual(line2["evidence_digests"][ref["role"]], "sha256:" + ref["sha256"])
        # v2 is resolved, so a candidate may build on it; the next look is the second
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        self.write_visible("v3", shifted(shifted(PARENT, DELTAS_INCONCLUSIVE), DELTAS_INCONCLUSIVE))
        self.assertEqual(self.gate("v3", "v2"), 0)
        line3 = self.lines()[2]
        self.assertEqual((line3["disposition"], line3["look_index"]), ("provisional", 2))
        fresh, _ = seedsmod.read_suite(self.suite_file("v3"))
        self.assertFalse(set(fresh) & (set(SEEDS) | set(self.suite_seeds)))

    def test_an_inconclusive_confirmation_reverts_and_frees_the_next_provisional(self) -> None:
        self.write_confirmation(PARENT, shifted(PARENT, DELTAS_INCONCLUSIVE))
        self.assertEqual(self.replicate()[0], 0)
        line2 = self.lines()[1]
        self.assertEqual((line2["verdict"], line2["disposition"]), ("inconclusive", "revert"))
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        self.write_visible("v3", shifted(PARENT, DELTAS_INCONCLUSIVE))
        self.assertEqual(self.gate("v3", "v1"), 0)
        self.assertEqual(self.lines()[2]["disposition"], "provisional")

    def test_a_missing_confirmation_receipt_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        self.confirmation_path("candidate").with_name("candidate_result.receipt.json").unlink()
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("receipt not found", err)
        self.assertEqual(len(self.lines()), 1)

    def test_each_bound_confirmation_receipt_field_is_compared(self) -> None:
        for field, value in (("suite_sha", "0" * 64), ("policy_digest", "0" * 64), ("profile_sha", "0" * 64),
                             ("games", 3), ("metric", "other"), ("max_moves", 10000),
                             ("cpu_budget_per_game", 5), ("result_sha256", "0" * 64),
                             ("evaluator", {"evaluate.py": "0" * 64, "game2048.py": "b" * 64})):
            with self.subTest(field=field):
                self.write_confirmation(PARENT, [p + 800 for p in PARENT])
                self.write_confirmation_receipt("candidate", **{field: value})
                code, err = self.replicate()
                self.assertEqual(code, 2)
                self.assertIn("candidate receipt", err)
        self.assertEqual(len(self.lines()), 1)

    def test_results_must_cover_exactly_the_confirmation_suite(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT], seeds=SEEDS)
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("does not cover exactly the confirmation suite", err)
        self.assertEqual(len(self.lines()), 1)

    def test_an_altered_suite_file_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        path = self.suite_file("v2")
        document = json.loads(path.read_text(encoding="utf-8"))
        document["seeds"][0] = 5
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("missing or altered", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_coherently_rewritten_suite_still_fails_to_re_derive(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        path = self.suite_file("v2")
        document = json.loads(path.read_text(encoding="utf-8"))
        document["seeds"][0] = 5
        payload = json.dumps(document, indent=2, sort_keys=True) + "\n"
        path.write_text(payload, encoding="utf-8")
        line1 = dict(self.line1)
        line1["suite"] = dict(line1["suite"], sha256=decide.sha256_of(path))
        log = self.methods / "decisions.jsonl"
        log.write_text(json.dumps(line1, sort_keys=True) + "\n", encoding="utf-8")
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("does not re-derive", err)
        self.assertEqual(len(self.lines()), 1)

    def test_screening_evidence_edited_after_the_freeze_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        write_result(self.visible_path("v2"), shifted(PARENT, DELTAS_CLEAR))
        self.write_visible_receipt("v2")
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("changed since the provisional line was written", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_candidate_edited_after_the_freeze_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        write_tree(self.methods / "main", DOWN)
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("main/ does not match versions/v2", err)
        write_tree(self.methods / "versions" / "v2", DOWN)
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("changed", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_parent_edited_after_the_screening_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        write_tree(self.methods / "versions" / "v1", DOWN)
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("versions/v1 changed after the screening that froze it", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_wrong_parent_or_version_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        write_tree(self.methods / "versions" / "v0", UP)
        self.assertEqual(self.gate("v2", "v0", "--replicates", "v2"), 2)
        self.assertEqual(self.gate("v2", "v1", "--replicates", "v1"), 2)
        self.assertEqual(len(self.lines()), 1)


if __name__ == "__main__":
    unittest.main()
