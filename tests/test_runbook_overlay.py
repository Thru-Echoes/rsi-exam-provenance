"""The program overlay is RSI-Exam's program text with a loop that routes bookkeeping through the mounted helper.

Run: python3 -m unittest tests.test_runbook_overlay
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OVERLAY = REPO / "runbook" / "autoresearch-provenance.md"
TEMPLATE = REPO / "runbook" / "autoresearch-provenance.j2"

# Sentences the record producer depends on, one per defect a real rollout exposed.
REQUIRED = (
    "run exactly `python3 /app/provenance.py init`",
    "snapshots the inherited main/ as v0",
    "prints your run window",
    "never create, edit, delete or copy into or out of those paths",
    "`python3 /app/provenance.py evaluate --change \"<one short line: what changed>\"`",
    "Do not run selfcheck.py yourself",
    "`python3 /app/provenance.py decide v<N> kept`",
    "`python3 /app/provenance.py decide v<N> reverted`",
    "Never restore or combine versions by copying files by hand",
    "run `python3 /app/provenance.py finalize`",
)


MOUNT = REPO / "runbook" / "mount-provenance.yaml"


class OverlayCarriesTheConventions(unittest.TestCase):
    def test_the_mount_file_adds_only_the_helper(self):
        text = MOUNT.read_text(encoding="utf-8")
        self.assertIn('"${ARB_PROVENANCE_PY}:/app/provenance.py:ro"', text)
        self.assertIn('"${ARB_PROGRAM}:/app/AUTORESEARCH.md:ro"', text)
        self.assertIn('"${ARB_BUDGET_PY}:/app/budget.py:ro"', text)
        declared = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        for forbidden in ("network_mode", "networks:"):
            self.assertNotIn(forbidden, declared)
        root = os.environ.get("RSI_EXAM_ROOT")
        source = Path(root) / "infra/prompts/mount.yaml" if root else None
        if source is not None and source.is_file():
            theirs = [l for l in source.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#")]
            ours = [l for l in text.splitlines() if not l.lstrip().startswith("#")
                    and "ARB_PROVENANCE_PY" not in l]
            self.assertEqual(ours, theirs)

    def test_every_required_sentence_is_present(self):
        text = OVERLAY.read_text(encoding="utf-8")
        for sentence in REQUIRED:
            self.assertIn(sentence, text, sentence)

    def test_the_template_embeds_the_instruction(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("{{ instruction }}", text)
        self.assertIn("/app/AUTORESEARCH.md", text)

    def test_the_template_carries_the_same_loop(self):
        md = OVERLAY.read_text(encoding="utf-8").split("LOOP FOREVER", 1)[1]
        j2 = TEMPLATE.read_text(encoding="utf-8").split("LOOP FOREVER", 1)[1].split("================================ TASK", 1)[0]
        self.assertEqual(md.strip(), j2.strip())

    def test_the_text_before_the_loop_is_rsi_exams_own(self):
        root = os.environ.get("RSI_EXAM_ROOT")
        source = Path(root) / "infra/prompts/autoresearch.md" if root else None
        if source is None or not source.is_file():
            self.skipTest("RSI_EXAM_ROOT is not set to a checkout with infra/prompts/autoresearch.md")
        ours = OVERLAY.read_bytes().split(b"LOOP FOREVER", 1)[0]
        theirs = source.read_bytes().split(b"LOOP FOREVER", 1)[0]
        self.assertEqual(ours, theirs)

    def test_the_overlay_keeps_the_loop(self):
        text = OVERLAY.read_text(encoding="utf-8")
        self.assertIn("LOOP FOREVER", text)
        self.assertIn("/app/methods/main/", text)


if __name__ == "__main__":
    unittest.main()
