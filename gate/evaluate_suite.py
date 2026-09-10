#!/usr/bin/env python3
"""Evaluate one policy directory on one seed suite in a child interpreter; write the result and a receipt.

The parent process holds the profile and does the bookkeeping: it checks that the task root's
``evaluate.py`` and ``game2048.py`` have exactly the digests the profile pins, digests the policy
tree (which must be a Python-only tree the grader would accept), reads the suite, and refuses any
output path that is not under a ``results`` directory or that passes through a symlink. It then
runs the evaluation in a fresh child interpreter started with ``PYTHONHASHSEED=0`` and
``PYTHONDONTWRITEBYTECODE=1`` (as the grader's policy process is), with one pooled ``RLIMIT_CPU`` of
``cpu_seconds_per_game * games`` (as ``selfcheck.py`` arms it) and a wall-clock limit. The child loads
``game2048`` and ``evaluate`` from the task root by exact path before the policy directory is put
first on ``sys.path``, so a policy cannot shadow the evaluator. The parent then requires every game
to be valid (``valid_fraction`` 1.0, no per-game error, exactly the suite's seeds), publishes the
result and the receipt through same-directory temporary files, and finally runs ``/app/budget.py``
when it is mounted, as ``selfcheck.py`` does.

CLI: ``--profile`` (the task profile; metric, CPU budget, and evaluator digests come from it),
``--task-root`` (default /app), ``--policy-dir`` (normally methods/versions/v<N>), ``--suite``,
``--output``, ``--receipt`` (default: the output with ``.json`` replaced by ``.receipt.json``),
``--wall-seconds`` (default: CPU budget plus 60), ``--safety-report`` (optional; see below).

Submission safety. A policy tree whose Python files exceed the grader's 10 MB cap is refused before
anything runs (exit 2), as the grader would score it zero. With ``--safety-report PATH`` the child
also times every ``choose_move`` call on the wall clock and the parent publishes, after the receipt,
a document of schema ``rsi-exam-gate-safety/v1`` at PATH (under a ``results`` directory, written
once): the policy digest and byte size, the games, the CPU seconds and CPU seconds per game, the
slowest move in seconds, and the result's digest. The result and the receipt are byte-for-byte what
they are without the flag; the report is what the in-rollout helper reads before it lets a candidate
become the head, against margins below the grader's limits (225 CPU seconds per game, 5 seconds per
move in the grader's own sandboxed process, which this in-process timing can only underestimate).

Exit codes: 0 written; 1 the evaluator raised; 2 bad input or an evaluator file that differs from
the profile; 4 CPU budget exhausted; 5 a game was invalid; 6 wall clock exceeded. Only exit 0
writes anything. ``DECIDE_FIXED_TIMESTAMP`` fixes the receipt's timestamp for fixtures. Standard
library only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import resource
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from seeds import SeedsError, read_suite
from task_profile import ProfileError, load_profile
from treedigest import TreeDigestError, file_sha256, method_files, method_tree_sha256

RECEIPT_SCHEMA = "rsi-exam-gate-receipt/v1"
SAFETY_SCHEMA = "rsi-exam-gate-safety/v1"
POLICY_MAX_BYTES = 10_000_000             # the grader's cap on the staged source, in bytes
EVALUATOR_FILES = ("evaluate.py", "game2048.py")
POLICY_TREES = ("main", "versions")
EVIDENCE_ROOT = "results"
BUDGET_HOOK = Path("/app/budget.py")
EXIT_EVALUATOR, EXIT_INPUT, EXIT_CPU, EXIT_INVALID, EXIT_WALL = 1, 2, 4, 5, 6


class RunnerError(ValueError):
    """A runner input is missing or malformed. Nothing is written (exit 2)."""


class InvalidGames(RunnerError):
    """The evaluator reported an invalid game. Nothing is written (exit 5)."""


class CpuExceeded(RunnerError):
    """The policy exhausted the CPU budget. Nothing is written (exit 4)."""


class WallClockExceeded(RunnerError):
    """The evaluation did not finish within the wall-clock limit. Nothing is written (exit 6)."""


class EvaluatorFailed(RunnerError):
    """The evaluator raised in the child. Nothing is written (exit 1)."""


def check_output_path(path: Path) -> Path:
    """The output must live under a ``results`` directory, outside every policy tree, with no symlink below it."""
    parts = path.parent.parts
    if any(part in POLICY_TREES for part in parts):
        raise RunnerError(f"output must not live in a policy tree: {path}")
    if EVIDENCE_ROOT not in parts:
        raise RunnerError(f"output must live under a {EVIDENCE_ROOT} directory: {path}")
    index = len(parts) - 1 - parts[::-1].index(EVIDENCE_ROOT)
    for depth in range(index, len(parts)):
        ancestor = Path(*parts[: depth + 1])
        if ancestor.is_symlink():
            raise RunnerError(f"output path goes through a symlink: {ancestor}")
    if path.is_symlink():
        raise RunnerError(f"output path is a symlink: {path}")
    return path


def receipt_path_for(output: Path) -> Path:
    """``<name>.json`` becomes ``<name>.receipt.json`` next to the result."""
    stem = output.name[:-5] if output.name.endswith(".json") else output.name
    return output.with_name(stem + ".receipt.json")


def validate_result(result: Any, seeds: list[int]) -> None:
    """Every game valid, exactly the suite's seeds, finite scores; otherwise ``InvalidGames``."""
    if not isinstance(result, dict) or not isinstance(result.get("instances"), list):
        raise InvalidGames("evaluator result lacks an instances list")
    instances = result["instances"]
    if len(instances) != len(seeds):
        raise InvalidGames(f"evaluator returned {len(instances)} games for {len(seeds)} seeds")
    seen: set[int] = set()
    for game in instances:
        if not isinstance(game, dict) or game.get("error") is not None:
            raise InvalidGames(f"invalid game: {game!r}"[:300])
        score = game.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise InvalidGames(f"non-finite or missing score: {game!r}"[:300])
        seen.add(int(game["seed"]))
    if seen != set(seeds):
        raise InvalidGames("evaluator games do not cover exactly the suite's seeds")
    if result.get("valid_fraction") != 1.0:
        raise InvalidGames(f"valid_fraction is {result.get('valid_fraction')!r}, not 1.0")


def publish(path: Path, payload: bytes) -> None:
    """Write through a same-directory temporary file and rename into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def run(*, profile_path: Path, task_root: Path, policy_dir: Path, suite: Path, output: Path, receipt: Path,
        wall_seconds: int | None, safety: Path | None = None) -> dict[str, Any]:
    """Parent side: check, evaluate in a child, validate, publish. Returns the receipt document."""
    profile, profile_sha = load_profile(profile_path)
    for name in EVALUATOR_FILES:
        candidate = task_root / name
        if not candidate.is_file():
            raise RunnerError(f"task root lacks {name}: {task_root}")
        if file_sha256(candidate) != profile["evaluator"][name]:
            raise RunnerError(f"{name} in {task_root} differs from the digest the profile pins")
    if not (policy_dir / "policy.py").is_file():
        raise RunnerError(f"policy.py not found in {policy_dir}")
    policy_bytes = sum((policy_dir / rel).stat().st_size for rel in method_files(policy_dir))
    if policy_bytes > POLICY_MAX_BYTES:
        raise RunnerError(f"policy source is {policy_bytes:,} bytes, over the grader's {POLICY_MAX_BYTES:,} byte cap; "
                          "the grader scores such a submission zero")
    if not suite.is_file():
        raise RunnerError(f"suite not found: {suite}")
    seeds, max_moves = read_suite(suite)
    check_output_path(output)
    check_output_path(receipt)
    if receipt.resolve() == output.resolve():
        raise RunnerError("the receipt path must differ from the output path")
    if output.exists() or receipt.exists():
        raise RunnerError("output or receipt already exists; evidence is written once")
    if safety is not None:
        check_output_path(safety)
        if safety.resolve() in (output.resolve(), receipt.resolve()):
            raise RunnerError("the safety report path must differ from the output and receipt paths")
        if safety.exists():
            raise RunnerError("safety report already exists; evidence is written once")
    policy_digest = method_tree_sha256(policy_dir)
    cpu_budget = int(profile["confirmation"]["cpu_seconds_per_game"])
    limit = wall_seconds if wall_seconds is not None else cpu_budget * len(seeds) + 60
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".evaluate.", dir=output.parent) as scratch:
        tmp_result = Path(scratch) / "result.json"
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = "0"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        child = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--child", str(task_root), str(policy_dir), str(suite),
             str(tmp_result), str(cpu_budget), "1" if safety is not None else "0"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, start_new_session=True,
        )
        try:
            out, err = child.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise WallClockExceeded(f"evaluation exceeded the wall-clock limit of {limit} s") from None
        if child.returncode == EXIT_CPU:
            raise CpuExceeded(err.strip() or f"policy exhausted the CPU budget of {cpu_budget * len(seeds)} s")
        if child.returncode != 0:
            raise EvaluatorFailed(err.strip().splitlines()[-1] if err.strip() else f"child exited {child.returncode}")
        meta = json.loads(out.strip().splitlines()[-1])
        result = json.loads(tmp_result.read_text(encoding="utf-8"))
        validate_result(result, seeds)
        result_bytes = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    publish(output, result_bytes)
    document: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "metric": profile["metric"],
        "profile_sha256": profile_sha,
        "policy_method_tree_sha256": policy_digest,
        "suite_sha256": file_sha256(suite),
        "max_moves": max_moves,
        "result_sha256": file_sha256(output),
        "evaluator": dict(profile["evaluator"]),
        "games": len(seeds),
        "cpu_seconds": result["cpu_seconds"],
        "cpu_budget_per_game": cpu_budget,
        "python": meta["python"],
        "timestamp": os.environ.get("DECIDE_FIXED_TIMESTAMP") or datetime.now(UTC).isoformat(),
    }
    publish(receipt, (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    if safety is not None:
        report: dict[str, Any] = {
            "schema": SAFETY_SCHEMA,
            "policy_method_tree_sha256": policy_digest,
            "policy_bytes": policy_bytes,
            "games": len(seeds),
            "cpu_seconds": result["cpu_seconds"],
            "cpu_seconds_per_game": result["cpu_seconds_per_game"],
            "max_move_seconds": meta["max_move_seconds"],
            "result_sha256": document["result_sha256"],
            "timestamp": document["timestamp"],
        }
        publish(safety, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    if BUDGET_HOOK.exists():
        sys.stdout.flush()
        subprocess.run([sys.executable, str(BUDGET_HOOK)], check=False)
    return document


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _time_moves(evaluate: ModuleType) -> dict[str, float]:
    """Wrap the evaluator's policy loader so every ``choose_move`` call is timed on the wall clock.

    Returns the live statistics dict (``max_move_seconds``). Side effect: rebinds ``load_policy`` on
    the evaluator module; the evaluator looks the name up when it runs, so the policy it loads has its
    ``choose_move`` replaced by the timing wrapper. Nothing about the game or the score changes.
    """
    stats = {"max_move_seconds": 0.0}
    original = getattr(evaluate, "load_policy")

    def load_policy(path: Path) -> ModuleType:
        module = original(path)
        inner = getattr(module, "choose_move")

        def choose_move(board: Any) -> Any:
            started = time.perf_counter()
            try:
                return inner(board)
            finally:
                stats["max_move_seconds"] = max(stats["max_move_seconds"], time.perf_counter() - started)

        setattr(module, "choose_move", choose_move)
        return module

    setattr(evaluate, "load_policy", load_policy)
    return stats


def child_main(task_root: Path, policy_dir: Path, suite: Path, out: Path, cpu_budget: int, timed: bool = False) -> int:
    """Child side: pinned evaluator by exact path, policy dir first on sys.path, CPU budget armed."""
    sys.dont_write_bytecode = True
    _load_module("game2048", task_root / "game2048.py")
    evaluate = _load_module("evaluate", task_root / "evaluate.py")
    stats = _time_moves(evaluate) if timed else None
    sys.path.insert(0, str(policy_dir))
    games = len(json.loads(suite.read_text(encoding="utf-8"))["seeds"])
    budget = cpu_budget * games

    def exceeded(_signum: int, _frame: object) -> None:
        print(f"policy exhausted the CPU budget of {budget} s", file=sys.stderr)
        raise SystemExit(EXIT_CPU)

    signal.signal(signal.SIGXCPU, exceeded)
    resource.setrlimit(resource.RLIMIT_CPU, (budget, budget + 20))
    before = resource.getrusage(resource.RUSAGE_SELF)
    result = evaluate.evaluate(policy_dir / "policy.py", suite)
    after = resource.getrusage(resource.RUSAGE_SELF)
    used = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    result["cpu_seconds"] = round(used, 1)
    result["cpu_seconds_per_game"] = round(used / games, 1)
    result["cpu_budget_per_game"] = cpu_budget
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"python": platform.python_version(),
                      "max_move_seconds": round(stats["max_move_seconds"], 6) if stats is not None else None}))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--child"]:
        task_root, policy_dir, suite, out, cpu_budget, timed = argv[1:7]
        return child_main(Path(task_root), Path(policy_dir), Path(suite), Path(out), int(cpu_budget), timed == "1")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--task-root", type=Path, default=Path("/app"))
    parser.add_argument("--policy-dir", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--wall-seconds", type=int, default=None)
    parser.add_argument("--safety-report", type=Path, default=None)
    args = parser.parse_args(argv)
    receipt = args.receipt or receipt_path_for(args.output)
    try:
        document = run(profile_path=args.profile, task_root=args.task_root, policy_dir=args.policy_dir,
                       suite=args.suite, output=args.output, receipt=receipt, wall_seconds=args.wall_seconds,
                       safety=args.safety_report)
    except CpuExceeded as exc:
        print(f"runner: {exc}", file=sys.stderr)
        return EXIT_CPU
    except InvalidGames as exc:
        print(f"runner refused: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except WallClockExceeded as exc:
        print(f"runner: {exc}", file=sys.stderr)
        return EXIT_WALL
    except EvaluatorFailed as exc:
        print(f"runner failed: {exc}", file=sys.stderr)
        return EXIT_EVALUATOR
    except (RunnerError, ProfileError, SeedsError, TreeDigestError) as exc:
        print(f"runner refused: {exc}", file=sys.stderr)
        return EXIT_INPUT
    print(json.dumps(document, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
