"""Structural and cross-layer checks for the NANDA ARA companion."""

from __future__ import annotations

from pathlib import Path
import json
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
ARA = REPO / "ara" / "nanda-2026"


def sections(path: Path, prefix: str) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(rf"^## ({prefix}\d+)\s+[^\n]*$", text, flags=re.M))
    return {
        match.group(1): text[match.start(): matches[index + 1].start()]
        if index + 1 < len(matches) else text[match.start():]
        for index, match in enumerate(matches)
    }


class NandaAraStructureTests(unittest.TestCase):
    def test_required_layers_and_files_exist(self):
        required = [
            "PAPER.md",
            "logic/problem.md",
            "logic/claims.md",
            "logic/concepts.md",
            "logic/experiments.md",
            "logic/related_work.md",
            "logic/solution/architecture.md",
            "logic/solution/constraints.md",
            "src/artifacts.md",
            "src/environment.md",
            "trace/exploration_tree.yaml",
            "evidence/README.md",
            "evidence/results/paper-results.json",
            "submission/main.tex",
            "submission/README.md",
        ]
        self.assertEqual([], [path for path in required if not (ARA / path).is_file()])

    def test_claim_cards_have_required_fields(self):
        claims = sections(ARA / "logic" / "claims.md", "C")
        self.assertEqual({f"C{i:02}" for i in range(1, 9)}, set(claims))
        fields = (
            "Statement", "Conditions", "Sources", "Status", "Falsification criteria",
            "Proof", "Evidence basis", "Dependencies", "Tags",
        )
        for claim_id, body in claims.items():
            with self.subTest(claim=claim_id):
                for field in fields:
                    self.assertIn(f"**{field}:**", body)

    def test_claim_experiment_links_are_bidirectional(self):
        claims = sections(ARA / "logic" / "claims.md", "C")
        experiments = sections(ARA / "logic" / "experiments.md", "E")
        self.assertEqual({f"E{i:02}" for i in range(1, 7)}, set(experiments))
        for claim_id, claim in claims.items():
            proof = set(re.findall(r"\[(E\d+)\]", claim))
            self.assertTrue(proof, claim_id)
            for experiment_id in proof:
                self.assertIn(experiment_id, experiments)
                self.assertRegex(experiments[experiment_id], rf"\*\*Verifies:\*\*[^\n]*\b{claim_id}\b")

    def test_experiment_cards_have_required_fields(self):
        experiments = sections(ARA / "logic" / "experiments.md", "E")
        fields = "Verifies", "Run", "Setup", "Procedure", "Expected outcome", "Evidence"
        for experiment_id, body in experiments.items():
            with self.subTest(experiment=experiment_id):
                for field in fields:
                    self.assertIn(f"**{field}:**", body)

    def test_exploration_tree_has_unique_typed_nodes_and_negative_result(self):
        text = (ARA / "trace" / "exploration_tree.yaml").read_text(encoding="utf-8")
        ids = re.findall(r"^\s+- id: (N\d+)$", text, flags=re.M)
        types = re.findall(r"^\s+type: (\w+)$", text, flags=re.M)
        support = re.findall(r"^\s+support_level: (\w+)$", text, flags=re.M)
        self.assertGreaterEqual(len(ids), 12)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), len(types))
        self.assertEqual(len(ids), len(support))
        self.assertTrue(set(support) <= {"explicit", "inferred"})
        self.assertIn("unsupported efficacy claim", text)
        self.assertIn("bound by committed capsule reward digests", text)
        self.assertIn("rounded committed pre-probe summary", text)

    def test_manuscript_uses_generated_claim_boundary(self):
        paper = (ARA / "submission/main.tex").read_text(encoding="utf-8")
        self.assertIn("author-designed characterization", paper)
        self.assertIn("do not estimate detection rates", paper)
        self.assertIn("only eight match", paper)
        self.assertIn("neither authenticates the grader", paper)

    def test_ieee_review_source_is_anonymous_and_result_aligned(self):
        source = (ARA / "submission" / "main.tex").read_text(encoding="utf-8")
        self.assertIn(r"\documentclass[conference]{IEEEtran}", source)
        self.assertIn("Anonymous Authors", source)
        self.assertIn("18 verified records", source)
        self.assertIn("nine per arm", source)
        self.assertNotRegex(source, r"Thru-Echoes|chenmingtang|Richard|Oliver")
        self.assertNotRegex(source, r"github\.com/(?!aiming-lab/RSI-Exam|ARA-Labs/Agent-Native-Research-Artifact|harveyai/harvey-labs)")

    def test_every_table_outcome_matches_execution(self):
        source = (ARA / "submission/main.tex").read_text()
        report = json.loads((REPO / "studies/decision-audit/fault-results.json").read_text())
        rows = re.findall(r"^(.+?) & ([AR])\s*&\s*([AR])\s*&\s*([AR])", source, re.M)
        self.assertEqual(len(report["cases"]), len(rows))
        labels = ["None (valid control)", "Excluded caches differ; full hashes refreshed",
                  "Reward and declaration rewritten together", "Unrecognized version status",
                  "Referenced measurement file removed", "Recorded orientation reversed",
                  "Recorded estimate increased by one", "Parent/candidate measurements exchanged",
                  "Submitted provisional left unconfirmed", "Submission changed; version claim retained",
                  "Recorded snapshot removed", "Unrecorded snapshot added"]
        for case, row, label in zip(report["cases"], rows, labels):
            self.assertEqual(label, row[0])
            expected = tuple("A" if case["outcomes"][key] == "accept" else "R"
                             for key in ("structure", "bindings", "full"))
            self.assertEqual(expected, row[1:], case["id"])


if __name__ == "__main__":
    unittest.main()
