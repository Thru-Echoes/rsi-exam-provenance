#!/usr/bin/env python3
"""Turn a verified provenance record into a table a human can audit.

Input: a record (``proofpress/rsi-exam-trajectory/v3``) and the verifier's result for it. Output:
one row per decision the gate recorded, in log order, carrying the rollout and version together,
the parent, the visible score, the interval, the verdict, the action, what confirmed it, and how
many of its evidence files the verifier checked.

What this report is for: reading a rollout's decisions without opening the record. What it is not
for: deciding whether a score moved for a real reason. Every interval here describes a measured
effect on a visible split that the agent had already used; it is not the probability a decision was
right, and it says nothing about the sealed reward. The report prints those limits with the table
rather than leaving them to be remembered.

Side effects: writes the output file when ``--output`` is given, otherwise writes to stdout. Zero
third-party dependencies; Python 3.11+.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "proofpress/rsi-exam-trajectory/v3"
COLUMNS = ("rollout / version", "parent", "score", "interval", "verdict", "action",
           "confirmed by", "evidence")
LIMITS = (
    "The interval describes the measured effect on a visible split the agent had already used. It "
    "is not the probability a decision was right, and it says nothing about the sealed reward.",
    "A verdict is the statistics; an action is what the gate did about it. They are separate "
    "columns because they answer separate questions.",
    "`evidence` counts the files behind a decision that the verifier recomputed or bound by "
    "digest, not the strength of the evidence.",
)


class ReportError(ValueError):
    """The record or the verifier result is not one this report can read."""


def get_rows(capsule: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per decision, in log order. Pure function; raises ReportError.

    ``confirmed by`` names the log line that resolved a provisional, or says plainly that nothing
    did. A decision the verifier reported on carries the first finding against it, so a reader sees
    the finding beside the decision rather than in a separate list.
    """
    if capsule.get("schema_version") != SCHEMA_VERSION:
        raise ReportError(f"not a {SCHEMA_VERSION} record")
    rollout = capsule.get("rollout", {}).get("id")
    if not rollout:
        raise ReportError("record has no rollout id")

    findings: dict[tuple[str, int], list[str]] = {}
    for error in result.get("errors", []):
        parts = error.split(":")
        for index, part in enumerate(parts):
            if part.isdigit() and index >= 2:
                findings.setdefault((parts[index - 1], int(part)), []).append(error)
                break

    resolved_by: dict[int, int] = {}
    for version in capsule.get("versions", []):
        for entry in version.get("decisions", []):
            if entry.get("resolves_log_line") is not None:
                resolved_by[entry["resolves_log_line"]] = entry["log_line"]

    rows: list[dict[str, Any]] = []
    for version in capsule.get("versions", []):
        vid = version["version_id"]
        score = (version.get("visible") or {}).get("score")
        for entry in version.get("decisions", []):
            line = entry["log_line"]
            interval = entry["interval"]
            if entry["kind"] == "confirmation":
                confirmed = f"is the confirmation of line {entry.get('resolves_log_line')}"
            elif entry["disposition"] != "provisional":
                confirmed = "no confirmation required"
            elif line in resolved_by:
                confirmed = f"line {resolved_by[line]}"
            else:
                confirmed = "not confirmed"
            rows.append({
                "rollout / version": f"{rollout} / {vid}",
                "parent": entry.get("parent_id") or "none",
                "score": "-" if score is None else f"{score:g}",
                "interval": (f"[{interval['lower']:g}, {interval['upper']:g}]"
                             f" at {interval['level']:g}"),
                "verdict": entry["verdict"],
                "action": entry["disposition"],
                "confirmed by": confirmed,
                "evidence": str(len(entry.get("evidence", []))),
                "log_line": line,
                "findings": findings.get((vid, line), []),
            })
    rows.sort(key=lambda row: row["log_line"])
    return rows


def render(rows: list[dict[str, Any]], result: dict[str, Any], capsule: dict[str, Any]) -> str:
    """The report as Markdown: a header stating what was verified, the table, then the limits."""
    lines = [f"# Decision evidence: {capsule.get('capsule_id', 'unknown record')}", ""]
    lines.append(f"- integrity: **{result.get('integrity', 'unknown')}**; "
                 f"coverage: **{result.get('coverage', 'unknown')}**; "
                 f"decisions: **{len(rows)}**")
    benchmark = capsule.get("benchmark", {})
    if benchmark.get("statistic"):
        lines.append(f"- statistic: `{benchmark['statistic']}`"
                     + (f", unit `{benchmark['unit']}`" if benchmark.get("unit") else ""))
    submission = capsule.get("final_submission", {})
    if submission.get("version_ids"):
        named = ", ".join(f"`{vid}`" for vid in submission["version_ids"])
        lines.append(f"- submitted method tree: {named}"
                     + (" (indistinguishable to the grader)"
                        if len(submission["version_ids"]) > 1 else ""))
    lines.append("")

    if not rows:
        lines.append("No decision log was recorded for this rollout.")
    else:
        lines.append("| " + " | ".join(COLUMNS) + " |")
        lines.append("|" + "|".join(" --- " for _ in COLUMNS) + "|")
        for row in rows:
            # A pipe in any value would silently split the row into different columns than the
            # header, which is a misreading rather than a rendering glitch.
            lines.append("| " + " | ".join(str(row[column]).replace("|", "\\|")
                                           for column in COLUMNS) + " |")
        flagged = [row for row in rows if row["findings"]]
        if flagged:
            lines.extend(["", "## Findings against a decision", ""])
            for row in flagged:
                lines.append(f"- line {row['log_line']} ({row['rollout / version']}): "
                             + "; ".join(f"`{finding}`" for finding in row["findings"]))

    other = [error for error in result.get("errors", [])
             if not any(error in row["findings"] for row in rows)]
    if other:
        lines.extend(["", "## Findings against the record", ""])
        lines.extend(f"- `{error}`" for error in other)

    lines.extend(["", "## What this report does not say", ""])
    lines.extend(f"- {limit}" for limit in LIMITS)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capsule", required=True, help="the provenance record")
    parser.add_argument("--result", default=None,
                        help="the verifier's JSON result; omit to verify the record here")
    parser.add_argument("--output", default=None, help="default: stdout")
    args = parser.parse_args(argv)

    capsule_path = Path(args.capsule)
    try:
        capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"report failed: capsule unreadable: {exc.__class__.__name__}", file=sys.stderr)
        return 2
    if args.result:
        try:
            result = json.loads(Path(args.result).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"report failed: result unreadable: {exc.__class__.__name__}", file=sys.stderr)
            return 2
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "profile"))
        from verify_capsule import verify_capsule       # noqa: PLC0415
        result = verify_capsule(capsule_path)

    try:
        text = render(get_rows(capsule, result), result, capsule)
    except ReportError as exc:
        print(f"report failed: {exc}", file=sys.stderr)
        return 2
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
