"""Local fixture demonstration, never human approval or a hosted service call.

Export the pinned Proofpress commit (ignoring local changes), then execute the
probe in a disposable repository with a minimal, credential-free environment.
The retained report contains counts, public source pins, hashes and diagnostics,
not temporary paths or full ledger history. No provider or network is used.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
PP_REV = "7fad672321ae00d7c7af350e7b26000846b37895"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe(root):
    from proofpress.kernel import operations as ops

    sys.path.insert(0, str(ROOT / "studies/decision-audit"))
    from run_faults import mutate, save, VERIFIER
    converter = load("boundary_converter", ROOT / "gate/trace_from_decisions.py")

    def counts():
        p = ops.v2_projection()
        return {key: len(p[key]) for key in ("sources", "evidence", "claims", "admissions", "events")}

    def cli(*args):
        result = subprocess.run([sys.executable, "-m", "proofpress.cli", *args],
                                text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def convert(job):
        log = job / "artifacts/app/methods/decisions.jsonl"
        lines = [json.loads(line) for line in log.read_text().splitlines()]
        return converter.build_session(lines, project="framework-boundary",
            rollout_id="conformance", task="game2048_policy_search", harness="fixture",
            model="none", decision_log_sha256=digest(log))

    job = root / "package"
    shutil.copytree(ROOT / "fixtures/gated/job", job)
    baseline = VERIFIER.verify_capsule(job / "capsule.json", require_complete=True)
    assert baseline["ok"], baseline
    trace = convert(job)
    trace_path = root / "session.json"
    save(trace_path, trace)
    ops.import_evidence_v2(trace_path)
    first = counts()
    assert first == {"sources": 3, "evidence": 3, "claims": 0, "admissions": 0, "events": 6}, first
    assert cli("context")["governed_context"] == []
    ops.import_evidence_v2(trace_path)
    assert counts() == first
    projection = ops.v2_projection()
    reverted_source = next(key for key, row in projection["sources"].items()
                           if row["attributes"]["event"]["disposition"] == "rejected")
    reverted_evidence = next(key for key, row in projection["evidence"].items()
                             if row["source_ref"] == reverted_source)
    confidence = [row["attributes"]["event"]["confidence"] for row in projection["sources"].values()]
    keys = ["evidence_digests", "interval", "method", "sample_size"]
    assert all(sorted(c) == keys for c in confidence)
    assert all(sorted(c["method"]) == ["name", "resamples"] for c in confidence)

    refused = {}
    for label in ("unsupported_version", "malformed_interval", "changed_identity_content"):
        changed = copy.deepcopy(trace)
        if label == "unsupported_version":
            changed["trace_version"] = "0.5.2"
            expected = "unsupported TRACE trace_version"
        elif label == "malformed_interval":
            changed["events"][0]["decision"]["confidence"]["interval"]["lower"] = 1000
            expected = "interval.lower must not exceed interval.upper"
        else:
            changed["trace_version"] = "0.5.0"
            expected = "immutable source_recorded conflict"
        path = root / (label + ".json")
        save(path, changed)
        try:
            ops.import_evidence_v2(path)
        except ValueError as error:
            assert expected in str(error), str(error)
            refused[label] = expected
        else:
            raise AssertionError("expected refusal: " + label)
        assert counts() == first

    # The existing numerical fault passes conversion/import because the adapter
    # does not recompute the raw results. This is not a new ninth/fault trial.
    capsule = json.loads((job / "capsule.json").read_text())
    mutate("wrong_estimate", job, capsule)
    save(job / "capsule.json", capsule)
    rejected = VERIFIER.verify_capsule(job / "capsule.json", require_complete=True)
    assert not rejected["ok"] and any("estimate" in e for e in rejected["errors"]), rejected
    changed_trace = convert(job)
    assert changed_trace != trace
    save(trace_path, changed_trace)
    # Use a fresh receiver: the changed rationale would correctly conflict
    # with an already imported identity. We test first-time import, not overwrite.
    receiver = root / "fault-receiver"
    receiver.mkdir()
    for argv in (["git", "init", "-q"], ["git", "config", "user.name", "Synthetic fixture"],
                 ["git", "config", "user.email", "fixture@example.invalid"]):
        subprocess.run(argv, cwd=receiver, check=True)
    previous = Path.cwd()
    try:
        os.chdir(receiver)
        ops.import_evidence_v2(trace_path)
        fault_counts = counts()
        assert fault_counts == first
        assert cli("context")["governed_context"] == []
    finally:
        os.chdir(previous)

    # Explicitly propose a synthetic candidate, never invoke review/admission.
    cli("propose", "--title", "Synthetic import boundary",
        "--statement", "The imported TRACE event records a revert disposition.",
        "--evidence", reverted_evidence, "--scope", "synthetic-framework-demo",
        "--proposer", "agent:framework-demo")
    after_proposal = counts()
    assert after_proposal["claims"] == 1 and after_proposal["admissions"] == 0
    assert cli("context")["governed_context"] == []
    return {
        "schema_version": 1, "kind": "local-synthetic-integration-demonstration",
        "proofpress_commit": PP_REV, "trace_wire_version": trace["trace_version"],
        "trace_release_pin": ops.TRACE_SUPPORTED_VERSIONS[trace["trace_version"]],
        "input_sha256": {p: digest(ROOT / p) for p in (
            "gate/trace_from_decisions.py", "profile/verify_capsule.py",
            "fixtures/gated/job/capsule.json",
            "fixtures/gated/job/artifacts/app/methods/decisions.jsonl")},
        "runner_sha256": digest(Path(__file__)),
        "baseline_verification": {"ok": baseline["ok"], "coverage": baseline["coverage"]},
        "after_import": first, "reimport_ledger_unchanged": True,
        "projected_confidence_keys": keys, "expected_refusals": refused,
        "wrong_estimate_boundary": {"verifier_accepts": False, "converter_accepts": True,
            "adapter_accepts_in_fresh_receiver": True, "after_import": fault_counts,
            "verifier_errors": rejected["errors"]},
        "after_explicit_proposal": {"claims": after_proposal["claims"],
            "admissions": after_proposal["admissions"], "governed_context_items": 0},
        "human_approval_exercised": False, "downstream_agent_run": False,
        "trace_schema_validation_rerun": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proofpress-root", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--_probe", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._probe:
        print(json.dumps(probe(args._probe), sort_keys=True, indent=2))
        return
    if not args.proofpress_root:
        parser.error("--proofpress-root must contain the pinned public commit")
    with tempfile.TemporaryDirectory(prefix="nanda-framework-") as temporary:
        root = Path(temporary)
        source = root / "proofpress"
        source.mkdir()
        archive = subprocess.check_output(["git", "archive", PP_REV], cwd=args.proofpress_root)
        subprocess.run(["tar", "-xf", "-", "-C", str(source)], input=archive, check=True)
        workspace = root / "workspace"
        workspace.mkdir()
        env = {k: os.environ[k] for k in ("PATH", "TMPDIR", "LANG") if k in os.environ}
        env.update(PYTHONPATH=str(source / "src"), PYTHONDONTWRITEBYTECODE="1",
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for argv in (["git", "init", "-q"], ["git", "config", "user.name", "Synthetic fixture"],
                     ["git", "config", "user.email", "fixture@example.invalid"]):
            subprocess.run(argv, cwd=workspace, env=env, check=True)
        raw = subprocess.check_output([sys.executable, str(Path(__file__).resolve()),
            "--_probe", str(workspace)], cwd=workspace, env=env, text=True)
    result = json.loads(raw)
    target = STUDY / "results.json"
    if args.check:
        assert result == json.loads(target.read_text()), "Integration receipt differs"
        print("Pinned local integration receipt reproduced; no human approval or downstream run.")
    elif args.write:
        target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print("Wrote " + str(target))
    else:
        print(raw, end="")


if __name__ == "__main__":
    main()
