#!/usr/bin/env python3
"""Build an RSI-Exam rollout provenance record from a harbor job directory.

Inputs: a harbor job directory (the layout RSI-Exam publishes:
agent/trajectory.json, artifacts/app/methods/{main,versions,experiment_log.md},
verifier/reward.json) and the task directory the rollout ran against (for the
frozen task and grader digests). Output: a capsule JSON conforming to
proofpress/rsi-exam-trajectory/v3, written inside the job directory by default
so every locator is relative to the capsule's parent.

The producer is strict and fails closed: a version snapshot that cannot be
classified from the experiment log, a submitted tree that was never
snapshotted, or a missing mandated file is an error, not a guess. Determinism:
output is json.dumps(..., indent=2, sort_keys=True) so the same job directory
always yields byte-identical output.

Side effects: writes the output file only. Zero third-party dependencies;
Python 3.11+ (uses tomllib).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "proofpress/rsi-exam-trajectory/v3"
# Bytecode caches drift on every import, so they are outside the digest that decides identity.
# Recorded in the record as source.exclusions so a verifier applies the same rule.
DECISION_LOG = "decisions.jsonl"
DECISION_SCHEMA = "rsi-exam-decision-log/v1"
# The section 1 fields the record carries per decision. `statistic` and `unit` are hoisted to the
# benchmark block because one log states one of each; `schema` and `line` become the record's own
# `log_line`. Any field a later contract adds under the same schema id is not carried here, which
# loses nothing: source.decision_log binds the log itself by digest.
DECISION_KEYS = ("version_id", "parent_id", "replicates", "timestamp", "direction", "estimate",
                 "interval", "method", "sample_size", "min_effect", "verdict", "disposition",
                 "evidence", "evidence_digests", "holdout", "confirm_policy", "profile_sha256",
                 "look_index", "parent_method_tree_sha256", "candidate_method_tree_sha256",
                 "sizing", "suite")
EXCLUSIONS = ("__pycache__/", "*.pyc", "*.pyo")
EXCLUDED_DIR = "__pycache__"
EXCLUDED_SUFFIXES = (".pyc", ".pyo")
VERSION_DIR = re.compile(r"^v[0-9]+$")
VERSION_TOKEN = re.compile(r"\bv[0-9]+\b")
SCORE_TOKEN = re.compile(r"scores?\s*[:=]?\s*(-?[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


class ProducerError(SystemExit):
    def __init__(self, code: str):
        super().__init__(f"producer_error: {code}")
        self.code = code


# Keep in step with verify_capsule.py (test_tree_digest_implementations_agree
# guards the pair).

def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(path: Path) -> str:
    if path.is_symlink():
        raise ProducerError(f"symlink:{path.name}")
    entries = []
    for child in path.rglob("*"):
        if child.is_symlink():
            raise ProducerError(f"symlink:{child.name}")
        if child.is_file():
            entries.append(child.relative_to(path).as_posix())
    try:
        lines = [f"{file_digest(path / rel)}  {rel}\n" for rel in sorted(entries)]
    except OSError as exc:
        raise ProducerError(f"unreadable:{path.name}:{exc.__class__.__name__}")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def method_files(path: Path) -> list[str]:
    """Sorted POSIX relpaths of the ``.py`` files a method-tree digest covers.

    This is digest construction, not submission validation: files the grader would not stage are
    skipped, not refused, so a snapshot that carries a note is still recordable. Refused instead
    are the cases where the staged set cannot be known: a symlink, anything that is not a regular
    file, and a ``.py`` file under ``__pycache__`` (bytecode there is ignored, but source there
    may or may not be staged, and a digest must not silently drop a file that might be).

    ``assert_stageable`` carries the rule that decides whether a tree is a valid submission.
    Raises ProducerError; no side effects.
    """
    if path.is_symlink():
        raise ProducerError(f"symlink:{path.name}")
    rels: list[str] = []
    for child in path.rglob("*"):
        rel = child.relative_to(path)
        if child.is_symlink():
            raise ProducerError(f"symlink:{rel.as_posix()}")
        if child.is_dir():
            continue
        cached = EXCLUDED_DIR in rel.parts
        if cached and child.suffix == ".py":
            raise ProducerError(f"source_in_cache_dir:{path.name}/{rel.as_posix()}")
        if cached or child.suffix in EXCLUDED_SUFFIXES:
            continue
        if not child.is_file():
            raise ProducerError(f"not_a_regular_file:{path.name}/{rel.as_posix()}")
        if child.suffix != ".py":
            continue
        rels.append(rel.as_posix())
    return sorted(rels)


def method_tree_digest(path: Path) -> str:
    """Cache-free digest of a method tree, in the same line format as tree_digest.

    A Python-only tree with no caches therefore digests identically under both functions. This is
    the digest that decides which snapshots the submission is, because it is the view the grader
    stages. Raises ProducerError; no side effects.
    """
    try:
        lines = [f"{file_digest(path / rel)}  {rel}\n" for rel in method_files(path)]
    except OSError as exc:
        raise ProducerError(f"unreadable:{path.name}:{exc.__class__.__name__}")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def assert_stageable(path: Path) -> None:
    """Refuse a tree the grader would not accept as a submission.

    The grader stages ``.py`` files only and scores a submission carrying any other regular file
    0.0, so such a tree has no digest it would honour. Applied to ``main/`` alone: a snapshot that
    is not stageable is still a fact worth recording. Raises ProducerError; no side effects.
    """
    stray = []
    found_python = False
    for child in path.rglob("*"):
        rel = child.relative_to(path)
        if child.is_dir() or EXCLUDED_DIR in rel.parts or child.suffix in EXCLUDED_SUFFIXES:
            continue
        if child.suffix == ".py":
            found_python = True
        else:
            stray.append(rel.as_posix())
    if stray:
        raise ProducerError(f"non_python_in_submission:{sorted(stray)[0]}")
    if not found_python:
        raise ProducerError("empty_submission")


def _reject_constant(token: str) -> Any:
    """Refuse the JSON extensions for non-finite numbers; the contract requires every number finite."""
    raise ValueError(f"non-finite number in the decision log: {token}")


def get_decisions(log_path: Path) -> tuple[dict[str, list[dict[str, Any]]], str, str]:
    """Read the gate's decision log into per-version entries, plus the shared statistic and unit.

    Returns ``({version_id: [entry, ...]}, statistic, unit)`` with entries in log order. Each entry
    carries ``log_line``, ``kind`` (``screening`` or ``confirmation``), the DECISION_KEYS fields,
    and ``resolves_log_line`` on a confirmation. A malformed line, a line numbered out of step with
    its physical position, a log mixing two statistics or units, and a confirmation with no open
    provisional to resolve are all errors rather than omissions. Raises ProducerError; reads only.
    """
    try:
        raw = log_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        raise ProducerError("decision_log_unreadable")
    if not raw:
        raise ProducerError("decision_log_empty")

    lines: list[dict[str, Any]] = []
    for position, text in enumerate(raw, start=1):
        if not text.strip():
            raise ProducerError(f"decision_log_blank_line:{position}")
        try:
            line = json.loads(text, parse_constant=_reject_constant)
        except (json.JSONDecodeError, ValueError):
            raise ProducerError(f"decision_log_malformed:{position}")
        if not isinstance(line, dict):
            raise ProducerError(f"decision_log_malformed:{position}")
        if line.get("schema") != DECISION_SCHEMA:
            raise ProducerError(f"decision_log_foreign_schema:{position}")
        if isinstance(line.get("line"), bool) or line.get("line") != position:
            raise ProducerError(f"decision_log_line_number:{position}")
        missing = [key for key in DECISION_KEYS if key not in line]
        if missing:
            raise ProducerError(f"decision_log_missing_field:{position}:{missing[0]}")
        for key in ("statistic", "unit"):
            # Checked per line before they are collected: a missing or non-string value would
            # otherwise raise KeyError or TypeError out of a set comprehension.
            value = line.get(key)
            if not isinstance(value, str) or not value:
                raise ProducerError(f"decision_log_bad_measurement:{position}:{key}")
        lines.append(line)

    statistics = {line["statistic"] for line in lines}
    units = {line["unit"] for line in lines}
    if len(statistics) != 1 or len(units) != 1:
        raise ProducerError("decision_log_mixed_measurement")
    statistic, unit = statistics.pop(), units.pop()

    decisions: dict[str, list[dict[str, Any]]] = {}
    # A confirmation resolves the latest still-open provisional for the version it replicates.
    open_provisional: dict[str, dict[str, Any]] = {}
    for line in lines:
        vid = line["version_id"]
        entry: dict[str, Any] = {"log_line": line["line"]}
        entry.update({key: line[key] for key in DECISION_KEYS})
        if line["replicates"] is not None:
            if line["replicates"] != vid:
                raise ProducerError(f"decision_log_replicates_other_version:{line['line']}")
            resolved = open_provisional.pop(vid, None)
            if resolved is None:
                raise ProducerError(f"decision_log_confirmation_without_provisional:{line['line']}")
            entry["kind"] = "confirmation"
            entry["resolves_log_line"] = resolved["log_line"]
        else:
            entry["kind"] = "screening"
            if line["disposition"] == "provisional":
                open_provisional[vid] = entry
        decisions.setdefault(vid, []).append(entry)
    return decisions, statistic, unit


def get_decided_status(entries: list[dict[str, Any]]) -> str:
    """The version's status from its resolved decision state.

    A provisional the log never resolved stays ``provisional``; one a confirmation resolved takes
    that confirmation's disposition, so a provisional resolved by a revert is ``reverted``. Pure
    function; raises ProducerError on a disposition the contract does not define.
    """
    last = entries[-1]
    disposition = last["disposition"]
    if disposition == "keep":
        return "kept"
    if disposition == "revert":
        return "reverted"
    if disposition == "provisional":
        return "provisional"
    raise ProducerError(f"decision_log_unknown_disposition:{last['log_line']}")


def get_log_reference(log_lines: list[str], version_id: str) -> tuple[int, str]:
    """First 1-based line that names the version. Raises when absent."""
    token = re.compile(rf"\b{re.escape(version_id)}\b")
    for number, line in enumerate(log_lines, start=1):
        if token.search(line):
            return number, line
    raise ProducerError(f"log_missing_version:{version_id}")


def get_status(line: str, version_id: str) -> str:
    lowered = line.lower()
    if "revert" in lowered:
        return "reverted"
    if "kept" in lowered or "keep" in lowered:
        return "kept"
    raise ProducerError(f"log_unclassifiable:{version_id}")


def get_parents(line: str, version_id: str) -> list[str]:
    others = [t for t in VERSION_TOKEN.findall(line) if t != version_id]
    return [others[0]] if others else []


def get_visible(line: str) -> dict[str, Any] | None:
    match = SCORE_TOKEN.search(line)
    if not match:
        return None
    return {"score": float(match.group(1)), "recorded_in": "experiment_log"}


def build_capsule(job_dir: Path, task_dir: Path, release: str, capsule_id: str,
                  model: str | None, harness: str | None,
                  trace_exports: list[tuple[str, str]]) -> dict[str, Any]:
    methods = job_dir / "artifacts/app/methods"
    log_path = methods / "experiment_log.md"
    versions_root = methods / "versions"
    main_dir = methods / "main"
    reward_path = job_dir / "verifier/reward.json"
    for path, code in ((methods, "missing_methods"), (log_path, "missing_log"),
                       (versions_root, "missing_versions_root"),
                       (main_dir, "missing_main"),
                       (reward_path, "missing_reward")):
        if not path.exists():
            raise ProducerError(code)

    task_toml = task_dir / "task.toml"
    grader_dir = task_dir / "tests"
    if not task_toml.is_file() or not grader_dir.is_dir():
        raise ProducerError("missing_task_files")
    config = tomllib.loads(task_toml.read_text(encoding="utf-8"))
    timeout_sec = float(config.get("agent", {}).get("timeout_sec", 0.0))
    if timeout_sec <= 0:
        raise ProducerError("missing_agent_timeout")
    task_id = str(config.get("task", {}).get("name", "")).strip()
    if not task_id:
        raise ProducerError("missing_task_name")

    trajectory_path = job_dir / "agent/trajectory.json"
    trajectory: dict[str, Any] | None = None
    agent_meta: dict[str, Any] = {}
    if trajectory_path.is_file():
        trajectory = {
            "locator": "agent/trajectory.json",
            "sha256": file_digest(trajectory_path),
            "format": "ATIF",
        }
        try:
            agent_meta = json.loads(
                trajectory_path.read_text(encoding="utf-8")).get("agent", {})
        except (OSError, json.JSONDecodeError, AttributeError):
            agent_meta = {}
    model = model or agent_meta.get("model_name")
    harness = harness or agent_meta.get("name")
    if not model or not harness:
        raise ProducerError("missing_model_or_harness")

    decision_log_path = methods / DECISION_LOG
    decisions: dict[str, list[dict[str, Any]]] = {}
    statistic = unit = None
    if decision_log_path.is_file():
        decisions, statistic, unit = get_decisions(decision_log_path)

    log_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    snapshot_dirs = sorted(
        (child for child in versions_root.iterdir()
         if child.is_dir() and VERSION_DIR.fullmatch(child.name)),
        key=lambda child: int(child.name[1:]))
    if not snapshot_dirs:
        raise ProducerError("no_snapshots")

    versions: list[dict[str, Any]] = []
    ids = {child.name for child in snapshot_dirs}
    lowest = min(int(child.name[1:]) for child in snapshot_dirs)
    digests: dict[str, str] = {}
    for child in snapshot_dirs:
        vid = child.name
        line_no, line = get_log_reference(log_lines, vid)
        parents = get_parents(line, vid)
        for parent in parents:
            if parent not in ids:
                raise ProducerError(f"unknown_parent:{vid}")
        if not parents and int(vid[1:]) != lowest:
            raise ProducerError(f"missing_parent:{vid}")
        digests[vid] = tree_digest(child)
        version: dict[str, Any] = {
            "version_id": vid,
            "ordinal": int(vid[1:]),
            "parent_ids": parents,
            "status": get_status(line, vid),
            "artifact": {
                "type": "directory",
                "locator": f"artifacts/app/methods/versions/{vid}",
                "tree_sha256": digests[vid],
                "method_tree_sha256": method_tree_digest(child),
            },
            "log": {"line": line_no},
        }
        entries = decisions.get(vid)
        if entries:
            # The gate's own record of what it decided outranks the prose in the experiment log.
            version["status"] = get_decided_status(entries)
            version["decisions"] = entries
        visible = get_visible(line)
        if visible is not None:
            version["visible"] = visible
        versions.append(version)

    # Identity is decided by the method tree, the view the grader stages: bytecode caches drift on
    # every import and would otherwise make a snapshot stop matching the tree it is. Two snapshots
    # can hold the same method tree, and then the reward cannot tell them apart either, so the
    # record names the whole class rather than guessing which one was restored.
    assert_stageable(main_dir)
    main_tree = tree_digest(main_dir)
    main_method_tree = method_tree_digest(main_dir)
    matches = [v for v in versions
               if v["artifact"]["method_tree_sha256"] == main_method_tree]
    if not matches:
        raise ProducerError("submitted_not_snapshotted")
    matches.sort(key=lambda v: v["ordinal"])
    # The lowest ordinal is a canonical representative, not a claim about which was restored.
    chosen = matches[0]
    chosen["status"] = "submitted"

    try:
        reward_payload = json.loads(reward_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ProducerError("reward_unreadable")
    reward = reward_payload.get("reward") if isinstance(reward_payload, dict) else None
    if isinstance(reward, bool) or not isinstance(reward, (int, float)):
        raise ProducerError("reward_invalid")

    hidden: dict[str, Any] = {
        "reward_locator": "verifier/reward.json",
        "reward_sha256": file_digest(reward_path),
        "reward": reward,
        "binding": {"basis": "job_directory", "job_id": job_dir.name},
    }
    if isinstance(reward_payload.get("error"), str):
        hidden["error"] = reward_payload["error"]
    details_path = job_dir / "verifier/score_details.json"
    if details_path.is_file():
        hidden["score_details_locator"] = "verifier/score_details.json"
        hidden["score_details_sha256"] = file_digest(details_path)

    source: dict[str, Any] = {
        "experiment_log": {
            "locator": "artifacts/app/methods/experiment_log.md",
            "sha256": file_digest(log_path),
        },
        "versions_root": {"locator": "artifacts/app/methods/versions"},
        "exclusions": list(EXCLUSIONS),
    }
    if decisions:
        source["decision_log"] = {
            "locator": f"artifacts/app/methods/{DECISION_LOG}",
            "sha256": file_digest(decision_log_path),
        }
    unrecorded = sorted(set(decisions) - {v["version_id"] for v in versions})
    if unrecorded:
        raise ProducerError(f"decision_log_unknown_version:{unrecorded[0]}")
    if trajectory is not None:
        source["trajectory"] = trajectory
    if trace_exports:
        source["trace_exports"] = [
            {"session_id": session_id, "locator": locator,
             "sha256": file_digest(job_dir / locator)}
            for session_id, locator in trace_exports
        ]

    benchmark: dict[str, Any] = {"name": "RSI-Exam", "release": release, "task_id": task_id}
    if statistic is not None and unit is not None:
        # One log states one measurement, so the decisions inherit these rather than repeating them.
        benchmark["statistic"] = statistic
        benchmark["unit"] = unit

    rollout: dict[str, Any] = {
        "id": job_dir.name,
        "model": model,
        "harness": harness,
        "config_digest": file_digest(task_toml),
        "budget_hours": timeout_sec / 3600.0,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "capsule_id": capsule_id,
        "benchmark": benchmark,
        "rollout": rollout,
        "freeze": {
            "task_digest": tree_digest(task_dir),
            "grader_digest": tree_digest(grader_dir),
        },
        "source": source,
        "versions": versions,
        "final_submission": {
            "version_id": chosen["version_id"],
            "locator": "artifacts/app/methods/main",
            "tree_sha256": main_tree,
            "method_tree_sha256": main_method_tree,
            "version_ids": [v["version_id"] for v in matches],
        },
        "hidden_evaluation": hidden,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--capsule-id", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--harness", default=None)
    parser.add_argument("--trace-export", action="append", default=[],
                        metavar="SESSION_ID=RELATIVE_PATH",
                        help="bind one share-safe TRACE export already inside the job dir")
    parser.add_argument("--output", default=None,
                        help="default: <job-dir>/capsule.json")
    args = parser.parse_args(argv)

    exports: list[tuple[str, str]] = []
    for item in args.trace_export:
        session_id, _, locator = item.partition("=")
        if not session_id or not locator:
            raise ProducerError("bad_trace_export_argument")
        exports.append((session_id, locator))

    capsule = build_capsule(Path(args.job_dir).resolve(),
                            Path(args.task_dir).resolve(),
                            args.release, args.capsule_id,
                            args.model, args.harness, exports)
    output = Path(args.output) if args.output else Path(args.job_dir) / "capsule.json"
    output.write_text(json.dumps(capsule, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
