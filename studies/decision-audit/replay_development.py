"""Report known development-vector behavior; stdout is a reproducible JSON report.

This is a retrospective capability inventory, not a held-out benchmark.
Validation refusals carry reasons; unexpected exceptions terminate the replay.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.test_conformance import DECIDE, CONVERTER, PRODUCER, VERIFIER  # noqa: E402


def inspect_case(lines: list[dict]) -> dict:
    outcomes = {}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        log = root / "decisions.jsonl"
        log.write_text("".join(json.dumps(line) + "\n" for line in lines))
        try:
            DECIDE.read_log(log)
            outcomes["gate_loader"] = {"outcome": "accept"}
        except DECIDE.GateError as exc:
            outcomes["gate_loader"] = {"outcome": "reject", "reason": str(exc).replace(str(root), "<temporary>")}
        try:
            CONVERTER.build_session(lines, project="conformance", rollout_id="conformance",
                                    task="game2048_policy_search", harness="test", model="none",
                                    decision_log_sha256="0" * 64)
            outcomes["converter"] = {"outcome": "accept"}
        except ValueError as exc:
            outcomes["converter"] = {"outcome": "reject", "reason": str(exc)}
        shutil.copytree(ROOT / "fixtures/gated", root / "fixture")
        job, task = root / "fixture/job", root / "fixture/task"
        shutil.copyfile(log, job / "artifacts/app/methods/decisions.jsonl")
        try:
            capsule = PRODUCER.build_capsule(job, task, "0.1@bc36dadb405b", "conformance", None, None, [])
        except PRODUCER.ProducerError as exc:
            outcomes["profile_verifier"] = {"outcome": "reject", "stage": "producer", "reason": str(exc)}
        else:
            capsule_path = job / "capsule.json"
            capsule_path.write_text(json.dumps(capsule, indent=2, sort_keys=True) + "\n")
            result = VERIFIER.verify_capsule(capsule_path)
            outcomes["profile_verifier"] = {
                "outcome": "accept" if result["ok"] else "reject",
                "stage": "verifier", "errors": result["errors"],
            }
    return outcomes


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_files(lines: list[dict]) -> dict:
    """Only check cited bytes; no decision semantics or canonical-path policy."""
    methods = (ROOT / "fixtures/gated/job/artifacts/app/methods").resolve()
    checked = 0
    for line in lines:
        for evidence in line["evidence"]:
            path = (methods / evidence["locator"]).resolve()
            if not path.is_relative_to(methods):
                return {"outcome": "error", "reason": "outside evidence root"}
            if not path.is_file():
                return {"outcome": "reject", "reason": "missing evidence"}
            if digest(path) != evidence["sha256"]:
                return {"outcome": "reject", "reason": "digest mismatch"}
            checked += 1
    return {"outcome": "accept" if checked else "not_assessed", "references": checked}


def main() -> None:
    rows = []
    for path in sorted((ROOT / "tests/conformance/vectors").glob("*.json")):
        vector = json.loads(path.read_text())
        details = inspect_case(vector["lines"])
        outcomes = {name: value["outcome"] for name, value in details.items()}
        rows.append({
            "case": path.stem,
            "input_sha256": digest(path),
            "description": vector["description"],
            "evidence_file_digests": evidence_files(vector["lines"]),
            "measured_local_outcomes": outcomes,
            "validation_details": details,
            "expected_local_outcomes": {key: vector["expect"][key] for key in outcomes},
        })
    sources = [ROOT / "studies/decision-audit/replay_development.py",
               ROOT / "studies/decision-audit/PROTOCOL.md",
               ROOT / "tests/test_conformance.py"]
    for directory in ("gate", "profile", "fixtures/gated"):
        sources.extend(path for path in (ROOT / directory).rglob("*")
                       if path.is_file() and "__pycache__" not in path.parts
                       and path.suffix not in (".pyc", ".pyo"))
    print(json.dumps({
        "study": "retrospective-development-replay",
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "limits": ["Known development cases; no held-out detection-rate estimate.",
                   "Converter includes contract checks; it is not schema-only.",
                   "File-digest acceptance is not record acceptance.",
                   "External implementations were not executed.",
                   "Expected validation exceptions carry reasons; unexpected exceptions abort execution."],
        "source_sha256": {str(path.relative_to(ROOT)): digest(path)
                          for path in sorted(set(sources))},
        "cases": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
