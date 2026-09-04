"""Shared helpers for the gate tests: result files in selfcheck shape, method trees, profiles, receipts.

Also carries the fixture task locations, the real evaluator digests the runner tests pin, and a
subprocess launcher for the runner (which arms ``RLIMIT_CPU`` for its own process and so may never
be called in-process from a test).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import treedigest  # noqa: E402

SEEDS = [104729, 130363, 155921, 181081, 205759, 232003, 260003, 287117]
PARENT = [3980, 4460, 3720, 4310, 4050, 4390, 4180, 3870]
DELTAS_INCONCLUSIVE = [1310, 820, 410, 200, 60, -190, -300, -230]
DELTAS_CLEAR = [610, 540, 480, 700, 390, 450, 520, 460]
DELTAS_BELOW = [-410, -220, -540, -300, -180, -350, -260, -290]
VISIBLE_SUITE_SHA = "3" * 64
EVALUATOR = {"evaluate.py": "a" * 64, "game2048.py": "b" * 64}
FIXTURE = REPO / "fixtures" / "task2048"
TASK_ROOT = FIXTURE / "environment"
VISIBLE_SUITE = TASK_ROOT / "visible_seeds.json"
POLICY_WEAK = FIXTURE / "policy_weak"
POLICY_VARIANT = FIXTURE / "policy_variant"
RUNNER = REPO / "gate" / "evaluate_suite.py"
EVALUATOR_FILES = ("evaluate.py", "game2048.py")
NO_CACHES = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def real_evaluator() -> dict[str, str]:
    """The digests of the fixture task's two evaluator files, as a profile pins them."""
    return {name: treedigest.file_sha256(TASK_ROOT / name) for name in EVALUATOR_FILES}


def real_visible_suite_sha() -> str:
    """The digest of the fixture task's visible seed file."""
    return treedigest.file_sha256(VISIBLE_SUITE)


def copy_policy(source: Path, target: Path) -> Path:
    """Copy a policy directory without bytecode caches, so a test can assert none appear."""
    shutil.copytree(source, target, ignore=NO_CACHES)
    return target


def run_runner(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run gate/evaluate_suite.py in a child process; returns the completed process."""
    return subprocess.run([sys.executable, str(RUNNER), *args], capture_output=True, text=True, env=env)


def write_result(path: Path, scores: Sequence[float], seeds: Sequence[int] = SEEDS) -> None:
    """Write a result file in the exact shape the task's selfcheck.py produces (extra keys included)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cpu_budget_per_game": 225,
        "cpu_seconds": 12.3,
        "cpu_seconds_per_game": 1.5,
        "mean_max_tile": 512.0,
        "mean_score": sum(scores) / len(scores),
        "median_score": sorted(scores)[len(scores) // 2],
        "valid_fraction": 1.0,
        "instances": [
            {"seed": s, "score": v, "max_tile": 512, "moves": 900, "error": None} for s, v in zip(seeds, scores)
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_tree(path: Path, text: str) -> None:
    """A one-file method tree (the gate digests trees; it never runs them here)."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "policy.py").write_text(text, encoding="utf-8")


def profile_document(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema": "rsi-exam-gate-profile/v1", "task": "game2048_policy_search", "rollout_id": "demo-rollout",
        "metric": "per_seed_2048_score", "unit": "game_score", "direction": "higher",
        "min_effect": {"kind": "fraction_of_parent_visible_mean", "fraction": 0.025},
        "level": 0.9, "resamples": 5000, "bootstrap_seed": 20260902, "confirm_policy": "always",
        "confirmation": {"floor": 4, "max_seeds": 8, "max_moves": 300, "cpu_seconds_per_game": 225},
        "visible_suite_sha256": VISIBLE_SUITE_SHA, "replication_key": "11" * 32,
        "audit_key_sha256": hashlib.sha256(b"audit").hexdigest(), "evaluator": dict(EVALUATOR),
    }
    doc.update(overrides)
    return doc


def write_profile(path: Path, **overrides: Any) -> str:
    """Write a valid profile with small confirmation bounds for tests; return its sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(profile_document(**overrides), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_receipt(result_path: Path, *, profile_sha: str, policy_digest: str, suite_sha: str, games: int,
                  max_moves: int = 300, **overrides: Any) -> Path:
    """A receipt next to a result, as the runner writes it, with the bound fields computed from the files."""
    receipt = {
        "schema": "rsi-exam-gate-receipt/v1", "metric": "per_seed_2048_score", "profile_sha256": profile_sha,
        "policy_method_tree_sha256": policy_digest, "suite_sha256": suite_sha, "max_moves": max_moves,
        "result_sha256": treedigest.file_sha256(result_path), "evaluator": dict(EVALUATOR), "games": games,
        "cpu_seconds": 0.1, "cpu_budget_per_game": 225, "python": "3.12.10", "timestamp": "2026-09-05T18:00:00+00:00",
    }
    receipt.update(overrides)
    path = result_path.with_name(result_path.name[:-5] + ".receipt.json")
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
