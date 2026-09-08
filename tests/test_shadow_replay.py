"""Host-side shadow audit: run the gate over a finished rollout's artifacts and compare.

Run: python3 -m unittest tests.test_shadow_replay
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "gate" / "shadow_replay.py"
FIXTURE = REPO / "fixtures" / "gated_mode"
TASK_ROOT = REPO / "fixtures" / "task2048" / "environment"


def load_replay():
    spec = importlib.util.spec_from_file_location("shadow_replay_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: the module declares a dataclass with postponed annotations, and
    # dataclasses resolves those through sys.modules[module.__name__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sr = load_replay()


def run_replay(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def tree_manifest(root: Path) -> list[tuple[str, str, int, str]]:
    """(relpath, kind, mode, digest or link target) for every entry, so a changed byte or mode is a changed manifest."""
    rows: list[tuple[str, str, int, str]] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink():
            rows.append((rel, "symlink", mode, os.readlink(path)))
        elif path.is_dir():
            rows.append((rel, "dir", mode, ""))
        else:
            rows.append((rel, "file", mode, hashlib.sha256(path.read_bytes()).hexdigest()))
    return rows


class ReplayReproducesTheGatedFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.job = self.tmp / "job"
        shutil.copytree(FIXTURE / "job", self.job)
        # The fixture's own profile is the replay configuration the recorded decisions were made under.
        self.profile = self.job / "artifacts/app/methods/gate/profile.json"
        self.assertTrue(self.profile.is_file())

    def replay(self, name: str, *extra: str) -> tuple[subprocess.CompletedProcess[str], Path]:
        out = self.tmp / f"{name}.json"
        proc = run_replay("--job-dir", str(self.job), "--task-dir", str(FIXTURE / "task"),
                          "--task-root", str(TASK_ROOT), "--profile", str(self.profile),
                          "--workdir", str(self.tmp / f"work-{name}"), "--output", str(out),
                          "--allow-host-execution", *extra)
        return proc, out

    def test_the_report_agrees_with_the_recorded_disposition(self):
        proc, out = self.replay("report", "--capsule", str(self.job / "capsule.json"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["schema"], "rsi-exam-shadow-replay/v1")
        self.assertEqual(report["mode"], "capsule")
        self.assertTrue(report["complete"])
        # Locators are relative: the job is named by its last two path components, never by a machine path.
        self.assertEqual(report["job"], f"{self.job.parent.name}/job")
        self.assertNotIn(str(self.tmp), json.dumps(report))
        self.assertEqual(len(report["pairs"]), 1)
        pair = report["pairs"][0]
        self.assertEqual((pair["parent_id"], pair["candidate_id"]), ("v1", "v2"))
        self.assertEqual(pair["parent_source_kind"], "snapshot")
        self.assertEqual(pair["recorded_status"], "reverted")
        gate = pair["gate"]
        # Identical policies: a provisional screening, a four-seed confirmation, a revert on inconclusive.
        self.assertEqual(gate["outcome"], "confirmed_revert")
        self.assertEqual(gate["disposition"], "revert")
        self.assertEqual(gate["screening"]["disposition"], "provisional")
        self.assertEqual(gate["screening"]["sizing"]["planned"], 4)
        self.assertFalse(gate["screening"]["sizing"]["exploratory"])
        self.assertEqual(gate["screening_deltas"]["deltas"], [0.0] * 8)
        self.assertEqual(gate["confirmation"]["disposition"], "revert")
        self.assertEqual(gate["confirmation"]["verdict"], "inconclusive")
        self.assertTrue(pair["agree"])
        self.assertEqual(pair["parent_method_tree_sha256"], report["inputs"]["expected_snapshot_digests"]["v1"])
        self.assertEqual(pair["omitted_files"], {"v1": [], "v2": []})
        self.assertFalse(pair["projected"])
        summary = report["summary"]
        self.assertEqual(summary["record_backed"], {"pairs": 1, "comparable": 1, "agree": 1, "disagree": 0})
        self.assertEqual(summary["task_starter"], {"pairs": 0, "comparable": 0, "agree": 0, "disagree": 0})
        self.assertEqual(summary["outcomes"]["confirmed_revert"], 1)
        self.assertEqual(summary["confirmed"], 1)
        self.assertEqual(summary["failure_policy"], {"action": "revert", "evaluation_failed": 0})
        self.assertEqual((summary["with_disposition"], summary["audit_kind"]), (1, "confirmation-and-screening"))
        self.assertEqual(len(report["limits"]), 7)

    def test_coverage_inputs_and_the_manifest_are_reported(self):
        proc, out = self.replay("coverage", "--capsule", str(self.job / "capsule.json"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["coverage"]["versions_in_record"], 2)
        self.assertEqual(report["coverage"]["versions_with_recorded_action"], 2)
        self.assertEqual(report["coverage"]["pairs_planned"], 1)
        self.assertEqual(report["coverage"]["not_replayable"], [{"candidate_id": "v1", "reason": "lineage_root"}])
        profile = json.loads(self.profile.read_text(encoding="utf-8"))
        inputs = report["inputs"]
        self.assertEqual(inputs["evaluator"], profile["evaluator"])
        self.assertEqual(inputs["visible_suite_sha256"], profile["visible_suite_sha256"])
        self.assertEqual(inputs["container"], {"image": None, "digest": None})
        self.assertEqual(inputs["execution_model"], "same-process-evaluator")
        self.assertIn("decide.py", inputs["gate_sources"])
        self.assertEqual(len(inputs["gate_sources"]["decide.py"]), 64)
        self.assertFalse(inputs["capsule"]["built_here"])
        self.assertEqual(inputs["capsule"]["locator"], "capsule.json")
        manifest = self.tmp / "work-coverage" / "inputs.json"
        self.assertTrue(manifest.is_file())
        self.assertEqual(hashlib.sha256(manifest.read_bytes()).hexdigest(), report["inputs_manifest_sha256"])

    def test_the_job_directory_is_never_written(self):
        before = tree_manifest(self.job)
        self.replay("untouched", "--capsule", str(self.job / "capsule.json"))
        self.assertEqual(before, tree_manifest(self.job))

    def test_a_record_that_fails_verification_is_refused(self):
        policy = self.job / "artifacts/app/methods/versions/v2/policy.py"
        policy.write_text(policy.read_text(encoding="utf-8") + "\n# altered after the record was built\n", encoding="utf-8")
        proc, out = self.replay("tampered", "--capsule", str(self.job / "capsule.json"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("failed verification", proc.stderr)
        self.assertFalse(out.exists())

    def test_pair_mode_names_its_candidate_source(self):
        proc, out = self.replay("pair", "--pair", "v1", "artifacts/app/methods/main", "v9")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["mode"], "pair")
        pair = report["pairs"][0]
        self.assertEqual(pair["candidate_id"], "v9")
        self.assertEqual(pair["candidate_source"], "artifacts/app/methods/main")
        self.assertIsNone(pair["recorded_status"])
        self.assertIsNone(pair["agree"])
        self.assertIn(pair["gate"]["disposition"], ("keep", "revert"))
        self.assertEqual(report["summary"]["undetermined"], 1)

    def test_a_non_python_file_in_a_snapshot_makes_the_pair_not_replayable_by_default(self):
        stray = self.job / "artifacts/app/methods/versions/v2/notes.txt"
        stray.write_text("scratch\n", encoding="utf-8")
        # No --capsule: the record is built from the job directory as it is now, so it verifies.
        proc, out = self.replay("stray")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(report["inputs"]["capsule"]["built_here"])
        pair = report["pairs"][0]
        self.assertEqual(pair["gate"]["outcome"], "not_replayable")
        self.assertIn("non_python_files_in_snapshot:v2: notes.txt", pair["gate"]["refusal"])
        self.assertEqual(pair["omitted_files"]["v2"], [{"path": "notes.txt", "bytes": 8,
                                                        "sha256": hashlib.sha256(b"scratch\n").hexdigest()}])
        self.assertEqual(report["summary"]["record_backed"]["comparable"], 0)

    def test_projection_can_be_allowed_and_is_marked(self):
        (self.job / "artifacts/app/methods/versions/v2/notes.txt").write_text("scratch\n", encoding="utf-8")
        proc, out = self.replay("projected", "--allow-projection")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        pair = report["pairs"][0]
        self.assertTrue(pair["projected"])
        self.assertEqual(pair["gate"]["outcome"], "confirmed_revert")
        self.assertEqual(report["summary"]["projected"], 1)
        self.assertTrue(report["inputs"]["allow_projection"])

    def test_the_workdir_must_be_fresh(self):
        proc, _ = self.replay("fresh", "--capsule", str(self.job / "capsule.json"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        again = run_replay("--job-dir", str(self.job), "--task-dir", str(FIXTURE / "task"), "--task-root", str(TASK_ROOT),
                           "--profile", str(self.profile), "--workdir", str(self.tmp / "work-fresh"),
                           "--output", str(self.tmp / "again.json"), "--allow-host-execution")
        self.assertEqual(again.returncode, 2)
        self.assertIn("not fresh", again.stderr)

    def test_the_inputs_manifest_can_be_written_first_and_enforced_later(self):
        proc, manifest = self.replay("inputs", "--capsule", str(self.job / "capsule.json"), "--inputs-only")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        written = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertIn("expected_snapshot_digests", written)
        self.assertFalse((self.tmp / "work-inputs" / "methods").exists())
        # A different commit or a dirty checkout between writing and enforcing must not matter.
        written["gate_commit"] = "f" * 40
        written["gate_tree_clean"] = False
        manifest.write_text(json.dumps(written, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        proc, out = self.replay("enforced", "--capsule", str(self.job / "capsule.json"), "--expect-inputs", str(manifest),
                                "--anchor-commit", "a" * 40)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(report["complete"])
        # The report carries the committed manifest's digest and the anchor, not a fresh manifest.
        self.assertEqual(report["inputs"]["gate_commit"], "f" * 40)
        self.assertEqual(report["inputs"]["anchor_commit"], "a" * 40)
        self.assertEqual(report["inputs_manifest_sha256"],
                         hashlib.sha256((self.tmp / "work-enforced" / "inputs.json").read_bytes()).hexdigest())
        written["profile_sha256"] = "0" * 64
        manifest.write_text(json.dumps(written), encoding="utf-8")
        proc, _ = self.replay("mismatch", "--capsule", str(self.job / "capsule.json"), "--expect-inputs", str(manifest))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("profile_sha256", proc.stderr)

    def test_an_unusable_snapshot_is_recorded_and_the_run_continues(self):
        empty = self.job / "artifacts/app/methods/scratch"
        empty.mkdir()
        (empty / "README.txt").write_text("nothing to run\n", encoding="utf-8")
        proc, out = self.replay("refused", "--pair", "v1", "artifacts/app/methods/scratch", "v9")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(report["complete"])
        pair = report["pairs"][0]
        self.assertEqual(pair["gate"]["outcome"], "not_replayable")
        self.assertIn("no Python files", pair["gate"]["refusal"])
        self.assertIsNone(pair["gate"]["disposition"])
        self.assertIsNone(pair["agree"])
        self.assertEqual(report["summary"]["outcomes"]["not_replayable"], 1)
        self.assertEqual(report["summary"]["undetermined"], 1)

    def test_host_execution_must_be_asked_for(self):
        proc = run_replay("--job-dir", str(self.job), "--task-dir", str(FIXTURE / "task"), "--profile", str(self.profile),
                          "--workdir", str(self.tmp / "w-host"), "--output", str(self.tmp / "h.json"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--container", proc.stderr)

    def test_a_missing_profile_is_refused(self):
        proc = run_replay("--job-dir", str(self.job), "--task-dir", str(FIXTURE / "task"),
                          "--profile", str(self.tmp / "nope.json"), "--workdir", str(self.tmp / "w3"),
                          "--output", str(self.tmp / "x.json"), "--allow-host-execution")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("profile", proc.stderr)


class ARefusalAfterScreeningKeepsWhatCompleted(unittest.TestCase):
    def test_the_screening_line_survives_a_confirmation_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            methods = root / "work/methods"
            (methods / "versions").mkdir(parents=True)
            state = sr.ReplayState(job_dir=root / "job", task_dir=root / "task", task_root=root / "task/environment",
                                   methods=methods, profile=methods / "gate/profile.json", direction="higher",
                                   container=None, wall_seconds=None)
            provisional = {"line": 1, "disposition": "provisional", "verdict": "inconclusive", "estimate": 0.0,
                           "interval": {"lower": 0.0, "upper": 0.0, "level": 0.9}, "min_effect": 51.5, "sample_size": 8,
                           "look_index": 1, "sizing": {"planned": 4, "exploratory": False},
                           "suite": {"locator": "results/v2/replication/seeds.json"}}
            calls: list[str | None] = []

            def fake_decide(_state, _version, _parent, replicates):
                calls.append(replicates)
                if replicates is None:
                    return provisional
                raise sr.GateRefused("gate refused v2 against v1: the confirmation suite does not re-derive")

            with mock.patch.object(sr, "stage_pair"), \
                    mock.patch.object(sr.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")), \
                    mock.patch.object(sr, "evaluate", return_value=None), \
                    mock.patch.object(sr, "cpu_seconds_of", return_value=1.5), \
                    mock.patch.object(sr, "screening_deltas", return_value={"seeds": [1], "deltas": [0.0], "min": 0.0,
                                                                            "median": 0.0, "max": 0.0}), \
                    mock.patch.object(sr, "decide", side_effect=fake_decide):
                row = sr.replay_pair(state, sr.make_pair("v1", "artifacts/app/methods/versions/v1", "v2",
                                                         "artifacts/app/methods/versions/v2", "reverted"))
        self.assertEqual(calls, [None, "v2"])
        gate = row["gate"]
        self.assertEqual(gate["outcome"], "gate_refused")
        self.assertIsNone(gate["disposition"])
        self.assertEqual(gate["screening"]["disposition"], "provisional")
        self.assertIsNotNone(gate["screening_deltas"])
        self.assertIn("does not re-derive", gate["refusal"])
        self.assertIsNone(row["agree"])
        self.assertEqual(row["cpu_seconds"], 6.0)


class TheManifestKeyIgnoresWhatCommittingChanges(unittest.TestCase):
    def test_commit_cleanliness_time_and_locator_do_not_count(self):
        base = {"capsule": {"locator": "a/capsule.json", "sha256": "x", "built_here": False}, "profile_sha256": "p",
                "gate_commit": "1" * 40, "gate_tree_clean": True, "anchor_commit": None, "created_utc": "t1"}
        other = dict(base, capsule={"locator": "b/capsule.json", "sha256": "x", "built_here": False},
                     gate_commit="2" * 40, gate_tree_clean=False, anchor_commit="3" * 40, created_utc="t2")
        self.assertEqual(sr.manifest_key(base), sr.manifest_key(other))
        self.assertNotEqual(sr.manifest_key(base), sr.manifest_key(dict(base, profile_sha256="q")))


class PairsComeFromTheRecord(unittest.TestCase):
    def test_an_unsnapshotted_v0_pairs_with_the_task_starter(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            (task / "environment/methods/main").mkdir(parents=True)
            (task / "environment/methods/main/policy.py").write_text("def choose_move(board):\n    return 'UP'\n")
            capsule = {"versions": [
                {"version_id": "v1", "parent_ids": [], "unsnapshotted_parent_ids": ["v0"], "status": "kept"},
                {"version_id": "v2", "parent_ids": ["v1"], "status": "reverted"},
                {"version_id": "v3", "parent_ids": [], "unsnapshotted_parent_ids": ["v9"], "status": "kept"},
                {"version_id": "v4", "parent_ids": ["v1", "v2"], "status": "kept"},
                {"version_id": "v5", "parent_ids": [], "status": "baseline"},
            ]}
            pairs, coverage = sr.get_pairs_from_capsule(capsule, task)
        self.assertEqual([(p["parent_id"], p["candidate_id"]) for p in pairs], [("v0", "v1"), ("v1", "v2")])
        self.assertEqual(pairs[0]["parent_source"], "task:environment/methods/main")
        self.assertEqual(pairs[0]["parent_source_kind"], "task_starter")
        self.assertEqual(pairs[1]["parent_source"], "artifacts/app/methods/versions/v1")
        self.assertEqual(coverage["versions_in_record"], 5)
        self.assertEqual(coverage["versions_with_recorded_action"], 4)
        self.assertEqual((coverage["pairs_planned"], coverage["record_backed"], coverage["task_starter_reconstruction"]),
                         (2, 1, 1))
        self.assertEqual([s["reason"] for s in coverage["not_replayable"]],
                         ["unsnapshotted_parent:v9", "multiple_parents", "lineage_root"])

    def test_without_a_starter_in_the_task_directory_v0_is_not_replayable(self):
        with tempfile.TemporaryDirectory() as tmp:
            capsule = {"versions": [{"version_id": "v1", "parent_ids": [], "unsnapshotted_parent_ids": ["v0"],
                                     "status": "kept"}]}
            pairs, coverage = sr.get_pairs_from_capsule(capsule, Path(tmp))
        self.assertEqual(pairs, [])
        self.assertEqual(coverage["not_replayable"], [{"candidate_id": "v1", "reason": "unsnapshotted_parent:v0"}])


class TheContainerCommandIsBuiltNotRun(unittest.TestCase):
    def test_paths_are_mapped_into_the_two_mounts_and_the_container_is_hardened(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            methods, task_root = root / "work/methods", root / "task/environment"
            (methods / "gate").mkdir(parents=True)
            task_root.mkdir(parents=True)
            command = sr.runner_command("python:3.13-slim", task_root=task_root, methods=methods,
                                        profile=methods / "gate/profile.json", policy_dir=methods / "versions/v2",
                                        suite=task_root / "visible_seeds.json",
                                        output=methods / "results/v2/visible_result.json", wall_seconds=900)
        self.assertEqual(command[:5], ["docker", "run", "--rm", "--network", "none"])
        for flag in ("--read-only", "--cap-drop", "--security-opt", "--pids-limit", "--memory", "--user", "--tmpfs"):
            self.assertIn(flag, command, flag)
        self.assertIn("python:3.13-slim", command)
        self.assertIn(f"{task_root.resolve()}:/task:ro", command)
        self.assertIn(f"{methods.resolve()}:/methods", command)
        self.assertNotIn("/var/run/docker.sock", " ".join(command))
        tail = command[command.index("/gate/evaluate_suite.py") + 1:]
        self.assertEqual(tail, ["--profile", "/methods/gate/profile.json", "--task-root", "/task",
                                "--policy-dir", "/methods/versions/v2", "--suite", "/task/visible_seeds.json",
                                "--output", "/methods/results/v2/visible_result.json", "--wall-seconds", "900"])

    def test_a_path_outside_both_mounts_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(sr.ReplayError):
                sr.runner_command("python:3.13-slim", task_root=root / "task", methods=root / "methods",
                                  profile=root / "elsewhere/profile.json", policy_dir=root / "methods/versions/v1",
                                  suite=root / "task/visible_seeds.json", output=root / "methods/results/v1/r.json",
                                  wall_seconds=None)

    def test_the_host_command_runs_the_runner_directly(self):
        command = sr.runner_command(None, task_root=Path("/t"), methods=Path("/m"), profile=Path("/m/gate/p.json"),
                                    policy_dir=Path("/m/versions/v1"), suite=Path("/t/visible_seeds.json"),
                                    output=Path("/m/results/v1/visible_result.json"), wall_seconds=None)
        self.assertEqual(command[0], sys.executable)
        self.assertTrue(command[1].endswith("evaluate_suite.py"))
        self.assertNotIn("--wall-seconds", command)


class StagingIsStrictUnlessProjectionIsAllowed(unittest.TestCase):
    def test_caches_are_ignored_and_other_files_refuse_the_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "src", Path(tmp) / "dst"
            (source / "__pycache__").mkdir(parents=True)
            (source / "policy.py").write_text("x = 1\n")
            (source / "__pycache__/policy.cpython-313.pyc").write_bytes(b"\x00")
            (source / "result.txt").write_text("42\n")
            with self.assertRaises(sr.NotReplayable) as caught:
                sr.stage_projection(source, target)
            self.assertIn("non_python_files_in_snapshot:src: result.txt", str(caught.exception))
            self.assertFalse(target.exists())
            omitted = sr.stage_projection(source, target, allow_projection=True)
            self.assertEqual(sorted(p.name for p in target.rglob("*")), ["policy.py"])
        self.assertEqual(omitted, [{"path": "result.txt", "bytes": 3, "sha256": hashlib.sha256(b"42\n").hexdigest()}])

    def test_a_special_file_refuses_the_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "policy.py").write_text("x = 1\n")
            os.mkfifo(source / "pipe.py")
            with self.assertRaises(sr.NotReplayable) as caught:
                sr.stage_projection(source, Path(tmp) / "dst")
            self.assertIn("special file", str(caught.exception))

    def test_a_symlink_refuses_the_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "policy.py").write_text("x = 1\n")
            (source / "link.py").symlink_to(source / "policy.py")
            with self.assertRaises(sr.NotReplayable):
                sr.stage_projection(source, Path(tmp) / "dst")


if __name__ == "__main__":
    unittest.main()
