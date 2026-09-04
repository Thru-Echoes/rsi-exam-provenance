"""Tests for gate/trace_from_decisions.py: decision log to TRACE session document."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import seeds as seedsmod  # noqa: E402
import trace_from_decisions as conv  # noqa: E402

D = "a" * 64
PROFILE_SHA = "9" * 64
PARENT_DIGEST = "6" * 64
CANDIDATE_DIGEST = "8" * 64
INTERVALS = {"inconclusive": (-30.0, 583.8, 260.0), "clears": (467.5, 575.0, 518.75),
             "below": (-382.5, -258.8, -318.75)}
UNSET: Any = object()
SIZING = {"rule": seedsmod.SIZING_RULE, "size": 8, "planned": 8, "floor": 4, "cap": 8, "exploratory": False,
          "screening_sd": 565.4833583505606, "z": 1.6448536269514715}
SIZING_EXPLORATORY = dict(SIZING, planned=327, exploratory=True)
SUITE = {"locator": "results/v3/replication/seeds.json", "sha256": "7" * 64,
         "derivation": {"algorithm": conv.SEEDS_ALGORITHM, "rollout_id": "game2048__abc123",
                        "candidate_method_tree_sha256": CANDIDATE_DIGEST, "look_index": 1, "size": 8,
                        "max_moves": 300}}


def line(n: int, version: str, parent: str, verdict: str, disposition: str, replicates: str | None = None,
         holdout_verdict: str | None = None, confirm_policy: str | None = None, suite: dict | None = None,
         look_index: int | None = None, sizing: dict | None = None, min_effect: float = 0.0,
         profile_sha256: Any = UNSET, parent_digest: Any = UNSET, candidate_digest: Any = UNSET,
         receipts: Any = UNSET) -> dict[str, Any]:
    """One decision-log line.

    Passing ``confirm_policy`` adds the seven gated keys; ``confirm_policy="always"`` also defaults the
    three digests to the constants above and adds the two receipt evidence entries a gated line carries.
    """
    gated = confirm_policy == "always"
    low, high, est = INTERVALS[verdict]
    evidence = [{"role": "parent", "locator": f"results/{parent}/visible_result.json", "sha256": D},
                {"role": "candidate", "locator": f"results/{version}/visible_result.json", "sha256": D}]
    if receipts is UNSET:
        receipts = gated
    if receipts:
        evidence += [{"role": "receipt-parent", "locator": f"results/{parent}/visible_result.receipt.json",
                      "sha256": "c" * 64},
                     {"role": "receipt-candidate", "locator": f"results/{version}/visible_result.receipt.json",
                      "sha256": "d" * 64}]
    holdout = None
    if holdout_verdict:
        hl, hh, he = INTERVALS[holdout_verdict]
        hev = [{"role": "holdout-parent", "locator": f"results/{version}/holdout/parent_result.json", "sha256": "e" * 64},
               {"role": "holdout-candidate", "locator": f"results/{version}/holdout/candidate_result.json", "sha256": "f" * 64}]
        holdout = {"estimate": he, "interval": {"lower": hl, "upper": hh, "level": 0.9}, "sample_size": 8,
                   "verdict": holdout_verdict, "evidence": hev,
                   "evidence_digests": {e["role"]: "sha256:" + e["sha256"] for e in hev}}
    doc: dict[str, Any] = {
        "schema": "rsi-exam-decision-log/v1", "line": n, "timestamp": f"2026-09-03T18:0{n}:00+00:00",
        "version_id": version, "parent_id": parent, "replicates": replicates,
        "statistic": "mean_paired_delta", "unit": "game_score", "direction": "higher", "estimate": est,
        "interval": {"lower": low, "upper": high, "level": 0.9},
        "method": {"name": "percentile_bootstrap", "algorithm": "rsi-exam-gate/percentile-bootstrap/1",
                   "resamples": 5000, "seed": 20260902},
        "sample_size": 8, "min_effect": min_effect, "verdict": verdict, "disposition": disposition,
        "evidence": evidence, "evidence_digests": {e["role"]: "sha256:" + e["sha256"] for e in evidence},
        "holdout": holdout,
    }
    if confirm_policy is not None:
        doc["confirm_policy"] = confirm_policy
        doc["profile_sha256"] = (PROFILE_SHA if gated else None) if profile_sha256 is UNSET else profile_sha256
        doc["look_index"] = look_index
        doc["parent_method_tree_sha256"] = (PARENT_DIGEST if gated else None) if parent_digest is UNSET else parent_digest
        doc["candidate_method_tree_sha256"] = ((CANDIDATE_DIGEST if gated else None)
                                               if candidate_digest is UNSET else candidate_digest)
        doc["sizing"] = sizing
        doc["suite"] = suite
    return doc


def provisional(n: int = 1, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {"confirm_policy": "always", "sizing": SIZING, "suite": SUITE, "look_index": 1}
    fields.update(overrides)
    return line(n, "v3", "v1", "inconclusive", "provisional", **fields)


def replication(n: int = 2, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {"replicates": "v3", "confirm_policy": "always", "sizing": SIZING, "suite": SUITE,
                              "look_index": 1}
    fields.update(overrides)
    return line(n, "v3", "v1", "clears", "keep", **fields)


class TestCanonicalKey(unittest.TestCase):
    def test_spec_algorithm(self) -> None:
        self.assertEqual(conv.canonical_project_key("  RSI Exam/Rollouts_2026 "), "rsi-exam-rollouts-2026")
        self.assertEqual(conv.canonical_project_key("trace-mcp"), "trace-mcp")
        with self.assertRaises(ValueError):
            conv.canonical_project_key("---")
        with self.assertRaises(ValueError):
            conv.canonical_project_key("auto")


class TestMapping(unittest.TestCase):
    def build(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        return conv.build_session(lines, project="RSI-Exam rollouts", rollout_id="game2048__abc123",
                                  task="game2048_policy_search", harness="claude-code", model="claude-opus-5",
                                  decision_log_sha256=D)

    def test_a_gated_provisional_and_its_replication_convert(self) -> None:
        doc = self.build([provisional(), replication()])
        events = doc["events"]
        self.assertEqual([e["decision"]["disposition"] for e in events], ["accepted", "accepted"])
        self.assertEqual(events[0]["decision"]["revision_note"], "Resolved by replication evt_002.")
        conf = events[0]["decision"]["confidence"]
        self.assertEqual(list(conf)[-7:], list(conv.GATED_KEYS))
        self.assertEqual(conf["confirm_policy"], "always")
        self.assertEqual(conf["profile_sha256"], PROFILE_SHA)
        self.assertEqual(conf["look_index"], 1)
        self.assertEqual(conf["parent_method_tree_sha256"], PARENT_DIGEST)
        self.assertEqual(conf["candidate_method_tree_sha256"], CANDIDATE_DIGEST)
        self.assertEqual(conf["sizing"], SIZING)
        self.assertEqual(conf["suite"], SUITE)
        self.assertEqual([e["role"] for e in conf["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])

    def test_an_under_planned_confirmation_reverts_with_its_own_note(self) -> None:
        doc = self.build([line(1, "v3", "v1", "inconclusive", "revert", confirm_policy="always",
                               sizing=SIZING_EXPLORATORY)])
        decision = doc["events"][0]["decision"]
        self.assertEqual(decision["disposition"], "rejected")
        self.assertEqual(decision["revision_note"],
                         "Confirmation would need more games than the profile allows; reverted without confirming.")
        self.assertEqual(decision["confidence"]["sizing"], SIZING_EXPLORATORY)
        self.assertIsNone(decision["confidence"]["suite"])
        self.assertIsNone(decision["confidence"]["look_index"])

    def test_a_gated_below_line_reverts_on_the_interval(self) -> None:
        doc = self.build([line(1, "v3", "v1", "below", "revert", confirm_policy="always")])
        self.assertEqual(doc["events"][0]["decision"]["revision_note"], "Interval entirely below zero.")

    def test_replay_lines_without_the_gated_keys_still_convert(self) -> None:
        doc = self.build([line(1, "v1", "v0", "clears", "keep")])
        conf = doc["events"][0]["decision"]["confidence"]
        for key in conv.GATED_KEYS:
            self.assertIn(key, conf)
            self.assertIsNone(conf[key])

    def test_gated_rule_violations_are_refused(self) -> None:
        bad: list[tuple[str, list[dict[str, Any]]]] = [
            ("empty confirm_policy", [provisional(confirm_policy="")]),
            ("unknown confirm_policy", [provisional(confirm_policy="sometimes")]),
            ("no receipt evidence", [provisional(receipts=False)]),
            ("provisional without a suite", [provisional(suite=None)]),
            ("provisional without a look index", [provisional(look_index=None, suite=None)]),
            ("screening without a plan", [provisional(sizing=None, suite=None)]),
            ("exploratory plan carrying a suite",
             [line(1, "v3", "v1", "inconclusive", "revert", confirm_policy="always", sizing=SIZING_EXPLORATORY,
                   suite=SUITE, look_index=1)]),
            ("below line carrying a plan",
             [line(1, "v3", "v1", "below", "revert", confirm_policy="always", sizing=SIZING)]),
            ("suite locator inside the policy tree",
             [provisional(suite=dict(SUITE, locator="versions/v3/seeds.json"))]),
            ("suite size disagrees with the plan",
             [provisional(suite=dict(SUITE, derivation=dict(SUITE["derivation"], size=4)))]),
            ("short profile digest", [provisional(profile_sha256="short")]),
            ("short parent digest", [provisional(parent_digest="short")]),
            ("look index below one", [provisional(look_index=0, suite=None)]),
            ("replication under another profile",
             [provisional(), replication(profile_sha256="1" * 64)]),
            ("replication under another look",
             [provisional(), replication(look_index=2, suite=dict(SUITE, derivation=dict(SUITE["derivation"],
                                                                                         look_index=2)))]),
            ("replication under another minimum effect", [provisional(), replication(min_effect=100.0)]),
            ("replication under another suite", [provisional(), replication(suite=dict(SUITE, sha256="0" * 64))]),
            ("replay line carrying a suite",
             [line(1, "v3", "v1", "inconclusive", "provisional", confirm_policy="inconclusive", suite=SUITE)]),
            ("replay line that should have kept",
             [line(1, "v1", "v0", "clears", "provisional", confirm_policy="inconclusive")]),
        ]
        for name, lines in bad:
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    self.build(lines)

    def test_keep_revert_provisional_dispositions(self) -> None:
        doc = self.build([line(1, "v1", "v0", "clears", "keep"), line(2, "v2", "v1", "below", "revert"),
                          line(3, "v3", "v1", "inconclusive", "provisional")])
        ev = doc["events"]
        self.assertEqual([e["id"] for e in ev], ["evt_001", "evt_002", "evt_003"])
        self.assertEqual([e["decision"]["disposition"] for e in ev], ["accepted", "rejected", "proposed"])
        self.assertEqual(ev[0]["decision"]["resolved_by"]["type"], "system")
        self.assertEqual(ev[0]["decision"]["proposed_by"]["type"], "ai")
        self.assertIsNone(ev[2]["decision"].get("resolved_by"))
        self.assertEqual(ev[1]["decision"]["revision_note"], "Interval entirely below zero.")
        self.assertEqual(ev[2]["decision"]["description"], "Keep v3 provisionally (parent v1)")
        self.assertEqual(doc["metadata"]["project_key"], "rsi-exam-rollouts")
        self.assertEqual(doc["metadata"]["experiment_id"], "game2048__abc123")
        self.assertEqual(doc["metadata"]["custom"]["source"], "rsi-exam-decision-log/v1")
        self.assertEqual(doc["status"], "completed")
        self.assertEqual(doc["trace_version"], "0.5.0")
        self.assertEqual(doc["summary"], "RSI-Exam rollout game2048__abc123 (game2048_policy_search, claude-code, "
                                         "claude-opus-5): 1 kept, 1 reverted, 1 provisional, 0 replicated.")

    def test_confidence_block_carries_the_proofpress_readable_keys_first(self) -> None:
        doc = self.build([line(1, "v1", "v0", "clears", "keep")])
        conf = doc["events"][0]["decision"]["confidence"]
        self.assertEqual(conf["interval"], {"lower": 467.5, "upper": 575.0, "level": 0.9})
        self.assertEqual(conf["method"], {"name": "percentile_bootstrap", "algorithm": "rsi-exam-gate/percentile-bootstrap/1",
                                          "resamples": 5000, "seed": 20260902})
        self.assertEqual(conf["sample_size"], 8)
        self.assertEqual(conf["evidence_digests"], {"parent": "sha256:" + D, "candidate": "sha256:" + D})
        self.assertEqual(conf["verdict"], "clears")
        self.assertEqual(conf["estimate"], 518.75)
        self.assertEqual(conf["min_effect"], 0.0)
        self.assertEqual(conf["direction"], "higher")
        self.assertEqual(conf["contract"], "rsi-exam-decision-log/v1")
        self.assertEqual(list(conf)[:5], ["interval", "method", "sample_size", "evidence_digests", "contract"])
        self.assertEqual([e["locator"] for e in conf["evidence"]],
                         ["results/v0/visible_result.json", "results/v1/visible_result.json"])
        self.assertIsNone(conf["holdout"])

    def test_rationale_template(self) -> None:
        doc = self.build([line(1, "v3", "v1", "inconclusive", "provisional")])
        self.assertEqual(doc["events"][0]["decision"]["rationale"],
                         "Mean paired delta +260.0 game_score (n=8); 90 percent percentile bootstrap interval "
                         "[-30.0, +583.8]; verdict inconclusive.")

    def test_holdout_is_preserved(self) -> None:
        doc = self.build([line(1, "v3", "v1", "clears", "provisional", holdout_verdict="inconclusive")])
        conf = doc["events"][0]["decision"]["confidence"]
        self.assertEqual(conf["holdout"]["verdict"], "inconclusive")
        self.assertEqual(set(conf["holdout"]["evidence_digests"]), {"holdout-parent", "holdout-candidate"})
        self.assertEqual(doc["events"][0]["decision"]["disposition"], "proposed")

    def test_replication_resolves_the_provisional(self) -> None:
        doc = self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                          line(2, "v3", "v1", "clears", "keep", replicates="v3")])
        ev = doc["events"]
        self.assertEqual(ev[0]["decision"]["disposition"], "accepted")
        self.assertEqual(ev[0]["decision"]["revision_note"], "Resolved by replication evt_002.")
        self.assertEqual(ev[1]["decision"]["revises_event_id"], "evt_001")
        self.assertEqual(ev[1]["decision"]["disposition"], "accepted")
        self.assertTrue(ev[1]["decision"]["description"].startswith("Replication of v3"))
        self.assertEqual(doc["summary"].split(": ")[1], "0 kept, 0 reverted, 1 provisional, 1 replicated.")

    def test_replication_that_fails_rejects_both(self) -> None:
        doc = self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                          line(2, "v3", "v1", "inconclusive", "revert", replicates="v3")])
        ev = doc["events"]
        self.assertEqual([e["decision"]["disposition"] for e in ev], ["rejected", "rejected"])
        doc = self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                          line(2, "v3", "v1", "clears", "revert", replicates="v3", holdout_verdict="inconclusive")])
        ev = doc["events"]
        self.assertEqual([e["decision"]["disposition"] for e in ev], ["rejected", "rejected"])
        self.assertEqual(ev[1]["decision"]["revision_note"], "Replication did not clear the minimum effect.")

    def test_contract_violations_are_refused(self) -> None:
        bad_verdict = line(1, "v1", "v0", "clears", "keep")
        bad_verdict["verdict"] = "inconclusive"
        with self.assertRaises(ValueError):
            self.build([bad_verdict])
        bad_digest = line(1, "v1", "v0", "clears", "keep")
        bad_digest["evidence_digests"]["parent"] = "sha256:" + "b" * 64
        with self.assertRaises(ValueError):
            self.build([bad_digest])
        with self.assertRaises(ValueError):
            self.build([line(1, "v3", "v1", "clears", "keep", replicates="v3")])
        with self.assertRaises(ValueError):
            self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                        line(2, "v3", "v2", "clears", "keep", replicates="v3")])
        with self.assertRaises(ValueError):
            self.build([line(1, "v3", "v1", "inconclusive", "provisional"), line(2, "v4", "v3", "clears", "keep")])
        alias = line(1, "v3", "v1", "clears", "provisional", holdout_verdict="inconclusive")
        alias["holdout"]["evidence"] = [dict(e, role="holdout-" + e["role"]) for e in alias["evidence"]]
        alias["holdout"]["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in alias["holdout"]["evidence"]}
        with self.assertRaises(ValueError):
            self.build([alias])
        unknown = line(1, "v1", "v0", "clears", "keep")
        unknown["evidence"].append({"role": "mystery", "locator": "results/x.json", "sha256": "c" * 64})
        unknown["evidence_digests"]["mystery"] = "sha256:" + "c" * 64
        with self.assertRaises(ValueError):
            self.build([unknown])
        dup = line(1, "v1", "v0", "clears", "keep")
        dup["evidence"].append(dict(dup["evidence"][0]))
        with self.assertRaises(ValueError):
            self.build([dup])
        with self.assertRaises(ValueError):
            self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                        line(2, "v4", "v1", "inconclusive", "provisional")])
        with self.assertRaises(ValueError):
            self.build([line(2, "v1", "v0", "clears", "keep")])

    def test_no_free_text_beyond_the_template(self) -> None:
        doc = self.build([provisional(), replication()])
        for event in doc["events"]:
            self.assertIsNone(event["context"]["reasoning_summary"])
            self.assertIsNone(event["context"]["conversation_snippet"])
        blob = json.dumps(doc)
        for banned in ("prompt", "transcript"):
            self.assertNotIn(banned, blob)

    def test_cli_writes_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "decisions.jsonl"
            log.write_text(json.dumps(line(1, "v1", "v0", "clears", "keep")) + "\n", encoding="utf-8")
            out = Path(tmp) / "session.json"
            code = conv.main([str(log), "--project", "p", "--rollout", "r1", "--task", "t", "--harness", "h",
                              "--model", "m", "--output", str(out)])
            self.assertEqual(code, 0)
            doc = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(doc["metadata"]["custom"]["decision_log_sha256"], conv.sha256_of(log))
            self.assertEqual(doc["metadata"]["custom"]["locator_base"], "artifacts/app/methods")

    def test_cli_refuses_a_gated_log_that_violates_the_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "decisions.jsonl"
            log.write_text(json.dumps(provisional(receipts=False)) + "\n", encoding="utf-8")
            out = Path(tmp) / "session.json"
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = conv.main([str(log), "--project", "p", "--rollout", "r1", "--task", "t",
                                  "--harness", "h", "--model", "m", "--output", str(out)])
            self.assertEqual(code, 2)
            self.assertIn("receipt evidence", err.getvalue())
            self.assertFalse(out.exists())


class TestRolloutIdentity(unittest.TestCase):
    def test_a_suite_derived_for_another_rollout_is_refused(self) -> None:
        provisional = line(1, "v3", "v1", "clears", "provisional", confirm_policy="always", suite=dict(SUITE), look_index=1)
        provisional["suite"] = dict(SUITE, derivation=dict(SUITE["derivation"], rollout_id="another-rollout"))
        with self.assertRaises(ValueError):
            conv.build_session([provisional], project="p", rollout_id="game2048__abc123", task="t", harness="h",
                               model="m", decision_log_sha256="a" * 64)


class TestLogWideRules(unittest.TestCase):
    def build(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        return conv.build_session(lines, project="p", rollout_id="game2048__abc123", task="t", harness="h",
                                  model="m", decision_log_sha256="a" * 64)

    def test_one_mode_and_one_profile_per_log(self) -> None:
        gated = line(1, "v3", "v1", "clears", "provisional", confirm_policy="always", suite=dict(SUITE), look_index=1,
                     sizing=dict(SIZING))
        replay_replication = line(2, "v3", "v1", "clears", "keep", replicates="v3")
        with self.assertRaises(ValueError):
            self.build([gated, replay_replication])
        other_profile = line(2, "v4", "v1", "below", "revert", confirm_policy="always", profile_sha256="1" * 64)
        with self.assertRaises(ValueError):
            self.build([line(1, "v2", "v1", "below", "revert", confirm_policy="always"), other_profile])
        with self.assertRaises(ValueError):
            self.build([line(1, "v2", "v1", "below", "revert"), line(2, "v4", "v1", "below", "revert", confirm_policy="always")])

    def test_sizing_must_follow_the_planning_rule(self) -> None:
        for bad in (dict(SIZING, size=7), dict(SIZING, exploratory=True), dict(SIZING, floor=1),
                    dict(SIZING, cap=3), dict(SIZING, planned=3), dict(SIZING, z=-1.0), dict(SIZING, screening_sd="x")):
            with self.subTest(sizing=bad):
                bad_line = line(1, "v3", "v1", "clears", "provisional", confirm_policy="always", suite=dict(SUITE),
                                look_index=1, sizing=bad)
                with self.assertRaises(ValueError):
                    self.build([bad_line])


if __name__ == "__main__":
    unittest.main()
