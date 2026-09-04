"""End to end: a gated rollout on the real 2048 evaluator, from screening to the TRACE document.

Uses the fixture task files, the runner in a subprocess (it arms ``RLIMIT_CPU``), the gate in gated
mode, and the converter. Every number asserted here is the deterministic outcome of the fixture
policies on the fixture seeds. Nothing here talks to TRACE or ProofPress; the run report does that.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import decide  # noqa: E402
import seeds as seedsmod  # noqa: E402
import trace_from_decisions as conv  # noqa: E402
import treedigest  # noqa: E402
from tests.gate_fixtures import (POLICY_VARIANT, POLICY_WEAK, TASK_ROOT, VISIBLE_SUITE, copy_policy,  # noqa: E402
                                 real_evaluator, real_visible_suite_sha, run_runner, write_profile)

VISIBLE_SEEDS = json.loads(VISIBLE_SUITE.read_text(encoding="utf-8"))["seeds"]
CONFIRMATION = {"floor": 4, "max_seeds": 8, "max_moves": 10000, "cpu_seconds_per_game": 225}
WEAK_VISIBLE_MEAN = 2060.0
VARIANT_VISIBLE_MEAN = 2386.5
MIN_EFFECT = 0.025 * WEAK_VISIBLE_MEAN  # 51.5 game score


class GatedRollout(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        self.methods.mkdir(parents=True)
        copy_policy(POLICY_WEAK, self.methods / "main")
        copy_policy(POLICY_WEAK, self.methods / "versions" / "v1")
        self.profile = self.methods / "gate" / "profile.json"
        self.profile_sha = write_profile(self.profile, rollout_id="e2e-rollout", confirmation=CONFIRMATION,
                                         min_effect={"kind": "fraction_of_parent_visible_mean", "fraction": 0.025},
                                         replication_key="22" * 32, evaluator=real_evaluator(),
                                         visible_suite_sha256=real_visible_suite_sha())
        self.evaluate("v1", VISIBLE_SUITE, self.methods / "results" / "v1" / "visible_result.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def evaluate(self, version: str, suite: Path, output: Path) -> dict[str, Any]:
        """Run the pinned evaluator on one snapshot; the runner also writes the receipt the gate requires."""
        proc = run_runner("--profile", str(self.profile), "--task-root", str(TASK_ROOT),
                          "--policy-dir", str(self.methods / "versions" / version), "--suite", str(suite),
                          "--output", str(output))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(output.read_text(encoding="utf-8"))

    def install_candidate(self, source: Path, version: str) -> dict[str, Any]:
        shutil.rmtree(self.methods / "main")
        copy_policy(source, self.methods / "main")
        copy_policy(source, self.methods / "versions" / version)
        return self.evaluate(version, VISIBLE_SUITE,
                             self.methods / "results" / version / "visible_result.json")

    def gate(self, *args: str) -> int:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = decide.main(["--methods", str(self.methods), "--profile", str(self.profile), *args])
        self.assertEqual(code, 0, err.getvalue())
        return code

    def lines(self) -> list[dict[str, Any]]:
        return [json.loads(x) for x in (self.methods / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]

    def confirm(self, version: str, parent: str) -> list[int]:
        """Evaluate the parent and the candidate on the suite the provisional line derived."""
        line = self.lines()[-1]
        suite = self.methods / line["suite"]["locator"]
        base = self.methods / "results" / version / "replication"
        self.evaluate(parent, suite, base / "parent_result.json")
        self.evaluate(version, suite, base / "candidate_result.json")
        chosen, _ = seedsmod.read_suite(suite)
        return chosen

    def assert_no_bytecode_in_policy_trees(self) -> None:
        for tree in [self.methods / "main", *sorted((self.methods / "versions").iterdir())]:
            self.assertEqual(list(tree.rglob("__pycache__")), [], f"bytecode written under {tree}")
            self.assertEqual(treedigest.method_files(tree), ["policy.py"])

    def test_an_identical_candidate_is_provisional_then_reverted(self) -> None:
        parent = json.loads((self.methods / "results" / "v1" / "visible_result.json").read_text(encoding="utf-8"))
        self.assertEqual(parent["mean_score"], WEAK_VISIBLE_MEAN)
        candidate = self.install_candidate(POLICY_WEAK, "v2")
        self.assertEqual(candidate["mean_score"], WEAK_VISIBLE_MEAN)

        self.gate("--version", "v2", "--parent", "v1")
        line1 = self.lines()[0]
        self.assertEqual((line1["verdict"], line1["disposition"]), ("inconclusive", "provisional"))
        self.assertEqual(line1["estimate"], 0.0)
        self.assertEqual((line1["interval"]["lower"], line1["interval"]["upper"]), (0.0, 0.0))
        self.assertEqual(line1["sample_size"], 8)
        self.assertAlmostEqual(line1["min_effect"], MIN_EFFECT)
        self.assertEqual(line1["sizing"]["screening_sd"], 0.0)
        self.assertEqual((line1["sizing"]["planned"], line1["sizing"]["size"], line1["sizing"]["exploratory"]),
                         (4, 4, False))
        self.assertEqual(line1["look_index"], 1)
        self.assertEqual(line1["suite"]["derivation"]["size"], 4)
        self.assertEqual(line1["suite"]["derivation"]["max_moves"], 10000)

        suite_seeds = self.confirm("v2", "v1")
        self.assertEqual(len(suite_seeds), 4)
        self.assertFalse(set(suite_seeds) & set(VISIBLE_SEEDS))
        self.gate("--version", "v2", "--parent", "v1", "--replicates", "v2")
        line2 = self.lines()[1]
        self.assertEqual((line2["verdict"], line2["disposition"], line2["estimate"]), ("inconclusive", "revert", 0.0))
        self.assertEqual(line2["sample_size"], 4)
        self.assertEqual([e["role"] for e in line2["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])
        for ref in line2["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
        self.assert_no_bytecode_in_policy_trees()

    def test_the_variant_candidate_is_too_noisy_to_confirm_and_reverts(self) -> None:
        candidate = self.install_candidate(POLICY_VARIANT, "v2")
        self.assertEqual(candidate["mean_score"], VARIANT_VISIBLE_MEAN)
        self.gate("--version", "v2", "--parent", "v1")
        line1 = self.lines()[0]
        self.assertEqual(line1["sample_size"], 8)
        self.assertEqual(line1["estimate"], 326.5)
        self.assertEqual((line1["interval"]["lower"], line1["interval"]["upper"]), (-569.5, 1191.0))
        self.assertAlmostEqual(line1["min_effect"], MIN_EFFECT)
        self.assertEqual(line1["verdict"], "inconclusive")
        # the spread of the per-seed deltas needs far more games than the profile's cap of 8 allows,
        # so the plan is exploratory and the candidate reverts without a confirmation
        self.assertEqual((line1["sizing"]["planned"], line1["sizing"]["size"], line1["sizing"]["exploratory"]),
                         (10586, 8, True))
        self.assertEqual(line1["disposition"], "revert")
        self.assertIsNone(line1["suite"])
        self.assertIsNone(line1["look_index"])
        self.assertFalse((self.methods / "results" / "v2" / "replication").exists())
        self.assertEqual(line1["candidate_method_tree_sha256"], treedigest.method_tree_sha256(POLICY_VARIANT))
        self.assertEqual(line1["parent_method_tree_sha256"], treedigest.method_tree_sha256(POLICY_WEAK))
        self.assertEqual(line1["profile_sha256"], self.profile_sha)

        log = self.methods / "decisions.jsonl"
        doc = conv.build_session(self.lines(), project="rsi-exam-provenance", rollout_id="e2e-rollout",
                                 task="game2048_policy_search", harness="test", model="none",
                                 decision_log_sha256=conv.sha256_of(log))
        self.assertEqual(doc["trace_version"], "0.5.1")
        decision = doc["events"][0]["decision"]
        self.assertEqual(decision["disposition"], "rejected")
        self.assertEqual(decision["revision_note"],
                         "Confirmation would need more games than the profile allows; reverted without confirming.")
        confidence = decision["confidence"]
        self.assertEqual(confidence["confirm_policy"], "always")
        self.assertEqual(confidence["profile_sha256"], self.profile_sha)
        self.assertEqual(confidence["parent_method_tree_sha256"], line1["parent_method_tree_sha256"])
        self.assertEqual(confidence["candidate_method_tree_sha256"], line1["candidate_method_tree_sha256"])
        self.assertEqual([e["role"] for e in confidence["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])
        self.assert_no_bytecode_in_policy_trees()


if __name__ == "__main__":
    unittest.main()
