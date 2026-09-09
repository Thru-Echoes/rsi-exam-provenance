"""The helper under the gate: every version measured by the gate's runner, a preview at evaluate, and
``decide v<N> kept`` as a proposal the gate rules on.

The helper runs as a subprocess against a rollout root assembled from the fixture task, with the gate's
scripts copied beside it and a profile whose confirmation bounds (floor 4, cap 8, the estimate-aware
planning rule) let the fixture policies be confirmed or found exploratory in seconds. After each scenario
the record producer and the verifier run over the methods tree, so every assertion is about what a
rollout's job directory would yield. Every number asserted is the deterministic outcome of the fixture
policies on the fixture seeds.

Run: python3 -m unittest tests.test_instrument
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import treedigest  # noqa: E402
from tests.gate_fixtures import (POLICY_GREEDY, POLICY_VARIANT, POLICY_WEAK, POLICY_WORST, TASK_ROOT,  # noqa: E402
                                 real_evaluator, real_visible_suite_sha, write_profile)
from tests.test_provenance_helper import build  # noqa: E402

HELPER = REPO / "runbook" / "provenance.py"
CONFIRMATION = {"floor": 4, "max_seeds": 8, "max_moves": 10000, "cpu_seconds_per_game": 225,
                "planning_rule": "estimate-aware"}
ILLEGAL = 'def choose_move(board):\n    return "JUMP"\n'


def make_root(case: unittest.TestCase, *, starter: Path = POLICY_WEAK, gate: bool = True,
              profile: bool = True) -> tuple[Path, dict[str, str]]:
    """A rollout root like /app with the gate at <root>/gate and the profile at <root>/profile.json."""
    temp = tempfile.TemporaryDirectory()
    case.addCleanup(temp.cleanup)
    root = Path(temp.name) / "app"
    root.mkdir()
    for name in ("evaluate.py", "game2048.py", "visible_seeds.json"):
        shutil.copy(TASK_ROOT / name, root / name)
    (root / "methods" / "main").mkdir(parents=True)
    shutil.copy(starter / "policy.py", root / "methods" / "main" / "policy.py")
    gate_dir = root / "gate"
    if gate:
        gate_dir.mkdir()
        for source in (REPO / "gate").glob("*.py"):
            shutil.copy(source, gate_dir / source.name)
    if profile:
        write_profile(root / "profile.json", rollout_id="instrument-test", confirmation=CONFIRMATION,
                      evaluator=real_evaluator(), visible_suite_sha256=real_visible_suite_sha(),
                      replication_key="22" * 32)
    env = {**os.environ, "PROVENANCE_ROOT": str(root), "PROVENANCE_GATE_DIR": str(gate_dir),
           "PROVENANCE_PROFILE": str(root / "profile.json"), "ARB_AGENT_TIMEOUT_SEC": "340",
           "PROVENANCE_WINDOW_START": f"{time.time():.3f}"}
    for key in ("PROVENANCE_KILL_AFTER", "PROVENANCE_SAFETY_FRACTION"):
        env.pop(key, None)
    return root, env


def run(root: Path, env: dict[str, str], *args: str, kill_after: str | None = None,
        **overrides: str) -> subprocess.CompletedProcess:
    env = {**env, **overrides}
    if kill_after:
        env["PROVENANCE_KILL_AFTER"] = kill_after
    return subprocess.run([sys.executable, str(HELPER), *args], env=env, capture_output=True, text=True)


def write_main(root: Path, source: Path | str) -> None:
    """Put a fixture policy directory's policy.py, or literal text, into main/."""
    if isinstance(source, Path):
        source = (source / "policy.py" if source.is_dir() else source).read_text(encoding="utf-8")
    (root / "methods" / "main" / "policy.py").write_text(source, encoding="utf-8")


def decisions(root: Path) -> list[dict]:
    path = root / "methods" / "decisions.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def block(root: Path, version_id: str) -> str:
    """The version's block of experiment_log.md, from its declaration to the next one."""
    text = (root / "methods" / "experiment_log.md").read_text(encoding="utf-8")
    start = text.index(f"## {version_id}\n")
    rest = text[start + len(f"## {version_id}\n"):]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


def main_digest(root: Path) -> str:
    return treedigest.method_tree_sha256(root / "methods" / "main")


def state_of(root: Path) -> dict:
    return json.loads((root / "methods" / ".provenance" / "state.json").read_text(encoding="utf-8"))


class TheGateIsMounted(unittest.TestCase):
    def test_init_measures_the_starter_with_the_runner_and_states_the_marks(self):
        root, env = make_root(self)
        proc = run(root, env, "init")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate is mounted", proc.stdout)
        self.assertIn("planning rule estimate-aware, confirmation floor 4 cap 8", proc.stdout)
        self.assertIn("safety margins 112.5 cpu s per game and 2.5 s per move", proc.stdout)
        self.assertIn("have your first candidate evaluated by minute 1.9; start closing out by minute 4.8", proc.stdout)
        for name in ("visible_result.json", "visible_result.receipt.json", "visible_safety.json"):
            self.assertTrue((root / "methods" / "results" / "v0" / name).is_file(), name)
        self.assertFalse((root / "methods" / "results" / "v0" / "selfcheck.json").exists())
        self.assertIn("- score: 2060 mean over the public suite", block(root, "v0"))
        self.assertIn("max move s", block(root, "v0"))
        state = state_of(root)
        self.assertTrue(state["instrument"])
        self.assertAlmostEqual(state["window_start"], float(env["PROVENANCE_WINDOW_START"]), places=2)
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None
        self.assertEqual([v["version_id"] for v in capsule["versions"]], ["v0"])

    def test_one_mount_without_the_other_is_refused(self):
        root, env = make_root(self, profile=False)
        proc = run(root, env, "init")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("instrument_misconfigured: gate mounted=True, profile mounted=False", proc.stderr)
        root, env = make_root(self, gate=False)
        proc = run(root, env, "init")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("instrument_misconfigured: gate mounted=False, profile mounted=True", proc.stderr)


class TheGateRules(unittest.TestCase):
    def test_a_keep_the_gate_confirms_moves_the_head_and_an_exploratory_one_is_overruled(self):
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK)
        proc = run(root, env, "evaluate", "--change", "the weak baseline")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("v1 (parent v0) snapshotted and logged; public-seed mean 2060.0", proc.stdout)
        self.assertIn("gate preview for v1 against v0: estimate +1680.5, interval [1117.0, 2270.0] at level 0.9, "
                      "minimum effect 9.5; verdict clears. A keep would be confirmed on 5 fresh seeds", proc.stdout)
        self.assertIn("time used:", proc.stdout)

        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("screening of v1 is provisional", proc.stdout)
        self.assertIn("confirming on 5 fresh seeds", proc.stdout)
        self.assertIn("the gate kept v1", proc.stdout)
        log = decisions(root)
        self.assertEqual([(l["version_id"], l["disposition"], l["replicates"]) for l in log],
                         [("v1", "provisional", None), ("v1", "keep", "v1")])
        self.assertEqual((log[1]["sample_size"], log[1]["verdict"]), (5, "clears"))
        base = root / "methods" / "results" / "v1" / "replication"
        for name in ("seeds.json", "parent_result.json", "parent_result.receipt.json", "candidate_result.json",
                     "candidate_result.receipt.json"):
            self.assertTrue((base / name).is_file(), name)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WEAK))
        text = block(root, "v1")
        self.assertIn("- status: kept", text)
        self.assertIn("- gate: keep, confirmed on fresh seeds (clears; estimate +", text)
        self.assertIn("- agent proposed: kept", text)
        self.assertEqual(state_of(root)["head"], "v1")

        write_main(root, POLICY_GREEDY)
        proc = run(root, env, "evaluate", "--change", "one-ply greedy")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("A keep would be reverted without confirming (exploratory): the plan needs 30 fresh seeds "
                      "and the cap is 8.", proc.stdout)
        proc = run(root, env, "decide", "v2", "kept", "--note", "the public seeds say otherwise")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate reverted v2 at screening (clears; exploratory: the plan needs 30 fresh seeds and the "
                      "cap is 8); main/ restored to the head v1", proc.stdout)
        log = decisions(root)
        self.assertEqual(len(log), 3)
        self.assertEqual((log[2]["version_id"], log[2]["disposition"], log[2]["sizing"]["exploratory"]),
                         ("v2", "revert", True))
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WEAK))
        text = block(root, "v2")
        self.assertIn("- status: reverted", text)
        self.assertIn("- gate: revert at screening (clears; exploratory", text)
        self.assertIn("- agent proposed: kept (overruled)", text)
        self.assertIn("- agent note: the public seeds say otherwise", text)

        proc = run(root, env, "status")
        self.assertIn("gate: 3 decision lines (1 keep, 1 revert, 0 provisional open)", proc.stdout)
        self.assertIn("head v1; pending none; main/ equals v1", proc.stdout)

        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None
        by_id = {v["version_id"]: v for v in capsule["versions"]}
        self.assertEqual(by_id["v1"]["status"], "submitted")
        self.assertEqual([d["disposition"] for d in by_id["v1"]["decisions"]], ["provisional", "keep"])
        self.assertEqual(by_id["v2"]["status"], "reverted")
        self.assertEqual([d["disposition"] for d in by_id["v2"]["decisions"]], ["revert"])
        self.assertEqual(by_id["v2"]["parent_ids"], ["v1"])

        proc = run(root, env, "finalize")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("finalized; main/ equals v1", proc.stdout)

    def test_an_identical_candidate_is_confirmed_and_reverted(self):
        root, env = make_root(self)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK.joinpath("policy.py").read_text(encoding="utf-8") + "# the same policy\n")
        proc = run(root, env, "evaluate", "--change", "a comment")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("estimate +0.0, interval [0.0, 0.0] at level 0.9, minimum effect 51.5; verdict inconclusive. "
                      "A keep would be confirmed on 4 fresh seeds", proc.stdout)
        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate reverted v1 at confirmation (inconclusive; estimate +0.0", proc.stdout)
        log = decisions(root)
        self.assertEqual([(l["disposition"], l["replicates"]) for l in log], [("provisional", None), ("revert", "v1")])
        self.assertEqual(log[1]["sample_size"], 4)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WEAK))
        text = block(root, "v1")
        self.assertIn("- status: reverted", text)
        self.assertIn("- gate: revert at confirmation (inconclusive;", text)
        self.assertIn("- agent proposed: kept (overruled)", text)
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None
        v1 = next(v for v in capsule["versions"] if v["version_id"] == "v1")
        self.assertEqual(v1["status"], "reverted")
        self.assertEqual([d["disposition"] for d in v1["decisions"]], ["provisional", "revert"])

    def test_an_agent_revert_consults_no_gate(self):
        root, env = make_root(self)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_VARIANT)
        proc = run(root, env, "evaluate", "--change", "prefer LEFT then DOWN")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("A keep would be reverted without confirming (exploratory): the plan needs 372 fresh seeds "
                      "and the cap is 8.", proc.stdout)
        proc = run(root, env, "decide", "v1", "reverted", "--note", "too noisy on eight seeds")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("v1 reverted; main/ restored to the head v0", proc.stdout)
        self.assertEqual(decisions(root), [])
        text = block(root, "v1")
        self.assertIn("- gate: not consulted (the agent reverted)", text)
        self.assertIn("- agent proposed: reverted", text)
        self.assertIn("- agent note: too noisy on eight seeds", text)
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None
        v1 = next(v for v in capsule["versions"] if v["version_id"] == "v1")
        self.assertEqual(v1["status"], "reverted")
        self.assertFalse(v1.get("decisions"))

    def test_a_keep_whose_confirmation_would_overrun_the_window_is_refused(self):
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init", ARB_AGENT_TIMEOUT_SEC="1").returncode, 0)
        write_main(root, POLICY_WEAK)
        self.assertEqual(run(root, env, "evaluate", ARB_AGENT_TIMEOUT_SEC="1").returncode, 0)
        proc = run(root, env, "decide", "v1", "kept", ARB_AGENT_TIMEOUT_SEC="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("v1 cannot be kept: its confirmation of 5 fresh seeds (about 0.2 min) would run past the "
                      "close-out mark; main/ restored to the head v0", proc.stdout)
        self.assertEqual(decisions(root), [])
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WORST))
        text = block(root, "v1")
        self.assertIn("- gate: not consulted; a confirmation of 5 fresh seeds (about 0.2 min) would run past the "
                      "close-out mark", text)
        self.assertIn("- agent proposed: kept (refused)", text)
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None

    def test_a_safety_margin_refuses_the_keep_and_finalize_keeps_the_head_within_the_margins(self):
        root, env = make_root(self, starter=POLICY_WORST)
        tiny = {"PROVENANCE_SAFETY_FRACTION": "0.000001"}     # margins of 0.000225 cpu s and 0.000005 s per move
        self.assertEqual(run(root, env, "init", **tiny).returncode, 0)
        write_main(root, POLICY_WEAK)
        self.assertEqual(run(root, env, "evaluate", **tiny).returncode, 0)
        proc = run(root, env, "decide", "v1", "kept", **tiny)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("v1 cannot be kept: max move s", proc.stdout)
        self.assertIn("exceeds the margin 0; main/ restored to the head v0", proc.stdout)
        self.assertEqual(decisions(root), [])
        self.assertIn("- gate: not consulted; the keep was refused for safety (max move s", block(root, "v1"))
        proc = run(root, env, "finalize", **tiny)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("is the inherited starter and fails the safety check", proc.stdout)
        self.assertIn("finalized; main/ equals v0", proc.stdout)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WORST))
        for bad in ("0", "nan", "2", "x"):
            proc = run(root, env, "status", PROVENANCE_SAFETY_FRACTION=bad)
            self.assertEqual(proc.returncode, 0, proc.stderr)   # status never consults the margin
        proc = run(make_root(self)[0], env, "init", PROVENANCE_SAFETY_FRACTION="nan")
        self.assertEqual(proc.returncode, 2)

    def test_an_unmeasurable_candidate_cannot_be_kept(self):
        root, env = make_root(self)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, ILLEGAL)
        proc = run(root, env, "evaluate", "--change", "an illegal move")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate's runner refused v1 (invalid_game", proc.stdout)
        self.assertIn("- score: not measured (the gate's runner refused the candidate: invalid_game", block(root, "v1"))
        self.assertEqual(state_of(root)["unmeasurable"]["v1"][:12], "invalid_game")
        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unmeasurable_candidate:v1", proc.stderr)
        proc = run(root, env, "decide", "v1", "reverted")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WEAK))
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None

    def test_main_edited_after_evaluate_is_refused(self):
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        write_main(root, POLICY_GREEDY)
        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("main_edited_after_evaluate:v1", proc.stderr)
        self.assertEqual(decisions(root), [])
        self.assertEqual(run(root, env, "decide", "v1", "reverted").returncode, 0)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WORST))

    def test_restore_refuses_a_version_the_gate_reverted(self):
        root, env = make_root(self)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_VARIANT)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        self.assertEqual(run(root, env, "decide", "v1", "kept").returncode, 0)     # exploratory: the gate reverts
        proc = run(root, env, "restore", "v1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not_confirmed:v1", proc.stderr)
        # an agent-reverted candidate, never gated, cannot become the head either
        write_main(root, POLICY_GREEDY)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        self.assertEqual(run(root, env, "decide", "v2", "reverted").returncode, 0)
        proc = run(root, env, "restore", "v2")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not_confirmed:v2", proc.stderr)
        self.assertEqual(run(root, env, "restore", "v0").returncode, 0)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WEAK))

    def test_init_without_evaluation_is_refused_under_the_gate_and_a_lost_head_measurement_is_redone(self):
        root, env = make_root(self, starter=POLICY_WORST)
        proc = run(root, env, "init", "--no-evaluate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no_evaluate_under_the_gate", proc.stderr)
        self.assertEqual(run(root, env, "init").returncode, 0)
        shutil.rmtree(root / "methods" / "results" / "v0")          # the head's measurement lost
        write_main(root, POLICY_WEAK)
        proc = run(root, env, "evaluate")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no gate preview; the head v0 is measured when you propose a keep", proc.stdout)
        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate kept v1", proc.stdout)
        self.assertTrue((root / "methods" / "results" / "v0" / "visible_result.receipt.json").is_file())
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None


class TheConfirmationWallClock(unittest.TestCase):
    def test_a_confirmation_evaluation_is_held_to_the_time_left_with_a_small_floor(self):
        # The estimate check keeps a confirmation from starting when it would overrun; the wall limit passed
        # to the runner is the backstop for one that starts and runs long. It is never below 10 s, so a
        # resume late in the window still gets a short evaluation rather than an instant refusal.
        sys.path.insert(0, str(REPO / "runbook"))
        import provenance  # noqa: PLC0415
        rollout = provenance.Rollout(Path("/app"))
        cmd = rollout.runner_command(Path("/app/methods/versions/v1"), Path("/app/methods/results/v1/replication/seeds.json"),
                                     Path("/app/methods/results/v1/replication/candidate_result.json"), safety=None,
                                     wall_seconds=3.2)
        self.assertEqual(cmd[cmd.index("--wall-seconds") + 1], "10")
        cmd = rollout.runner_command(Path("/app/methods/versions/v1"), Path("/app/s.json"), Path("/app/methods/results/x.json"),
                                     safety=None, wall_seconds=901.9)
        self.assertEqual(cmd[cmd.index("--wall-seconds") + 1], "901")
        cmd = rollout.runner_command(Path("/app/methods/versions/v1"), Path("/app/s.json"), Path("/app/methods/results/x.json"),
                                     safety=Path("/app/methods/results/v1/visible_safety.json"))
        self.assertNotIn("--wall-seconds", cmd)
        self.assertIn("--safety-report", cmd)


class InterruptedConfirmations(unittest.TestCase):
    def open_confirmation(self) -> tuple[Path, dict[str, str]]:
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        proc = run(root, env, "decide", "v1", "kept", kill_after="confirmation_opened")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(state_of(root)["confirming"], "v1")
        self.assertEqual([l["disposition"] for l in decisions(root)], ["provisional"])
        self.assertTrue((root / "methods" / "results" / "v1" / "replication" / "seeds.json").is_file())
        return root, env

    def test_finalize_finishes_the_confirmation(self):
        root, env = self.open_confirmation()
        proc = run(root, env, "status")
        self.assertIn("gate: 1 decision lines (0 keep, 0 revert, 1 provisional open)", proc.stdout)
        proc = run(root, env, "finalize", "--keep", "v1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("finishing the confirmation of v1 the gate's log holds open", proc.stdout)
        self.assertIn("the gate kept v1", proc.stdout)
        self.assertIn("finalized; main/ equals v1", proc.stdout)
        self.assertEqual([l["disposition"] for l in decisions(root)], ["provisional", "keep"])
        self.assertIsNone(state_of(root)["confirming"])
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None

    def test_the_gate_resolves_an_open_confirmation_even_when_the_agent_now_says_reverted(self):
        root, env = self.open_confirmation()
        proc = run(root, env, "decide", "v1", "reverted")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("finishing the confirmation of v1 the gate's log holds open", proc.stdout)
        self.assertIn("the gate kept v1", proc.stdout)
        self.assertEqual([l["disposition"] for l in decisions(root)], ["provisional", "keep"])
        self.assertEqual(state_of(root)["head"], "v1")
        self.assertIn("- agent proposed: kept", block(root, "v1"))          # the proposal the gate was asked, not the later command
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None

    def test_an_edit_to_main_during_the_confirmation_is_put_aside_so_the_gate_can_resolve(self):
        root, env = self.open_confirmation()
        write_main(root, POLICY_GREEDY)
        proc = run(root, env, "finalize", "--keep", "v1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("main/ was edited while the confirmation of v1 was open", proc.stdout)
        self.assertIn("the gate kept v1", proc.stdout)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WEAK))
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)

    def test_an_orphan_result_from_an_interrupted_measurement_is_measured_again(self):
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK)
        proc = run(root, env, "evaluate", kill_after="appended")   # stopped before the runner ran
        self.assertEqual(proc.returncode, 3)
        result = root / "methods" / "results" / "v1" / "visible_result.json"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text("{}", encoding="utf-8")                    # a result without its receipt: not evidence
        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("v1 was never measured; measuring it first", proc.stdout)
        self.assertIn("the gate kept v1", proc.stdout)
        self.assertTrue(result.with_name("visible_result.receipt.json").is_file())

    def test_a_stop_after_the_screening_line_before_the_state_save_is_repaired_from_the_log(self):
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        proc = run(root, env, "decide", "v1", "kept", kill_after="screening_returned")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual([l["disposition"] for l in decisions(root)], ["provisional"])
        self.assertIsNone(state_of(root)["confirming"])
        proc = run(root, env, "decide", "v1", "kept")                 # never screens twice
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate's log holds open", proc.stdout)
        self.assertEqual([l["disposition"] for l in decisions(root)], ["provisional", "keep"])

    def test_a_stop_after_a_screening_revert_line_is_applied_not_repeated(self):
        root, env = make_root(self)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_VARIANT)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        proc = run(root, env, "decide", "v1", "kept", kill_after="screening_returned")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual([l["disposition"] for l in decisions(root)], ["revert"])
        self.assertEqual(state_of(root)["pending"], "v1")
        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("already reverted v1 at screening; applying it", proc.stdout)
        self.assertEqual(len(decisions(root)), 1)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WEAK))
        self.assertIn("- agent proposed: kept (overruled)", block(root, "v1"))

    def test_a_stop_after_the_confirmation_line_is_applied_by_the_next_command(self):
        root, env = self.open_confirmation()
        proc = run(root, env, "decide", "v1", "kept", kill_after="confirmation_returned")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual([l["disposition"] for l in decisions(root)], ["provisional", "keep"])
        self.assertEqual(state_of(root)["head"], "v0")
        proc = run(root, env, "status")                                  # any command completes the settlement? no: status reads only
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = run(root, env, "finalize", "--keep", "v1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("already resolves v1; applying it", proc.stdout)
        self.assertEqual(state_of(root)["head"], "v1")
        self.assertEqual(len(decisions(root)), 2)
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None

    def test_a_stop_inside_the_settlement_is_completed_by_the_next_command(self):
        root, env = self.open_confirmation()
        proc = run(root, env, "decide", "v1", "kept", kill_after="settling")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(state_of(root)["settling"]["version"], "v1")
        self.assertEqual(state_of(root)["head"], "v1")
        proc = run(root, env, "status")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(state_of(root)["settling"])
        text = block(root, "v1")
        self.assertIn("- status: kept", text)
        self.assertIn("- gate: keep, confirmed on fresh seeds", text)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WEAK))
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None

    def test_the_gate_cannot_be_dropped_after_init(self):
        root, env = make_root(self)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_VARIANT)
        proc = run(root, env, "evaluate", PROVENANCE_GATE_DIR="/nonexistent", PROVENANCE_PROFILE="/nonexistent.json")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("instrument_downgraded", proc.stderr)
        other = root / "other-profile.json"
        other.write_text((root / "profile.json").read_text(encoding="utf-8").replace('"rollout_id": "instrument-test"', '"rollout_id": "other"'), encoding="utf-8")
        proc = run(root, env, "evaluate", PROVENANCE_PROFILE=str(other))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("profile_changed", proc.stderr)

    def test_a_missing_or_tampered_safety_report_refuses_the_keep(self):
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        report = root / "methods" / "results" / "v1" / "visible_safety.json"
        original = report.read_text(encoding="utf-8")
        doc = json.loads(original)
        doc["cpu_seconds_per_game"] = 0
        report.write_text(json.dumps(doc), encoding="utf-8")                  # the digest of the result still binds
        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate kept v1", proc.stdout)                           # a value edit within the margins is harmless
        write_main(root, POLICY_GREEDY)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        report = root / "methods" / "results" / "v2" / "visible_safety.json"
        doc = json.loads(report.read_text(encoding="utf-8"))
        doc["result_sha256"] = "0" * 64
        report.write_text(json.dumps(doc), encoding="utf-8")
        proc = run(root, env, "decide", "v2", "kept")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("cannot be kept: safety report is not bound to the visible result", proc.stdout)
        self.assertEqual(decisions(root)[-1]["version_id"], "v1")
        write_main(root, POLICY_VARIANT)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        (root / "methods" / "results" / "v3" / "visible_safety.json").unlink()
        proc = run(root, env, "decide", "v3", "kept")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("v3 was never measured; measuring it first", proc.stdout)   # a missing report is not evidence
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None

    def test_a_non_regular_file_in_main_is_refused_before_hashing(self):
        root, env = make_root(self)
        self.assertEqual(run(root, env, "init").returncode, 0)
        os.mkfifo(root / "methods" / "main" / "pipe.py")
        proc = run(root, env, "evaluate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("non_regular_file_in_tree:pipe.py", proc.stderr)

    def test_a_runner_refusal_during_the_confirmation_leaves_the_decision_open_and_the_gate_blocked(self):
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        broken = {"PROVENANCE_TEST_BREAK_CONFIRMATION": "candidate"}
        proc = run(root, env, "decide", "v1", "kept", **broken)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("confirmation_runner_failed:v1", proc.stderr)
        self.assertIn("the gate is blocked for the rest of the run", proc.stderr)
        self.assertEqual([l["disposition"] for l in decisions(root)], ["provisional"])
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WORST))
        state = state_of(root)
        self.assertEqual((state["gate_blocked"]["version"], state["pending"], state["confirming"]), ("v1", "v1", "v1"))
        self.assertIn("- status: reverted", block(root, "v1"))              # reads as reverted until decided; no gate line invented
        self.assertNotIn("- gate:", block(root, "v1"))
        proc = run(root, env, "evaluate", **broken)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("pending_decision:v1", proc.stderr)
        proc = run(root, env, "status", **broken)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1 provisional open); blocked:", proc.stdout)
        proc = run(root, env, "finalize", **broken)                          # finalize never retries: it says why and holds the head
        self.assertEqual(proc.returncode, 2)
        self.assertIn("gate_blocked:v1", proc.stderr)
        self.assertNotIn("confirmation_runner_failed", proc.stderr)
        self.assertEqual(main_digest(root), treedigest.method_tree_sha256(POLICY_WORST))
        proc = run(root, env, "decide", "v1", "kept", **broken)              # an explicit retry runs the confirmation again
        self.assertEqual(proc.returncode, 2)
        self.assertIn("confirmation_runner_failed:v1", proc.stderr)
        capsule, refusal = build(self, root)
        self.assertIsNone(refusal)
        assert capsule is not None
        v1 = next(v for v in capsule["versions"] if v["version_id"] == "v1")
        self.assertEqual(v1["status"], "provisional")
        # If the runner later succeeds, the open decision resolves as the contract says: by a confirmation line.
        proc = run(root, env, "decide", "v1", "kept")                        # the refusal was transient: the retry resolves it
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate kept v1", proc.stdout)
        self.assertEqual([l["disposition"] for l in decisions(root)], ["provisional", "keep"])
        self.assertIsNone(state_of(root)["gate_blocked"])                     # a resolved decision cannot stay blocked
        proc = run(root, env, "status")
        self.assertNotIn("blocked", proc.stdout)

    def test_the_proposal_the_gate_was_asked_survives_a_stop(self):
        root, env = make_root(self, starter=POLICY_WORST)
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, POLICY_WEAK)
        self.assertEqual(run(root, env, "evaluate").returncode, 0)
        proc = run(root, env, "decide", "v1", "kept", "--note", "a large improvement", kill_after="screening_returned")
        self.assertEqual(proc.returncode, 3)
        proc = run(root, env, "finalize")                                   # no --keep: the gate still rules on the keep it was asked
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate kept v1", proc.stdout)
        text = block(root, "v1")
        self.assertIn("- agent proposed: kept", text)
        self.assertIn("- agent note: a large improvement", text)
        self.assertIsNone(state_of(root)["proposal"])

    def test_a_policy_that_sleeps_is_stopped_by_the_wall_clock(self):
        root, env = make_root(self)
        env["ARB_AGENT_TIMEOUT_SEC"] = "100"
        env["PROVENANCE_WINDOW_START"] = f"{time.time() - 65:.3f}"       # 5 s to the close-out mark: the floor of 10 s applies
        self.assertEqual(run(root, env, "init").returncode, 0)
        write_main(root, "import time\ndef choose_move(board):\n    time.sleep(0.5)\n    return \"LEFT\"\n")
        proc = run(root, env, "evaluate", "--change", "a sleeper")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("the gate's runner refused v1 (wall_clock_exceeded", proc.stdout)
        proc = run(root, env, "decide", "v1", "kept")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unmeasurable_candidate:v1", proc.stderr)

    def test_evaluate_waits_for_the_open_confirmation(self):
        root, env = self.open_confirmation()
        write_main(root, POLICY_GREEDY)
        proc = run(root, env, "evaluate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("pending_decision:v1", proc.stderr)


if __name__ == "__main__":
    unittest.main()
