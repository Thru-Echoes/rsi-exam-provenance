"""Tests for gate/trace_from_decisions.py: decision log to TRACE session document."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import trace_from_decisions as conv  # noqa: E402

D = "a" * 64
INTERVALS = {"inconclusive": (-30.0, 583.8, 260.0), "clears": (467.5, 575.0, 518.75), "below": (-382.5, -258.8, -318.75)}


def line(n: int, version: str, parent: str, verdict: str, disposition: str, replicates: str | None = None,
         holdout_verdict: str | None = None) -> dict:
    low, high, est = INTERVALS[verdict]
    evidence = [{"role": "parent", "locator": f"results/{parent}/visible_result.json", "sha256": D},
                {"role": "candidate", "locator": f"results/{version}/visible_result.json", "sha256": D}]
    holdout = None
    if holdout_verdict:
        hl, hh, he = INTERVALS[holdout_verdict]
        hev = [{"role": "holdout-parent", "locator": f"results/{version}/holdout/parent_result.json", "sha256": "e" * 64},
               {"role": "holdout-candidate", "locator": f"results/{version}/holdout/candidate_result.json", "sha256": "f" * 64}]
        holdout = {"estimate": he, "interval": {"lower": hl, "upper": hh, "level": 0.9}, "sample_size": 8,
                   "verdict": holdout_verdict, "evidence": hev,
                   "evidence_digests": {e["role"]: "sha256:" + e["sha256"] for e in hev}}
    return {
        "schema": "rsi-exam-decision-log/v1", "line": n, "timestamp": f"2026-09-03T18:0{n}:00+00:00",
        "version_id": version, "parent_id": parent, "replicates": replicates,
        "statistic": "mean_paired_delta", "unit": "game_score", "direction": "higher", "estimate": est,
        "interval": {"lower": low, "upper": high, "level": 0.9},
        "method": {"name": "percentile_bootstrap", "algorithm": "rsi-exam-gate/percentile-bootstrap/1", "resamples": 5000, "seed": 20260902},
        "sample_size": 8, "min_effect": 0.0, "verdict": verdict, "disposition": disposition,
        "evidence": evidence, "evidence_digests": {e["role"]: "sha256:" + e["sha256"] for e in evidence},
        "holdout": holdout,
    }


class TestCanonicalKey(unittest.TestCase):
    def test_spec_algorithm(self) -> None:
        self.assertEqual(conv.canonical_project_key("  RSI Exam/Rollouts_2026 "), "rsi-exam-rollouts-2026")
        self.assertEqual(conv.canonical_project_key("trace-mcp"), "trace-mcp")
        with self.assertRaises(ValueError):
            conv.canonical_project_key("---")
        with self.assertRaises(ValueError):
            conv.canonical_project_key("auto")


class TestMapping(unittest.TestCase):
    def build(self, lines: list[dict]) -> dict:
        return conv.build_session(lines, project="RSI-Exam rollouts", rollout_id="game2048__abc123",
                                  task="game2048_policy_search", harness="claude-code", model="claude-opus-5",
                                  decision_log_sha256=D)

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
            self.build([line(1, "v3", "v1", "inconclusive", "provisional"), line(2, "v3", "v2", "clears", "keep", replicates="v3")])
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
            self.build([line(1, "v3", "v1", "inconclusive", "provisional"), line(2, "v4", "v1", "inconclusive", "provisional")])
        with self.assertRaises(ValueError):
            self.build([line(2, "v1", "v0", "clears", "keep")])

    def test_no_free_text_beyond_the_template(self) -> None:
        doc = self.build([line(1, "v1", "v0", "clears", "keep")])
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


if __name__ == "__main__":
    unittest.main()
