#!/usr/bin/env python3
"""The shadow audit's two tables over one cohort's committed reports. Usage: ab_tables.py <cohort dir> "<title>".

Reads every ``<cohort>/*/report.json`` and ``<cohort>/exits.txt``; prints markdown. Reads only; standard library only.
"""
import glob
import json
import os
import statistics
import sys

cohort, title = sys.argv[1], sys.argv[2]
exits = dict(line.split(" exit=") for line in open(f"{cohort}/exits.txt").read().split("\n") if " exit=" in line)
print(f"# {title}\n")
print("Descriptive and directionless. Pairs are what each record recovers, not the agent's action history. "
      "An exploratory outcome means the planning rule the replay configuration names asked for more confirmation "
      "seeds than its cap allows. Comparable pairs have both a gate disposition and a recorded keep or revert.\n")
cols = ["rollout", "versions", "pairs", "with disposition", "record-backed comparable", "agree", "disagree",
        "task-starter pairs", "confirmed", "exploratory", "screening below", "evaluation failed", "not replayable",
        "other failures", "median planned", "cpu s", "audit kind", "exit"]
print("| " + " | ".join(cols) + " |")
print("|" + "---|" * len(cols))
for path in sorted(glob.glob(f"{cohort}/*/report.json")):
    r = json.load(open(path))
    s = r["summary"]
    o = s["outcomes"]
    rb = s["record_backed"]
    rid = os.path.basename(os.path.dirname(path))
    planned = [p["gate"]["screening"]["sizing"]["planned"] for p in r["pairs"]
               if p["gate"].get("screening") and p["gate"]["screening"].get("sizing")]
    row = [rid, "" if r["coverage"]["versions_in_record"] is None else str(r["coverage"]["versions_in_record"]),
           str(s["pairs"]), str(s["with_disposition"]), str(rb["comparable"]), str(rb["agree"]), str(rb["disagree"]),
           str(s["task_starter"]["pairs"]), str(s["confirmed"]), str(o["exploratory"]), str(o["screening_below"]),
           str(o["evaluation_failed"]), str(o["not_replayable"]), str(o["gate_refused"] + o["infrastructure_failed"]),
           str(int(statistics.median(planned))) if planned else "", f"{s['cpu_seconds']:.0f}", s["audit_kind"],
           exits.get(rid, "?").strip()]
    print("| " + " | ".join(row) + " |")
print("\nPer-pair screening lines:\n")
print("| rollout | parent | candidate | recorded | outcome | estimate | interval | min_effect | screening sd | planned |")
print("|---|---|---|---|---|---|---|---|---|---|")
for path in sorted(glob.glob(f"{cohort}/*/report.json")):
    r = json.load(open(path))
    rid = os.path.basename(os.path.dirname(path))
    for p in r["pairs"]:
        g = p["gate"]
        sc = g.get("screening") or {}
        sz = sc.get("sizing") or {}
        iv = sc.get("interval") or {}
        est = sc.get("estimate")
        est = f"{est:.1f}" if isinstance(est, (int, float)) else ""
        lo, hi = iv.get("lower"), iv.get("upper")
        interval = f"{lo:.1f} to {hi:.1f}" if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) else ""
        me = sc.get("min_effect")
        me = f"{me:.1f}" if isinstance(me, (int, float)) else ""
        print(f"| {rid} | {p['parent_id']} | {p['candidate_id']} | {p['recorded_status'] or ''} | {g['outcome']} | "
              f"{est} | {interval} | {me} | {round(sz['screening_sd']) if sz else ''} | {sz.get('planned', '')} |")
