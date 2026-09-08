#!/usr/bin/env python3
"""Score snapshots of a finished rollout on the task's published sealed seeds: a retrospective, not a gate.

RSI-Exam publishes each public task's sealed seeds with their per-seed anchors
(``tests/heldout_seeds.json``) and its grader (``tests/grade.py``), so after a rollout every snapshot
can be scored the way the submission was scored. This tool does that on the host, in the audit's
throwaway container, and reports per snapshot the per-seed scores, the mean score, and the reward
under the grader's own mapping (baseline to 0, frontier to 0.6, a soft cap approaching 1),
reproduced here line for line from the grader. With ``--capsule`` it also reports, per recorded
version, the recorded status and the paired sealed delta against the recorded parent, so the
agent's keeps and reverts can be read against the grader's truth.

Limits, stated in every report. A retrospective on the sealed suite turns that suite into analysis
data for this project; nothing here may be used to tune the gate's rule. The scores describe these
snapshots on these seeds and say nothing about official results. The evaluator is the environment's
in-process one under the runner's pooled CPU budget, not the grader's sandboxed process with its
per-move limit; the engine and seeds are identical, so scores agree for any policy that finishes
within the limits, and a policy that cannot is reported as unmeasured, never scored. A snapshot is
staged as its Python-only projection; omitted files are listed.

Inputs: ``--task-dir`` (``tests/heldout_seeds.json`` and ``environment/``), ``--profile`` (a replay
configuration: evaluator digests and the CPU budget), ``--workdir`` (fresh), ``--output``,
``--container IMAGE`` or ``--allow-host-execution`` (fixtures only), and the snapshots: ``--job-dir``
(every ``versions/<id>`` and ``main``, the latter reported as ``submission``) or ``--snapshot ID=PATH`` (repeatable); ``--capsule`` joins
the record's versions. ``--wall-seconds`` defaults to 1200: strong policies take about a minute a
game, and one that cannot finish sixteen games in twenty minutes is reported as unmeasured.

Output: JSON with schema ``rsi-exam-sealed-retrospective/v1``: ``sealed_suite`` (count, digest,
max_moves), ``inputs`` (profile digest, evaluator digests, container, gate source digests),
``snapshots`` (id, source, method-tree digest, measured, failure, mean_score, reward, per_seed),
``versions`` when a record was given (status, parent_ids, visible score, sealed mean, reward, the
paired mean delta and reward delta against the recorded parent), ``limits``, ``summary``.
Exit 0 when every snapshot was measured, 1 when the complete report carries unmeasured snapshots,
2 when the run could not proceed. Side effects: writes under ``--workdir`` and ``--output``; never
writes into ``--job-dir``. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shadow_replay as sr  # noqa: E402
from seeds import write_suite  # noqa: E402
from treedigest import TreeDigestError, file_sha256, method_tree_sha256  # noqa: E402

SCHEMA = "rsi-exam-sealed-retrospective/v1"
SEALED_FILE = Path("tests/heldout_seeds.json")
LIMITS = (
    "A retrospective on the sealed suite turns that suite into analysis data for this project; nothing here "
    "may be used to tune the gate's rule.",
    "The scores describe these snapshots on these seeds; they say nothing about official RSI-Exam results.",
    "The evaluator is the environment's in-process one under the runner's pooled CPU budget, not the grader's "
    "sandboxed process with its per-move limit; engine and seeds are identical, so scores agree for a policy "
    "that finishes within the limits, and one that cannot is reported as unmeasured, never scored.",
    "Snapshots are staged as their Python-only projection; a snapshot carrying other files is marked and its "
    "omitted files are listed.",
    "A sealed delta against a parent is the paired mean over the seeds both were measured on; it is a "
    "description, not a test.",
)


class RetroError(ValueError):
    """The run cannot proceed (exit 2)."""


def reward_of(metric: float, anchors: tuple[float, float]) -> float:
    """The grader's mapping: baseline to 0, frontier to 0.6, then a soft cap asymptotic to 1. Pure function."""
    baseline, frontier = anchors
    if not (0.0 < baseline < frontier):
        raise ValueError("anchors must satisfy 0 < baseline < frontier")
    if not math.isfinite(metric) or metric <= baseline:
        return 0.0
    if metric <= frontier:
        return 0.6 * math.log(metric / baseline) / math.log(frontier / baseline)
    log_progress = math.log(metric / frontier)
    tau = math.log(frontier / baseline) / math.log(4.0)
    return min(1.0, 0.6 + 0.4 * (1.0 - math.exp(-log_progress / tau)))


def read_sealed(task_dir: Path) -> tuple[list[int], dict[int, tuple[float, float]], int]:
    """The sealed seeds, their anchors, and max_moves from the task's published file."""
    path = task_dir / SEALED_FILE
    if not path.is_file():
        raise RetroError(f"task directory lacks {SEALED_FILE.as_posix()}")
    data = json.loads(path.read_text(encoding="utf-8"))
    anchors: dict[int, tuple[float, float]] = {}
    seeds: list[int] = []
    for item in data["seeds"]:
        seed = int(item["seed"]) if isinstance(item, dict) else int(item)
        seeds.append(seed)
        if isinstance(item, dict):
            anchors[seed] = (float(item["baseline"]), float(item["frontier"]))
    if len(set(seeds)) != len(seeds) or not seeds:
        raise RetroError("sealed seeds must be unique and non-empty")
    return seeds, anchors, int(data.get("max_moves", 10000))


def score(result_path: Path, anchors: dict[int, tuple[float, float]]) -> dict[str, Any]:
    """Per-seed scores and rewards from a result file, with the grader's rounding of the mean reward."""
    data = json.loads(result_path.read_text(encoding="utf-8"))
    per_seed = []
    for game in sorted(data["instances"], key=lambda g: int(g["seed"])):
        seed, metric = int(game["seed"]), float(game["score"])
        reward = reward_of(metric, anchors[seed]) if seed in anchors else None
        per_seed.append({"seed": seed, "score": metric, "reward": reward})
    scores = [g["score"] for g in per_seed]
    rewards = [g["reward"] for g in per_seed if g["reward"] is not None]
    return {"per_seed": per_seed, "mean_score": sum(scores) / len(scores),
            "reward": round(sum(rewards) / len(rewards), 8) if rewards and len(rewards) == len(per_seed) else None}


def paired_delta(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any] | None:
    """Mean of child minus parent over the seeds both were measured on. Pure function."""
    if not parent.get("measured") or not child.get("measured"):
        return None
    p = {g["seed"]: g["score"] for g in parent["per_seed"]}
    c = {g["seed"]: g["score"] for g in child["per_seed"]}
    common = sorted(set(p) & set(c))
    if not common:
        return None
    deltas = [c[s] - p[s] for s in common]
    return {"seeds": len(common), "mean": sum(deltas) / len(deltas), "min": min(deltas), "max": max(deltas),
            "positive": sum(1 for d in deltas if d > 0), "negative": sum(1 for d in deltas if d < 0)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--task-root", type=Path, default=None)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--job-dir", type=Path, default=None)
    parser.add_argument("--snapshot", action="append", default=[], metavar="ID=PATH")
    parser.add_argument("--capsule", type=Path, default=None)
    parser.add_argument("--container", default=None)
    parser.add_argument("--allow-host-execution", action="store_true")
    parser.add_argument("--wall-seconds", type=int, default=1200)
    args = parser.parse_args(argv)
    try:
        if args.container is None and not args.allow_host_execution:
            raise RetroError("pass --container IMAGE; --allow-host-execution is for the repository's fixtures only")
        if not args.profile.is_file():
            raise RetroError(f"profile not found: {args.profile}")
        if args.output.exists():
            raise RetroError(f"output already exists: {args.output}")
        task_root = args.task_root or (args.task_dir / "environment")
        methods = args.workdir / "methods"
        if methods.exists():
            raise RetroError(f"workdir {args.workdir} is not fresh; use a new one")
        seeds, anchors, max_moves = read_sealed(args.task_dir)
        snapshots: list[tuple[str, Path, str]] = []
        capsule: dict[str, Any] | None = None
        if args.job_dir is not None:
            versions = args.job_dir / "artifacts/app/methods/versions"
            if versions.is_dir():
                for child in sorted(versions.iterdir()):
                    if child.is_dir() and not child.is_symlink():
                        snapshots.append((child.name, child, f"artifacts/app/methods/versions/{child.name}"))
            snapshots.append(("submission", args.job_dir / "artifacts/app/methods/main", "artifacts/app/methods/main"))
        for spec in args.snapshot:
            sid, _, path = spec.partition("=")
            if not sid or not path:
                raise RetroError(f"--snapshot needs ID=PATH, got {spec!r}")
            snapshots.append((sid, Path(path), path if not Path(path).is_absolute() else Path(path).name))
        if not snapshots:
            raise RetroError("nothing to evaluate: pass --job-dir or --snapshot")
        if args.capsule is not None:
            capsule = json.loads(args.capsule.read_text(encoding="utf-8"))
        (methods / "versions").mkdir(parents=True)
        (methods / "results").mkdir()
        (methods / "gate").mkdir()
        profile_copy = methods / "gate" / "profile.json"
        shutil.copyfile(args.profile, profile_copy)
        suite_path = methods / "gate" / "sealed_suite.json"
        suite_sha = write_suite(suite_path, seeds, max_moves=max_moves)
        if args.container is not None:
            sr.check_container_mounts(args.container, HERE, task_root, methods)
        profile_doc = json.loads(args.profile.read_text(encoding="utf-8"))
        inputs = {"profile_sha256": file_sha256(args.profile), "evaluator": profile_doc.get("evaluator"),
                  "gate_sources": {p.name: file_sha256(p) for p in sorted(HERE.glob("*.py"))},
                  "container": {"image": args.container,
                                "digest": sr.container_digest(args.container) if args.container else None},
                  "execution_model": sr.EXECUTION_MODEL}
        rows: list[dict[str, Any]] = []
        for sid, source, locator in snapshots:
            row: dict[str, Any] = {"id": sid, "source": locator, "method_tree_sha256": None, "omitted_files": [],
                                   "projected": False, "measured": False, "failure": None, "mean_score": None,
                                   "reward": None, "per_seed": []}
            target = methods / "versions" / sid
            try:
                row["omitted_files"] = sr.stage_projection(source, target, allow_projection=True)
                row["projected"] = bool(row["omitted_files"])
                row["method_tree_sha256"] = method_tree_sha256(target)
            except (sr.NotReplayable, TreeDigestError) as exc:
                row["failure"] = f"not_stageable: {exc}".replace(str(source), locator)
                rows.append(row)
                continue
            # The runner refuses an output path with a main or versions component, so a snapshot id that
            # collides with a policy-tree name gets a prefixed results directory.
            results_name = sid if sid not in ("main", "versions") else f"snapshot-{sid}"
            output = methods / "results" / results_name / "sealed_result.json"
            output.parent.mkdir(parents=True)
            command = sr.runner_command(args.container, task_root=task_root, methods=methods, profile=profile_copy,
                                        policy_dir=target, suite=suite_path, output=output,
                                        wall_seconds=args.wall_seconds)
            proc = subprocess.run(command, capture_output=True, text=True)
            if proc.returncode == 0:
                row.update(score(output, anchors))
                row["measured"] = True
            elif proc.returncode in sr.RUNNER_FAILURES:
                row["failure"] = sr.RUNNER_FAILURES[proc.returncode]
            else:
                row["failure"] = f"runner exit {proc.returncode}: {proc.stderr.strip()[-300:]}".replace(str(args.workdir), "<workdir>")
            rows.append(row)
        by_id = {r["id"]: r for r in rows}
        versions_out: list[dict[str, Any]] | None = None
        if capsule is not None:
            versions_out = []
            for v in capsule["versions"]:
                me = by_id.get(v["version_id"])
                parent = by_id.get(v["parent_ids"][0]) if len(v["parent_ids"]) == 1 else None
                versions_out.append({
                    "version_id": v["version_id"], "status": v["status"], "parent_ids": v["parent_ids"],
                    "unsnapshotted_parent_ids": v.get("unsnapshotted_parent_ids", []),
                    "visible_score": (v.get("visible") or {}).get("score"),
                    "measured": bool(me and me["measured"]),
                    "sealed_mean": me["mean_score"] if me and me["measured"] else None,
                    "reward": me["reward"] if me and me["measured"] else None,
                    "delta_vs_parent": paired_delta(parent, me) if parent and me else None,
                    "reward_delta_vs_parent": (round(me["reward"] - parent["reward"], 8)
                                               if parent and me and parent["measured"] and me["measured"]
                                               and me["reward"] is not None and parent["reward"] is not None else None),
                })
        measured = sum(1 for r in rows if r["measured"])
        report = {"schema": SCHEMA, "job": (f"{args.job_dir.parent.name}/{args.job_dir.name}" if args.job_dir else None),
                  "sealed_suite": {"seeds": len(seeds), "sha256": suite_sha, "max_moves": max_moves,
                                   "anchors": bool(anchors)},
                  "inputs": inputs, "snapshots": rows, "versions": versions_out, "limits": list(LIMITS),
                  "summary": {"snapshots": len(rows), "measured": measured, "unmeasured": len(rows) - measured}}
    except RetroError as exc:
        print(f"sealed retrospective refused: {exc}", file=sys.stderr)
        return 2
    digest = sr.write_json(args.output, report)
    print(json.dumps({**report["summary"], "report_sha256": digest}, sort_keys=True))
    return 0 if report["summary"]["unmeasured"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
