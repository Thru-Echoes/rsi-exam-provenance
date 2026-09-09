"""Tests for gate/evaluate_suite.py: the evaluation runner and its receipts.

The runner arms ``RLIMIT_CPU`` for its own process, so every test here runs it in a subprocess.
Metric, CPU budget, and evaluator digests come from a real profile file built per test class from
the fixture task's own digests; the runner is never handed a hand-written digest.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import evaluate_suite  # noqa: E402
import treedigest  # noqa: E402
from tests.gate_fixtures import (NO_CACHES, POLICY_WEAK, TASK_ROOT, copy_policy, real_evaluator,  # noqa: E402
                                 real_visible_suite_sha, run_runner, write_profile)

TWO_SEEDS = {"max_moves": 300, "seeds": [11, 22]}
ONE_SEED = {"max_moves": 300, "seeds": [11]}
RECEIPT_KEYS = {"schema", "metric", "profile_sha256", "policy_method_tree_sha256", "suite_sha256", "max_moves",
                "result_sha256", "evaluator", "games", "cpu_seconds", "cpu_budget_per_game", "python", "timestamp"}


def write_suite(path: Path, document: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


class RunnerCase(unittest.TestCase):
    """A temporary root with a real profile, the two-seed suite, and a cache-free copy of the weak policy."""

    profile_overrides: dict = {}

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.profile = self.root / "gate" / "profile.json"
        self.profile_sha = write_profile(self.profile, evaluator=real_evaluator(),
                                         visible_suite_sha256=real_visible_suite_sha(), **self.profile_overrides)
        self.suite = write_suite(self.root / "suite.json", TWO_SEEDS)
        self.policy = copy_policy(POLICY_WEAK, self.root / "policy_weak")
        self.output = self.root / "results" / "v1" / "replication" / "parent_result.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_weak(self, *extra: str, policy: Path | None = None, suite: Path | None = None,
                 output: Path | None = None, task_root: Path | None = None, profile: Path | None = None,
                 env: dict[str, str] | None = None):
        return run_runner("--profile", str(profile or self.profile), "--task-root", str(task_root or TASK_ROOT),
                          "--policy-dir", str(policy or self.policy), "--suite", str(suite or self.suite),
                          "--output", str(output or self.output), *extra, env=env)


class TestSubmissionSafety(RunnerCase):
    """The size cap the grader enforces, and the optional safety report the in-rollout helper reads."""

    def test_a_safety_report_records_the_slowest_move_and_the_policy_size(self) -> None:
        report = self.root / "results" / "v1" / "visible_safety.json"
        proc = self.run_weak("--safety-report", str(report))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(set(doc), {"schema", "policy_method_tree_sha256", "policy_bytes", "games", "cpu_seconds",
                                    "cpu_seconds_per_game", "max_move_seconds", "result_sha256", "timestamp"})
        self.assertEqual(doc["schema"], "rsi-exam-gate-safety/v1")
        self.assertEqual(doc["policy_method_tree_sha256"], treedigest.method_tree_sha256(POLICY_WEAK))
        self.assertEqual(doc["policy_bytes"], (self.policy / "policy.py").stat().st_size)
        self.assertEqual(doc["games"], 2)
        self.assertGreater(doc["max_move_seconds"], 0.0)
        self.assertLess(doc["max_move_seconds"], 1.0)
        self.assertEqual(doc["result_sha256"], treedigest.file_sha256(self.output))
        # The result and the receipt are what they are without the flag: the report is a third file.
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertNotIn("max_move_seconds", result)
        receipt = json.loads(self.output.with_name("parent_result.receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(set(receipt), RECEIPT_KEYS)
        self.assertEqual(result["mean_score"], 1400.0)

    def test_a_safety_report_is_evidence_and_is_written_once(self) -> None:
        inside_tree = self.policy / "visible_safety.json"
        proc = self.run_weak("--safety-report", str(inside_tree))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("must live under a results directory", proc.stderr)
        self.assertFalse(self.output.exists())
        report = self.root / "results" / "v1" / "visible_safety.json"
        self.assertEqual(self.run_weak("--safety-report", str(report)).returncode, 0)
        again = self.run_weak("--safety-report", str(report),
                              output=self.root / "results" / "v1" / "replication" / "candidate_result.json")
        self.assertEqual(again.returncode, 2)
        self.assertIn("safety report already exists", again.stderr)

    def test_an_oversized_policy_is_refused_before_anything_runs(self) -> None:
        big = self.root / "policy_big"
        big.mkdir()
        (big / "policy.py").write_bytes((self.policy / "policy.py").read_bytes() + b"#" * 10_000_001 + b"\n")
        proc = self.run_weak(policy=big)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("over the grader's 10,000,000 byte cap", proc.stderr)
        self.assertFalse(self.output.exists())


class TestRunnerResultAndReceipt(RunnerCase):
    def test_writes_the_result_in_selfcheck_shape_and_a_binding_receipt(self) -> None:
        proc = self.run_weak()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        for key in ("mean_score", "median_score", "mean_max_tile", "valid_fraction", "instances",
                    "cpu_seconds", "cpu_seconds_per_game", "cpu_budget_per_game"):
            self.assertIn(key, result)
        self.assertEqual([i["seed"] for i in result["instances"]], [11, 22])
        self.assertEqual(result["mean_score"], 1400.0)
        self.assertEqual(result["instances"][0]["score"], 1892)
        self.assertEqual(result["valid_fraction"], 1.0)
        self.assertEqual(result["cpu_budget_per_game"], 225)

        receipt_path = self.output.with_name("parent_result.receipt.json")
        self.assertEqual(evaluate_suite.receipt_path_for(self.output), receipt_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(set(receipt), RECEIPT_KEYS)
        self.assertEqual(receipt["schema"], "rsi-exam-gate-receipt/v1")
        self.assertEqual(receipt["metric"], "per_seed_2048_score")
        self.assertEqual(receipt["profile_sha256"], treedigest.file_sha256(self.profile))
        self.assertEqual(receipt["profile_sha256"], self.profile_sha)
        self.assertEqual(receipt["policy_method_tree_sha256"], treedigest.method_tree_sha256(POLICY_WEAK))
        self.assertEqual(receipt["suite_sha256"], treedigest.file_sha256(self.suite))
        self.assertEqual(receipt["max_moves"], 300)
        self.assertEqual(receipt["result_sha256"], treedigest.file_sha256(self.output))
        self.assertEqual(receipt["evaluator"], real_evaluator())
        self.assertEqual(receipt["games"], 2)
        self.assertEqual(receipt["cpu_budget_per_game"], 225)
        self.assertTrue(receipt["python"].startswith(f"{sys.version_info.major}.{sys.version_info.minor}"))
        self.assertTrue(receipt["timestamp"].endswith("+00:00"))

        self.assertEqual(list(self.policy.rglob("__pycache__")), [],
                         "the runner must not write bytecode into a policy tree")
        self.assertEqual(json.loads(proc.stdout.strip().splitlines()[-1]), receipt)

    def test_fixed_timestamp_and_an_explicit_receipt_path(self) -> None:
        env = dict(os.environ, DECIDE_FIXED_TIMESTAMP="2026-09-05T18:00:00+00:00")
        receipt_path = self.root / "results" / "v1" / "replication" / "elsewhere.json"
        proc = self.run_weak("--receipt", str(receipt_path), env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["timestamp"], "2026-09-05T18:00:00+00:00")
        self.assertFalse(self.output.with_name("parent_result.receipt.json").exists())

    def test_an_existing_output_is_never_overwritten(self) -> None:
        self.assertEqual(self.run_weak().returncode, 0)
        before = self.output.read_bytes()
        receipt_before = self.output.with_name("parent_result.receipt.json").read_bytes()
        second = self.run_weak()
        self.assertEqual(second.returncode, 2)
        self.assertIn("already exists", second.stderr)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(self.output.with_name("parent_result.receipt.json").read_bytes(), receipt_before)


class TestRunnerRefusals(RunnerCase):
    def assert_refused(self, proc, *, message: str) -> None:
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn(message, proc.stderr)
        self.assertFalse(self.output.exists())

    def test_output_inside_a_policy_tree_is_refused(self) -> None:
        for component in ("versions", "main"):
            with self.subTest(component=component):
                target = self.root / "methods" / component / "v1" / "r.json"
                self.assert_refused(self.run_weak(output=target), message="must not live in a policy tree")
                self.assertFalse(target.exists())

    def test_output_outside_a_results_directory_is_refused(self) -> None:
        target = self.root / "elsewhere" / "r.json"
        self.assert_refused(self.run_weak(output=target), message="must live under a results directory")
        self.assertFalse(target.exists())

    def test_a_symlinked_results_directory_is_refused(self) -> None:
        real = self.root / "real_evidence"
        real.mkdir()
        link_root = self.root / "linked"
        link_root.mkdir()
        os.symlink(real, link_root / "results")
        target = link_root / "results" / "v1" / "r.json"
        self.assert_refused(self.run_weak(output=target), message="goes through a symlink")
        self.assertEqual(list(real.iterdir()), [])

    def test_a_missing_policy_directory_is_refused(self) -> None:
        self.assert_refused(self.run_weak(policy=self.root / "absent"), message="policy.py not found")

    def test_an_evaluator_that_differs_from_the_profile_is_refused(self) -> None:
        drifted = self.root / "drifted_task"
        shutil.copytree(TASK_ROOT, drifted, ignore=NO_CACHES)
        (drifted / "evaluate.py").write_text(
            (drifted / "evaluate.py").read_text(encoding="utf-8") + "# an edit the profile does not pin\n",
            encoding="utf-8")
        self.assert_refused(self.run_weak(task_root=drifted),
                            message="differs from the digest the profile pins")

    def test_a_missing_or_empty_suite_is_refused(self) -> None:
        self.assert_refused(self.run_weak(suite=self.root / "absent.json"), message="suite not found")
        empty = write_suite(self.root / "empty.json", {"max_moves": 300, "seeds": []})
        self.assert_refused(self.run_weak(suite=empty), message="unique seeds")

    def test_a_missing_profile_is_refused(self) -> None:
        self.assert_refused(self.run_weak(profile=self.root / "absent.json"), message="profile not found")


class TestRunnerBudgets(RunnerCase):
    profile_overrides = {"confirmation": {"floor": 4, "max_seeds": 8, "max_moves": 300, "cpu_seconds_per_game": 1}}

    def test_cpu_exhaustion_exits_4_and_writes_nothing(self) -> None:
        spinner = self.root / "spinner"
        spinner.mkdir()
        (spinner / "policy.py").write_text("def choose_move(board):\n    while True:\n        pass\n", encoding="utf-8")
        one = write_suite(self.root / "one.json", ONE_SEED)
        proc = self.run_weak(policy=spinner, suite=one)
        self.assertEqual(proc.returncode, 4, proc.stderr)
        self.assertIn("CPU budget", proc.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name("parent_result.receipt.json").exists())

    def test_a_wall_clock_overrun_exits_6_and_writes_nothing(self) -> None:
        sleeper = self.root / "sleeper"
        sleeper.mkdir()
        (sleeper / "policy.py").write_text(
            "import time\n\n\ndef choose_move(board):\n    time.sleep(30)\n    return 'UP'\n", encoding="utf-8")
        one = write_suite(self.root / "one.json", ONE_SEED)
        started = time.monotonic()
        proc = self.run_weak("--wall-seconds", "2", policy=sleeper, suite=one)
        self.assertEqual(proc.returncode, 6, proc.stderr)
        self.assertLess(time.monotonic() - started, 20.0)
        self.assertIn("wall-clock", proc.stderr)
        self.assertFalse(self.output.exists())


class TestRunnerEvaluatorOutcomes(RunnerCase):
    def test_an_invalid_game_exits_5_and_writes_nothing(self) -> None:
        sideways = self.root / "sideways"
        sideways.mkdir()
        (sideways / "policy.py").write_text("def choose_move(board):\n    return 'SIDEWAYS'\n", encoding="utf-8")
        proc = self.run_weak(policy=sideways)
        self.assertEqual(proc.returncode, 5, proc.stderr)
        self.assertIn("invalid game", proc.stderr)
        self.assertFalse(self.output.exists())

    def test_an_evaluator_that_raises_exits_1_and_writes_nothing(self) -> None:
        nameless = self.root / "nameless"
        nameless.mkdir()
        (nameless / "policy.py").write_text("VALUE = 1\n", encoding="utf-8")
        proc = self.run_weak(policy=nameless)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("choose_move", proc.stderr)
        self.assertFalse(self.output.exists())


class TestRunnerShadowing(RunnerCase):
    def test_a_policy_directory_cannot_shadow_the_pinned_evaluator_or_game_engine(self) -> None:
        shadow = self.root / "shadow"
        shadow.mkdir()
        shutil.copy(POLICY_WEAK / "policy.py", shadow / "policy.py")
        (shadow / "evaluate.py").write_text(
            "def evaluate(policy_path, suite_path):\n"
            "    return {'mean_score': 99999.0, 'valid_fraction': 1.0,\n"
            "            'instances': [{'seed': 11, 'score': 99999, 'max_tile': 2048, 'moves': 1, 'error': None},\n"
            "                          {'seed': 22, 'score': 99999, 'max_tile': 2048, 'moves': 1, 'error': None}]}\n",
            encoding="utf-8")
        (shadow / "game2048.py").write_text('raise SystemExit("shadowed")\n', encoding="utf-8")
        proc = self.run_weak(policy=shadow)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(result["mean_score"], 1400.0)
        self.assertEqual({i["seed"]: i["score"] for i in result["instances"]}, {11: 1892, 22: 908})
        receipt = json.loads(self.output.with_name("parent_result.receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["evaluator"], real_evaluator())
        self.assertEqual(receipt["policy_method_tree_sha256"], treedigest.method_tree_sha256(shadow))


class TestReceiptPath(RunnerCase):
    def test_receipt_must_differ_from_the_output(self) -> None:
        proc = self.run_weak("--receipt", str(self.output))
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
