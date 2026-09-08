#!/usr/bin/env python3
"""Run the decision gate over a finished rollout's artifacts, on the host, and compare: a shadow audit.

This is a shadow audit, not an in-rollout gate. The agent has finished; nothing here runs in its
environment, and every candidate's bytes were fixed before the host generated any replay input
(the profile, the replication key, the confirmation suites). Policy code written by the agent still
executes here. It runs in a throwaway container (``--container IMAGE``): no network, a read-only
root, all capabilities dropped, the operator's uid, the task root and the gate mounted read-only,
only the workdir writable, one fresh container per evaluation. That protects the operator's
machine from careless or buggy policy code. It does not separate the policy from the evaluator's
process: as in the task's own self-check, the policy is imported into the evaluator, so a policy
written to defeat the evaluator from inside is outside what this audit detects, and nothing here
claims otherwise. ``--allow-host-execution`` runs the policy as the operator's user and is for the
repository's fixtures only.

Inputs: ``--job-dir`` (a harbor trial directory, read only), ``--task-dir`` (task.toml and tests/,
which the record producer and verifier need), ``--task-root`` (the directory holding evaluate.py,
game2048.py and visible_seeds.json; default ``<task-dir>/environment``), ``--profile`` (a replay
configuration written by runbook/make_profile.py, kept outside the job directory), ``--workdir``
(scratch this script owns), ``--output`` (the report). Either ``--capsule`` (a record built from the
job directory; built into the workdir when omitted) or ``--pair PARENT_ID CANDIDATE_SRC
CANDIDATE_ID`` for one comparison the operator names, with CANDIDATE_SRC relative to the job
directory.

Pairs come from the record, which is verified first: the run refuses unless
profile/verify_capsule.py reports integrity pass against the job directory. Every version with
exactly one recorded parent is compared with that parent; a version whose only declared parent is
the unsnapshotted ``v0`` is compared with the task's own starter policy
(``<task-dir>/environment/methods/main``), labelled ``task_starter`` and counted separately, because
the program text defines v0 as the inherited main/. Anything else is listed as not replayable with
a reason. These are record-recoverable candidate-parent-status tuples, not the agent's action
history: attempts the agent never snapshotted or never logged are not here, and the report says so.

Each snapshot is staged as it is: regular ``.py`` files outside ``__pycache__``. A symlink refuses
the pair. A snapshot that also carries other regular files is not replayable by default, because
evaluating a Python-only copy of it is not evaluating the snapshot; ``--allow-projection`` stages the
Python-only projection anyway and marks the pair ``projected``. Either way every regular file left
behind is listed with its size and digest, and the staged tree's method-tree digest must equal the
one the record carries for that version. For each pair: restore the candidate into
``methods/main`` with gate/restore.py, evaluate both on the visible suite with
gate/evaluate_suite.py, screen with gate/decide.py, and on a provisional screening evaluate both on
the derived suite and confirm.

The ``outcome`` names why the gate ended where it did. ``screening_below``: the screening interval
lay entirely below zero. ``exploratory``: the confirmation plan exceeded the profile's cap and the
gate reverted without confirming; the screening verdict is kept beside it. ``confirmed_keep`` and
``confirmed_revert``: a confirmation ran. ``evaluation_failed``: the runner refused a policy for CPU
budget, an invalid game, or the wall clock; there is no gate disposition, ``agree`` is null, and the
configured failure policy (revert) is reported as metadata only. ``gate_refused``: the gate rejected
its inputs. ``infrastructure_failed``: the runner or the evaluator crashed. ``not_replayable``: the
snapshot could not be staged, carries non-Python files, or does not match the record. A failure on
one pair is recorded and the run continues; the report is checkpointed after every pair. Within one
run a snapshot is evaluated once per suite and the result reused. ``agree`` and ``disagree`` are
counted over comparable pairs only (a gate disposition and a recorded keep or revert), separately
for record-backed pairs and for task-starter reconstructions.

The workdir must be fresh: the run refuses one that already holds ``methods/`` or ``inputs.json``,
so nothing produced under another configuration is ever reused. Before the first evaluation an
inputs manifest is written to ``<workdir>/inputs.json``: the capsule's digest, the record's
method-tree digest per version, the profile digest, the evaluator and visible-suite digests, the
starter's digest, the digest of every ``gate/*.py`` file, the gate's git commit and whether the
checkout was clean, the container image and its resolved digest, the execution model, and the UTC
time. ``--inputs-only`` writes that manifest to ``--output`` and stops, so the operator can commit
and push it before any evaluation; ``--expect-inputs PATH`` makes the run refuse unless its own
manifest matches that file (creation time, the checkout's commit, and file locations aside; the
digest of every gate source file is what pins the code), and the report then carries the committed
manifest's exact bytes and digest, plus ``--anchor-commit`` when given. Every locator in a manifest
or report is relative (a job is ``<job name>/<trial name>``, a capsule its file name), and refusal
messages have the run's own paths replaced by tokens, so the files can be committed. This anchors the audit's inputs and outputs from the pushed commit onward; it does not
authenticate anything that happened inside the rollout.

Exit status: 0 when the report is complete and every pair reached a gate disposition; 1 when the
report is complete but at least one pair failed, was refused, or was not replayable (inspect the
report before using it); 2 when the run could not proceed. Side effects: writes under ``--workdir``
and writes ``--output``. Never writes into ``--job-dir``. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from treedigest import TreeDigestError, file_sha256, method_tree_sha256  # noqa: E402

SCHEMA = "rsi-exam-shadow-replay/v1"
RUNNER_FAILURES = {4: "cpu_budget_exhausted", 5: "invalid_game", 6: "wall_clock_exceeded"}
OUTCOMES = ("screening_below", "exploratory", "confirmed_keep", "confirmed_revert", "evaluation_failed",
            "gate_refused", "infrastructure_failed", "not_replayable")
FAILURE_OUTCOMES = ("evaluation_failed", "gate_refused", "infrastructure_failed", "not_replayable")
EXECUTION_MODEL = "same-process-evaluator"
LIMITS = (
    "The pairs are record-recoverable candidate-parent-status tuples, not the agent's action history.",
    "The policy is imported into the evaluator's process, as in the task's own self-check; the container "
    "protects the operator's machine, not the result, against a policy written to manipulate the evaluator.",
    "The disagreement counts are descriptive and directionless; nothing here says who was right.",
    "An interval describes the measured effect on the seeds evaluated; it is not the probability a decision "
    "was right and not a statement about the sealed reward.",
    "Anchoring starts at the commit that carries the inputs manifest; nothing inside the rollout is authenticated.",
    "The eight-seed screening interval is a screening heuristic on reused seeds, not a stable inference about the "
    "policy; the confirmation on fresh seeds is what decides.",
    "The replay configuration, including the replication key, is mounted where the policy can read it; after the "
    "rollout that key protects nothing, because every candidate was fixed before it existed.",
)
EXCLUDED_DIR = "__pycache__"
EXCLUDED_SUFFIXES = (".pyc", ".pyo")
STARTER_LOCATOR = "task:environment/methods/main"
SNAPSHOTS = "artifacts/app/methods/versions"
FAILURE_POLICY = "revert"
CONTAINER_MEMORY = "4g"
CONTAINER_PIDS = "256"


class ReplayError(ValueError):
    """The run cannot proceed (exit 2)."""


class NotReplayable(ReplayError):
    """A pair's snapshot cannot be staged or does not match the record; recorded, run continues."""


class GateRefused(ReplayError):
    """The gate rejected its inputs for one pair; recorded, run continues."""


class InfrastructureFailed(ReplayError):
    """The runner or the evaluator crashed for one pair; recorded, run continues."""


PAIR_OUTCOMES = {NotReplayable: "not_replayable", GateRefused: "gate_refused", InfrastructureFailed: "infrastructure_failed"}


@dataclass
class ReplayState:
    """Everything one run shares across pairs. Mutable by design: caches and the workdir."""
    job_dir: Path
    task_dir: Path
    task_root: Path
    methods: Path
    profile: Path
    direction: str
    container: str | None
    wall_seconds: int | None
    allow_projection: bool = False
    expected_digests: dict[str, str] = field(default_factory=dict)
    failed: dict[tuple[str, str], str] = field(default_factory=dict)
    omitted: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    digests: dict[str, str] = field(default_factory=dict)


def load_producer() -> Any:
    """Import profile/build_capsule.py by path; ``profile`` shadows a standard-library module."""
    spec = importlib.util.spec_from_file_location("build_capsule_for_replay", REPO / "profile" / "build_capsule.py")
    if spec is None or spec.loader is None:
        raise ReplayError("cannot import profile/build_capsule.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, document: dict[str, Any]) -> str:
    """Write JSON through a same-directory temporary file and rename; return the file's digest."""
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    return hashlib.sha256(payload).hexdigest()


def stage_projection(source: Path, target: Path, allow_projection: bool = False) -> list[dict[str, Any]]:
    """Stage a snapshot's Python files: regular ``.py`` files outside ``__pycache__``.

    Returns the regular files left behind, each with its POSIX relpath, size and digest. Raises
    NotReplayable on a missing source, a symlink anywhere in the tree, a tree with no Python file,
    or, unless ``allow_projection`` is set, a tree that also carries other regular files (the
    inventory is in the message). Side effect: creates ``target``.
    """
    if source.is_symlink() or not source.is_dir():
        raise NotReplayable(f"snapshot not found: {source.name}")
    omitted: list[dict[str, Any]] = []
    copied = 0
    for child in sorted(source.rglob("*")):
        rel = child.relative_to(source)
        if EXCLUDED_DIR in rel.parts or child.suffix in EXCLUDED_SUFFIXES:
            continue
        if child.is_symlink():
            raise NotReplayable(f"snapshot contains a symlink: {source.name}/{rel.as_posix()}")
        if child.is_dir():
            continue
        if not child.is_file():
            shutil.rmtree(target, ignore_errors=True)
            raise NotReplayable(f"snapshot contains a special file: {source.name}/{rel.as_posix()}")
        if child.suffix != ".py":
            omitted.append({"path": rel.as_posix(), "bytes": child.stat().st_size, "sha256": file_sha256(child)})
            continue
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(child, destination)
        copied += 1
    if not copied:
        shutil.rmtree(target, ignore_errors=True)
        raise NotReplayable(f"snapshot has no Python files: {source.name}")
    if omitted and not allow_projection:
        shutil.rmtree(target, ignore_errors=True)
        names = ", ".join(entry["path"] for entry in omitted)
        raise NotReplayable(f"non_python_files_in_snapshot:{source.name}: {names}")
    return omitted


def inventory_non_python(source: Path) -> list[dict[str, Any]]:
    """The regular non-Python files of a snapshot, for the record of a pair that was refused."""
    if not source.is_dir():
        return []
    return [{"path": child.relative_to(source).as_posix(), "bytes": child.stat().st_size, "sha256": file_sha256(child)}
            for child in sorted(source.rglob("*"))
            if child.is_file() and not child.is_symlink() and child.suffix != ".py"
            and EXCLUDED_DIR not in child.relative_to(source).parts and child.suffix not in EXCLUDED_SUFFIXES]


def make_pair(parent_id: str, parent_source: str, candidate_id: str, candidate_source: str,
              recorded_status: str | None) -> dict[str, Any]:
    kind = "task_starter" if parent_source.startswith("task:") else "snapshot"
    return {"parent_id": parent_id, "parent_source": parent_source, "parent_source_kind": kind,
            "candidate_id": candidate_id, "candidate_source": candidate_source, "recorded_status": recorded_status}


def get_pairs_from_capsule(capsule: dict[str, Any], task_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The candidate-parent pairs a record supports, and the coverage block that says what it does not.

    A version with exactly one recorded parent pairs with that parent's snapshot. A version whose
    only declared parent is the unsnapshotted ``v0`` pairs with the task's starter policy when the
    task directory carries one. Every other version is listed under ``not_replayable`` with a
    reason. Pure function.
    """
    starter = task_dir / "environment/methods/main"
    pairs: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for version in capsule["versions"]:
        vid = version["version_id"]
        parents = version["parent_ids"]
        unsnapshotted = version.get("unsnapshotted_parent_ids", [])
        if len(parents) == 1:
            pairs.append(make_pair(parents[0], f"{SNAPSHOTS}/{parents[0]}", vid, f"{SNAPSHOTS}/{vid}", version["status"]))
        elif not parents and unsnapshotted == ["v0"] and (starter / "policy.py").is_file():
            pairs.append(make_pair("v0", STARTER_LOCATOR, vid, f"{SNAPSHOTS}/{vid}", version["status"]))
        elif not parents and not unsnapshotted:
            skipped.append({"candidate_id": vid, "reason": "lineage_root"})
        elif not parents:
            skipped.append({"candidate_id": vid, "reason": "unsnapshotted_parent:" + ",".join(unsnapshotted)})
        else:
            skipped.append({"candidate_id": vid, "reason": "multiple_parents"})
    classifiable = sum(1 for v in capsule["versions"] if v["status"] in ("kept", "submitted", "reverted"))
    coverage = {"versions_in_record": len(capsule["versions"]), "versions_with_recorded_action": classifiable,
                "pairs_planned": len(pairs),
                "record_backed": sum(1 for p in pairs if p["parent_source_kind"] == "snapshot"),
                "task_starter_reconstruction": sum(1 for p in pairs if p["parent_source_kind"] == "task_starter"),
                "not_replayable": skipped}
    return pairs, coverage


def redact(state: ReplayState, text: str) -> str:
    """Replace the run's machine-specific path prefixes in a message with stable tokens."""
    for prefix, token in ((str(state.methods.parent), "<workdir>"), (str(state.job_dir), "<job>"),
                          (str(state.task_root), "<task>"), (str(state.task_dir), "<task-dir>"), (str(REPO), "<repo>")):
        text = text.replace(prefix, token)
    return text


def resolve_source(state: ReplayState, locator: str) -> Path:
    """A pair source is a job-relative locator, or ``task:<path>`` relative to the task directory."""
    if locator.startswith("task:"):
        return state.task_dir / locator[len("task:"):]
    return state.job_dir / locator


def runner_command(container: str | None, *, task_root: Path, methods: Path, profile: Path, policy_dir: Path,
                   suite: Path, output: Path, wall_seconds: int | None) -> list[str]:
    """The argv of one evaluation: the runner on the host, or the runner inside a throwaway container.

    In the container the task root is ``/task`` read-only, the gate is ``/gate`` read-only, and the
    workdir's ``methods`` is ``/methods``; every path the runner receives must lie under one of the
    mounted trees. No network, read-only root, all capabilities dropped, no new privileges, a pid
    and memory limit, the operator's uid and gid, and an environment of exactly the variables the
    runner needs. Pure function.
    """
    if container is None:
        command = [sys.executable, str(HERE / "evaluate_suite.py"), "--profile", str(profile), "--task-root",
                   str(task_root), "--policy-dir", str(policy_dir), "--suite", str(suite), "--output", str(output)]
    else:
        def inside(path: Path) -> str:
            for host, guest in ((methods.resolve(), "/methods"), (task_root.resolve(), "/task")):
                resolved = path.resolve()
                if resolved == host:
                    return guest
                if host in resolved.parents:
                    return guest + "/" + resolved.relative_to(host).as_posix()
            raise ReplayError(f"path lies under neither the workdir nor the task root: {path}")
        command = ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--pids-limit", CONTAINER_PIDS, "--memory", CONTAINER_MEMORY,
                   "--user", f"{os.getuid()}:{os.getgid()}", "--tmpfs", "/tmp:rw,size=256m",
                   "-e", "PYTHONHASHSEED=0", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "LC_ALL=C", "-e", "TZ=UTC",
                   "-v", f"{task_root.resolve()}:/task:ro", "-v", f"{HERE}:/gate:ro",
                   "-v", f"{methods.resolve()}:/methods", container, "python3", "/gate/evaluate_suite.py",
                   "--profile", inside(profile), "--task-root", "/task", "--policy-dir", inside(policy_dir),
                   "--suite", inside(suite), "--output", inside(output)]
    if wall_seconds is not None:
        command += ["--wall-seconds", str(wall_seconds)]
    return command


def container_digest(image: str) -> str:
    """The resolved digest of a locally present image; refuses when the image has not been pulled."""
    proc = subprocess.run(["docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}", image],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise ReplayError(f"container image {image} is not available locally; docker pull it first")
    return proc.stdout.strip()


def check_container_mounts(image: str, *paths: Path) -> None:
    """Refuse unless every directory the run will mount is visible inside a container.

    A Docker daemon in a virtual machine (colima, Docker Desktop) shares only some host directories
    with the VM; a bind mount from anywhere else appears empty inside the container and the runner
    fails on every pair. The check mounts each directory read-only and lists it.
    """
    for path in paths:
        proc = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{path.resolve()}:/probe:ro", image,
                               "python3", "-c", "import os, sys; sys.exit(0 if os.listdir('/probe') else 3)"],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise ReplayError(f"{path} is not visible inside a container (empty or missing mount); on colima and "
                              "Docker Desktop every path handed to --container must lie under a shared directory, "
                              "normally your home directory")


def evaluate(state: ReplayState, vid: str, suite: Path, output: Path) -> str | None:
    """Evaluate one staged snapshot on one suite unless its result exists. Returns None, or the failure name.

    A failure the runner reports as CPU budget, invalid game, or wall clock is remembered for the
    version and suite and never retried in this run. Any other non-zero exit raises
    InfrastructureFailed. Side effects: writes the result and receipt under the workdir.
    """
    key = (vid, str(suite))
    if key in state.failed:
        return state.failed[key]
    receipt = output.with_name(output.name[:-5] + ".receipt.json")
    if output.exists() and receipt.exists():
        return None
    output.parent.mkdir(parents=True, exist_ok=True)
    command = runner_command(state.container, task_root=state.task_root, methods=state.methods, profile=state.profile,
                             policy_dir=state.methods / "versions" / vid, suite=suite, output=output,
                             wall_seconds=state.wall_seconds)
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode == 0:
        return None
    if proc.returncode in RUNNER_FAILURES:
        state.failed[key] = RUNNER_FAILURES[proc.returncode]
        return state.failed[key]
    raise InfrastructureFailed(redact(state, f"runner exit {proc.returncode} for {vid}: {proc.stderr.strip()[-500:]}"))


def decide(state: ReplayState, version: str, parent: str, replicates: str | None) -> dict[str, Any]:
    """One gate call; the appended line. Raises GateRefused with the gate's own words when it refuses."""
    args = ["--methods", str(state.methods), "--profile", str(state.profile), "--version", version, "--parent", parent]
    if replicates:
        args += ["--replicates", replicates]
    proc = subprocess.run([sys.executable, str(HERE / "decide.py"), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise GateRefused(redact(state, f"gate refused {version} against {parent}: {proc.stderr.strip()[-500:]}"))
    return json.loads(proc.stdout.strip().splitlines()[-1])


def line_summary(line: dict[str, Any]) -> dict[str, Any]:
    """The fields of a decision line the report carries."""
    return {key: line.get(key) for key in ("line", "disposition", "verdict", "estimate", "interval", "min_effect",
                                            "sample_size", "look_index", "sizing")}


def load_scores(path: Path) -> dict[int, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(game["seed"]): float(game["score"]) for game in data["instances"]}


def screening_deltas(parent_result: Path, candidate_result: Path, direction: str) -> dict[str, Any]:
    """The eight paired deltas behind a screening, with their tail summary. Pure apart from reads."""
    parent, candidate = load_scores(parent_result), load_scores(candidate_result)
    sign = 1.0 if direction == "higher" else -1.0
    seeds = sorted(set(parent) & set(candidate))
    deltas = [sign * (candidate[s] - parent[s]) for s in seeds]
    return {"seeds": seeds, "deltas": deltas, "min": min(deltas), "median": statistics.median(deltas),
            "max": max(deltas)}


def cpu_seconds_of(result: Path) -> float:
    receipt = result.with_name(result.name[:-5] + ".receipt.json")
    try:
        return float(json.loads(receipt.read_text(encoding="utf-8"))["cpu_seconds"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return 0.0


def empty_gate() -> dict[str, Any]:
    return {"outcome": None, "disposition": None, "screening": None, "screening_deltas": None, "confirmation": None,
            "evaluation_failed": None, "failure_policy_action": None, "refusal": None}


def stage_pair(state: ReplayState, pair: dict[str, Any]) -> None:
    """Stage both snapshots of a pair (once per version) and check each against the record's digest."""
    versions = state.methods / "versions"
    for vid, locator in ((pair["parent_id"], pair["parent_source"]), (pair["candidate_id"], pair["candidate_source"])):
        target = versions / vid
        if target.exists():
            continue
        source = resolve_source(state, locator)
        try:
            state.omitted[vid] = stage_projection(source, target, state.allow_projection)
        except NotReplayable:
            state.omitted[vid] = inventory_non_python(source)
            raise
        try:
            digest = method_tree_sha256(target)
        except TreeDigestError as exc:
            raise NotReplayable(str(exc)) from exc
        expected = state.expected_digests.get(vid)
        if expected is not None and digest != expected:
            shutil.rmtree(target)
            raise NotReplayable(f"snapshot_digest_mismatch:{vid}: staged {digest} recorded {expected}")
        state.digests[vid] = digest


def audit_pair(state: ReplayState, parent: str, candidate: str, gate: dict[str, Any], spent: dict[str, float]) -> None:
    """Evaluate, screen and confirm one staged pair, filling ``gate`` stage by stage and ``spent["cpu"]``.

    Raises GateRefused or InfrastructureFailed after filling whatever stages completed, so the
    caller keeps them.
    """
    visible = state.task_root / "visible_seeds.json"
    results = state.methods / "results"
    failed: dict[str, str] = {}
    for vid in (parent, candidate):
        out = results / vid / "visible_result.json"
        reason = evaluate(state, vid, visible, out)
        if reason:
            failed[vid] = reason
        else:
            spent["cpu"] += cpu_seconds_of(out)
    if failed:
        gate.update({"outcome": "evaluation_failed", "evaluation_failed": failed, "failure_policy_action": FAILURE_POLICY})
        return
    gate["screening_deltas"] = screening_deltas(results / parent / "visible_result.json",
                                                results / candidate / "visible_result.json", state.direction)
    screening = decide(state, candidate, parent, None)
    gate["screening"] = line_summary(screening)
    if screening["disposition"] == "revert":
        gate["disposition"] = "revert"
        if screening["verdict"] == "below":
            gate["outcome"] = "screening_below"
        elif (screening.get("sizing") or {}).get("exploratory"):
            gate["outcome"] = "exploratory"
        else:
            raise GateRefused(f"screening reverted {candidate} with verdict {screening['verdict']!r} and no "
                              "exploratory plan; the gate's rule has changed under this replay")
        return
    if screening["disposition"] != "provisional":
        raise GateRefused(f"unexpected screening disposition {screening['disposition']!r} for {candidate}")
    suite = state.methods / screening["suite"]["locator"]
    base = results / candidate / "replication"
    for vid, name in ((parent, "parent_result.json"), (candidate, "candidate_result.json")):
        reason = evaluate(state, vid, suite, base / name)
        if reason:
            failed[vid] = reason
        else:
            spent["cpu"] += cpu_seconds_of(base / name)
    if failed:
        gate.update({"outcome": "evaluation_failed", "evaluation_failed": failed, "failure_policy_action": FAILURE_POLICY})
        return
    confirmation = decide(state, candidate, parent, candidate)
    gate["confirmation"] = line_summary(confirmation)
    gate["disposition"] = confirmation["disposition"]
    gate["outcome"] = "confirmed_keep" if confirmation["disposition"] == "keep" else "confirmed_revert"


def replay_pair(state: ReplayState, pair: dict[str, Any]) -> dict[str, Any]:
    """One candidate against its parent, end to end. Raises a ReplayError subclass when a step refuses."""
    parent, candidate = pair["parent_id"], pair["candidate_id"]
    stage_pair(state, pair)
    restored = subprocess.run([sys.executable, str(HERE / "restore.py"), "--methods", str(state.methods),
                               "--version", candidate], capture_output=True, text=True)
    if restored.returncode != 0:
        raise NotReplayable(redact(state, f"restore refused {candidate}: {restored.stderr.strip()[-500:]}"))

    gate = empty_gate()
    spent = {"cpu": 0.0}
    try:
        audit_pair(state, parent, candidate, gate, spent)
    except (GateRefused, InfrastructureFailed) as exc:
        # A refusal after some stages completed keeps what completed: the screening line, its deltas
        # and the CPU already spent stay in the row; only the terminal outcome names the refusal.
        gate.update({"outcome": PAIR_OUTCOMES[type(exc)], "disposition": None, "refusal": str(exc)})
    recorded = pair["recorded_status"]
    agent_kept = True if recorded in ("kept", "submitted") else False if recorded == "reverted" else None
    agree = None if agent_kept is None or gate["disposition"] is None else (gate["disposition"] == "keep") == agent_kept
    omitted = {parent: state.omitted.get(parent, []), candidate: state.omitted.get(candidate, [])}
    return {**pair, "parent_method_tree_sha256": state.digests.get(parent),
            "candidate_method_tree_sha256": state.digests.get(candidate), "omitted_files": omitted,
            "projected": any(omitted.values()), "gate": gate, "agree": agree, "cpu_seconds": round(spent["cpu"], 1)}


def refused_pair(state: ReplayState, pair: dict[str, Any], outcome: str, reason: str) -> dict[str, Any]:
    gate = empty_gate()
    gate.update({"outcome": outcome, "refusal": reason})
    omitted = {vid: state.omitted.get(vid, []) for vid in (pair["parent_id"], pair["candidate_id"])}
    return {**pair, "parent_method_tree_sha256": state.digests.get(pair["parent_id"]),
            "candidate_method_tree_sha256": state.digests.get(pair["candidate_id"]), "omitted_files": omitted,
            "projected": False, "gate": gate, "agree": None, "cpu_seconds": 0.0}


def git_state() -> tuple[str | None, bool | None]:
    """The gate's git commit and whether gate/ and profile/ are clean, when the gate lives in a checkout."""
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode != 0 or not head.stdout.strip():
        return None, None
    status = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", "gate", "profile"],
                            capture_output=True, text=True)
    return head.stdout.strip(), (status.returncode == 0 and not status.stdout.strip())


def verify_record(capsule: Path, job_dir: Path) -> dict[str, Any]:
    """Run the offline verifier against the job directory; refuse unless integrity passes."""
    proc = subprocess.run([sys.executable, str(REPO / "profile" / "verify_capsule.py"), str(capsule),
                           "--artifact-root", str(job_dir), "--json"], capture_output=True, text=True)
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ReplayError(f"verifier produced no JSON for {capsule}: {proc.stderr.strip()[-300:]}") from exc
    if result.get("integrity") != "pass":
        raise ReplayError(f"record failed verification ({result.get('integrity')}): {result.get('errors')}")
    return result


def agreement(pairs: list[dict[str, Any]]) -> dict[str, int]:
    """Pairs, comparable pairs (a gate disposition and a recorded keep or revert), agree, disagree."""
    comparable = [p for p in pairs if p["agree"] is not None]
    return {"pairs": len(pairs), "comparable": len(comparable), "agree": sum(1 for p in comparable if p["agree"]),
            "disagree": sum(1 for p in comparable if not p["agree"])}


def summarize(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    confirmed = sum(1 for p in pairs if p["gate"]["outcome"] in ("confirmed_keep", "confirmed_revert"))
    return {"pairs": len(pairs), "with_disposition": sum(1 for p in pairs if p["gate"]["disposition"] is not None),
            "audit_kind": "confirmation-and-screening" if confirmed else "screening-and-feasibility",
            "record_backed": agreement([p for p in pairs if p["parent_source_kind"] == "snapshot"]),
            "task_starter": agreement([p for p in pairs if p["parent_source_kind"] == "task_starter"]),
            "undetermined": sum(1 for p in pairs if p["agree"] is None),
            "confirmed": confirmed,
            "projected": sum(1 for p in pairs if p.get("projected")),
            "outcomes": {name: sum(1 for p in pairs if p["gate"]["outcome"] == name) for name in OUTCOMES},
            "failure_policy": {"action": FAILURE_POLICY,
                               "evaluation_failed": sum(1 for p in pairs if p["gate"]["outcome"] == "evaluation_failed")},
            "cpu_seconds": round(sum(p["cpu_seconds"] for p in pairs), 1)}


MANIFEST_VOLATILE = ("created_utc", "gate_commit", "gate_tree_clean", "anchor_commit")


def manifest_key(inputs: dict[str, Any]) -> dict[str, Any]:
    """The part of an inputs manifest that must agree between a committed manifest and a run.

    The commit and the checkout's cleanliness are recorded but not compared: committing the manifest
    itself moves the commit, and the digest of every gate source file already pins the code exactly.
    """
    key = {k: v for k, v in inputs.items() if k not in MANIFEST_VOLATILE}
    key["capsule"] = {k: v for k, v in inputs["capsule"].items() if k != "locator"}
    return key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--job-dir", required=True, type=Path)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--task-root", type=Path, default=None)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--capsule", type=Path, default=None)
    parser.add_argument("--pair", nargs=3, metavar=("PARENT_ID", "CANDIDATE_SRC", "CANDIDATE_ID"), default=None)
    parser.add_argument("--container", default=None, help="image for the throwaway evaluation containers")
    parser.add_argument("--allow-host-execution", action="store_true",
                        help="run policy code as the operator's user (fixtures only)")
    parser.add_argument("--allow-projection", action="store_true",
                        help="stage the Python-only projection of a snapshot that carries other files")
    parser.add_argument("--inputs-only", action="store_true",
                        help="write the inputs manifest to --output and stop before any evaluation")
    parser.add_argument("--expect-inputs", type=Path, default=None,
                        help="a committed inputs manifest this run must match")
    parser.add_argument("--anchor-commit", default=None,
                        help="the pushed commit that carries the inputs manifest, recorded in the report")
    parser.add_argument("--wall-seconds", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        if args.container is None and not args.allow_host_execution:
            raise ReplayError("pass --container IMAGE; --allow-host-execution is for the repository's fixtures only")
        if not args.profile.is_file():
            raise ReplayError(f"profile not found: {args.profile}")
        if args.output.exists():
            raise ReplayError(f"output already exists: {args.output}")
        task_root = args.task_root or (args.task_dir / "environment")
        if not (task_root / "visible_seeds.json").is_file():
            raise ReplayError(f"task environment lacks visible_seeds.json: {task_root}")
        profile_doc = json.loads(args.profile.read_text(encoding="utf-8"))
        methods = args.workdir / "methods"
        if methods.exists() or (args.workdir / "inputs.json").exists():
            raise ReplayError(f"workdir {args.workdir} is not fresh; use a new one so nothing is reused across runs")
        (methods / "versions").mkdir(parents=True, exist_ok=True)
        (methods / "results").mkdir(exist_ok=True)
        (methods / "gate").mkdir(exist_ok=True)
        profile_copy = methods / "gate" / "profile.json"
        if not profile_copy.exists():
            shutil.copyfile(args.profile, profile_copy)
        expected: dict[str, str] = {}
        capsule_input: dict[str, Any] = {"locator": None, "sha256": None, "built_here": False}
        if args.pair:
            mode = "pair"
            pairs = [make_pair(args.pair[0], f"{SNAPSHOTS}/{args.pair[0]}", args.pair[2], args.pair[1], None)]
            coverage: dict[str, Any] = {"versions_in_record": None, "versions_with_recorded_action": None,
                                        "pairs_planned": 1, "record_backed": 1, "task_starter_reconstruction": 0,
                                        "not_replayable": []}
        else:
            mode = "capsule"
            capsule_path = args.capsule
            if capsule_path is None:
                capsule_path = args.workdir / "capsule.json"
                if not capsule_path.exists():
                    built = load_producer().build_capsule(args.job_dir, args.task_dir, "shadow", args.job_dir.name,
                                                          "shadow", "shadow", [])
                    write_json(capsule_path, built)
                capsule_input["built_here"] = True
            verify_record(capsule_path, args.job_dir)
            capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
            capsule_input.update({"locator": capsule_path.name, "sha256": file_sha256(capsule_path)})
            expected = {v["version_id"]: v["artifact"]["method_tree_sha256"] for v in capsule["versions"]}
            pairs, coverage = get_pairs_from_capsule(capsule, args.task_dir)
        if args.container is not None:
            check_container_mounts(args.container, HERE, task_root, methods)
        state = ReplayState(job_dir=args.job_dir, task_dir=args.task_dir, task_root=task_root, methods=methods,
                            profile=profile_copy, direction=str(profile_doc.get("direction", "higher")),
                            container=args.container, wall_seconds=args.wall_seconds,
                            allow_projection=args.allow_projection, expected_digests=expected)
        starter = args.task_dir / "environment/methods/main"
        try:
            starter_digest = method_tree_sha256(starter) if starter.is_dir() else None
        except TreeDigestError:
            starter_digest = None
        commit, clean = git_state()
        inputs = {"capsule": capsule_input, "expected_snapshot_digests": expected,
                  "task_starter_method_tree_sha256": starter_digest, "profile_sha256": file_sha256(args.profile),
                  "evaluator": profile_doc.get("evaluator"), "visible_suite_sha256": profile_doc.get("visible_suite_sha256"),
                  "gate_sources": {p.name: file_sha256(p) for p in sorted(HERE.glob("*.py"))},
                  "gate_commit": commit, "gate_tree_clean": clean,
                  "container": {"image": args.container,
                                "digest": container_digest(args.container) if args.container else None},
                  "execution_model": EXECUTION_MODEL, "allow_projection": args.allow_projection,
                  "anchor_commit": args.anchor_commit, "created_utc": datetime.now(UTC).isoformat()}
        started = inputs["created_utc"]
        if args.expect_inputs is not None:
            committed_bytes = args.expect_inputs.read_bytes()
            expected_manifest = json.loads(committed_bytes)
            mine, theirs = manifest_key(inputs), manifest_key(expected_manifest)
            differing = sorted(k for k in set(mine) | set(theirs) if mine.get(k) != theirs.get(k))
            if differing:
                raise ReplayError(f"inputs do not match {args.expect_inputs.name}: {', '.join(differing)}")
            # The committed manifest is the anchor: the report carries its exact bytes and digest.
            inputs = expected_manifest
            if args.anchor_commit is not None:
                inputs["anchor_commit"] = args.anchor_commit
        if args.inputs_only:
            shutil.rmtree(args.workdir / "methods")
            digest = write_json(args.output, inputs)
            print(json.dumps({"inputs_manifest_sha256": digest, "output": args.output.name}))
            return 0
        manifest_sha = write_json(args.workdir / "inputs.json", inputs)
        job_locator = f"{args.job_dir.parent.name}/{args.job_dir.name}"

        def report(replayed: list[dict[str, Any]], complete: bool) -> dict[str, Any]:
            return {"schema": SCHEMA, "mode": mode, "complete": complete, "rollout_id": args.job_dir.name,
                    "job": job_locator, "run_started_utc": started, "profile_sha256": inputs["profile_sha256"],
                    "inputs_manifest_sha256": manifest_sha, "inputs": inputs, "limits": list(LIMITS),
                    "coverage": coverage, "pairs": replayed, "summary": summarize(replayed)}

        replayed: list[dict[str, Any]] = []
        write_json(args.output, report(replayed, False))
        for pair in pairs:
            try:
                replayed.append(replay_pair(state, pair))
            except ReplayError as exc:
                outcome = PAIR_OUTCOMES.get(type(exc))
                if outcome is None:
                    raise
                replayed.append(refused_pair(state, pair, outcome, str(exc)))
            write_json(args.output, report(replayed, False))
        final = report(replayed, True)
    except ReplayError as exc:
        print(f"shadow replay refused: {exc}", file=sys.stderr)
        return 2
    final["pairs"] = [dict(p, gate=dict(p["gate"], refusal=redact(state, p["gate"]["refusal"]) if p["gate"]["refusal"] else None))
                      for p in final["pairs"]]
    digest = write_json(args.output, final)
    print(json.dumps({**final["summary"], "report_sha256": digest}, sort_keys=True))
    return 1 if any(p["gate"]["outcome"] in FAILURE_OUTCOMES for p in replayed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
