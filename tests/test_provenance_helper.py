"""The mounted provenance helper: records that build, refusals that name themselves, and interruption at
every checkpoint.

The helper is exercised the way the agent runs it, as a subprocess against a rollout root assembled
from the fixture task (its evaluator, engine and public seeds, with a stand-in self-check that writes the
same result file). After each scenario the record producer runs over the methods tree and the verifier
over the record, so every assertion here is about what a rollout's job directory would yield.

Run: python3 -m unittest tests.test_provenance_helper
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HELPER = REPO / "runbook" / "provenance.py"
TASK_ENV = REPO / "fixtures" / "task2048" / "environment"
STARTER = REPO / "fixtures" / "task2048" / "policy_weak" / "policy.py"
VARIANT = REPO / "fixtures" / "task2048" / "policy_variant" / "policy.py"
CANDIDATE = 'def choose_move(board):\n    return "LEFT"\n'
SELFCHECK = textwrap.dedent('''
    """Stand-in for the task's self-check: the same evaluator and result file, no CPU arming."""
    import json, pathlib
    from evaluate import evaluate
    ROOT = pathlib.Path(__file__).resolve().parent
    result = evaluate(ROOT / "methods/main/policy.py", ROOT / "visible_seeds.json")
    (ROOT / "visible_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\\n")
    print(json.dumps({k: v for k, v in result.items() if k != "instances"}, sort_keys=True))
''')


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bc = load("build_capsule_for_helper_tests", REPO / "profile" / "build_capsule.py")
vc = load("verify_capsule_for_helper_tests", REPO / "profile" / "verify_capsule.py")
td = load("treedigest_for_helper_tests", REPO / "gate" / "treedigest.py")


def make_root(case: unittest.TestCase) -> Path:
    """A rollout root like /app: evaluator, engine, seeds, stand-in self-check, starter main/."""
    temp = tempfile.TemporaryDirectory()
    case.addCleanup(temp.cleanup)
    root = Path(temp.name) / "app"
    root.mkdir()
    for name in ("evaluate.py", "game2048.py", "visible_seeds.json"):
        shutil.copy(TASK_ENV / name, root / name)
    (root / "selfcheck.py").write_text(SELFCHECK, encoding="utf-8")
    (root / "methods" / "main").mkdir(parents=True)
    shutil.copy(STARTER, root / "methods" / "main" / "policy.py")
    return root


def run(root: Path, *args: str, kill_after: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PROVENANCE_ROOT": str(root), "ARB_AGENT_TIMEOUT_SEC": "340"}
    env.pop("PROVENANCE_KILL_AFTER", None)
    if kill_after:
        env["PROVENANCE_KILL_AFTER"] = kill_after
    return subprocess.run([sys.executable, str(HELPER), *args], env=env, capture_output=True, text=True)


def write_main(root: Path, text: str) -> None:
    (root / "methods" / "main" / "policy.py").write_text(text, encoding="utf-8")


def build(case: unittest.TestCase, root: Path):
    """Run the record producer over the root's methods tree inside a copy of the golden job directory.

    Returns (capsule, None) when it builds and (None, reason) when it refuses.
    """
    temp = tempfile.TemporaryDirectory()
    case.addCleanup(temp.cleanup)
    shutil.copytree(REPO / "fixtures" / "valid", temp.name, dirs_exist_ok=True)
    job, task = Path(temp.name) / "job", Path(temp.name) / "task"
    shutil.rmtree(job / "artifacts" / "app" / "methods")
    shutil.copytree(root / "methods", job / "artifacts" / "app" / "methods", symlinks=True)
    try:
        capsule = bc.build_capsule(job, task, "0.1@bc36dadb405b", "helper-test", "claude-haiku-4-5",
                                   "claude-code", [])
    except bc.ProducerError as exc:
        return None, str(exc).removeprefix("producer_error: ")
    path = job / "capsule.json"
    path.write_text(json.dumps(capsule, indent=1), encoding="utf-8")
    result = vc.verify_capsule(path, artifact_root=job, require_complete=True)
    case.assertEqual(result["integrity"], "pass", result)
    case.assertEqual(result["coverage"], "complete", result)
    return capsule, None


def session(case: unittest.TestCase, root: Path) -> None:
    """init, a kept variant, a reverted candidate: the scenario most tests start from."""
    case.assertEqual(run(root, "init").returncode, 0)
    shutil.copy(VARIANT, root / "methods" / "main" / "policy.py")
    case.assertEqual(run(root, "evaluate", "--change", "variant policy").returncode, 0)
    case.assertEqual(run(root, "decide", "v1", "kept").returncode, 0)
    write_main(root, CANDIDATE)
    case.assertEqual(run(root, "evaluate", "--change", "always LEFT").returncode, 0)
    case.assertEqual(run(root, "decide", "v2", "reverted").returncode, 0)


class TheRecordBuilds(unittest.TestCase):
    def test_a_session_yields_a_complete_verified_record(self):
        root = make_root(self)
        session(self, root)
        capsule, reason = build(self, root)
        self.assertIsNone(reason)
        assert capsule is not None
        by_id = {v["version_id"]: v for v in capsule["versions"]}
        self.assertEqual([v["version_id"] for v in capsule["versions"]], ["v0", "v1", "v2"])
        self.assertEqual(by_id["v0"]["status"], "baseline")
        self.assertEqual(by_id["v1"]["status"], "submitted")  # the kept head is what main/ holds
        self.assertEqual(by_id["v2"]["status"], "reverted")
        self.assertEqual(by_id["v1"]["parent_ids"], ["v0"])
        self.assertEqual(by_id["v2"]["parent_ids"], ["v1"])
        for vid in ("v0", "v1", "v2"):
            self.assertIn("visible", by_id[vid], vid)
            self.assertTrue((root / "methods" / "results" / vid / "selfcheck.json").is_file(), vid)

    def test_finalize_drops_undecided_edits_and_leaves_main_equal_to_the_head(self):
        root = make_root(self)
        session(self, root)
        write_main(root, 'def choose_move(board):\n    return "RIGHT"\n')
        _, reason = build(self, root)
        self.assertEqual(reason, "submitted_not_snapshotted")
        self.assertEqual(run(root, "finalize").returncode, 0)
        capsule, reason = build(self, root)
        self.assertIsNone(reason)
        assert capsule is not None
        self.assertEqual({v["version_id"] for v in capsule["versions"]}, {"v0", "v1", "v2"})
        self.assertEqual((root / "methods" / "main" / "policy.py").read_text(), VARIANT.read_text())

    def test_finalize_keeps_a_pending_candidate_when_told_to(self):
        root = make_root(self)
        session(self, root)
        write_main(root, 'def choose_move(board):\n    return "DOWN"\n')
        self.assertEqual(run(root, "evaluate", "--change", "always DOWN").returncode, 0)
        self.assertEqual(run(root, "finalize", "--keep", "v3").returncode, 0)
        capsule, reason = build(self, root)
        self.assertIsNone(reason)
        assert capsule is not None
        self.assertEqual({v["version_id"]: v["status"] for v in capsule["versions"]}["v3"], "submitted")

    def test_evaluate_from_a_working_copy_places_it_in_main(self):
        root = make_root(self)
        self.assertEqual(run(root, "init", "--no-evaluate").returncode, 0)
        work = root / "work.py"
        work.write_text(CANDIDATE, encoding="utf-8")
        self.assertEqual(run(root, "evaluate", "--from", str(work), "--change", "from a working copy").returncode, 0)
        self.assertEqual((root / "methods" / "main" / "policy.py").read_text(), CANDIDATE)
        self.assertEqual(run(root, "decide", "v1", "kept").returncode, 0)
        capsule, reason = build(self, root)
        self.assertIsNone(reason)
        assert capsule is not None
        self.assertEqual({v["version_id"]: v["status"] for v in capsule["versions"]}["v1"], "submitted")

    def test_the_digest_is_the_repositorys_method_tree_digest(self):
        root = make_root(self)
        self.assertEqual(run(root, "init", "--no-evaluate").returncode, 0)
        state = json.loads((root / "methods" / ".provenance" / "state.json").read_text())
        self.assertEqual(state["digests"]["v0"], td.method_tree_sha256(root / "methods" / "versions" / "v0"))

    def test_the_log_blocks_read_as_the_producer_reads_them(self):
        root = make_root(self)
        session(self, root)
        lines = (root / "methods" / "experiment_log.md").read_text().splitlines()
        blocks = bc.get_version_blocks(lines)
        self.assertEqual(list(blocks), ["v0", "v1", "v2"])
        for vid, expected in (("v0", "baseline"), ("v1", "kept"), ("v2", "reverted")):
            line_no, block = blocks[vid]
            self.assertEqual(bc.get_status(block, vid, bc.get_table_status(lines, line_no - 1)), expected)
        self.assertEqual(bc.get_block_parents(blocks["v2"][1], "v2"), ["v1"])
        self.assertEqual(bc.get_block_parents(blocks["v0"][1], "v0"), [])


class RefusalsNameThemselves(unittest.TestCase):
    def test_before_init(self):
        root = make_root(self)
        proc = run(root, "evaluate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not_initialized", proc.stderr)

    def test_a_second_candidate_waits_for_the_decision(self):
        root = make_root(self)
        self.assertEqual(run(root, "init", "--no-evaluate").returncode, 0)
        write_main(root, CANDIDATE)
        self.assertEqual(run(root, "evaluate").returncode, 0)
        write_main(root, 'def choose_move(board):\n    return "DOWN"\n')
        proc = run(root, "evaluate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("pending_decision:v1", proc.stderr)
        self.assertEqual(run(root, "decide", "v2", "kept").returncode, 2)

    def test_nothing_new_to_evaluate_is_not_a_snapshot(self):
        root = make_root(self)
        self.assertEqual(run(root, "init", "--no-evaluate").returncode, 0)
        proc = run(root, "evaluate")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("identical to the head", proc.stdout)
        self.assertEqual(sorted(p.name for p in (root / "methods" / "versions").iterdir()), ["v0"])

    def test_main_equal_to_an_older_snapshot_is_refused_with_the_restore_hint(self):
        root = make_root(self)
        session(self, root)
        shutil.copy(STARTER, root / "methods" / "main" / "policy.py")
        proc = run(root, "evaluate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("main_equals_snapshot:v0", proc.stderr)
        self.assertEqual(run(root, "restore", "v0").returncode, 0)
        capsule, reason = build(self, root)
        self.assertIsNone(reason)
        assert capsule is not None
        self.assertEqual({v["version_id"]: v["status"] for v in capsule["versions"]}["v0"], "submitted")

    def test_init_after_hand_made_snapshots_is_refused(self):
        root = make_root(self)
        (root / "methods" / "versions" / "v3").mkdir(parents=True)
        shutil.copy(STARTER, root / "methods" / "versions" / "v3" / "policy.py")
        proc = run(root, "init", "--no-evaluate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("init_after_changes", proc.stderr)

    def test_a_non_python_file_in_main_is_refused(self):
        root = make_root(self)
        (root / "methods" / "main" / "notes.txt").write_text("x", encoding="utf-8")
        proc = run(root, "init", "--no-evaluate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("non_python_file_in_tree:notes.txt", proc.stderr)


class InterruptionAtEveryCheckpoint(unittest.TestCase):
    """The helper is stopped right after each named step; the producer's outcome is asserted, then the
    agent's next natural command is run and the record must build."""

    def assert_outcome(self, root: Path, expected: str | None) -> None:
        capsule, reason = build(self, root)
        if expected is None:
            self.assertIsNone(reason, reason)
            self.assertIsNotNone(capsule)
        else:
            self.assertEqual(reason, expected)

    def test_init(self):
        # (checkpoint, producer outcome right after the stop)
        for checkpoint, expected in (("staged", "missing_versions_root"), ("renamed", "missing_log"),
                                     ("appended", None), ("state_saved", None), ("scored", None)):
            with self.subTest(checkpoint=checkpoint):
                root = make_root(self)
                proc = run(root, "init", kill_after=checkpoint)
                self.assertEqual(proc.returncode, 3, checkpoint)
                if checkpoint == "staged":
                    # nothing reached versions/ yet; the producer sees a rollout without snapshots
                    self.assertFalse((root / "methods" / "versions").exists())
                else:
                    self.assert_outcome(root, expected)
                # the agent runs init again, as the overlay tells it to when in doubt
                self.assertEqual(run(root, "init").returncode, 0)
                self.assert_outcome(root, None)
                self.assertEqual(sorted(p.name for p in (root / "methods" / "versions").iterdir()), ["v0"])

    def test_evaluate(self):
        for checkpoint, expected in (("staged", "submitted_not_snapshotted"), ("renamed", "log_missing_version:v2"),
                                     ("appended", None), ("state_saved", None), ("scored", None)):
            with self.subTest(checkpoint=checkpoint):
                root = make_root(self)
                self.assertEqual(run(root, "init", "--no-evaluate").returncode, 0)
                shutil.copy(VARIANT, root / "methods" / "main" / "policy.py")
                self.assertEqual(run(root, "evaluate").returncode, 0)
                self.assertEqual(run(root, "decide", "v1", "kept").returncode, 0)
                write_main(root, CANDIDATE)
                proc = run(root, "evaluate", "--change", "always LEFT", kill_after=checkpoint)
                self.assertEqual(proc.returncode, 3, checkpoint)
                self.assert_outcome(root, expected)
                # recovery: the agent decides (a stop before the block exists is adopted first) or re-evaluates
                if checkpoint == "staged":
                    self.assertEqual(run(root, "evaluate", "--change", "always LEFT").returncode, 0)
                proc = run(root, "decide", "v2", "reverted")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assert_outcome(root, None)
                versions = sorted(p.name for p in (root / "methods" / "versions").iterdir())
                self.assertEqual(versions, ["v0", "v1", "v2"])
                self.assertEqual((root / "methods" / "main" / "policy.py").read_text(), VARIANT.read_text())

    def test_decide_reverted(self):
        for checkpoint, expected in (("status_rewritten", None), ("state_saved", None),
                                     ("main_moved_aside", "missing_main"), ("restored", None)):
            with self.subTest(checkpoint=checkpoint):
                root = make_root(self)
                self.assertEqual(run(root, "init", "--no-evaluate").returncode, 0)
                write_main(root, CANDIDATE)
                self.assertEqual(run(root, "evaluate").returncode, 0)
                proc = run(root, "decide", "v1", "reverted", kill_after=checkpoint)
                self.assertEqual(proc.returncode, 3, checkpoint)
                self.assert_outcome(root, expected)
                # recovery: finalize settles whatever is pending and restores the head
                proc = run(root, "finalize")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assert_outcome(root, None)
                self.assertEqual((root / "methods" / "main" / "policy.py").read_text(), STARTER.read_text())
                lines = (root / "methods" / "experiment_log.md").read_text().splitlines()
                _, block = bc.get_version_blocks(lines)["v1"]
                self.assertEqual(bc.get_status(block, "v1"), "reverted")

    def test_decide_kept(self):
        for checkpoint in ("status_rewritten", "state_saved"):
            with self.subTest(checkpoint=checkpoint):
                root = make_root(self)
                self.assertEqual(run(root, "init", "--no-evaluate").returncode, 0)
                write_main(root, CANDIDATE)
                self.assertEqual(run(root, "evaluate").returncode, 0)
                proc = run(root, "decide", "v1", "kept", kill_after=checkpoint)
                self.assertEqual(proc.returncode, 3, checkpoint)
                self.assert_outcome(root, None)
                proc = run(root, "finalize", "--keep", "v1") if checkpoint == "status_rewritten" else run(root, "status")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                capsule, reason = build(self, root)
                self.assertIsNone(reason)
                assert capsule is not None
                self.assertEqual({v["version_id"]: v["status"] for v in capsule["versions"]}["v1"], "submitted")


if __name__ == "__main__":
    unittest.main()
