"""The program overlay is RSI-Exam's program text plus exactly the sentences the record needs.

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
    "Before your first change, copy the inherited /app/methods/main to /app/methods/versions/v0",
    "Name snapshot directories exactly v0, v1, v2, and so on: a lowercase v followed by an integer",
    "Append the log line for a version immediately after you snapshot it, before any further edit",
    "state its parent version id and whether it was kept or reverted",
    # The image copies only environment/methods into /app/methods, so versions/ does not exist yet.
    "mkdir -p /app/methods/versions && cp -r /app/methods/main /app/methods/versions/v0",
)


class OverlayCarriesTheConventions(unittest.TestCase):
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
