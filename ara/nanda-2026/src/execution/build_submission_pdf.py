#!/usr/bin/env python3
"""Render the working NANDA manuscript as a four-page IEEE-style proof PDF.

This is a layout proof, not the official IEEE template. It intentionally uses
anonymous author text until the joint anonymity and authorship decisions close.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    FrameBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


REPO = Path(__file__).resolve().parents[4]
ARA = REPO / "ara" / "nanda-2026"
OUTPUT = REPO / "output" / "pdf" / "nanda-2026-track3-working-paper.pdf"
PAPER = ARA / "PAPER.md"
RESULTS = ARA / "evidence" / "results" / "paper-results.json"

# Stable PDF IDs and timestamps make identical source produce identical bytes.
rl_config.invariant = 1


def _font(name: str, candidates: list[str]) -> str:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, path))
            return name
    return "Helvetica"


BODY_FONT = _font(
    "PaperSerif",
    [
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Supplemental/Times.ttf",
    ],
)
BOLD_FONT = _font(
    "PaperSerifBold",
    [
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        "/System/Library/Fonts/Supplemental/Times Bold.ttf",
    ],
)


def _inline(text: str) -> str:
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text.replace("&", "&amp;").replace("—", "-").replace("–", "-")


def _paper_body() -> list[tuple[str, str | list[str]]]:
    text = PAPER.read_text(encoding="utf-8")
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    start = text.index("## Abstract")
    text = text[start:]
    text = re.sub(r"## 10\. Open decisions.*?(?=## References)", "", text, flags=re.S)
    parts: list[tuple[str, str | list[str]]] = []
    paragraph: list[str] = []
    bullets: list[str] = []
    current_section = ""

    def flush() -> None:
        nonlocal paragraph, bullets
        if paragraph:
            parts.append(("paragraph", " ".join(paragraph)))
            paragraph = []
        if bullets:
            parts.append(("bullets", bullets))
            bullets = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith("## "):
            flush()
            current_section = re.sub(r"^##\s+(?:\d+\.\s*)?", "", line)
            parts.append(("h2", current_section))
        elif line.startswith("### "):
            flush()
            parts.append(("h3", re.sub(r"^###\s+(?:\d+\.\d+\s*)?", "", line)))
        elif line.startswith("- "):
            if paragraph:
                flush()
            bullets.append(line[2:])
        elif re.match(r"^\d+\.\s", line) and current_section == "References":
            flush()
            bullets.append(line)
        elif re.match(r"^\d+\.\s", line):
            flush()
            parts.append(("numbered", line))
        elif line.startswith("|"):
            continue
        elif line.startswith("**Draft status:**"):
            continue
        else:
            paragraph.append(line)
    flush()
    return parts


def _result_table(styles: dict[str, ParagraphStyle]) -> Table:
    result = json.loads(RESULTS.read_text(encoding="utf-8"))
    rows = [["Stage", "Blocks", "Fav. I", "Fav. H", "Mean I-H"]]
    for stage in ("haiku", "sonnet", "opus"):
        item = result["primary_summary"]["by_stage"][stage]
        mean = float(item["mean_instrument_minus_helper"])
        suffix = "*" if stage == "opus" else ""
        rows.append([
            stage.title() + suffix,
            str(item["observed_blocks"]),
            str(item["favors_instrument"]),
            str(item["favors_helper"]),
            f"{mean:.4f}{suffix}",
        ])
    rows.append(["Total", "10", "3", "7", "-"])
    rows.append([Paragraph("<i>* Rounded summary-backed inputs.</i>", styles["table_note"]), "", "", "", ""])
    table = Table(rows, colWidths=[0.57 * inch, 0.43 * inch, 0.43 * inch, 0.43 * inch, 0.67 * inch])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
        ("FONTNAME", (0, 1), (-1, -2), BODY_FONT),
        ("FONTSIZE", (0, 0), (-1, -2), 6.6),
        ("LEADING", (0, 0), (-1, -2), 7.4),
        ("ALIGN", (1, 0), (-1, -2), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEBELOW", (0, -3), (-1, -3), 0.25, colors.grey),
        ("SPAN", (0, -1), (-1, -1)),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return table


def build() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = letter
    margin_x = 0.62 * inch
    margin_bottom = 0.62 * inch
    gap = 0.24 * inch
    title_height = 0.92 * inch
    body_top = page_height - 0.55 * inch
    column_width = (page_width - 2 * margin_x - gap) / 2

    title_frame = Frame(margin_x, body_top - title_height, page_width - 2 * margin_x,
                        title_height, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                        id="title")
    first_columns = [
        Frame(margin_x, margin_bottom, column_width, body_top - title_height - margin_bottom,
              leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0, id="first-left"),
        Frame(margin_x + column_width + gap, margin_bottom, column_width,
              body_top - title_height - margin_bottom, leftPadding=0, rightPadding=0,
              topPadding=4, bottomPadding=0, id="first-right"),
    ]
    later_columns = [
        Frame(margin_x, margin_bottom, column_width, body_top - margin_bottom,
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="left"),
        Frame(margin_x + column_width + gap, margin_bottom, column_width, body_top - margin_bottom,
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="right"),
    ]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(BODY_FONT, 7)
        canvas.drawCentredString(page_width / 2, 0.34 * inch, str(doc.page))
        canvas.restoreState()

    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=letter, leftMargin=margin_x, rightMargin=margin_x,
        topMargin=0.55 * inch, bottomMargin=margin_bottom,
        title="Auditable Keeps", author="Anonymous authors - working proof",
    )
    doc.addPageTemplates([
        PageTemplate(id="First", frames=[title_frame, *first_columns], onPage=footer,
                     autoNextPageTemplate="Later"),
        PageTemplate(id="Later", frames=later_columns, onPage=footer),
    ])

    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("title", parent=base["Title"], fontName=BOLD_FONT,
                                fontSize=15.5, leading=17, alignment=TA_CENTER,
                                spaceAfter=3),
        "authors": ParagraphStyle("authors", parent=base["Normal"], fontName=BODY_FONT,
                                  fontSize=8, leading=9, alignment=TA_CENTER),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=BOLD_FONT,
                             fontSize=10.0, leading=11.0, spaceBefore=6, spaceAfter=2.5,
                             keepWithNext=True),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=BOLD_FONT,
                             fontSize=9.2, leading=10.0, spaceBefore=4, spaceAfter=2,
                             keepWithNext=True),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName=BODY_FONT,
                               fontSize=9.5, leading=10.7, alignment=TA_JUSTIFY,
                               spaceAfter=4.0),
        "abstract": ParagraphStyle("abstract", parent=base["BodyText"], fontName=BODY_FONT,
                                   fontSize=9.0, leading=10.2, alignment=TA_JUSTIFY,
                                   leftIndent=5, rightIndent=5, spaceAfter=4),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontName=BODY_FONT,
                                 fontSize=9.15, leading=10.3, leftIndent=9,
                                 firstLineIndent=-6, spaceAfter=2),
        "reference": ParagraphStyle("reference", parent=base["BodyText"], fontName=BODY_FONT,
                                    fontSize=8.1, leading=9.0, leftIndent=10,
                                    firstLineIndent=-10, spaceAfter=1.7),
        "table_note": ParagraphStyle("table_note", parent=base["BodyText"], fontName=BODY_FONT,
                                     fontSize=6.2, leading=6.8),
    }

    story = [
        Paragraph("Auditable Keeps: Offline-Verifiable Decision Provenance for Self-Improving Agents",
                  styles["title"]),
        Paragraph("Anonymous authors - working layout proof; authorship and anonymity pending",
                  styles["authors"]),
        FrameBreak(),
    ]
    in_abstract = False
    in_references = False
    table_added = False
    for kind, content in _paper_body():
        if kind == "h2":
            heading = str(content)
            in_abstract = heading == "Abstract"
            in_references = heading == "References"
            story.append(Paragraph(_inline(heading.upper()), styles["h2"]))
            continue
        if kind == "h3":
            story.append(Paragraph(_inline(str(content)), styles["h3"]))
            continue
        if kind == "paragraph":
            style = styles["abstract"] if in_abstract else styles["body"]
            rendered = Paragraph(_inline(str(content)), style)
            if str(content).startswith("All runs are reduced-window"):
                story.append(KeepTogether([rendered]))
            else:
                story.append(rendered)
            in_abstract = False
            continue
        if kind == "numbered":
            story.append(Paragraph(_inline(str(content)), styles["bullet"]))
            continue
        assert isinstance(content, list)
        flowables = []
        for item in content:
            prefix = "" if in_references else "- "
            style = styles["reference"] if in_references else styles["bullet"]
            flowables.append(Paragraph(_inline(prefix + item), style))
        story.extend(flowables)
        if not table_added and not in_references and any("Haiku:" in item for item in content):
            story.extend([Spacer(1, 2), KeepTogether([
                Paragraph("TABLE I. PRIMARY DIRECTION BY MODEL STAGE", styles["h3"]),
                _result_table(styles),
            ]), Spacer(1, 2)])
            table_added = True

    doc.build(story)
    return OUTPUT


if __name__ == "__main__":
    print(build())
