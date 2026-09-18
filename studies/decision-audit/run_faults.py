"""Run the frozen authored-case manifest against an unchanged verifier.

All mutation takes place in disposable copies of fixtures/gated. Unexpected
exceptions terminate the run and cannot be mistaken for detected faults.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_development import ROOT, VERIFIER, digest

STUDY = Path(__file__).resolve().parent
METHODS = "artifacts/app/methods"


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def schema(data: dict) -> list[str]:
    errors = []
    VERIFIER.CAPSULE_SPEC(data, "$", errors)
    return errors


def binding_checks(job: Path, data: dict) -> list[str]:
    """Hash-check the supplied references without interpreting relationships."""
    errors = schema(data)
    if errors:
        return errors
    references = []
    for value in data["source"].values():
        if isinstance(value, dict) and "sha256" in value:
            references.append((value["locator"], value["sha256"], "file"))
    hidden = data["hidden_evaluation"]
    for prefix in ("reward", "score_details"):
        if prefix + "_locator" in hidden:
            references.append((hidden[prefix + "_locator"], hidden[prefix + "_sha256"], "file"))
    for node in [data["final_submission"]] + [v["artifact"] for v in data["versions"]]:
        for key, kind in (("tree_sha256", "tree"), ("method_tree_sha256", "method")):
            references.append((node["locator"], node[key], kind))
    for version in data["versions"]:
        for decision in version.get("decisions", []):
            for item in decision["evidence"]:
                references.append((METHODS + "/" + item["locator"], item["sha256"], "file"))
            holdout = decision.get("holdout")
            if isinstance(holdout, dict):
                for item in holdout.get("evidence", []):
                    references.append((METHODS + "/" + item["locator"], item["sha256"], "file"))
    functions = {"file": digest, "tree": VERIFIER.tree_digest, "method": VERIFIER.method_tree_digest}
    for locator, expected, kind in references:
        path = (job / locator).resolve()
        if not path.is_relative_to(job.resolve()):
            raise RuntimeError("case unexpectedly contains an escaping locator")
        if not path.exists():
            errors.append("binding:missing:" + locator)
        elif functions[kind](path) != expected:
            errors.append("binding:digest_mismatch:" + locator)
    return sorted(set(errors))


def mutate(case_id: str, job: Path, data: dict) -> None:
    methods = job / METHODS
    v2, v3 = data["versions"][1:]
    log_path = methods / "decisions.jsonl"
    lines = [json.loads(line) for line in log_path.read_text().splitlines()]
    if case_id == "clean":
        return
    if case_id == "cache_variation":
        for node, payload in ((data["final_submission"], b"main-cache"),
                              (v3["artifact"], b"snapshot-cache")):
            path = job / node["locator"]
            (path / "__pycache__").mkdir()
            (path / "__pycache__/policy.cpython-313.pyc").write_bytes(payload)
            node["tree_sha256"] = VERIFIER.tree_digest(path)
    elif case_id == "reward_rewrite":
        path = job / data["hidden_evaluation"]["reward_locator"]
        reward = json.loads(path.read_text())
        reward["reward"] = 0.5
        save(path, reward)
        data["hidden_evaluation"]["reward"] = 0.5
        data["hidden_evaluation"]["reward_sha256"] = digest(path)
    elif case_id == "bad_status":
        v2["status"] = "unrecognized"
    elif case_id == "missing_evidence":
        (methods / "results/v2/visible_result.json").unlink()
    elif case_id == "submission_mismatch":
        shutil.copyfile(methods / "versions/v2/policy.py", methods / "main/policy.py")
        data["final_submission"]["tree_sha256"] = VERIFIER.tree_digest(methods / "main")
        data["final_submission"]["method_tree_sha256"] = VERIFIER.method_tree_digest(methods / "main")
    elif case_id == "missing_snapshot":
        shutil.rmtree(methods / "versions/v2")
    elif case_id == "unrecorded_snapshot":
        (methods / "versions/v4").mkdir()
        (methods / "versions/v4/policy.py").write_text("# unrecorded experiment\nx = 4\n")
    else:
        if case_id == "orientation":
            lines[0]["direction"] = "lower"
        elif case_id == "wrong_estimate":
            lines[0]["estimate"] += 1
        elif case_id == "swapped_measurements":
            a, b = lines[0]["evidence"]
            for field in ("locator", "sha256"):
                a[field], b[field] = b[field], a[field]
            lines[0]["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in (a, b)}
        elif case_id == "unconfirmed_submission":
            lines.pop()
            v3["decisions"].pop()
        else:
            raise ValueError("unknown case " + case_id)
        if case_id != "unconfirmed_submission":
            for key in ("direction", "estimate", "evidence", "evidence_digests"):
                v2["decisions"][0][key] = copy.deepcopy(lines[0][key])
        log_path.write_text("".join(json.dumps(line, sort_keys=True) + "\n" for line in lines))
        data["source"]["decision_log"]["sha256"] = digest(log_path)


def file_manifest(root: Path) -> dict:
    return {str(path.relative_to(root)): digest(path) for path in sorted(root.rglob("*")) if path.is_file()}


def run_case(case: dict) -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "fixture"
        shutil.copytree(ROOT / "fixtures/gated", root)
        job = root / "job"
        before = VERIFIER.verify_capsule(job / "capsule.json", require_complete=True)
        if not before["ok"]:
            raise RuntimeError("clean fixture failed: " + repr(before))
        old_files = file_manifest(job)
        data = json.loads((job / "capsule.json").read_text())
        mutate(case["id"], job, data)
        save(job / "capsule.json", data)
        new_files = file_manifest(job)
        structural = schema(data)
        bindings = binding_checks(job, data)
        full = VERIFIER.verify_capsule(job / "capsule.json", require_complete=True)
        full_outcome = "accept" if full["ok"] else "reject"
        target_found = (case["target"] == "coverage:partial" and full["coverage"] == "partial") or any(
            error.startswith(case["target"]) for error in full["errors"])
        return {
            **case,
            "outcomes": {"structure": "reject" if structural else "accept",
                         "bindings": "reject" if bindings else "accept", "full": full_outcome},
            "structure_errors": structural, "binding_errors": bindings, "full_result": full,
            "target_found": target_found if case["kind"] == "fault" else None,
            "expectation_met": full_outcome == case["expected_full"] and
                               (case["kind"] != "fault" or target_found),
            "changed_files": {name: {"before": old_files.get(name), "after": new_files.get(name)}
                              for name in sorted(old_files.keys() | new_files.keys())
                              if old_files.get(name) != new_files.get(name)},
            "package_manifest_sha256": hashlib.sha256(json.dumps(new_files, sort_keys=True).encode()).hexdigest(),
        }


def main() -> None:
    manifest = json.loads((STUDY / "fault-manifest.json").read_text())
    rows = [run_case(case) for case in manifest["cases"]]
    source_paths = [STUDY / "fault-manifest.json", Path(__file__), STUDY / "replay_development.py",
                    ROOT / "profile/verify_capsule.py", ROOT / "tests/test_conformance.py"]
    print(json.dumps({
        "study": "authored-controlled-fault-cases", "manifest": manifest,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in source_paths},
        "fixture_sha256": file_manifest(ROOT / "fixtures/gated"),
        "cases": rows,
        "all_expectations_met": all(row["expectation_met"] for row in rows),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
