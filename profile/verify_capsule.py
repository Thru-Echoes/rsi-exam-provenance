#!/usr/bin/env python3
"""Offline integrity and coverage checks for RSI-Exam rollout provenance records.

Schema version: proofpress/rsi-exam-trajectory/v3.

What this verifier establishes: the record's shape conforms to the v3 schema
(structural rules are enforced here, without third-party dependencies), the
supplied files match their declared digests, the version lineage is a single
rooted DAG (one root, every parent present with a smaller ordinal, which by
induction makes every version reach the root) with exactly one submitted version bound to the final submission
and the hidden reward file, and every snapshot directory under the versions
root corresponds one-to-one with a recorded version. Coverage is anchored on
the harness-preserved snapshot directories, not on producer-supplied event
lists; "complete" means complete relative to the snapshot directories
supplied to this invocation. An experiment whose snapshot, log entry, and
trajectory evidence were all removed before verification is undetectable
from the remaining evidence.

What it does not establish: that RSI-Exam issued the scores (reward files are
unsigned; bindings are self-consistent, not issuer-authenticated), that the
producer captured events outside the methods tree, or that the method is any
good. Inputs are tamper-evident relative to the supplied files only.

Zero third-party dependencies; Python 3.11+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "proofpress/rsi-exam-trajectory/v3"
DIGEST = re.compile(r"^[0-9a-f]{64}$")
VERSION_ID = re.compile(r"^v[0-9]+$")
MAX_STRING = 2000

Errors = list[str]
Checker = Callable[[Any, str, Errors], None]


EXCLUDED_DIR = "__pycache__"
EXCLUDED_SUFFIXES = (".pyc", ".pyo")
EXPECTED_EXCLUSIONS = ["__pycache__/", "*.pyc", "*.pyo"]


def _add(errors: Errors, code: str) -> None:
    if code not in errors:
        errors.append(code)


# ---------------------------------------------------------------------------
# Canonical digests
# ---------------------------------------------------------------------------

def file_digest(path: Path) -> str:
    """SHA-256 of one file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(path: Path) -> str:
    """Canonical digest of a directory tree.

    One line per regular file: '<sha256hex>  <posix relpath>\\n', relpaths
    byte-sorted, lines concatenated, SHA-256 of the result. Symlinks raise
    ValueError; empty directories contribute nothing. Equivalent shell:
    (cd DIR && find . -type f | LC_ALL=C sort | xargs -r sha256sum | sed
    's|\\./||' | sha256sum).
    """
    if path.is_symlink():
        raise ValueError("symlink")
    lines: list[str] = []
    entries = []
    for child in path.rglob("*"):
        if child.is_symlink():
            raise ValueError("symlink")
        if child.is_file():
            entries.append(child.relative_to(path).as_posix())
    for rel in sorted(entries):
        lines.append(f"{file_digest(path / rel)}  {rel}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Structural validation (mirrors schema.json; keep the two in step)
# ---------------------------------------------------------------------------

def method_files(path: Path) -> list[str]:
    """Sorted POSIX relpaths of the ``.py`` files a method-tree digest covers.

    Mirrors the producer: files the grader would not stage are skipped, and the cases where the
    staged set cannot be known are refused (a symlink, anything that is not a regular file, and a
    ``.py`` file under ``__pycache__``). Raises ValueError; no side effects.
    """
    if path.is_symlink():
        raise ValueError(f"symlink:{path.name}")
    rels: list[str] = []
    for child in path.rglob("*"):
        rel = child.relative_to(path)
        if child.is_symlink():
            raise ValueError(f"symlink:{rel.as_posix()}")
        if child.is_dir():
            continue
        cached = EXCLUDED_DIR in rel.parts
        if cached and child.suffix == ".py":
            raise ValueError(f"source_in_cache_dir:{rel.as_posix()}")
        if cached or child.suffix in EXCLUDED_SUFFIXES:
            continue
        if not child.is_file():
            raise ValueError(f"not_a_regular_file:{rel.as_posix()}")
        if child.suffix != ".py":
            continue
        rels.append(rel.as_posix())
    return sorted(rels)


def method_tree_digest(path: Path) -> str:
    """Cache-free digest of a method tree, in the same line format as tree_digest."""
    try:
        lines = [f"{file_digest(path / rel)}  {rel}\n" for rel in method_files(path)]
    except OSError as exc:
        raise ValueError(f"unreadable:{exc.__class__.__name__}")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _string(min_len: int = 1, max_len: int = MAX_STRING,
            pattern: re.Pattern[str] | None = None) -> Checker:
    def check(value: Any, path: str, errors: Errors) -> None:
        if not isinstance(value, str):
            _add(errors, f"schema:{path}:invalid")
            return
        if len(value) < min_len:
            _add(errors, f"schema:{path}:invalid")
        elif len(value) > max_len:
            _add(errors, f"schema:{path}:string_too_long")
        elif pattern is not None and not pattern.fullmatch(value):
            _add(errors, f"schema:{path}:invalid")
    return check


def _reject_constant(token: str) -> Any:
    """Refuse the JSON extensions for non-finite numbers; the contract requires every number finite."""
    raise ValueError(f"non-finite number: {token}")


def _nullable(checker: Checker) -> Checker:
    """Accept null, or whatever `checker` accepts. The gate writes null in every field a replay-mode
    line leaves unset, so the record carries those nulls rather than dropping the key."""
    def check(value: Any, path: str, errors: Errors) -> None:
        if value is not None:
            checker(value, path, errors)
    return check


_PREFIXED_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _digest_map(value: Any, path: str, errors: Errors) -> None:
    """A non-empty map of evidence role to prefixed digest, as the decision-log contract states."""
    if not isinstance(value, dict) or not value:
        _add(errors, f"schema:{path}:invalid")
        return
    for role, digest in value.items():
        if not isinstance(role, str) or not role:
            _add(errors, f"schema:{path}:invalid")
        elif not isinstance(digest, str) or not _PREFIXED_DIGEST.fullmatch(digest):
            _add(errors, f"schema:{path}.{role}:invalid")


def _any_object(value: Any, path: str, errors: Errors) -> None:
    """A block the record carries verbatim and does not interpret; the decision log binds its bytes."""
    if not isinstance(value, dict):
        _add(errors, f"schema:{path}:invalid")


def _const(expected: str) -> Checker:
    def check(value: Any, path: str, errors: Errors) -> None:
        if value != expected:
            _add(errors, f"schema:{path}:invalid")
    return check


def _number(minimum: float | None = None, maximum: float | None = None,
            exclusive_minimum: float | None = None,
            exclusive_maximum: float | None = None) -> Checker:
    def check(value: Any, path: str, errors: Errors) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _add(errors, f"schema:{path}:invalid")
            return
        if value != value or value in (float("inf"), float("-inf")):
            _add(errors, f"schema:{path}:invalid")
            return
        if minimum is not None and value < minimum:
            _add(errors, f"schema:{path}:invalid")
        if maximum is not None and value > maximum:
            _add(errors, f"schema:{path}:invalid")
        if exclusive_minimum is not None and value <= exclusive_minimum:
            _add(errors, f"schema:{path}:invalid")
        if exclusive_maximum is not None and value >= exclusive_maximum:
            _add(errors, f"schema:{path}:invalid")
    return check


def _integer(minimum: int | None = None) -> Checker:
    def check(value: Any, path: str, errors: Errors) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            _add(errors, f"schema:{path}:invalid")
            return
        if minimum is not None and value < minimum:
            _add(errors, f"schema:{path}:invalid")
    return check


def _enum(*allowed: str) -> Checker:
    def check(value: Any, path: str, errors: Errors) -> None:
        if value not in allowed:
            _add(errors, f"schema:{path}:invalid")
    return check


def _array(item: Checker, unique: bool = False, min_items: int = 0) -> Checker:
    def check(value: Any, path: str, errors: Errors) -> None:
        if not isinstance(value, list):
            _add(errors, f"schema:{path}:invalid")
            return
        if len(value) < min_items:
            _add(errors, f"schema:{path}:invalid")
        if unique:
            seen: list[Any] = []
            for entry in value:
                if entry in seen:
                    _add(errors, f"schema:{path}:duplicate_item")
                seen.append(entry)
        for index, entry in enumerate(value):
            item(entry, f"{path}[{index}]", errors)
    return check


def _obj(spec: dict[str, tuple[bool, Checker]]) -> Checker:
    def check(value: Any, path: str, errors: Errors) -> None:
        if not isinstance(value, dict):
            _add(errors, f"schema:{path}:invalid")
            return
        for key in value:
            if key not in spec:
                _add(errors, f"schema:{path}.{key}:unknown_key")
        for key, (required, checker) in spec.items():
            if key not in value:
                if required:
                    _add(errors, f"schema:{path}.{key}:missing")
                continue
            checker(value[key], f"{path}.{key}", errors)
    return check


_digest_checker = _string(64, 64, DIGEST)
_locator = _string(1, 500)
_version_ref = _string(1, 200, VERSION_ID)

_BOUND_FILE = _obj({
    "locator": (True, _locator),
    "sha256": (True, _digest_checker),
})

_DECISION = _obj({
    "log_line": (True, _integer(minimum=1)),
    "kind": (True, _enum("screening", "confirmation")),
    "resolves_log_line": (False, _integer(minimum=1)),
    "version_id": (True, _version_ref),
    "parent_id": (True, _nullable(_version_ref)),
    "replicates": (True, _nullable(_version_ref)),
    "timestamp": (True, _string(1, 100)),
    "direction": (True, _enum("higher", "lower")),
    "estimate": (True, _number()),
    "interval": (True, _obj({
        "lower": (True, _number()),
        "upper": (True, _number()),
        "level": (True, _number(exclusive_minimum=0, exclusive_maximum=1)),
    })),
    "method": (True, _obj({
        "name": (True, _string(1, 200)),
        "algorithm": (True, _nullable(_string(1, 200))),
        "resamples": (True, _nullable(_integer(minimum=1))),
        "seed": (True, _nullable(_integer())),
    })),
    "sample_size": (True, _integer(minimum=1)),
    "min_effect": (True, _number(minimum=0)),
    "verdict": (True, _enum("clears", "below", "inconclusive")),
    "disposition": (True, _enum("keep", "revert", "provisional")),
    "evidence": (True, _array(_obj({
        "role": (True, _enum("parent", "candidate", "holdout-parent", "holdout-candidate",
                             "receipt-parent", "receipt-candidate")),
        "locator": (True, _locator),
        "sha256": (True, _digest_checker),
    }), min_items=1)),
    "evidence_digests": (True, _digest_map),
    "holdout": (True, _nullable(_any_object)),
    "confirm_policy": (True, _enum("always", "inconclusive")),
    "profile_sha256": (True, _nullable(_digest_checker)),
    "look_index": (True, _nullable(_integer(minimum=1))),
    "parent_method_tree_sha256": (True, _nullable(_digest_checker)),
    "candidate_method_tree_sha256": (True, _nullable(_digest_checker)),
    "sizing": (True, _nullable(_any_object)),
    "suite": (True, _nullable(_any_object)),
})

CAPSULE_SPEC: Checker = _obj({
    "schema_version": (True, _const(SCHEMA_VERSION)),
    "capsule_id": (True, _string(1, 200)),
    "benchmark": (True, _obj({
        "name": (True, _const("RSI-Exam")),
        "release": (True, _string(1, 200)),
        "task_id": (True, _string(1, 200)),
        "statistic": (False, _string(1, 200)),
        "unit": (False, _string(1, 200)),
    })),
    "rollout": (True, _obj({
        "id": (True, _string(1, 200)),
        "model": (True, _string(1, 200)),
        "harness": (True, _string(1, 200)),
        "config_digest": (True, _digest_checker),
        "budget_hours": (True, _number(exclusive_minimum=0)),
        "trace_session_ids": (False, _array(_string(1, 200), unique=True)),
    })),
    "freeze": (True, _obj({
        "task_digest": (True, _digest_checker),
        "grader_digest": (True, _digest_checker),
    })),
    "source": (True, _obj({
        "experiment_log": (True, _BOUND_FILE),
        "versions_root": (True, _obj({"locator": (True, _locator)})),
        "exclusions": (True, _array(_string(1, 200), unique=True, min_items=1)),
        "decision_log": (False, _BOUND_FILE),
        "trajectory": (False, _obj({
            "locator": (True, _locator),
            "sha256": (True, _digest_checker),
            "format": (True, _const("ATIF")),
        })),
        "trace_exports": (False, _array(_obj({
            "session_id": (True, _string(1, 200)),
            "locator": (True, _locator),
            "sha256": (True, _digest_checker),
        }))),
    })),
    "resources": (False, _obj({
        "wall_time_seconds": (False, _number(minimum=0)),
        "input_tokens": (False, _integer(minimum=0)),
        "output_tokens": (False, _integer(minimum=0)),
        "model_calls": (False, _integer(minimum=0)),
        "estimated_cost_usd": (False, _number(minimum=0)),
    })),
    "versions": (True, _array(_obj({
        "version_id": (True, _version_ref),
        "ordinal": (True, _integer(minimum=0)),
        "parent_ids": (True, _array(_version_ref, unique=True)),
        "status": (True, _enum("baseline", "kept", "reverted", "provisional", "submitted")),
        "decisions": (False, _array(_DECISION, min_items=1)),
        "stage": (False, _string(1, 200)),
        "artifact": (True, _obj({
            "type": (True, _enum("directory", "file")),
            "locator": (True, _locator),
            "tree_sha256": (True, _digest_checker),
            "method_tree_sha256": (True, _digest_checker),
        })),
        "log": (True, _obj({"line": (True, _integer(minimum=1))})),
        "visible": (False, _obj({
            "score": (True, _number()),
            "recorded_in": (True, _enum("experiment_log", "result_file")),
            "result_locator": (False, _locator),
            "result_sha256": (False, _digest_checker),
        })),
        "trace_event_ids": (False, _array(_string(1, 200), unique=True,
                                          min_items=1)),
    }), min_items=1)),
    "final_submission": (True, _obj({
        "version_id": (True, _version_ref),
        "locator": (True, _locator),
        "tree_sha256": (True, _digest_checker),
        "method_tree_sha256": (True, _digest_checker),
        "version_ids": (True, _array(_version_ref, unique=True, min_items=1)),
    })),
    "hidden_evaluation": (True, _obj({
        "reward_locator": (True, _locator),
        "reward_sha256": (True, _digest_checker),
        "reward": (True, _number(minimum=0, maximum=1)),
        "error": (False, _string(1, 2000)),
        "score_details_locator": (False, _locator),
        "score_details_sha256": (False, _digest_checker),
        "binding": (True, _obj({
            "basis": (True, _const("job_directory")),
            "job_id": (True, _string(1, 200)),
        })),
    })),
})


# ---------------------------------------------------------------------------
# Semantic validation
# ---------------------------------------------------------------------------

DISPOSITION_STATUS = {"keep": "kept", "revert": "reverted", "provisional": "provisional"}
# The fields the record projects from each decision-log line. Mirrors the producer's DECISION_KEYS;
# the record is only as good as the projection, so every one is compared against the bound log.
DECISION_SCHEMA = "rsi-exam-decision-log/v1"
DECISION_KEYS = ("version_id", "parent_id", "replicates", "timestamp", "direction", "estimate",
                 "interval", "method", "sample_size", "min_effect", "verdict", "disposition",
                 "evidence", "evidence_digests", "holdout", "confirm_policy", "profile_sha256",
                 "look_index", "parent_method_tree_sha256", "candidate_method_tree_sha256",
                 "sizing", "suite")


def _check_decisions_match_log(root: Path, data: dict[str, Any], errors: Errors) -> None:
    """Compare every projected decision against the line it claims to project.

    Binding the log by digest proves the file has not changed; it proves nothing about whether the
    record's own `decisions[]` say what that file says. Without this the record could carry any
    verdict, interval or evidence digest it liked and still verify. Appends to `errors`; reads only.
    """
    bound = data["source"].get("decision_log")
    if bound is None:
        return
    path = _inside(root, bound["locator"])
    if path is None or not path.is_file() or path.is_symlink():
        return          # already reported by the bound-file check
    try:
        raw = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        # A named error, not a traceback: a bound file whose bytes are not text is a finding.
        _add(errors, f"file:decision_log:unreadable:{exc.__class__.__name__}")
        return
    if not raw:
        _add(errors, "decision:log_empty")
        return

    logged: dict[int, dict[str, Any]] = {}
    for position, text in enumerate(raw, start=1):
        try:
            line = json.loads(text, parse_constant=_reject_constant)
        except (json.JSONDecodeError, ValueError):
            _add(errors, f"decision:log_unparsable:{position}")
            return
        if not isinstance(line, dict):
            _add(errors, f"decision:log_unparsable:{position}")
            return
        if line.get("schema") != DECISION_SCHEMA:
            _add(errors, f"decision:log_foreign_schema:{position}")
        if isinstance(line.get("line"), bool) or line.get("line") != position:
            # The record addresses lines by number, so a log that numbers itself differently makes
            # every projection ambiguous.
            _add(errors, f"decision:log_line_number:{position}")
        logged[position] = line

    for key in ("statistic", "unit"):
        stated = [line.get(key) for line in logged.values()]
        if any(not isinstance(value, str) or not value for value in stated):
            # Collected only after they are known to be strings: an unhashable value here would
            # otherwise raise TypeError out of the set below instead of being reported.
            _add(errors, f"decision:log_bad_{key}")
            continue
        values = set(stated)
        if len(values) != 1:
            _add(errors, f"decision:log_mixed_{key}")
        elif data["benchmark"].get(key) != next(iter(values)):
            # Hoisting these to the benchmark block is only safe if the hoist is checked.
            _add(errors, f"decision:log_{key}_mismatch")

    projected: dict[int, list[tuple[str, dict[str, Any]]]] = {}
    for version in data["versions"]:
        for entry in version.get("decisions", []):
            projected.setdefault(entry["log_line"], []).append((version["version_id"], entry))

    for position in sorted(set(logged) | set(projected)):
        claimants = projected.get(position, [])
        if not claimants:
            _add(errors, f"decision:log_line_missing:{position}")
            continue
        for vid, entry in claimants:      # every claimant, so a duplicate is still compared
            if position not in logged:
                _add(errors, f"decision:log_line_absent:{vid}:{position}")
                continue
            line = logged[position]
            _compare_decision(vid, position, entry, line, errors)


def _compare_decision(vid: str, position: int, entry: dict[str, Any], line: dict[str, Any],
                      errors: Errors) -> None:
    """Compare one projected decision against the log line it claims to project."""
    for key in DECISION_KEYS:
        # Membership first: a key the log never had and a key the record carries as null both
        # read as None, and the record must not claim a field the log does not state.
        if key not in line:
            _add(errors, f"decision:log_line_absent_field:{vid}:{position}:{key}")
        elif entry.get(key) != line[key]:
            _add(errors, f"decision:log_line_mismatch:{vid}:{position}:{key}")





def _check_decision_consistency(data: dict[str, Any], errors: Errors) -> None:
    """Cross-check the projected decisions against the record that carries them.

    These are the checks that need only the record: a decision must belong to the version it is
    nested under, its kind must agree with whether it replicates, a confirmation must resolve an
    earlier open provisional of the same version, line numbers must not collide, and the version's
    status must be the one its own decisions imply. Whether the decisions match the log, the result
    files, or the rule the gate claims to have applied is a separate question that needs the job
    directory. Appends to `errors`; no other effects.
    """
    decided = [v for v in data["versions"] if v.get("decisions")]
    if not decided:
        return
    if "decision_log" not in data["source"]:
        _add(errors, "semantic:source:decision_log_missing")
    benchmark = data["benchmark"]
    if "statistic" not in benchmark or "unit" not in benchmark:
        _add(errors, "semantic:benchmark:measurement_missing")

    seen_lines: set[int] = set()
    for version in decided:
        vid = version["version_id"]
        previous = 0
        provisional_lines: set[int] = set()
        for entry in version["decisions"]:
            line = entry["log_line"]
            if line in seen_lines:
                _add(errors, f"semantic:decision:duplicate_log_line:{line}")
            seen_lines.add(line)
            if line <= previous:
                _add(errors, f"semantic:decision:log_line_order:{vid}:{line}")
            previous = line
            if entry["version_id"] != vid:
                _add(errors, f"semantic:decision:version_mismatch:{vid}:{line}")
            replicates = entry["replicates"]
            expected_kind = "confirmation" if replicates is not None else "screening"
            if entry["kind"] != expected_kind:
                _add(errors, f"semantic:decision:kind_mismatch:{vid}:{line}")
            if entry["kind"] == "confirmation":
                if replicates != vid:
                    _add(errors, f"semantic:decision:replicates_mismatch:{vid}:{line}")
                resolved = entry.get("resolves_log_line")
                if resolved is None:
                    _add(errors, f"semantic:decision:resolves_missing:{vid}:{line}")
                elif resolved not in provisional_lines:
                    _add(errors, f"semantic:decision:resolves_unknown:{vid}:{line}")
                else:
                    provisional_lines.discard(resolved)
                if entry["disposition"] == "provisional":
                    _add(errors, f"semantic:decision:confirmation_provisional:{vid}:{line}")
            else:
                if entry.get("resolves_log_line") is not None:
                    _add(errors, f"semantic:decision:resolves_unexpected:{vid}:{line}")
                if entry["disposition"] == "provisional":
                    provisional_lines.add(line)

        implied = DISPOSITION_STATUS.get(version["decisions"][-1]["disposition"])
        # `submitted` marks the tree that was handed in and outranks the decision state; whether a
        # version with an open provisional may be submitted at all is a protocol question.
        if version["status"] not in ("submitted", implied):
            _add(errors, f"semantic:version:status_not_decided:{vid}")
        if version["status"] == "submitted" and implied == "provisional":
            # The contract is explicit: an unresolved provisional cannot be the submission without
            # a protocol failure. Letting `submitted` mask it would hide exactly that failure.
            _add(errors, f"protocol:unresolved_provisional_submitted:{vid}")


def expected_main_locator(versions_root: str) -> str:
    """The submitted tree's locator: the sibling of the versions root named ``main``.

    Derived rather than trusted, so a record cannot point the verifier at a directory other than
    the one the grader read. Pure function.
    """
    parent, separator, _ = versions_root.rstrip("/").rpartition("/")
    return f"{parent}/main" if separator else "main"


def _check_semantics(data: dict[str, Any], errors: Errors) -> None:
    versions: list[dict[str, Any]] = data["versions"]
    by_id: dict[str, dict[str, Any]] = {}
    ordinals: set[int] = set()
    trace_events: set[str] = set()
    for version in versions:
        vid = version["version_id"]
        if vid in by_id:
            _add(errors, f"semantic:versions:{vid}:duplicate_id")
        by_id[vid] = version
        ordinal = version["ordinal"]
        if ordinal in ordinals:
            _add(errors, f"semantic:versions:{vid}:duplicate_ordinal")
        ordinals.add(ordinal)
        for event_id in version.get("trace_event_ids", []):
            if event_id in trace_events:
                _add(errors, f"semantic:versions:{vid}:duplicate_trace_event")
            trace_events.add(event_id)

    roots = [v["version_id"] for v in versions if not v["parent_ids"]]
    if len(roots) != 1:
        _add(errors, "semantic:versions:root_count")

    for version in versions:
        vid = version["version_id"]
        for parent in version["parent_ids"]:
            if parent not in by_id:
                _add(errors, f"semantic:version:{vid}:missing_parent")
            elif by_id[parent]["ordinal"] >= version["ordinal"]:
                _add(errors, f"semantic:version:{vid}:parent_order")

    submitted = [v for v in versions if v["status"] == "submitted"]
    if len(submitted) != 1:
        _add(errors, "semantic:versions:submitted_count")
    else:
        final = data["final_submission"]
        chosen = submitted[0]
        if final["version_id"] != chosen["version_id"]:
            _add(errors, "semantic:final:submitted_mismatch")
        if final["method_tree_sha256"] != chosen["artifact"]["method_tree_sha256"]:
            _add(errors, "semantic:final:method_tree_mismatch")
        # The full trees may legitimately differ: main/ picks up bytecode caches the snapshot was
        # taken without, which is why identity is decided on the method tree. Both full-tree
        # digests are still recomputed from disk, so neither is unchecked.
        klass = sorted((v for v in versions
                        if v["artifact"]["method_tree_sha256"] == final["method_tree_sha256"]),
                       key=lambda v: v["ordinal"])
        if [v["version_id"] for v in klass] != list(final["version_ids"]):
            _add(errors, "semantic:final:class_mismatch")
        elif klass and final["version_id"] != klass[0]["version_id"]:
            _add(errors, "semantic:final:not_canonical")

    if data["final_submission"]["locator"] != expected_main_locator(
            data["source"]["versions_root"]["locator"]):
        # Without this the record chooses which directory the verifier recomputes, and a record
        # pointing at a snapshot would never have main/ read at all.
        _add(errors, "semantic:final:locator_convention")

    _check_decision_consistency(data, errors)

    if sorted(data["source"]["exclusions"]) != sorted(EXPECTED_EXCLUSIONS):
        _add(errors, "semantic:source:exclusions_mismatch")

    versions_root = data["source"]["versions_root"]["locator"].rstrip("/")
    for version in versions:
        expected = f"{versions_root}/{version['version_id']}"
        if version["artifact"]["locator"] != expected:
            _add(errors, f"semantic:version:{version['version_id']}:locator_convention")


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

def _inside(root: Path, locator: str) -> Path | None:
    candidate = Path(locator)
    if candidate.is_absolute():
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _check_bound_file(root: Path, locator: str, expected: str,
                      label: str, errors: Errors) -> Path | None:
    path = _inside(root, locator)
    if path is None:
        _add(errors, f"file:{label}:locator_outside_root")
        return None
    if not path.is_file() or path.is_symlink():
        _add(errors, f"file:{label}:missing_file")
        return None
    if file_digest(path) != expected:
        _add(errors, f"file:{label}:digest_mismatch")
        return None
    return path


def _check_artifact(root: Path, version: dict[str, Any], errors: Errors) -> None:
    vid = version["version_id"]
    artifact = version["artifact"]
    path = _inside(root, artifact["locator"])
    if path is None:
        _add(errors, f"file:artifact:{vid}:locator_outside_root")
        return
    if artifact["type"] == "directory":
        if not path.is_dir():
            _add(errors, f"file:artifact:{vid}:missing_file")
            return
        try:
            actual = tree_digest(path)
        except ValueError:
            _add(errors, f"file:artifact:{vid}:symlink")
            actual = None
        except OSError as exc:
            _add(errors, f"file:artifact:{vid}:unreadable:{exc.__class__.__name__}")
            actual = None
    else:
        if not path.is_file() or path.is_symlink():
            _add(errors, f"file:artifact:{vid}:missing_file")
            return
        actual = file_digest(path)
    if actual is not None and actual != artifact["tree_sha256"]:
        _add(errors, f"file:artifact:{vid}:digest_mismatch")
    # Independent of the full-tree outcome, so a symlink reported above does not hide which path
    # the method-tree view objects to.
    if artifact["type"] == "directory":
        try:
            method_actual = method_tree_digest(path)
        except ValueError as exc:
            _add(errors, f"file:artifact:{vid}:method_tree_unreadable:{exc}")
            return
        if method_actual != artifact["method_tree_sha256"]:
            _add(errors, f"file:artifact:{vid}:method_tree_mismatch")


def _check_final_submission(root: Path, data: dict[str, Any], errors: Errors) -> None:
    """Recompute the submitted tree's digests from disk.

    Without this the record's final digests are only checked against a snapshot the record itself
    names, so a `main/` holding something else would pass. Appends to `errors`; no other effects.
    """
    final = data["final_submission"]
    path = _inside(root, final["locator"])
    if path is None:
        _add(errors, "file:final_submission:locator_outside_root")
        return
    if not path.is_dir():
        _add(errors, "file:final_submission:missing_file")
        return
    try:
        if tree_digest(path) != final["tree_sha256"]:
            _add(errors, "file:final_submission:digest_mismatch")
    except ValueError:
        _add(errors, "file:final_submission:symlink")
    except OSError as exc:
        _add(errors, f"file:final_submission:unreadable:{exc.__class__.__name__}")
    # Not chained to the full-tree result: a symlink reported there must not hide which path the
    # method-tree view objects to.
    try:
        if method_tree_digest(path) != final["method_tree_sha256"]:
            _add(errors, "file:final_submission:method_tree_mismatch")
    except ValueError as exc:
        _add(errors, f"file:final_submission:method_tree_unreadable:{exc}")
    # The producer refuses to build a record for a tree the grader would score 0.0. Re-check it
    # here, or that rule would hold only for records this producer wrote.
    stray = sorted(
        rel.as_posix() for rel in (c.relative_to(path) for c in path.rglob("*"))
        if not (path / rel).is_dir()
        and EXCLUDED_DIR not in rel.parts
        and (path / rel).suffix not in EXCLUDED_SUFFIXES
        and (path / rel).suffix != ".py")
    if stray:
        _add(errors, f"protocol:submission_not_stageable:{stray[0]}")


def _check_log_lines(log_path: Path, versions: list[dict[str, Any]],
                     errors: Errors) -> None:
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for version in versions:
        log_ref = version.get("log")
        if not log_ref:
            continue
        vid = version["version_id"]
        line_no = log_ref["line"]
        if line_no > len(lines):
            _add(errors, f"file:log:{vid}:line_out_of_range")
            continue
        if not re.search(rf"\b{re.escape(vid)}\b", lines[line_no - 1]):
            _add(errors, f"file:log:{vid}:line_mismatch")


def _check_reward(root: Path, hidden: dict[str, Any], errors: Errors) -> None:
    path = _check_bound_file(root, hidden["reward_locator"],
                             hidden["reward_sha256"], "reward", errors)
    if path is None:
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _add(errors, "file:reward:unreadable")
        return
    if not isinstance(payload, dict):
        _add(errors, "file:reward:not_object")
        return
    for key, value in payload.items():
        if key == "error":
            if not isinstance(value, str):
                _add(errors, "file:reward:unexpected_field")
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            _add(errors, "file:reward:unexpected_field")
    reward = payload.get("reward")
    if isinstance(reward, bool) or not isinstance(reward, (int, float)) \
            or reward != reward or not 0.0 <= float(reward) <= 1.0:
        _add(errors, "file:reward:invalid")
        return
    if reward != hidden["reward"]:
        _add(errors, "file:reward:reward_mismatch")
    if payload.get("error") != hidden.get("error"):
        _add(errors, "file:reward:error_mismatch")


def _check_files(root: Path, data: dict[str, Any], errors: Errors) -> None:
    source = data["source"]
    log_path = _check_bound_file(root, source["experiment_log"]["locator"],
                                 source["experiment_log"]["sha256"],
                                 "experiment_log", errors)
    if log_path is not None:
        _check_log_lines(log_path, data["versions"], errors)

    trajectory = source.get("trajectory")
    if trajectory is not None:
        _check_bound_file(root, trajectory["locator"], trajectory["sha256"],
                          "trajectory", errors)
    for index, export in enumerate(source.get("trace_exports", [])):
        _check_bound_file(root, export["locator"], export["sha256"],
                          f"trace_export:{index}", errors)

    decision_log = source.get("decision_log")
    if decision_log is not None:
        _check_bound_file(root, decision_log["locator"], decision_log["sha256"],
                          "decision_log", errors)

    _check_decisions_match_log(root, data, errors)
    _check_final_submission(root, data, errors)
    _check_unrecorded_matches(root, data, errors)

    for version in data["versions"]:
        _check_artifact(root, version, errors)
        visible = version.get("visible")
        if visible and visible.get("result_locator"):
            expected = visible.get("result_sha256")
            if expected is None:
                _add(errors, f"file:visible:{version['version_id']}:missing_digest")
            else:
                _check_bound_file(root, visible["result_locator"], expected,
                                  f"visible:{version['version_id']}", errors)

    hidden = data["hidden_evaluation"]
    _check_reward(root, hidden, errors)
    if hidden.get("score_details_locator"):
        expected = hidden.get("score_details_sha256")
        if expected is None:
            _add(errors, "file:score_details:missing_digest")
        else:
            _check_bound_file(root, hidden["score_details_locator"], expected,
                              "score_details", errors)


# ---------------------------------------------------------------------------
# Coverage (anchored on the harness-preserved snapshot directories)
# ---------------------------------------------------------------------------

def _check_unrecorded_matches(root: Path, data: dict[str, Any], errors: Errors) -> None:
    """Flag a snapshot on disk that shares the submitted method tree and is not in the record.

    The record's equivalence class is only as honest as the set of snapshots it lists, so the class
    is re-derived from the job directory. Appends to `errors`; no other effects.
    """
    path = _inside(root, data["source"]["versions_root"]["locator"])
    if path is None or not path.is_dir():
        return
    recorded = {v["version_id"] for v in data["versions"]}
    final_digest = data["final_submission"]["method_tree_sha256"]
    for child in sorted(path.iterdir()):
        if not child.is_dir() or child.name in recorded or not VERSION_ID.fullmatch(child.name):
            continue
        try:
            if method_tree_digest(child) == final_digest:
                _add(errors, f"identity:unrecorded_match:{child.name}")
        except ValueError as exc:
            # Skipping it silently would let an unreadable directory hide a member of the class.
            _add(errors, f"identity:unscannable_snapshot:{child.name}:{exc}")


def _coverage(root: Path, data: dict[str, Any], errors: Errors) -> str:
    locator = data["source"]["versions_root"]["locator"]
    path = _inside(root, locator)
    if path is None:
        _add(errors, "file:versions_root:locator_outside_root")
        return "unverifiable"
    if not path.is_dir():
        return "unverifiable"
    snapshot_ids = {child.name for child in path.iterdir()
                    if child.is_dir() and VERSION_ID.fullmatch(child.name)}
    capsule_ids = {v["version_id"] for v in data["versions"]}
    if snapshot_ids == capsule_ids:
        return "complete"
    return "partial"


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def verify_capsule(capsule_path: str | Path,
                   artifact_root: str | Path | None = None,
                   require_complete: bool = False) -> dict[str, Any]:
    capsule = Path(capsule_path).resolve()
    root = Path(artifact_root).resolve() if artifact_root else capsule.parent
    errors: Errors = []
    checks: dict[str, bool] = {}

    try:
        with capsule.open(encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError):
        data = None
    if not isinstance(data, dict):
        return {
            "ok": False,
            "integrity": "fail",
            "coverage": "unverifiable",
            "coverage_basis": "versions_directory",
            "capsule_id": None,
            "errors": ["capsule_unreadable"],
            "checks": {"json": False, "schema": False, "semantics": False,
                       "files": False},
        }

    checks["json"] = True
    CAPSULE_SPEC(data, "$", errors)
    checks["schema"] = not errors
    if errors:
        return {
            "ok": False,
            "integrity": "fail",
            "coverage": "unverifiable",
            "coverage_basis": "versions_directory",
            "capsule_id": data.get("capsule_id"),
            "errors": errors,
            "checks": {**checks, "semantics": False, "files": False},
        }

    before = len(errors)
    _check_semantics(data, errors)
    checks["semantics"] = len(errors) == before

    before = len(errors)
    _check_files(root, data, errors)
    checks["files"] = len(errors) == before

    coverage = _coverage(root, data, errors)
    integrity = "pass" if not errors else "fail"
    ok = integrity == "pass" and (coverage == "complete" if require_complete else True)
    return {
        "ok": ok,
        "integrity": integrity,
        "coverage": coverage,
        "coverage_basis": "versions_directory",
        "capsule_id": data.get("capsule_id"),
        "errors": errors,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capsule")
    parser.add_argument("--artifact-root", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-complete", action="store_true",
                        help="fail unless integrity passes and coverage is complete")
    args = parser.parse_args(argv)
    result = verify_capsule(args.capsule, args.artifact_root,
                            require_complete=args.require_complete)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"integrity={result['integrity']} "
              f"coverage={result['coverage']} (relative to the supplied versions directory)")
        for error in result["errors"]:
            print(f"error: {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
