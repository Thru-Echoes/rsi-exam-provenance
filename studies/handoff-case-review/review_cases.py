"""Inspect retained historical evidence, not re-execute absent original jobs.

Stdlib only. All inputs are read-only. --check compares the saved dossier; the
optional --proofpress-root also verifies projections against original source bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(proofpress_root: Path | None = None) -> dict:
    relative = "docs/figures/sources/ab-opus-1-I"
    base = ROOT / relative
    capsule = json.loads((base / "capsule.json").read_text())
    log = (base / "experiment_log.md").read_bytes()
    refs = {}

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if (key == "locator" or key.endswith("_locator")) and isinstance(item, str):
                    locator = item if not item.startswith("results/") else "artifacts/app/methods/" + item
                    # Only experiment_log.md is retained at this flattened export location.
                    available = base / "experiment_log.md" if locator == "artifacts/app/methods/experiment_log.md" else base / locator
                    refs[locator] = available.exists()
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(capsule)
    versions = {v["version_id"]: v for v in capsule["versions"]}
    v1, v2, v3 = (versions[k] for k in ("v1", "v2", "v3"))
    declaration_rows = [{"version": v["version_id"], "parents": v["parent_ids"],
                         "status": v["status"], "reported_visible_mean": v["visible"]["score"],
                         "decisions": [{"kind": d["kind"], "disposition": d["disposition"],
                                        "estimate": d["estimate"], "replicates": d["replicates"]}
                                       for d in v.get("decisions", [])]}
                        for v in capsule["versions"]]
    projection_path = HERE / "harvey-source-projection.json"
    projection = json.loads(projection_path.read_text())
    for source in projection["sources"]:
        for excerpt in source.get("excerpts", []):
            if sha(excerpt["text"].encode()) != excerpt["sha256"]:
                raise ValueError("excerpt digest mismatch")
        if proofpress_root is not None:
            raw = (proofpress_root / source["path"]).read_bytes()
            if sha(raw) != source["sha256"]:
                raise ValueError("original source digest mismatch: " + source["path"])
            if "json_projection" in source:
                data = json.loads(raw)
                keys = source["selected_top_level_keys"]
                if keys is not None:
                    data = {key: data[key] for key in keys}
                if data != source["json_projection"]:
                    raise ValueError("JSON projection mismatch")
            for excerpt in source.get("excerpts", []):
                if raw.decode()[excerpt["start"]:excerpt["end"]] != excerpt["text"]:
                    raise ValueError("text projection mismatch")
    result = projection["sources"][0]["json_projection"]
    protocol = projection["sources"][1]["json_projection"]
    pairs = result["protection"]["pairs_detail"]
    license_pairs = [p for p in pairs if p["task"] == "license"]
    if len(license_pairs) != 3 or len(pairs) != 9:
        raise ValueError("unexpected historical denominator")
    h5_path = ROOT / "docs/shadow-audit/helper-cohort/records.md"
    h5 = [line for line in h5_path.read_text().splitlines() if "campaign-H5-" in line]
    if len(h5) != 1 or "submitted_not_snapshotted" not in h5[0]:
        raise ValueError("historical H5 record no longer matches")
    sources = [base / "capsule.json", base / "experiment_log.md", h5_path,
               ROOT / "docs/PREFLIGHT.md", projection_path, Path(__file__)]
    return {
        "schema_version": 1,
        "mode": "retained-record-inspection-not-original-run-reproduction",
        "source_sha256": {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sources},
        "rsi_case": {
            "id": capsule["capsule_id"],
            "evidence_class": "historical real-run capsule and bound log; incomplete original package",
            "log_binding_matches": sha(log) == capsule["source"]["experiment_log"]["sha256"],
            "declared_final_matches_v3_digest": capsule["final_submission"]["method_tree_sha256"] == v3["artifact"]["method_tree_sha256"],
            "versions": declaration_rows,
            "v2_reported_mean_gain_over_v1": v2["visible"]["score"] - v1["visible"]["score"],
            "v2_is_reverted_without_gate_decision": v2["status"] == "reverted" and not v2.get("decisions"),
            "v3_branches_from_v1": v3["parent_ids"] == ["v1"],
            "reference_availability_in_retained_export": dict(sorted(refs.items())),
            "can_recompute_per_seed_statistics": False,
            "can_verify_original_snapshot_bytes": False,
            "original_job_rerun": False,
        },
        "rsi_failure_report": {
            "id": "campaign-H5-wcEU25o", "evidence_class": "historical report only",
            "record_row": h5[0], "reason": "submitted_not_snapshotted",
            "interpretation_source": "docs/PREFLIGHT.md: helper-overlay campaign; edit after last decision",
            "current_verifier_reproduction": False,
        },
        "harvey_case": {
            "evidence_class": "historical model-run result projection with controlled perturbation",
            "selected_task": "license", "selected_stress_pairs": license_pairs,
            "ordinary_unsafe_count": sum(p["ordinary_unsafe"] for p in license_pairs),
            "proofpress_unsafe_count": sum(p["proofpress_unsafe"] for p in license_pairs),
            "full_pilot_stress_pairs": len(pairs),
            "full_pilot_ordinary_unsafe_count": sum(p["ordinary_unsafe"] for p in pairs),
            "full_pilot_proofpress_unsafe_count": sum(p["proofpress_unsafe"] for p in pairs),
            "treatment_difference": protocol["stress_arm"]["treatment_difference"],
            "selection": projection["selection"],
            "runtime_reproduction": False,
            "same_implementation_as_rsi": False,
            "upstream_source_commit": projection["sources"][0]["commit"],
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--proofpress-root", type=Path)
    args = parser.parse_args()
    result = inspect(args.proofpress_root)
    if args.check:
        expected = json.loads((HERE / "case-results.json").read_text())
        if expected != result:
            raise SystemExit("Historical dossier changed; inspect before regenerating.")
        print("Historical dossier reproduced; original model runs and absent file contents are NOT reproduced.")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
