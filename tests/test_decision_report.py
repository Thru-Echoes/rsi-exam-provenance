"""The decision-evidence report: one row per decision, and the limits printed beside them."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATED = REPO_ROOT / "fixtures/gated"
VALID = REPO_ROOT / "fixtures/valid"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REPORT = _load("decision_report", REPO_ROOT / "report/decision_report.py")
VERIFIER = _load("report_verifier", REPO_ROOT / "profile/verify_capsule.py")


class DecisionReportTests(unittest.TestCase):
    def materialize(self, source=GATED):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        shutil.copytree(source, root, dirs_exist_ok=True)
        return root / "job"

    def report(self, job):
        capsule = json.loads((job / "capsule.json").read_text(encoding="utf-8"))
        result = VERIFIER.verify_capsule(job / "capsule.json")
        rows = REPORT.get_rows(capsule, result)
        return rows, REPORT.render(rows, result, capsule)

    def test_one_row_per_decision_in_log_order(self):
        rows, _ = self.report(self.materialize())
        self.assertEqual([row["log_line"] for row in rows], [1, 2, 3])
        self.assertEqual([row["verdict"] for row in rows], ["below", "inconclusive", "clears"])
        self.assertEqual([row["action"] for row in rows], ["revert", "provisional", "keep"])

    def test_the_confirmation_column_says_what_resolved_what(self):
        rows, _ = self.report(self.materialize())
        self.assertEqual(rows[0]["confirmed by"], "no confirmation required")
        self.assertEqual(rows[1]["confirmed by"], "line 3")
        self.assertEqual(rows[2]["confirmed by"], "is the confirmation of line 2")

    def test_an_unresolved_provisional_says_so_rather_than_leaving_it_blank(self):
        job = self.materialize()
        capsule = json.loads((job / "capsule.json").read_text(encoding="utf-8"))
        version = next(v for v in capsule["versions"] if v["version_id"] == "v3")
        version["decisions"] = version["decisions"][:1]
        rows = REPORT.get_rows(capsule, {"errors": []})
        self.assertEqual(rows[1]["confirmed by"], "not confirmed")

    def test_a_rollout_that_ran_no_gate_produces_a_report_that_says_so(self):
        rows, text = self.report(self.materialize(VALID))
        self.assertEqual(rows, [])
        self.assertIn("No decision log was recorded", text)

    def test_a_finding_appears_beside_the_decision_it_names(self):
        job = self.materialize()
        capsule = json.loads((job / "capsule.json").read_text(encoding="utf-8"))
        version = next(v for v in capsule["versions"] if v["version_id"] == "v2")
        version["decisions"][0]["verdict"] = "clears"
        (job / "capsule.json").write_text(
            json.dumps(capsule, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows, text = self.report(job)
        self.assertTrue(rows[0]["findings"], rows[0])
        self.assertIn("decision:verdict_inconsistent:v2:1", text)
        self.assertIn("## Findings against a decision", text)

    def test_a_finding_about_the_record_is_not_attached_to_a_decision(self):
        job = self.materialize()
        capsule = json.loads((job / "capsule.json").read_text(encoding="utf-8"))
        capsule["source"]["exclusions"] = ["*.pyc"]
        (job / "capsule.json").write_text(
            json.dumps(capsule, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows, text = self.report(job)
        self.assertFalse(any(row["findings"] for row in rows))
        self.assertIn("## Findings against the record", text)
        self.assertIn("semantic:source:exclusions_mismatch", text)

    def test_the_limits_are_always_printed(self):
        for source in (GATED, VALID):
            with self.subTest(source=source.name):
                _, text = self.report(self.materialize(source))
                self.assertIn("What this report does not say", text)
                self.assertIn("not the probability a decision was right", text)
                self.assertIn("says nothing about the sealed reward", text)

    def test_a_pipe_in_a_value_cannot_split_the_table(self):
        capsule = json.loads((GATED / "job/capsule.json").read_text(encoding="utf-8"))
        capsule["rollout"]["id"] = "roll|out"
        text = REPORT.render(REPORT.get_rows(capsule, {"errors": []}), {"errors": []}, capsule)
        import re
        rows = [line for line in text.splitlines() if line.startswith("| ")]
        header, first = rows[0], rows[2]
        # Only an unescaped pipe separates columns; the escaped one renders as a literal.
        separators = lambda line: len(re.findall(r"(?<!\\)\|", line))
        self.assertEqual(separators(first), separators(header))
        self.assertIn(r"roll\|out", text)

    def test_a_record_of_another_schema_is_refused(self):
        capsule = json.loads((GATED / "job/capsule.json").read_text(encoding="utf-8"))
        capsule["schema_version"] = "proofpress/rsi-exam-trajectory/v2"
        with self.assertRaises(REPORT.ReportError):
            REPORT.get_rows(capsule, {"errors": []})

    def test_the_header_names_the_submitted_class(self):
        job = self.materialize()
        capsule = json.loads((job / "capsule.json").read_text(encoding="utf-8"))
        capsule["final_submission"]["version_ids"] = ["v2", "v3"]
        text = REPORT.render(REPORT.get_rows(capsule, {"errors": []}), {"errors": []}, capsule)
        self.assertIn("indistinguishable to the grader", text)


if __name__ == "__main__":
    unittest.main()
