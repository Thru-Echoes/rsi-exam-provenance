#!/usr/bin/env python3
"""Build fixtures/gated_mode from a real gated run of the gate over the fixture task.

Every number in that fixture is the deterministic outcome of the fixture policies on the fixture
seeds, produced by running `gate/evaluate_suite.py` and `gate/decide.py` for real: the receipts are
the runner's, the confirmation suite is derived by `gate/seeds.py`, and the frozen method-tree
digests are the ones the gate recorded at gate time. Nothing here is hand-written JSON, which is the
point: `fixtures/gated` is a replay-mode log whose seven gated fields are all null, so the checks
that read them had nothing real to read.

Run from the repository root:

    python3 fixtures/build_gated_mode.py

Side effects: removes and rewrites `fixtures/gated_mode/`. Standard library only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "gate"))

import decide                                                          # noqa: E402
import seeds as seedsmod                                               # noqa: E402
import treedigest                                                      # noqa: E402
from tests.gate_fixtures import (POLICY_WEAK, TASK_ROOT, VISIBLE_SUITE,  # noqa: E402
                                 copy_policy, real_evaluator, real_visible_suite_sha,
                                 run_runner, write_profile)

OUT = REPO / "fixtures/gated_mode"
# The candidate is the parent's policy unchanged. That is what makes a confirmation feasible here:
# the per-seed deltas are all zero, so the screening spread is zero and the planning rule asks for
# the floor rather than more games than the profile allows. A candidate that genuinely differs on
# these eight seeds needs thousands of games to confirm, which is the exploratory path
# fixtures/gated already covers.
CANDIDATE = POLICY_WEAK
CONFIRMATION = {"floor": 4, "max_seeds": 8, "max_moves": 10000, "cpu_seconds_per_game": 225}
ROLLOUT = "gated-mode-fixture"


def evaluate(methods: Path, profile: Path, version: str, suite: Path, output: Path) -> dict:
    """Run the pinned evaluator on one snapshot; the runner writes the receipt beside the result."""
    output.parent.mkdir(parents=True, exist_ok=True)
    proc = run_runner("--profile", str(profile), "--task-root", str(TASK_ROOT),
                      "--policy-dir", str(methods / "versions" / version), "--suite", str(suite),
                      "--output", str(output))
    if proc.returncode != 0:
        raise SystemExit(f"runner failed for {version}: {proc.stderr}")
    return json.loads(output.read_text(encoding="utf-8"))


def gate(methods: Path, profile: Path, *args: str, at: str) -> None:
    os.environ["DECIDE_FIXED_TIMESTAMP"] = at        # a fixture has to be byte-stable
    code = decide.main(["--methods", str(methods), "--profile", str(profile), *args])
    if code != 0:
        raise SystemExit(f"gate refused: {args}")


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    job = OUT / "job"
    methods = job / "artifacts/app/methods"
    methods.mkdir(parents=True)
    shutil.copytree(REPO / "fixtures/valid/task", OUT / "task")

    copy_policy(POLICY_WEAK, methods / "main")
    copy_policy(POLICY_WEAK, methods / "versions/v1")
    profile = methods / "gate/profile.json"
    write_profile(profile, rollout_id=ROLLOUT, confirmation=CONFIRMATION,
                  min_effect={"kind": "fraction_of_parent_visible_mean", "fraction": 0.025},
                  replication_key="22" * 32, evaluator=real_evaluator(),
                  visible_suite_sha256=real_visible_suite_sha())

    parent = evaluate(methods, profile, "v1", VISIBLE_SUITE,
                      methods / "results/v1/visible_result.json")
    shutil.rmtree(methods / "main")
    copy_policy(CANDIDATE, methods / "main")
    copy_policy(CANDIDATE, methods / "versions/v2")
    candidate = evaluate(methods, profile, "v2", VISIBLE_SUITE,
                         methods / "results/v2/visible_result.json")

    gate(methods, profile, "--version", "v2", "--parent", "v1",
         at="2026-09-05T12:00:00+00:00")
    line = json.loads((methods / "decisions.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    if line["disposition"] != "provisional":
        raise SystemExit(f"expected a provisional screening, got {line['disposition']}")

    suite = methods / line["suite"]["locator"]
    base = methods / "results/v2/replication"
    evaluate(methods, profile, "v1", suite, base / "parent_result.json")
    evaluate(methods, profile, "v2", suite, base / "candidate_result.json")
    gate(methods, profile, "--version", "v2", "--parent", "v1", "--replicates", "v2",
         at="2026-09-05T12:05:00+00:00")

    lines = [json.loads(text) for text in
             (methods / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    final = lines[-1]
    # main/ holds whichever policy the gate's outcome leaves standing.
    if final["disposition"] == "revert":
        shutil.rmtree(methods / "main")
        copy_policy(POLICY_WEAK, methods / "main")
        submitted, other = "v1", "v2"
    else:
        submitted, other = "v2", "v1"

    (methods / "experiment_log.md").write_text(
        "# Experiment log\n\n"
        f"- v1 (parent: none): the weak baseline policy. score: {parent['mean_score']:g}. kept\n"
        f"- v2 (parent: v1): the variant policy, gated on fresh seeds. "
        f"score: {candidate['mean_score']:g}. "
        f"{'reverted' if final['disposition'] == 'revert' else 'kept'}\n",
        encoding="utf-8")

    (job / "agent").mkdir()
    (job / "agent/trajectory.json").write_text(json.dumps(
        {"agent": {"name": "fixture-harness", "model_name": "fixture-model"}, "steps": []},
        indent=2) + "\n", encoding="utf-8")
    (job / "verifier").mkdir()
    (job / "verifier/reward.json").write_text(json.dumps(
        {"mean_score": 0.0, "reward": 0.0, "valid_fraction": 1.0}, indent=2) + "\n",
        encoding="utf-8")

    for tree in (methods / "main", methods / "versions/v1", methods / "versions/v2"):
        if list(tree.rglob("__pycache__")):
            raise SystemExit(f"bytecode written under {tree}")
    print(f"gated-mode fixture built: submitted {submitted} (against {other}), "
          f"{len(lines)} decisions, receipts "
          f"{sorted(p.name for p in (methods / 'results/v2').rglob('*.receipt.json'))}")

    build = subprocess.run(
        [sys.executable, str(REPO / "profile/build_capsule.py"), "--job-dir", str(job),
         "--task-dir", str(OUT / "task"), "--release", "0.1@bc36dadb405b",
         "--capsule-id", "fixture-gated-mode-001"],
        capture_output=True, text=True)
    if build.returncode != 0:
        raise SystemExit(f"producer failed: {build.stderr}")
    print(build.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
