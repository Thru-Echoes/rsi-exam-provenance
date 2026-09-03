#!/usr/bin/env python3
"""Build a TRACE session document from an RSI-Exam decision log.

Mapping: docs/decision-log-contract.md (the ``confidence`` object and the event
mapping). Pure functions; ``main`` reads one file and writes one file (or
stdout). Standard library only, so it runs anywhere the gate runs. No text is
copied from anywhere: every string in the output is built from the templates
below and the log's numbers and ids.

The document declares ``trace_version`` ``0.5.0``: it is valid under the
shipped TRACE 0.5.0 schema (``decision.confidence`` is an additive property)
and is the version the ProofPress evidence adapter accepts. When TRACE ships a
typed ``confidence`` field, the constant is the one place to change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

TRACE_VERSION = "0.5.0"
CONTEXT = "https://trace-protocol.org/v0.3"
SOURCE_SCHEMA = "rsi-exam-decision-log/v1"
IMPORTER = "rsi-exam-provenance/trace_from_decisions.py 0.1"
LOCATOR_BASE = "artifacts/app/methods"
GATE_ACTOR = {"type": "system", "id": "rsi-exam-gate/decide.py", "role": "decision-gate"}
CONFIDENCE_KEYS = ("interval", "method", "sample_size", "evidence_digests", "contract", "statistic", "unit",
                   "direction", "estimate", "min_effect", "verdict", "evidence", "holdout")
ROLES = ("parent", "candidate", "holdout-parent", "holdout-candidate", "receipt-parent", "receipt-candidate")
HOLDOUT_KEYS = ("estimate", "interval", "sample_size", "verdict", "evidence", "evidence_digests")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_project_key(label: str) -> str:
    """The TRACE specification's canonical key algorithm (section 3.2.2)."""
    key = unicodedata.normalize("NFC", label).strip().casefold()
    key = re.sub(r"[\s/_]+", "-", key)
    key = re.sub(r"[^\w.-]+", "-", key)
    key = re.sub(r"\.{2,}", ".", key)
    key = re.sub(r"-{2,}", "-", key)
    key = key.strip(".-")
    if not key or key in ("auto", "shared"):
        raise ValueError(f"label {label!r} does not name a project")
    return key


def _sanitize_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", text)


def _check_line(line: dict[str, Any]) -> None:
    """Cross-field rules the contract states; a violation refuses the whole conversion."""
    if line.get("schema") != SOURCE_SCHEMA:
        raise ValueError(f"line {line.get('line')}: schema is not {SOURCE_SCHEMA}")
    interval = line["interval"]
    low, high, level = interval["lower"], interval["upper"], interval["level"]
    if not all(math.isfinite(x) for x in (low, high, level, line["estimate"], line["min_effect"])):
        raise ValueError(f"line {line['line']}: non-finite number")
    if low > high:
        raise ValueError(f"line {line['line']}: interval lower exceeds upper")
    if not 0.0 < level < 1.0:
        raise ValueError(f"line {line['line']}: level outside the open unit interval")
    if line["min_effect"] < 0.0:
        raise ValueError(f"line {line['line']}: negative min_effect")
    expected_verdict = "clears" if low > line["min_effect"] else ("below" if high < 0.0 else "inconclusive")
    if line["verdict"] != expected_verdict:
        raise ValueError(f"line {line['line']}: verdict {line['verdict']} contradicts the interval")
    roles = [e["role"] for e in line["evidence"]]
    if len(set(roles)) != len(roles) or roles[:2] != ["parent", "candidate"] or any(r not in ROLES for r in roles):
        raise ValueError(f"line {line['line']}: evidence roles must be unique, known, and start with parent, candidate")
    digests = {e["role"]: "sha256:" + e["sha256"] for e in line["evidence"]}
    for e in line["evidence"]:
        loc = e["locator"]
        if (not loc or loc.startswith("/") or "\\" in loc or "%" in loc or ":" in loc
                or any(part in ("..", "", ".") for part in loc.split("/")) or loc.split("/", 1)[0] in ("versions", "main")):
            raise ValueError(f"line {line['line']}: bad evidence locator {loc!r}")
    if line["evidence_digests"] != digests:
        raise ValueError(f"line {line['line']}: evidence_digests do not match evidence")
    holdout = line.get("holdout")
    holdout_verdict = holdout["verdict"] if holdout else None
    if holdout:
        hroles = [e["role"] for e in holdout["evidence"]]
        if len(set(hroles)) != len(hroles) or any(r not in ROLES for r in hroles):
            raise ValueError(f"line {line['line']}: holdout evidence roles must be unique and known")
        if set(e["sha256"] for e in holdout["evidence"]) & set(e["sha256"] for e in line["evidence"]):
            raise ValueError(f"line {line['line']}: holdout evidence aliases the primary evidence")
        if holdout["interval"]["level"] != level:
            raise ValueError(f"line {line['line']}: holdout level differs from the primary level")
    if line.get("replicates"):
        if line["replicates"] != line["version_id"]:
            raise ValueError(f"line {line['line']}: replicates must equal version_id")
        if line["disposition"] == "provisional":
            raise ValueError(f"line {line['line']}: a replication line cannot be provisional")
        expected = "keep" if line["verdict"] == "clears" and holdout_verdict in (None, "clears") else "revert"
    else:
        if line["verdict"] == "below":
            expected = "revert"
        elif line["verdict"] == "clears" and holdout_verdict in (None, "clears"):
            expected = "keep"
        else:
            expected = "provisional"
    if line["disposition"] != expected:
        raise ValueError(f"line {line['line']}: disposition {line['disposition']} contradicts the rule ({expected})")


def _confidence(line: dict[str, Any]) -> dict[str, Any]:
    block = {key: (SOURCE_SCHEMA if key == "contract" else line[key]) for key in CONFIDENCE_KEYS if key != "holdout"}
    holdout = line.get("holdout")
    block["holdout"] = {key: holdout[key] for key in HOLDOUT_KEYS} if holdout else None
    return block


def _rationale(line: dict[str, Any]) -> str:
    low, high = line["interval"]["lower"], line["interval"]["upper"]
    statistic = line["statistic"].replace("_", " ")
    statistic = statistic[:1].upper() + statistic[1:]
    unit = f" {line['unit']}" if line.get("unit") else ""
    level = f"{line['interval']['level'] * 100:g}"
    method = line["method"]["name"].replace("_", " ")
    return (
        f"{statistic} {line['estimate']:+.1f}{unit} (n={line['sample_size']}); "
        f"{level} percent {method} interval [{low:+.1f}, {high:+.1f}]; verdict {line['verdict']}."
    )


def _event(event_id: str, session_id: str, line: dict[str, Any], agent: dict[str, Any],
           description: str, disposition: str, revision_note: str | None, revises: str | None) -> dict[str, Any]:
    decision: dict[str, Any] = {
        "description": description,
        "rationale": _rationale(line),
        "proposed_by": agent,
        "disposition": disposition,
        "resolved_by": None if disposition == "proposed" else GATE_ACTOR,
        "revision_note": revision_note,
        "revises_event_id": revises,
        "suggestion_type": "proactive",
        "tags": ["rsi-exam", "decision-gate", line["version_id"]],
        "warnings": [],
        "confidence": _confidence(line),
    }
    return {
        "id": event_id,
        "timestamp": line["timestamp"],
        "session_id": session_id,
        "type": "decision",
        "actor": agent,
        "tool_call": None,
        "decision": decision,
        "annotation": None,
        "state_change": None,
        "contribution": None,
        "context": {"conversation_turn": None, "reasoning_summary": None, "conversation_snippet": None,
                    "related_event_ids": []},
    }


def build_session(lines: list[dict[str, Any]], *, project: str, rollout_id: str, task: str, harness: str,
                  model: str, decision_log_sha256: str, importer: str = IMPORTER,
                  locator_base: str = LOCATOR_BASE) -> dict[str, Any]:
    """Map decision-log lines (in file order) onto one completed TRACE session document."""
    if not lines:
        raise ValueError("decision log is empty")
    session_id = _sanitize_id(f"rsiexam_{rollout_id}")
    agent = {"type": "ai", "id": f"{harness}:{model}", "role": "rollout-agent"}
    events: list[dict[str, Any]] = []
    open_provisional: dict[str, tuple[str, str]] = {}
    counts = {"keep": 0, "revert": 0, "provisional": 0, "replicated": 0}

    for number, line in enumerate(lines, start=1):
        if line.get("line") != number:
            raise ValueError(f"line {number}: line field {line.get('line')!r} does not match position")
        _check_line(line)
        event_id = f"evt_{len(events) + 1:03d}"
        version, parent = line["version_id"], line["parent_id"]
        if line.get("replicates"):
            opened = open_provisional.get(line["replicates"])
            if opened is None:
                raise ValueError(f"line {number} replicates {line['replicates']} but no provisional decision is open")
            original_id, original_parent = opened
            if parent != original_parent:
                raise ValueError(f"line {number}: replication parent {parent} differs from the provisional line's parent {original_parent}")
            original = next(e for e in events if e["id"] == original_id)
            disposition = "accepted" if line["disposition"] == "keep" else "rejected"
            note = None if disposition == "accepted" else "Replication did not clear the minimum effect."
            events.append(_event(event_id, session_id, line, agent,
                                 f"Replication of {version} on fresh seeds (parent {parent})",
                                 disposition, note, original_id))
            original["decision"]["disposition"] = disposition
            original["decision"]["resolved_by"] = GATE_ACTOR
            original["decision"]["revision_note"] = f"Resolved by replication {event_id}."
            del open_provisional[line["replicates"]]
            counts["replicated"] += 1
            continue
        if line["disposition"] == "provisional" and open_provisional:
            raise ValueError(f"line {number} opens a second provisional decision")
        if any(parent == v for v in open_provisional):
            raise ValueError(f"line {number} builds on {parent} while its provisional decision is unresolved")
        if line["disposition"] == "keep":
            events.append(_event(event_id, session_id, line, agent, f"Keep {version} (parent {parent})",
                                 "accepted", None, None))
        elif line["disposition"] == "revert":
            events.append(_event(event_id, session_id, line, agent, f"Revert {version} (parent {parent})",
                                 "rejected", "Interval entirely below zero.", None))
        else:
            events.append(_event(event_id, session_id, line, agent,
                                 f"Keep {version} provisionally (parent {parent})", "proposed", None, None))
            open_provisional[version] = (event_id, parent)
        counts[line["disposition"]] += 1

    summary = (f"RSI-Exam rollout {rollout_id} ({task}, {harness}, {model}): {counts['keep']} kept, "
               f"{counts['revert']} reverted, {counts['provisional']} provisional, {counts['replicated']} replicated.")
    return {
        "context": CONTEXT,
        "trace_version": TRACE_VERSION,
        "id": session_id,
        "created": events[0]["timestamp"],
        "ended": events[-1]["timestamp"],
        "status": "completed",
        "metadata": {
            "project": project,
            "project_key": canonical_project_key(project),
            "experiment_id": rollout_id,
            "description": f"Decision-gate record for RSI-Exam rollout {rollout_id}",
            "participants": [agent, GATE_ACTOR],
            "environment": None,
            "tags": ["rsi-exam", "decision-gate"],
            "doi": None,
            "custom": {"source": SOURCE_SCHEMA, "importer": importer, "rollout_id": rollout_id, "task": task,
                       "harness": harness, "model": model, "decision_log_sha256": decision_log_sha256,
                       "locator_base": locator_base},
        },
        "summary": summary,
        "events": events,
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("log", type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--rollout", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--importer", default=IMPORTER)
    parser.add_argument("--locator-base", default=LOCATOR_BASE)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        raw_lines = args.log.read_text(encoding="utf-8").splitlines()
        if any(not raw.strip() for raw in raw_lines):
            raise ValueError("blank line in decision log")
        lines = [json.loads(raw) for raw in raw_lines]
        doc = build_session(lines, project=args.project, rollout_id=args.rollout, task=args.task,
                            harness=args.harness, model=args.model, decision_log_sha256=sha256_of(args.log),
                            importer=args.importer, locator_base=args.locator_base)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"conversion failed: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
