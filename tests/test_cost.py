"""The cost script prices the harness's usage records and refuses what it cannot price.

Run: python3 -m unittest tests.test_cost
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "runbook" / "cost.py"
sys.path.insert(0, str(REPO / "runbook"))

import cost  # noqa: E402


def write_job(root: Path, lines: list[str], extra_jsonl: bool = False) -> Path:
    job = root / "job"
    sessions = job / "trial/agent/sessions/projects/-app"
    sessions.mkdir(parents=True)
    (sessions / "session.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if extra_jsonl:
        (job / "trial/agent/trajectory.jsonl").write_text(json.dumps({"type": "assistant", "message": {
            "usage": {"input_tokens": 10_000_000, "output_tokens": 0}}}) + "\n", encoding="utf-8")
    return job


def assistant(inp: int, out: int, cache_write: int = 0, cache_read: int = 0, stamp: str | None = None) -> str:
    record = {"type": "assistant", "message": {"usage": {"input_tokens": inp, "output_tokens": out,
                                                         "cache_creation_input_tokens": cache_write,
                                                         "cache_read_input_tokens": cache_read}}}
    if stamp:
        record["timestamp"] = stamp
    return json.dumps(record)


def run_cost(rates: str | None, *args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "RATES"}
    if rates is not None:
        env["RATES"] = rates
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)


class Pricing(unittest.TestCase):
    def test_exact_price_under_each_rate_card(self):
        tokens = {"input": 1_000_000, "output": 200_000, "cache_write": 400_000, "cache_read": 2_000_000}
        # haiku: 1.00 + 200000*5/1e6 + 400000*1.25/1e6 + 2000000*0.10/1e6 = 1 + 1 + 0.5 + 0.2
        self.assertAlmostEqual(cost.get_cost(tokens, "haiku"), 2.70)
        # opus: 5 + 5 + 2.5 + 1.0
        self.assertAlmostEqual(cost.get_cost(tokens, "opus"), 13.50)

    def test_an_unknown_rate_card_is_refused(self):
        with self.assertRaises(cost.CostError):
            cost.get_cost({"input": 1, "output": 1, "cache_write": 0, "cache_read": 0}, "sonnet")

    def test_only_session_records_are_priced(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = write_job(Path(tmp), [assistant(1000, 100, stamp="2026-09-08T10:00:00Z"),
                                        json.dumps({"type": "user", "message": {"content": "hi"}}),
                                        assistant(2000, 200, stamp="2026-09-08T10:02:00Z")], extra_jsonl=True)
            usage = cost.get_usage(job)
            self.assertEqual(usage["tokens"], {"input": 3000, "output": 300, "cache_write": 0, "cache_read": 0})
            self.assertEqual(usage["messages"], 2)
            self.assertEqual(usage["files"], 1)
            proc = run_cost("opus", str(job))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("COST               : $0.0225", proc.stdout)
            self.assertIn("agent wall clock   : 2.0 min", proc.stdout)


class Refusals(unittest.TestCase):
    def test_no_rate_card_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = write_job(Path(tmp), [assistant(1, 1)])
            proc = run_cost(None, str(job))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("RATES", proc.stderr)

    def test_a_malformed_usage_line_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = write_job(Path(tmp), [assistant(1, 1), '{"type": "assistant", "message": {"usage": '])
            proc = run_cost("haiku", str(job))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not JSON", proc.stderr)

    def test_a_non_integer_token_count_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = write_job(Path(tmp), [json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": "12"}}})])
            proc = run_cost("haiku", str(job))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("input_tokens", proc.stderr)

    def test_a_job_with_no_usage_records_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = write_job(Path(tmp), [json.dumps({"type": "user"})])
            proc = run_cost("haiku", str(job))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("no assistant usage records", proc.stderr)


if __name__ == "__main__":
    unittest.main()
