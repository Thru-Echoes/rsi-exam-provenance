#!/usr/bin/env python3
"""The A/B's endpoints, as counts, from the job directories, the records, and the sealed retrospective.

Usage: ab_measures.py --jobs-root <RSI-Exam jobs dir> --prefix <job name prefix> --records <records dir>
       --rates haiku|sonnet|opus [--sealed <sealed cohort dir>] [--profiles <dir of the instrument arm's profiles>]

Prints markdown: (1) one row per trial started, from result.json, agent/trajectory.json, agent/claude-code.txt,
verifier/reward.json, the methods tree (experiment_log.md, decisions.jsonl, replication receipts,
.provenance/state.json) and the record at <records>/<rollout id>/capsule.json (verified again here against the job
directory); (2) for trials named <prefix><block>-<arm>, the paired table per block with the count of blocks
favouring each arm and an exact two-sided sign test as a descriptive number; (3) with --sealed, the gate's decisions
in the instrument arm read against the sealed seeds. Counts, never rates. Reads only; standard library only.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]


def load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


vc = load("verify_capsule_for_ab_measures", REPO / "profile" / "verify_capsule.py")
cost = load("cost_for_ab_measures", REPO / "runbook" / "cost.py")
TRIAL = re.compile(r"^(?P<prefix>.*?)(?P<block>[0-9]+)-(?P<arm>[IH])$")


def parse_stamp(text: str) -> datetime:
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def first_commands(trial: Path) -> dict[str, float]:
    """Minutes from the agent's first transcript event to the first init, evaluate, decide and finalize."""
    first: dict[str, float] = {}
    start: datetime | None = None
    pending: list[str] = []
    path = trial / "agent" / "claude-code.txt"
    if not path.is_file():
        return first
    for line in path.open(encoding="utf-8", errors="ignore"):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        stamp = record.get("timestamp")
        if stamp:
            now = parse_stamp(stamp)
            start = start or now
            for key in pending:
                first.setdefault(key, (now - start).total_seconds() / 60)
            pending = []
        if record.get("type") == "assistant":
            for item in (record.get("message") or {}).get("content") or []:
                if item.get("type") == "tool_use":
                    command = str((item.get("input") or {}).get("command") or "")
                    for key in ("init", "evaluate", "decide", "finalize"):
                        if f"provenance.py {key}" in command:
                            pending.append(key)
    return first


def decisions_of(methods: Path) -> list[dict[str, Any]]:
    path = methods / "decisions.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def confirmation_minutes(lines: list[dict[str, Any]]) -> list[float]:
    """Minutes from each provisional screening line to the confirmation line that resolved it."""
    opened: dict[str, datetime] = {}
    out: list[float] = []
    for line in lines:
        if line.get("replicates"):
            started = opened.pop(line["version_id"], None)
            if started is not None:
                out.append((parse_stamp(line["timestamp"]) - started).total_seconds() / 60)
        elif line.get("disposition") == "provisional":
            opened[line["version_id"]] = parse_stamp(line["timestamp"])
    return out


def trial_row(trial: Path, records: Path, rates: str, profiles: Path | None, sealed_dir: Path | None = None) -> dict[str, Any]:
    job = trial.parent.name
    rollout_id = f"{job}-{trial.name[-7:]}"
    row: dict[str, Any] = {"trial": job, "rollout_id": rollout_id, "arm": "", "block": ""}
    match = TRIAL.match(job)
    if match:
        row["arm"], row["block"] = match.group("arm"), int(match.group("block"))
    result = json.loads((trial / "result.json").read_text(encoding="utf-8")) if (trial / "result.json").is_file() else None
    if result is None:
        row.update({"agent_s": "", "stopped": "no result.json"})
        return row
    phase = result.get("agent_execution") or {}
    row["agent_s"] = (f"{(parse_stamp(phase['finished_at']) - parse_stamp(phase['started_at'])).total_seconds():.0f}"
                      if phase.get("started_at") and phase.get("finished_at") else "")
    exc = (result.get("exception_info") or {}).get("exception_type")
    row["stopped"] = {"AgentTimeoutError": "harness timeout", None: "agent finished"}.get(exc, str(exc))
    trajectory = trial / "agent" / "trajectory.json"
    row["steps"] = ((json.loads(trajectory.read_text(encoding="utf-8")).get("final_metrics") or {}).get("total_steps", "")
                    if trajectory.is_file() else "")
    methods = trial / "artifacts" / "app" / "methods"
    versions = sorted(p.name for p in (methods / "versions").iterdir() if p.is_dir()) if (methods / "versions").is_dir() else []
    row["snapshots"] = len(versions)
    capsule = records / rollout_id / "capsule.json"
    row["record"] = "no record"
    row["pairs"] = ""
    row["gate_kept"] = row["gate_reverted"] = row["overruled"] = ""
    if capsule.is_file():
        verdict = vc.verify_capsule(capsule, artifact_root=trial, require_complete=True)
        row["record"] = "verified" if verdict["ok"] else "integrity fail: " + ", ".join(verdict["errors"][:3])
        doc = json.loads(capsule.read_text(encoding="utf-8"))
        row["pairs"] = sum(1 for v in doc["versions"] if v.get("parent_ids") and v["status"] in ("kept", "reverted", "submitted"))
    log = (methods / "experiment_log.md").read_text(encoding="utf-8", errors="replace") if (methods / "experiment_log.md").is_file() else ""
    lines = decisions_of(methods)
    row["gate_lines"] = len(lines)
    row["gate_kept"] = sum(1 for l in lines if l.get("disposition") == "keep")
    row["gate_reverted"] = sum(1 for l in lines if l.get("disposition") == "revert")
    resolved = {l["version_id"] for l in lines if l.get("replicates")}
    row["provisional_open"] = sum(1 for l in lines if l.get("disposition") == "provisional" and l["version_id"] not in resolved)
    state_path = methods / ".provenance" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    row["blocked"] = "yes" if state.get("gate_blocked") else ""
    row["pending_at_stop"] = state.get("pending") or ""
    row["overruled"] = log.count("- agent proposed: kept (overruled)")
    row["refused_safety"] = log.count("the keep was refused for safety")
    row["refused_window"] = log.count("would run past the close-out mark")
    row["unmeasurable"] = log.count("the gate's runner refused the candidate")
    kept_versions = {l["version_id"] for l in lines if l.get("disposition") == "keep"}
    over = 0
    for version_id in kept_versions:
        report = methods / "results" / version_id / "visible_safety.json"
        if report.is_file():
            doc = json.loads(report.read_text(encoding="utf-8"))
            if float(doc.get("cpu_seconds_per_game") or 0) > 112.5 or float(doc.get("max_move_seconds") or 0) > 2.5:
                over += 1
    row["kept_over_margin"] = over      # a kept version over the plan's margins means the margin was weakened in the rollout
    receipts = sorted(methods.glob("results/*/replication/candidate_result.receipt.json"))
    sizes = [json.loads(r.read_text(encoding="utf-8")).get("games") for r in receipts]
    row["confirmations"] = f"{len(receipts)}" + (f" ({', '.join(str(s) for s in sizes)} seeds)" if sizes else "")
    minutes = confirmation_minutes(lines)
    row["confirmation_min"] = ", ".join(f"{m:.1f}" for m in minutes)
    firsts = first_commands(trial)
    for key in ("evaluate", "decide", "finalize"):
        row[f"first_{key}"] = f"{firsts[key]:.1f}" if key in firsts else ""
    row["finalize"] = "yes" if "finalize" in firsts else "no"
    row["profile_bound"] = ""
    if profiles is not None and lines:
        profile = profiles / f"{job}.json"
        if profile.is_file():
            digest = vc.file_digest(profile) if hasattr(vc, "file_digest") else None
            row["profile_bound"] = "yes" if digest and all(l.get("profile_sha256") == digest for l in lines) else "NO"
    reward = trial / "verifier" / "reward.json"
    doc = json.loads(reward.read_text(encoding="utf-8")) if reward.is_file() else {}
    row["reward"] = doc.get("reward")
    row["sealed_mean"] = doc.get("mean_score")
    row["reward_reason"] = "" if reward.is_file() else ("no result.json" if result is None else "no reward.json (the verifier did not run)")
    row["regret"] = ""
    if sealed_dir is not None:
        report = sealed_dir / rollout_id / "report.json"
        if report.is_file() and isinstance(row["reward"], (int, float)):
            snapshots = json.loads(report.read_text(encoding="utf-8")).get("snapshots", [])
            rewards = [s["reward"] for s in snapshots if s.get("measured") and isinstance(s.get("reward"), (int, float))]
            if rewards:
                # Final-selection regret: the best sealed reward among the measured snapshots (the starter and every
                # version) less the submission's reward; zero when the submission was the best available choice.
                row["regret"] = f"{max(rewards) - float(row['reward']):.4f}"
    try:
        usage = cost.get_usage(trial.parent)
        row["cost"] = f"{cost.get_cost(usage['tokens'], rates):.2f}" if usage["messages"] else ""
    except cost.CostError as exc:
        row["cost"] = f"unpriced: {exc}"
    return row


def sign_test(differences: list[float]) -> str:
    """Exact two-sided sign test over the non-zero differences, as a descriptive number."""
    nonzero = [d for d in differences if d != 0]
    n = len(nonzero)
    if n == 0:
        return "no non-zero differences"
    k = sum(1 for d in nonzero if d > 0)
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return f"{min(1.0, 2 * tail):.3f} (n={n})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--jobs-root", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--rates", choices=("haiku", "sonnet", "opus"), required=True)
    parser.add_argument("--sealed", type=Path, default=None)
    parser.add_argument("--profiles", type=Path, default=None)
    args = parser.parse_args(argv)
    trials = sorted(Path(p) for p in glob.glob(str(args.jobs_root / f"{args.prefix}*" / "game2048_policy_search__*")))
    rows = [trial_row(t, args.records, args.rates, args.profiles, args.sealed) for t in trials]
    cols = [("trial", "trial"), ("arm", "arm"), ("block", "block"), ("agent_s", "agent s"), ("stopped", "stopped"),
            ("steps", "steps"), ("snapshots", "snapshots"), ("record", "record"), ("pairs", "pairs"),
            ("gate_lines", "gate lines"), ("gate_kept", "gate kept"), ("gate_reverted", "gate reverted"),
            ("provisional_open", "provisional open"), ("blocked", "blocked"), ("pending_at_stop", "undecided at stop"),
            ("overruled", "keeps overruled"), ("refused_safety", "refused: safety"), ("refused_window", "refused: window"),
            ("unmeasurable", "unmeasurable"), ("kept_over_margin", "kept over margin"), ("confirmations", "confirmations"),
            ("confirmation_min", "confirmation min"),
            ("first_evaluate", "first evaluate min"), ("first_decide", "first decide min"), ("finalize", "finalize"),
            ("profile_bound", "profile bound"), ("reward", "sealed reward"), ("reward_reason", "no reward because"),
            ("sealed_mean", "sealed mean"), ("regret", "final-selection regret"), ("cost", "cost $")]
    print("| " + " | ".join(label for _, label in cols) + " |")
    print("|" + "---|" * len(cols))
    for row in rows:
        print("| " + " | ".join("" if row.get(key) is None else str(row.get(key, "")) for key, _ in cols) + " |")
    blocks: dict[int, dict[str, dict[str, Any]]] = {}
    for row in rows:
        if row["arm"]:
            blocks.setdefault(int(row["block"]), {})[row["arm"]] = row
    if blocks:
        print("\nPaired by block (sealed reward of the submission, instrument minus helper). A block with both rewards has a "
              "numeric difference; when exactly one trial has a reward from the verifier the other arm's failure is an "
              "outcome and the scorable arm is counted as favoured, with no numeric difference; a block with neither, or "
              "with a trial not started, is incomplete and enters no count.\n")
        print("| block | instrument trial | helper trial | reward I | reward H | I minus H | block outcome | regret I | regret H |")
        print("|---|---|---|---|---|---|---|---|---|")
        diffs: list[float] = []
        favour_i = favour_h = ties = incomplete = 0
        for block in sorted(blocks):
            pair = blocks[block]
            i, h = pair.get("I"), pair.get("H")
            ri = i.get("reward") if i else None
            rh = h.get("reward") if h else None
            numeric_i, numeric_h = isinstance(ri, (int, float)), isinstance(rh, (int, float))
            diff = (float(ri) - float(rh)) if isinstance(ri, (int, float)) and isinstance(rh, (int, float)) else None
            if diff is not None:
                diffs.append(diff)
                outcome = "favours I" if diff > 0 else ("favours H" if diff < 0 else "tie")
            elif i is None or h is None:
                outcome = "incomplete: a trial did not start"
            elif numeric_i != numeric_h:
                outcome = "favours I (helper trial has no reward)" if numeric_i else "favours H (instrument trial has no reward)"
            else:
                outcome = "incomplete: neither trial has a reward"
            favour_i += outcome.startswith("favours I")
            favour_h += outcome.startswith("favours H")
            ties += outcome == "tie"
            incomplete += outcome.startswith("incomplete")
            print(f"| {block} | {i['trial'] if i else 'not started'} | {h['trial'] if h else 'not started'} | "
                  f"{ri if ri is not None else ''} | {rh if rh is not None else ''} | {f'{diff:+.4f}' if diff is not None else ''} | "
                  f"{outcome} | {i.get('regret', '') if i else ''} | {h.get('regret', '') if h else ''} |")
        mean = f"{sum(diffs) / len(diffs):+.4f}" if diffs else "none"
        print(f"\nBlocks: {len(blocks)}; favouring the instrument: {favour_i}; favouring the helper: {favour_h}; ties: {ties}; "
              f"incomplete: {incomplete}. Over the {len(diffs)} blocks with two rewards: mean difference {mean}; exact two-sided "
              f"sign test p: {sign_test(diffs)} (zero differences dropped). With this many blocks the sign test cannot fall "
              "below 0.125 (four blocks) or 0.25 (three); the number describes the direction of these blocks and "
              "establishes nothing.")
    if args.sealed is not None:
        print("\nDecisions read against the sealed seeds, both arms (descriptive; the sealed suite is analysis data). In the "
              "instrument arm a decision is the gate's (its last line for the version); in the helper arm it is the agent's "
              "recorded status. The threshold is the minimum effect on the sealed scale, 2.5 percent of the parent's sealed "
              "mean: a keep whose sealed delta is below minus that, and a revert whose delta is above it, are the decisions "
              "the sealed seeds disagreed with; a delta within the threshold is indeterminate and counted apart.\n")
        print("| trial | arm | keeps | keeps the sealed seeds disagreed with | reverts | reverts the sealed seeds disagreed with | within the threshold | unmeasured |")
        print("|---|---|---|---|---|---|---|---|")
        for row in rows:
            report = args.sealed / row["rollout_id"] / "report.json"
            capsule = args.records / row["rollout_id"] / "capsule.json"
            if not report.is_file() or not capsule.is_file():
                print(f"| {row['trial']} | {row['arm']} | no sealed report or record | | | | |")
                continue
            sealed = {v["version_id"]: v for v in json.loads(report.read_text(encoding="utf-8")).get("versions", [])}
            counts = {"k": 0, "kn": 0, "r": 0, "rp": 0, "w": 0, "u": 0}
            for version in json.loads(capsule.read_text(encoding="utf-8"))["versions"]:
                if not version.get("parent_ids"):
                    continue
                decisions = version.get("decisions") or []
                if decisions:
                    kind = {"keep": "keep", "revert": "revert"}.get(decisions[-1]["disposition"])
                else:
                    kind = {"kept": "keep", "submitted": "keep", "reverted": "revert"}.get(version["status"])
                if kind is None:
                    continue
                entry = sealed.get(version["version_id"]) or {}
                delta = (entry.get("delta_vs_parent") or {}).get("mean")
                sealed_mean = entry.get("sealed_mean")
                if not isinstance(delta, (int, float)) or not isinstance(sealed_mean, (int, float)):
                    counts["u"] += 1
                    continue
                threshold = 0.025 * (sealed_mean - delta)          # the parent's sealed mean times the minimum-effect fraction
                counts["k" if kind == "keep" else "r"] += 1
                if abs(delta) <= threshold:
                    counts["w"] += 1
                elif kind == "keep" and delta < -threshold:
                    counts["kn"] += 1
                elif kind == "revert" and delta > threshold:
                    counts["rp"] += 1
            print(f"| {row['trial']} | {row['arm']} | {counts['k']} | {counts['kn']} | {counts['r']} | {counts['rp']} | {counts['w']} | {counts['u']} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
