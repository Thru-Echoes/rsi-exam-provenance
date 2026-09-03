"""Tests for gate/decide.py: paired bootstrap gate for RSI-Exam rollouts."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import decide  # noqa: E402

PARENT = [3980, 4460, 3720, 4310, 4050, 4390, 4180, 3870]
DELTAS_INCONCLUSIVE = [1310, 820, 410, 200, 60, -190, -300, -230]
DELTAS_CLEAR = [610, 540, 480, 700, 390, 450, 520, 460]
DELTAS_BELOW = [-410, -220, -540, -300, -180, -350, -260, -290]
SEEDS = [104729, 130363, 155921, 181081, 205759, 232003, 260003, 287117]


def write_result(path: Path, scores: Sequence[float]) -> None:
    """Write a result file in the exact shape the task's selfcheck.py produces (extra keys included)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cpu_budget_per_game": 225,
        "cpu_seconds": 12.3,
        "cpu_seconds_per_game": 1.5,
        "mean_max_tile": 512.0,
        "mean_score": sum(scores) / len(scores),
        "median_score": sorted(scores)[len(scores) // 2],
        "valid_fraction": 1.0,
        "instances": [
            {"seed": s, "score": v, "max_tile": 512, "moves": 900, "error": None} for s, v in zip(SEEDS, scores)
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        low, high = decide.bootstrap_interval([float(d) for d in DELTAS_INCONCLUSIVE], level=0.9, resamples=5000, seed=20260902)
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


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_result(self.methods / "versions" / "v6" / "visible_result.json", PARENT)
        write_result(self.methods / "versions" / "v7" / "visible_result.json", [p + d for p, d in zip(PARENT, DELTAS_INCONCLUSIVE)])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_gate(self, *extra: str) -> int:
        return decide.main(["--methods", str(self.methods), "--version", "v7", "--parent", "v6", *extra])

    def lines(self) -> list[dict]:
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
                         ["versions/v6/visible_result.json", "versions/v7/visible_result.json"])
        for ref in line["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
            self.assertEqual(line["evidence_digests"][ref["role"]], "sha256:" + ref["sha256"])
        self.assertTrue(line["timestamp"].endswith("+00:00"))
        self.assertIsNone(line["holdout"])

    def test_refuses_to_stack_on_an_unreplicated_provisional(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "versions" / "v8" / "visible_result.json", [p + d + 20 for p, d in zip(PARENT, DELTAS_INCONCLUSIVE)])
        code = decide.main(["--methods", str(self.methods), "--version", "v8", "--parent", "v7"])
        self.assertEqual(code, 3)
        self.assertEqual(len(self.lines()), 1)

    def test_refuses_a_second_open_provisional_on_another_parent(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "versions" / "v8" / "visible_result.json", [p + d for p, d in zip(PARENT, DELTAS_INCONCLUSIVE)])
        code = decide.main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6"])
        self.assertEqual(code, 3)
        self.assertEqual(len(self.lines()), 1)

    def test_a_clear_keep_on_another_parent_is_allowed_while_one_provisional_is_open(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "versions" / "v8" / "visible_result.json", [p + d for p, d in zip(PARENT, DELTAS_CLEAR)])
        code = decide.main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6"])
        self.assertEqual(code, 0)
        self.assertEqual(self.lines()[1]["disposition"], "keep")

    def test_replication_resolves_the_provisional(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "versions" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "versions" / "v7" / "replication" / "candidate_result.json",
                     [p + d for p, d in zip(PARENT, DELTAS_CLEAR)])
        self.assertEqual(self.run_gate("--replicates", "v7"), 0)
        lines = self.lines()
        self.assertEqual(lines[1]["replicates"], "v7")
        self.assertEqual(lines[1]["disposition"], "keep")
        self.assertEqual(lines[1]["line"], 2)
        self.assertEqual(lines[1]["evidence"][0]["locator"], "versions/v7/replication/parent_result.json")
        # the provisional is now resolved, so building on v7 is allowed
        write_result(self.methods / "versions" / "v8" / "visible_result.json", [p + d + 600 for p, d in zip(PARENT, DELTAS_CLEAR)])
        self.assertEqual(decide.main(["--methods", str(self.methods), "--version", "v8", "--parent", "v7"]), 0)

    def test_replication_without_an_open_provisional_is_refused(self) -> None:
        write_result(self.methods / "versions" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "versions" / "v7" / "replication" / "candidate_result.json", PARENT)
        self.assertEqual(self.run_gate("--replicates", "v7"), 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_replication_with_wrong_parent_is_refused(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "versions" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "versions" / "v7" / "replication" / "candidate_result.json", PARENT)
        code = decide.main(["--methods", str(self.methods), "--version", "v7", "--parent", "v5", "--replicates", "v7"])
        self.assertEqual(code, 2)
        self.assertEqual(len(self.lines()), 1)

    def test_replication_with_non_clearing_holdout_reverts(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "versions" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "versions" / "v7" / "replication" / "candidate_result.json",
                     [p + d for p, d in zip(PARENT, DELTAS_CLEAR)])
        write_result(self.methods / "versions" / "v7" / "holdout" / "parent_result.json", PARENT)
        write_result(self.methods / "versions" / "v7" / "holdout" / "candidate_result.json",
                     [p + d for p, d in zip(PARENT, DELTAS_INCONCLUSIVE)])
        code = self.run_gate("--replicates", "v7",
                             "--holdout-parent-result", "versions/v7/holdout/parent_result.json",
                             "--holdout-candidate-result", "versions/v7/holdout/candidate_result.json")
        self.assertEqual(code, 0)
        lines = self.lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual((lines[1]["verdict"], lines[1]["holdout"]["verdict"], lines[1]["disposition"]),
                         ("clears", "inconclusive", "revert"))
        # the provisional is resolved, so a new line on v6 may open a fresh provisional
        write_result(self.methods / "versions" / "v8" / "visible_result.json", [p + d for p, d in zip(PARENT, DELTAS_INCONCLUSIVE)])
        self.assertEqual(decide.main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6"]), 0)

    def test_holdout_forces_provisional_and_is_recorded(self) -> None:
        write_result(self.methods / "versions" / "v7" / "visible_result.json", [p + d for p, d in zip(PARENT, DELTAS_CLEAR)])
        write_result(self.methods / "versions" / "v7" / "holdout" / "parent_result.json", PARENT)
        write_result(self.methods / "versions" / "v7" / "holdout" / "candidate_result.json",
                     [p + d for p, d in zip(PARENT, DELTAS_INCONCLUSIVE)])
        code = self.run_gate("--holdout-parent-result", "versions/v7/holdout/parent_result.json",
                             "--holdout-candidate-result", "versions/v7/holdout/candidate_result.json")
        self.assertEqual(code, 0)
        line = self.lines()[0]
        self.assertEqual(line["verdict"], "clears")
        self.assertEqual(line["disposition"], "provisional")
        self.assertEqual(line["holdout"]["verdict"], "inconclusive")
        self.assertEqual([e["role"] for e in line["holdout"]["evidence"]], ["holdout-parent", "holdout-candidate"])
        self.assertEqual(set(line["holdout"]["evidence_digests"]), {"holdout-parent", "holdout-candidate"})

    def test_missing_result_file_fails_loud(self) -> None:
        code = decide.main(["--methods", str(self.methods), "--version", "v9", "--parent", "v6"])
        self.assertEqual(code, 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_negative_min_effect_flag_is_refused(self) -> None:
        self.assertEqual(self.run_gate("--min-effect", "-5"), 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_locator_escaping_methods_is_refused(self) -> None:
        self.assertEqual(self.run_gate("--parent-result", "../outside.json"), 2)

    def test_corrupt_log_is_refused(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        log = self.methods / "decisions.jsonl"
        log.write_text(log.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        write_result(self.methods / "versions" / "v8" / "visible_result.json", [p + d for p, d in zip(PARENT, DELTAS_CLEAR)])
        self.assertEqual(decide.main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6"]), 2)


if __name__ == "__main__":
    unittest.main()
