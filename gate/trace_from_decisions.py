#!/usr/bin/env python3
"""Convert an RSI-Exam decision log into a TRACE 0.5.0 session document.

One ``decision`` event per log line: the rollout agent proposes, the gate resolves; ``keep`` is
``accepted``, ``revert`` is ``rejected``, ``provisional`` stays ``proposed`` until its replication
event revises it. Each event carries a ``confidence`` block whose first four keys are the ones the
ProofPress evidence adapter reads (``interval``, ``method``, ``sample_size``, ``evidence_digests``),
followed by the contract id and the rest of the line, including the gated-mode fields
(``confirm_policy``, ``profile_sha256``, ``look_index``, ``parent_method_tree_sha256``,
``candidate_method_tree_sha256``, ``sizing``, ``suite``), which TRACE preserves as extras.

Every cross-field rule of the contract is re-checked on conversion, including the gated rules: a
gated screening line carries the profile and snapshot digests and receipt evidence; an
under-planned confirmation is a revert with no suite; a provisional line carries its plan and
suite; a replication line repeats its provisional line's profile digest, look index, digests, plan,
suite, and minimum effect; every line of a log is in one mode under one profile; every suite was
derived for the rollout being converted. A violation
refuses the whole conversion (exit 2). The document carries
numbers, identifiers, locators, and digests only. Standard library only.
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
IMPORTER = "rsi-exam-provenance/trace_from_decisions.py 0.2"
LOCATOR_BASE = "artifacts/app/methods"
GATE_ACTOR = {"type": "system", "id": "rsi-exam-gate/decide.py", "role": "decision-gate"}
CONFIDENCE_KEYS = ("interval", "method", "sample_size", "evidence_digests", "contract", "statistic", "unit",
                   "direction", "estimate", "min_effect", "verdict", "evidence", "holdout",
                   "confirm_policy", "profile_sha256", "look_index", "parent_method_tree_sha256",
                   "candidate_method_tree_sha256", "sizing", "suite")
GATED_KEYS = ("confirm_policy", "profile_sha256", "look_index", "parent_method_tree_sha256",
              "candidate_method_tree_sha256", "sizing", "suite")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CONFIRM_POLICIES = ("always", "inconclusive")
ROLES = ("parent", "candidate", "holdout-parent", "holdout-candidate", "receipt-parent", "receipt-candidate")
HOLDOUT_KEYS = ("estimate", "interval", "sample_size", "verdict", "evidence", "evidence_digests")
SIZING_KEYS = {"rule", "size", "planned", "floor", "cap", "exploratory", "screening_sd", "z"}
DERIVATION_KEYS = {"algorithm", "rollout_id", "candidate_method_tree_sha256", "look_index", "size", "max_moves"}
SEEDS_ALGORITHM = "rsi-exam-gate/hmac-seeds/1"


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


def _fail(line: dict[str, Any], message: str) -> ValueError:
    return ValueError(f"line {line.get('line')}: {message}")


def _check_locator(locator: Any, what: str, line: dict[str, Any]) -> None:
    """The evidence-locator rule: canonical relative POSIX path under results/."""
    bad = (not isinstance(locator, str) or not locator or locator.startswith("/") or "\\" in locator
           or "%" in locator or ":" in locator
           or any(part in ("..", "", ".") for part in locator.split("/"))
           or locator.split("/", 1)[0] != "results")
    if bad:
        raise _fail(line, f"bad {what} locator {locator!r}")


def _is_hex(value: Any) -> bool:
    return isinstance(value, str) and HEX64.match(value) is not None


def _is_pos_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _check_measurement(line: dict[str, Any]) -> None:
    interval = line["interval"]
    low, high, level = interval["lower"], interval["upper"], interval["level"]
    if not all(math.isfinite(x) for x in (low, high, level, line["estimate"], line["min_effect"])):
        raise _fail(line, "non-finite number")
    if low > high:
        raise _fail(line, "interval lower exceeds upper")
    if not 0.0 < level < 1.0:
        raise _fail(line, "level outside the open unit interval")
    if line["min_effect"] < 0.0:
        raise _fail(line, "negative min_effect")
    expected_verdict = "clears" if low > line["min_effect"] else ("below" if high < 0.0 else "inconclusive")
    if line["verdict"] != expected_verdict:
        raise _fail(line, f"verdict {line['verdict']} contradicts the interval")
    roles = [e["role"] for e in line["evidence"]]
    if len(set(roles)) != len(roles) or roles[:2] != ["parent", "candidate"] or any(r not in ROLES for r in roles):
        raise _fail(line, "evidence roles must be unique, known, and start with parent, candidate")
    for e in line["evidence"]:
        _check_locator(e["locator"], "evidence", line)
        if not _is_hex(e["sha256"]):
            raise _fail(line, "evidence sha256 must be 64 hex characters")
    if line["evidence_digests"] != {e["role"]: "sha256:" + e["sha256"] for e in line["evidence"]}:
        raise _fail(line, "evidence_digests do not match evidence")
    holdout = line.get("holdout")
    if holdout:
        hroles = [e["role"] for e in holdout["evidence"]]
        if len(set(hroles)) != len(hroles) or any(r not in ROLES for r in hroles):
            raise _fail(line, "holdout evidence roles must be unique and known")
        if set(e["sha256"] for e in holdout["evidence"]) & set(e["sha256"] for e in line["evidence"]):
            raise _fail(line, "holdout evidence aliases the primary evidence")
        if holdout["interval"]["level"] != level:
            raise _fail(line, "holdout level differs from the primary level")


def _check_gated_shapes(line: dict[str, Any]) -> None:
    """Shape rules for the seven gated keys on a line written under a profile."""
    for key in ("profile_sha256", "parent_method_tree_sha256", "candidate_method_tree_sha256"):
        if not _is_hex(line.get(key)):
            raise _fail(line, f"{key} must be 64 hex characters on a gated line")
    look = line.get("look_index")
    if look is not None and not _is_pos_int(look):
        raise _fail(line, "look_index must be a positive integer or null")
    sizing = line.get("sizing")
    if sizing is not None:
        if (not isinstance(sizing, dict) or set(sizing) != SIZING_KEYS or not isinstance(sizing["exploratory"], bool)
                or not all(_is_pos_int(sizing[k]) for k in ("size", "planned", "floor", "cap"))
                or not all(isinstance(sizing[k], (int, float)) and not isinstance(sizing[k], bool)
                           and math.isfinite(sizing[k]) and sizing[k] >= 0 for k in ("screening_sd", "z"))):
            raise _fail(line, "malformed sizing")
        if (sizing["floor"] < 2 or sizing["cap"] < sizing["floor"] or sizing["planned"] < sizing["floor"]
                or sizing["size"] != min(sizing["planned"], sizing["cap"])
                or sizing["exploratory"] != (sizing["size"] < sizing["planned"])):
            raise _fail(line, "sizing does not follow the planning rule")
    suite = line.get("suite")
    if suite is not None:
        if (not isinstance(suite, dict) or set(suite) != {"locator", "sha256", "derivation"} or not _is_hex(suite["sha256"])
                or not isinstance(suite["derivation"], dict) or set(suite["derivation"]) != DERIVATION_KEYS):
            raise _fail(line, "malformed suite")
        _check_locator(suite["locator"], "suite", line)
        d = suite["derivation"]
        if (d["algorithm"] != SEEDS_ALGORITHM or d["candidate_method_tree_sha256"] != line["candidate_method_tree_sha256"]
                or d["look_index"] != look or sizing is None or d["size"] != sizing["size"]):
            raise _fail(line, "suite derivation does not match the line")
    roles = [e["role"] for e in line["evidence"]]
    if "receipt-parent" not in roles or "receipt-candidate" not in roles:
        raise _fail(line, "a gated line must carry receipt evidence for both results")


def _check_line(line: dict[str, Any], opened: dict[str, Any] | None) -> None:
    """Every cross-field rule of the contract; ``opened`` is the provisional line a replication resolves."""
    if line.get("schema") != SOURCE_SCHEMA:
        raise ValueError(f"line {line.get('line')}: schema is not {SOURCE_SCHEMA}")
    _check_measurement(line)
    policy = line.get("confirm_policy")
    if policy is None:
        policy = "inconclusive"
    if policy not in CONFIRM_POLICIES:
        raise _fail(line, f"unknown confirm_policy {policy!r}")
    gated = policy == "always"
    if gated:
        _check_gated_shapes(line)
    else:
        for key in GATED_KEYS[1:]:
            if line.get(key) is not None:
                raise _fail(line, f"{key} must be null on a replay-mode line")
    holdout = line.get("holdout")
    holdout_verdict = holdout["verdict"] if holdout else None
    if line.get("replicates"):
        if line["replicates"] != line["version_id"]:
            raise _fail(line, "replicates must equal version_id")
        if line["disposition"] == "provisional":
            raise _fail(line, "a replication line cannot be provisional")
        if opened is None:
            raise _fail(line, "replication without an open provisional decision")
        if gated:
            for key in ("profile_sha256", "look_index", "parent_method_tree_sha256", "candidate_method_tree_sha256",
                        "sizing", "suite", "min_effect", "parent_id"):
                if line.get(key) != opened.get(key):
                    raise _fail(line, f"replication {key} differs from the provisional line it resolves")
            if holdout is not None:
                raise _fail(line, "a gated confirmation carries no holdout")
        expected = "keep" if line["verdict"] == "clears" and holdout_verdict in (None, "clears") else "revert"
    elif gated:
        if holdout is not None:
            raise _fail(line, "a gated screening carries no holdout")
        sizing, suite, look = line.get("sizing"), line.get("suite"), line.get("look_index")
        if line["verdict"] == "below":
            expected = "revert"
            if sizing is not None or suite is not None or look is not None:
                raise _fail(line, "a screening that reverts on below plans no confirmation")
        elif sizing is None:
            raise _fail(line, "a gated screening that does not revert must carry its confirmation plan")
        elif sizing["exploratory"]:
            expected = "revert"
            if suite is not None or look is not None:
                raise _fail(line, "an under-planned confirmation is a revert without a suite")
        else:
            expected = "provisional"
            if suite is None or look is None:
                raise _fail(line, "a provisional line must carry its confirmation suite and look index")
    else:
        if line["verdict"] == "below":
            expected = "revert"
        elif line["verdict"] == "clears" and holdout_verdict in (None, "clears"):
            expected = "keep"
        else:
            expected = "provisional"
    if line["disposition"] != expected:
        raise _fail(line, f"disposition {line['disposition']} contradicts the rule ({expected})")


def _confidence(line: dict[str, Any]) -> dict[str, Any]:
    holdout = line.get("holdout")
    block: dict[str, Any] = {}
    for key in CONFIDENCE_KEYS:
        if key == "contract":
            block[key] = SOURCE_SCHEMA
        elif key == "holdout":
            block[key] = {k: holdout[k] for k in HOLDOUT_KEYS} if holdout else None
        else:
            block[key] = line.get(key)
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


def _revert_note(line: dict[str, Any]) -> str:
    sizing = line.get("sizing")
    if isinstance(sizing, dict) and sizing.get("exploratory"):
        return "Confirmation would need more games than the profile allows; reverted without confirming."
    return "Interval entirely below zero."


def build_session(lines: list[dict[str, Any]], *, project: str, rollout_id: str, task: str, harness: str,
                  model: str, decision_log_sha256: str, importer: str = IMPORTER,
                  locator_base: str = LOCATOR_BASE) -> dict[str, Any]:
    """Map decision-log lines (in file order) onto one completed TRACE session document."""
    if not lines:
        raise ValueError("decision log is empty")
    session_id = _sanitize_id(f"rsiexam_{rollout_id}")
    agent = {"type": "ai", "id": f"{harness}:{model}", "role": "rollout-agent"}
    events: list[dict[str, Any]] = []
    open_provisional: dict[str, tuple[str, str, dict[str, Any]]] = {}
    counts = {"keep": 0, "revert": 0, "provisional": 0, "replicated": 0}

    log_mode: str | None = None
    log_profile: str | None = None
    for number, line in enumerate(lines, start=1):
        if line.get("line") != number:
            raise ValueError(f"line {number}: line field {line.get('line')!r} does not match position")
        mode = "gated" if line.get("confirm_policy") == "always" else "replay"
        if log_mode is None:
            log_mode, log_profile = mode, line.get("profile_sha256")
        elif mode != log_mode or line.get("profile_sha256") != log_profile:
            raise ValueError(f"line {number}: a log is written in one mode under one profile; this line differs from line 1")
        opened_entry = open_provisional.get(line["replicates"]) if line.get("replicates") else None
        _check_line(line, opened_entry[2] if opened_entry else None)
        suite = line.get("suite")
        if isinstance(suite, dict) and suite["derivation"]["rollout_id"] != rollout_id:
            raise ValueError(f"line {number}: suite was derived for rollout {suite['derivation']['rollout_id']!r}, "
                             f"not {rollout_id!r}")
        event_id = f"evt_{len(events) + 1:03d}"
        version, parent = line["version_id"], line["parent_id"]
        if line.get("replicates"):
            if opened_entry is None:
                raise ValueError(f"line {number} replicates {line['replicates']} but no provisional decision is open")
            original_id, original_parent, _ = opened_entry
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
                                 "rejected", _revert_note(line), None))
        else:
            events.append(_event(event_id, session_id, line, agent,
                                 f"Keep {version} provisionally (parent {parent})", "proposed", None, None))
            open_provisional[version] = (event_id, parent, line)
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
