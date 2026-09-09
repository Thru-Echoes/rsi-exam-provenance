"""The sealed-suite retrospective: the grader's reward mapping and snapshots scored on the sealed seeds.

Run: python3 -m unittest tests.test_sealed_eval
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "gate" / "sealed_eval.py"
FIXTURE = REPO / "fixtures" / "task2048"
GATED = REPO / "fixtures" / "gated_mode"
sys.path.insert(0, str(REPO / "gate"))


def load():
    spec = importlib.util.spec_from_file_location("sealed_eval_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


se = load()

# Three per-seed values from a real verifier output of this task (the Opus probe rollout), plus the
# starter policy, whose raw score equals its baseline anchor on every seed.
REAL = [(176168.0, (1620.0, 81136.0), 0.6960579460302295), (40508.0, (1048.0, 108116.0), 0.47295462804492555),
        (61436.0, (848.0, 47744.0), 0.633226397436444), (1620.0, (1620.0, 81136.0), 0.0)]


class TheGradersMapping(unittest.TestCase):
    def test_real_verifier_values_are_reproduced_exactly(self):
        for metric, anchors, expected in REAL:
            self.assertEqual(se.reward_of(metric, anchors), expected)

    def test_shape_of_the_curve(self):
        self.assertEqual(se.reward_of(500.0, (1000.0, 4000.0)), 0.0)
        self.assertAlmostEqual(se.reward_of(4000.0, (1000.0, 4000.0)), 0.6)
        self.assertAlmostEqual(se.reward_of(2000.0, (1000.0, 4000.0)), 0.3)
        self.assertGreater(se.reward_of(16000.0, (1000.0, 4000.0)), 0.6)
        self.assertLessEqual(se.reward_of(1e12, (1000.0, 4000.0)), 1.0)
        with self.assertRaises(ValueError):
            se.reward_of(10.0, (5.0, 5.0))


def make_task(tmp: Path) -> Path:
    """A task directory: the fixture environment plus a sealed file in the published shape."""
    task = tmp / "task"
    shutil.copytree(FIXTURE / "environment", task / "environment", ignore=shutil.ignore_patterns("__pycache__"))
    (task / "tests").mkdir()
    (task / "tests" / "heldout_seeds.json").write_text(json.dumps({"max_moves": 300, "seeds": [
        {"seed": 11, "baseline": 500.0, "frontier": 3000.0}, {"seed": 22, "baseline": 500.0, "frontier": 3000.0},
        {"seed": 33, "baseline": 500.0, "frontier": 3000.0}]}), encoding="utf-8")
    return task


def make_profile(tmp: Path, task: Path) -> Path:
    from gate_fixtures import write_profile  # noqa: PLC0415
    profile = tmp / "profile.json"
    write_profile(profile, confirmation={"floor": 4, "max_seeds": 8, "max_moves": 300, "cpu_seconds_per_game": 225},
                  evaluator={name: __import__("treedigest").file_sha256(task / "environment" / name)
                             for name in ("evaluate.py", "game2048.py")},
                  visible_suite_sha256=__import__("treedigest").file_sha256(task / "environment" / "visible_seeds.json"))
    return profile


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


class SnapshotsAreScoredOnTheSealedSeeds(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        sys.path.insert(0, str(REPO / "tests"))
        self.task = make_task(self.tmp)
        self.profile = make_profile(self.tmp, self.task)

    def test_two_policies_are_measured_and_the_run_is_deterministic(self):
        outs = []
        for name in ("a", "b"):
            out = self.tmp / f"{name}.json"
            proc = run("--task-dir", str(self.task), "--profile", str(self.profile), "--workdir", str(self.tmp / f"w{name}"),
                       "--output", str(out), "--allow-host-execution",
                       "--snapshot", f"weak={FIXTURE / 'policy_weak'}", "--snapshot", f"variant={FIXTURE / 'policy_variant'}")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outs.append(json.loads(out.read_text(encoding="utf-8")))
        report = outs[0]
        self.assertEqual(report["schema"], "rsi-exam-sealed-retrospective/v1")
        self.assertEqual(report["sealed_suite"], {"seeds": 3, "sha256": report["sealed_suite"]["sha256"], "max_moves": 300,
                                                  "anchors": True})
        self.assertEqual(report["summary"], {"snapshots": 2, "measured": 2, "unmeasured": 0})
        for row in report["snapshots"]:
            self.assertTrue(row["measured"])
            self.assertEqual([g["seed"] for g in row["per_seed"]], [11, 22, 33])
            self.assertTrue(all(0.0 <= g["reward"] <= 1.0 for g in row["per_seed"]))
            self.assertEqual(row["reward"], round(sum(g["reward"] for g in row["per_seed"]) / 3, 8))
        self.assertEqual([r["per_seed"] for r in outs[0]["snapshots"]], [r["per_seed"] for r in outs[1]["snapshots"]])
        self.assertEqual(len(report["limits"]), 5)
        self.assertEqual(report["inputs"]["execution_model"], "same-process-evaluator")

    def test_a_record_joins_versions_with_their_parents(self):
        job = self.tmp / "job"
        shutil.copytree(GATED / "job", job)
        out = self.tmp / "r.json"
        proc = run("--task-dir", str(self.task), "--profile", str(self.profile), "--workdir", str(self.tmp / "w"),
                   "--output", str(out), "--allow-host-execution", "--job-dir", str(job), "--capsule", str(job / "capsule.json"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in report["snapshots"]], ["v1", "v2", "submission"])
        self.assertEqual(report["snapshots"][2]["source"], "artifacts/app/methods/main")
        self.assertEqual(report["job"], f"{job.parent.name}/job")
        by_id = {v["version_id"]: v for v in report["versions"]}
        # v2 is v1's policy unchanged, so the paired sealed delta is zero on every seed.
        self.assertEqual(by_id["v2"]["parent_ids"], ["v1"])
        self.assertEqual(by_id["v2"]["delta_vs_parent"]["mean"], 0.0)
        self.assertEqual(by_id["v2"]["reward_delta_vs_parent"], 0.0)
        self.assertIsNone(by_id["v1"]["delta_vs_parent"])
        self.assertEqual(by_id["v1"]["status"], "submitted")

    def test_a_policy_that_cannot_finish_is_unmeasured_not_scored(self):
        slow = self.tmp / "slow"
        slow.mkdir()
        (slow / "policy.py").write_text("import time\n\ndef choose_move(board):\n    time.sleep(30)\n    return 'UP'\n")
        out = self.tmp / "s.json"
        proc = run("--task-dir", str(self.task), "--profile", str(self.profile), "--workdir", str(self.tmp / "ws"),
                   "--output", str(out), "--allow-host-execution", "--wall-seconds", "3",
                   "--snapshot", f"slow={slow}", "--snapshot", f"weak={FIXTURE / 'policy_weak'}")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        rows = {r["id"]: r for r in report["snapshots"]}
        self.assertFalse(rows["slow"]["measured"])
        self.assertEqual(rows["slow"]["failure"], "wall_clock_exceeded")
        self.assertIsNone(rows["slow"]["reward"])
        self.assertTrue(rows["weak"]["measured"])
        self.assertEqual(report["summary"]["unmeasured"], 1)

    def test_refusals(self):
        proc = run("--task-dir", str(self.task), "--profile", str(self.profile), "--workdir", str(self.tmp / "w1"),
                   "--output", str(self.tmp / "x.json"), "--snapshot", f"weak={FIXTURE / 'policy_weak'}")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--container", proc.stderr)
        (self.tmp / "w2" / "methods").mkdir(parents=True)
        proc = run("--task-dir", str(self.task), "--profile", str(self.profile), "--workdir", str(self.tmp / "w2"),
                   "--output", str(self.tmp / "y.json"), "--allow-host-execution", "--snapshot", f"weak={FIXTURE / 'policy_weak'}")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not fresh", proc.stderr)


if __name__ == "__main__":
    unittest.main()
