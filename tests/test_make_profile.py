"""A replay configuration generated from the real task files is one the gate accepts.

Run: python3 -m unittest tests.test_make_profile
"""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))

import task_profile  # noqa: E402
import treedigest  # noqa: E402

TASK = REPO / "fixtures" / "task2048"
SCRIPT = REPO / "runbook" / "make_profile.py"


def make(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


class ProfileFromTaskFiles(unittest.TestCase):
    def test_the_generated_profile_is_accepted_and_pins_the_real_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "shadow" / "profile.json"
            proc = make("--task-dir", str(TASK), "--rollout-id", "test-rollout", "--output", str(out),
                        "--replication-key-hex", "ab" * 32)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            profile = json.loads(out.read_text(encoding="utf-8"))
            checked = task_profile.check_profile(profile)
            env = TASK / "environment"
            self.assertEqual(checked["evaluator"]["evaluate.py"], treedigest.file_sha256(env / "evaluate.py"))
            self.assertEqual(checked["evaluator"]["game2048.py"], treedigest.file_sha256(env / "game2048.py"))
            self.assertEqual(checked["visible_suite_sha256"], treedigest.file_sha256(env / "visible_seeds.json"))
            self.assertEqual(checked["rollout_id"], "test-rollout")
            self.assertEqual(checked["replication_key"], "ab" * 32)
            self.assertEqual(checked["confirmation"], {"floor": 16, "max_seeds": 64, "max_moves": 10000,
                                                       "cpu_seconds_per_game": 225})
            self.assertEqual(checked["min_effect"], {"kind": "fraction_of_parent_visible_mean", "fraction": 0.025})
            # The reserved field commits to a documented literal, not to a key anyone holds.
            self.assertEqual(checked["audit_key_sha256"], hashlib.sha256(b"unused-shadow-audit-key-v1").hexdigest())
            # The profile carries the replication key, so it is private and so is its directory.
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(out.parent.stat().st_mode), 0o700)

    def test_a_fresh_key_is_generated_when_none_is_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "profile.json"
            proc = make("--task-dir", str(TASK), "--rollout-id", "r", "--output", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            key = json.loads(out.read_text())["replication_key"]
            self.assertEqual(len(key), 64)
            self.assertNotEqual(key, "ab" * 32)

    def test_the_cap_and_the_fraction_are_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "profile.json"
            proc = make("--task-dir", str(TASK), "--rollout-id", "r", "--output", str(out),
                        "--max-seeds", "16", "--min-effect-fraction", "0.1")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            profile = json.loads(out.read_text())
            self.assertEqual(profile["confirmation"]["max_seeds"], 16)
            self.assertEqual(profile["min_effect"]["fraction"], 0.1)

    def test_the_planning_rule_is_a_flag_and_the_default_writes_no_key(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "profile.json"
            self.assertEqual(make("--task-dir", str(TASK), "--rollout-id", "r", "--output", str(out),
                                  "--planning-rule", "estimate-aware").returncode, 0)
            profile = json.loads(out.read_text())
            self.assertEqual(profile["confirmation"]["planning_rule"], "estimate-aware")
            self.assertEqual(task_profile.resolve_planning_rule(task_profile.check_profile(profile)), "estimate-aware")
            plain = Path(temp) / "plain.json"
            self.assertEqual(make("--task-dir", str(TASK), "--rollout-id", "r", "--output", str(plain)).returncode, 0)
            self.assertNotIn("planning_rule", json.loads(plain.read_text())["confirmation"])

    def test_the_floor_is_a_flag_the_profile_rules_still_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "profile.json"
            proc = make("--task-dir", str(TASK), "--rollout-id", "r", "--output", str(out), "--floor", "8",
                        "--max-seeds", "16", "--planning-rule", "estimate-aware")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            profile = task_profile.check_profile(json.loads(out.read_text()))
            self.assertEqual((profile["confirmation"]["floor"], profile["confirmation"]["max_seeds"]), (8, 16))
            self.assertEqual(json.loads(proc.stdout)["floor"], 8)
            # A floor above the cap, or under two, is refused by the profile's own rules, not silently clamped.
            bad = Path(temp) / "bad.json"
            proc = make("--task-dir", str(TASK), "--rollout-id", "r", "--output", str(bad), "--floor", "32", "--max-seeds", "16")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("max_seeds must be at least the floor", proc.stderr)
            self.assertFalse(bad.exists())

    def test_an_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "profile.json"
            out.write_text("{}")
            proc = make("--task-dir", str(TASK), "--rollout-id", "r", "--output", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("already exists", proc.stderr)
            self.assertEqual(out.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()
