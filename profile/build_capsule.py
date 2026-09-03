#!/usr/bin/env python3
"""Build an RSI-Exam rollout provenance record from a harbor job directory.

Inputs: a harbor job directory (the layout RSI-Exam publishes:
agent/trajectory.json, artifacts/app/methods/{main,versions,experiment_log.md},
verifier/reward.json) and the task directory the rollout ran against (for the
frozen task and grader digests). Output: a capsule JSON conforming to
proofpress/rsi-exam-trajectory/v2, written inside the job directory by default
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

SCHEMA_VERSION = "proofpress/rsi-exam-trajectory/v2"
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
    lines = [f"{file_digest(path / rel)}  {rel}\n" for rel in sorted(entries)]
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


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
            },
            "log": {"line": line_no},
        }
        visible = get_visible(line)
        if visible is not None:
            version["visible"] = visible
        versions.append(version)

    main_tree = tree_digest(main_dir)
    matches = [v for v in versions if v["artifact"]["tree_sha256"] == main_tree]
    if not matches:
        raise ProducerError("submitted_not_snapshotted")
    chosen = max(matches, key=lambda v: v["ordinal"])
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
    }
    if trajectory is not None:
        source["trajectory"] = trajectory
    if trace_exports:
        source["trace_exports"] = [
            {"session_id": session_id, "locator": locator,
             "sha256": file_digest(job_dir / locator)}
            for session_id, locator in trace_exports
        ]

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
        "benchmark": {"name": "RSI-Exam", "release": release, "task_id": task_id},
        "rollout": rollout,
        "freeze": {
            "task_digest": tree_digest(task_dir),
            "grader_digest": tree_digest(grader_dir),
        },
        "source": source,
        "versions": versions,
        "final_submission": {
            "version_id": chosen["version_id"],
            "tree_sha256": main_tree,
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
