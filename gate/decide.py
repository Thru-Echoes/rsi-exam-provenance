#!/usr/bin/env python3
"""Decision gate for RSI-Exam rollouts: a paired bootstrap interval on per-seed deltas.

Reads per-seed result files for a parent version and a candidate version, pairs the scores,
bootstraps a confidence interval on the mean delta, applies the rule, and appends one JSON line to
``<methods>/decisions.jsonl`` (contract: docs/decision-log-contract.md, schema id
``rsi-exam-decision-log/v1``). Two modes.

Gated mode (``--profile <task profile>``): the profile fixes direction, unit, the minimum effect,
level, resamples, the bootstrap seed, and the confirmation bounds; the flags for those, the result
locator overrides, and the held-out flags are refused. Screening (no ``--replicates``): the two
visible results under ``results/<parent>/`` and ``results/<version>/`` must carry runner receipts
that bind them to the parent and candidate snapshots, the profile's visible suite, and the
profile's evaluator; the snapshots' method-tree digests are recorded and ``main/`` must equal the
candidate's; ``below`` reverts; otherwise the confirmation is planned from the screening deltas,
and when the plan fits under the profile's cap a fresh suite is derived and written to
``results/<version>/replication/seeds.json`` and the line is ``provisional`` (an under-planned
confirmation reverts instead: it is never allowed to keep). Confirmation (``--replicates
<version>``): the open provisional line is re-verified from its evidence (digests, minimum effect,
plan, exclusion set, and the suite re-derived from the key), the two confirmation results and their
receipts are checked against the frozen digests, the suite, and the profile, and the decision
resolves to ``keep`` or ``revert``.

Replay mode (no ``--profile``; ``--confirm inconclusive`` is required so the weaker rule is stated
on the command line): the screening rule for shadow replay and fixtures. Locators may be
overridden, a held-out pair may be supplied, nothing is frozen, and no suite is derived. A log
written in one mode refuses lines from the other.

The whole read-check-write transaction runs under an exclusive lock on ``<methods>/decisions.lock``.
Evidence locators must live under ``results/`` with no symlink on the way; a suite file is created
exclusively and removed again if the line cannot be appended.

Outputs: exit 0 with the appended line on stdout; exit 2 on a missing or malformed input or a
contract violation (nothing appended); exit 3 when the log already carries an unresolved
provisional decision that this line would build on or duplicate (nothing appended).
``DECIDE_FIXED_TIMESTAMP`` overrides the timestamp for fixtures. Standard library only.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import random
from fractions import Fraction
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seeds import SEEDS_ALGORITHM, SeedsError, confirmation_size, derive_seeds, read_suite, write_suite
from task_profile import ProfileError, load_profile, resolve_min_effect
from treedigest import TreeDigestError, file_sha256, method_tree_sha256

SCHEMA = "rsi-exam-decision-log/v1"
LOG_NAME = "decisions.jsonl"
LOCK_NAME = "decisions.lock"
SUITE_NAME = "seeds.json"
EVIDENCE_ROOT = "results"
METHOD_NAME = "percentile_bootstrap"
ALGORITHM = "rsi-exam-gate/percentile-bootstrap/1"
STATISTIC = "mean_paired_delta"
RECEIPT_SCHEMA = "rsi-exam-gate-receipt/v1"
RECEIPT_KEYS = ("profile_sha256", "policy_method_tree_sha256", "suite_sha256", "max_moves", "result_sha256",
                "evaluator", "metric", "cpu_budget_per_game", "games", "python")
CONFIRM_POLICIES = ("always", "inconclusive")
LINE_KEYS = ("schema", "line", "timestamp", "version_id", "parent_id", "replicates", "statistic", "unit",
             "direction", "estimate", "interval", "method", "sample_size", "min_effect", "verdict", "disposition",
             "evidence", "evidence_digests", "holdout")
DEFAULT_DIRECTION = "higher"
DEFAULT_LEVEL = 0.9
DEFAULT_RESAMPLES = 5000
DEFAULT_SEED = 20260902
DEFAULT_MIN_EFFECT = 0.0
DEFAULT_UNIT = "game_score"
GATED_FIXED_FLAGS = ("confirm", "direction", "level", "resamples", "seed", "min_effect", "unit", "parent_result",
                     "candidate_result", "holdout_parent_result", "holdout_candidate_result")


class GateError(ValueError):
    """A gate input is missing, malformed, or inconsistent. Nothing is written (exit 2)."""


class StackedProvisional(GateError):
    """The log holds an unresolved provisional decision this line would stack on (exit 3)."""


INPUT_ERRORS = (GateError, ProfileError, SeedsError, TreeDigestError)


def sha256_of(path: Path) -> str:
    """Hex SHA-256 of a file's bytes."""
    return file_sha256(path)


def check_locator(locator: str) -> str:
    """A locator is a canonical relative POSIX path under ``results/``.

    Rules: no leading slash, no backslash, no percent escape, no drive prefix, no ``..`` or empty
    segment, no control characters, first segment ``results`` (never ``versions/`` or ``main/``: the
    sealed grader rejects non-Python files in the policy tree, so evidence stays out of every snapshot).
    """
    bad = (not locator or locator.startswith("/") or "\\" in locator or "%" in locator or ":" in locator
           or any(ord(c) < 32 for c in locator) or any(part in ("..", "", ".") for part in locator.split("/")))
    if bad:
        raise GateError(f"bad locator: {locator!r}")
    if locator.split("/", 1)[0] != EVIDENCE_ROOT:
        raise GateError(f"evidence locator must live under {EVIDENCE_ROOT}/: {locator!r}")
    return locator


def evidence_path(methods: Path, locator: str) -> Path:
    """The file a locator names, after checking that no component from ``results`` down is a symlink."""
    check_locator(locator)
    current = methods
    for part in locator.split("/"):
        current = current / part
        if current.is_symlink():
            raise GateError(f"evidence path goes through a symlink: {locator!r}")
    return current


def load_scores(path: Path) -> dict[int, float]:
    """Per-seed scores from a task self-check result file (``instances`` list with ``seed`` and ``score``)."""
    if not path.is_file():
        raise GateError(f"result file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        instances = data["instances"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GateError(f"malformed result file {path}: {exc}") from exc
    scores: dict[int, float] = {}
    for inst in instances:
        try:
            seed = int(inst["seed"])
            score = float(inst["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GateError(f"malformed instance in {path}: {exc}") from exc
        if seed in scores:
            raise GateError(f"duplicate seed {seed} in {path}")
        if not math.isfinite(score):
            raise GateError(f"non-finite score for seed {seed} in {path}")
        scores[seed] = score
    if not scores:
        raise GateError(f"result file has no instances: {path}")
    return scores


def paired_deltas(parent: Mapping[int, float], candidate: Mapping[int, float], direction: str = "higher") -> list[float]:
    """Candidate minus parent for every seed, oriented so a positive value favours the candidate."""
    if set(parent) != set(candidate):
        raise GateError("parent and candidate result files cover different seed sets")
    if direction not in ("higher", "lower"):
        raise GateError(f"direction must be 'higher' or 'lower', got {direction!r}")
    sign = 1.0 if direction == "higher" else -1.0
    return [sign * (candidate[s] - parent[s]) for s in sorted(parent)]


def bootstrap_interval(deltas: list[float], *, level: float, resamples: int, seed: int) -> tuple[float, float]:
    """Percentile bootstrap interval on the mean of ``deltas``. Deterministic for a given seed."""
    if not deltas:
        raise GateError("no deltas to bootstrap")
    if not 0.0 < level < 1.0:
        raise GateError("level must lie strictly between 0 and 1")
    if resamples < 1:
        raise GateError("resamples must be at least 1")
    rng = random.Random(seed)
    n = len(deltas)
    means = sorted(sum(rng.choice(deltas) for _ in range(n)) / n for _ in range(resamples))
    # The index is computed exactly. Through binary floats (1.0 - 0.9) / 2.0 is a shade under 0.05,
    # so int(alpha * 5000) yields 249 where the contract's floor(alpha * resamples) is 250: the
    # implementation would sit one order statistic below its own specification, at the level and
    # resample count this project actually uses.
    alpha = (Fraction(1) - Fraction(str(level))) / 2
    return means[int(alpha * resamples)], means[int((1 - alpha) * resamples) - 1]


def get_verdict(interval: tuple[float, float], min_effect: float) -> str:
    """``clears`` when the lower bound exceeds the minimum effect, ``below`` when the upper bound is under zero, else ``inconclusive``.

    ``inconclusive`` means neither condition holds: the interval establishes neither an effect above the
    minimum nor harm. It is not "straddles zero": an interval entirely positive but under ``min_effect``
    is ``inconclusive``.
    """
    if min_effect < 0.0:
        raise GateError("min_effect must be at or above zero")
    low, high = interval
    if low > min_effect:
        return "clears"
    if high < 0.0:
        return "below"
    return "inconclusive"


def get_disposition(verdict: str, holdout_verdict: str | None, confirm_policy: str = "inconclusive") -> str:
    """The action for a screening line.

    ``below`` reverts. Under ``inconclusive`` (the replay rule) a clear win keeps unless a held-out
    measurement fails to clear. Under ``always`` (the gated rule) every non-reverting candidate is
    provisional until a confirmation on fresh seeds resolves it.
    """
    if confirm_policy not in CONFIRM_POLICIES:
        raise GateError(f"confirm_policy must be 'always' or 'inconclusive', got {confirm_policy!r}")
    if verdict == "below":
        return "revert"
    if confirm_policy == "inconclusive" and verdict == "clears" and holdout_verdict in (None, "clears"):
        return "keep"
    return "provisional"


def read_log(path: Path) -> list[dict[str, Any]]:
    """Existing decision-log lines, validated as objects of this schema with consecutive line numbers and the contract's keys."""
    if not path.exists():
        return []
    lines: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            raise GateError(f"{path}:{number}: blank line in decision log")
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GateError(f"{path}:{number}: not JSON: {exc}") from exc
        if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
            raise GateError(f"{path}:{number}: not a {SCHEMA} line")
        if obj.get("line") != number:
            raise GateError(f"{path}:{number}: line field {obj.get('line')!r} does not match position")
        missing = [key for key in LINE_KEYS if key not in obj]
        if missing:
            raise GateError(f"{path}:{number}: line lacks {', '.join(missing)}")
        lines.append(obj)
    return lines


def get_open_provisional(log_lines: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The unresolved provisional line, if any. More than one open at once is a corrupt log."""
    open_by_version: dict[str, dict[str, Any]] = {}
    for line in log_lines:
        vid = line["version_id"]
        if line.get("replicates"):
            if line["replicates"] not in open_by_version:
                raise GateError(f"line {line['line']} replicates {line['replicates']} but no provisional decision is open")
            del open_by_version[line["replicates"]]
        elif line.get("disposition") == "provisional":
            if open_by_version:
                raise GateError(f"line {line['line']} opens a second provisional decision")
            open_by_version[vid] = line
    if len(open_by_version) > 1:
        raise GateError("more than one provisional decision is open")
    return next(iter(open_by_version.values()), None)


def check_stacked_provisional(log_lines: list[dict[str, Any]], parent_id: str) -> None:
    """Refuse to build on a parent whose decision is provisional and unreplicated."""
    open_line = get_open_provisional(log_lines)
    if open_line is not None and open_line["version_id"] == parent_id:
        raise StackedProvisional(
            f"parent {parent_id} carries an unreplicated provisional decision (line {open_line['line']}); "
            "replicate it before building on it"
        )


def measure(methods: Path, parent_locator: str, candidate_locator: str, *, direction: str, level: float,
            resamples: int, seed: int, min_effect: float) -> dict[str, Any]:
    """Interval, verdict, and evidence references for one parent/candidate pair."""
    parent_path = evidence_path(methods, parent_locator)
    candidate_path = evidence_path(methods, candidate_locator)
    deltas = paired_deltas(load_scores(parent_path), load_scores(candidate_path), direction)
    low, high = bootstrap_interval(deltas, level=level, resamples=resamples, seed=seed)
    estimate = sum(deltas) / len(deltas)
    evidence = [
        {"role": "parent", "locator": parent_locator, "sha256": file_sha256(parent_path)},
        {"role": "candidate", "locator": candidate_locator, "sha256": file_sha256(candidate_path)},
    ]
    return {
        "estimate": estimate,
        "interval": {"lower": low, "upper": high, "level": level},
        "sample_size": len(deltas),
        "verdict": get_verdict((low, high), min_effect),
        "evidence": evidence,
        "evidence_digests": {e["role"]: "sha256:" + e["sha256"] for e in evidence},
    }


def build_line(*, line_number: int, version_id: str, parent_id: str, replicates: str | None,
               main: dict[str, Any], holdout: dict[str, Any] | None, disposition: str, unit: str, direction: str,
               resamples: int, seed: int, min_effect: float, confirm_policy: str, profile_sha256: str | None,
               look_index: int | None, parent_digest: str | None, candidate_digest: str | None,
               sizing: dict[str, Any] | None, suite: dict[str, Any] | None) -> dict[str, Any]:
    """Assemble one decision-log line from a measurement (and an optional held-out measurement)."""
    if replicates is not None and replicates != version_id:
        raise GateError("a replication line must carry replicates equal to its own version_id")
    if disposition not in ("keep", "revert", "provisional"):
        raise GateError(f"unknown disposition {disposition!r}")
    return {
        "schema": SCHEMA,
        "line": line_number,
        "timestamp": os.environ.get("DECIDE_FIXED_TIMESTAMP") or datetime.now(UTC).isoformat(),
        "version_id": version_id,
        "parent_id": parent_id,
        "replicates": replicates,
        "statistic": STATISTIC,
        "unit": unit,
        "direction": direction,
        "estimate": main["estimate"],
        "interval": main["interval"],
        "method": {"name": METHOD_NAME, "algorithm": ALGORITHM, "resamples": resamples, "seed": seed},
        "sample_size": main["sample_size"],
        "min_effect": min_effect,
        "verdict": main["verdict"],
        "disposition": disposition,
        "evidence": main["evidence"],
        "evidence_digests": main["evidence_digests"],
        "holdout": (
            {k: holdout[k] for k in ("estimate", "interval", "sample_size", "verdict", "evidence", "evidence_digests")}
            if holdout else None
        ),
        "confirm_policy": confirm_policy,
        "profile_sha256": profile_sha256,
        "look_index": look_index,
        "parent_method_tree_sha256": parent_digest,
        "candidate_method_tree_sha256": candidate_digest,
        "sizing": sizing,
        "suite": suite,
    }


def load_receipt(path: Path) -> dict[str, Any]:
    """A runner receipt (schema rsi-exam-gate-receipt/v1) with every key the gate compares."""
    if not path.is_file():
        raise GateError(f"receipt not found: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GateError(f"malformed receipt {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != RECEIPT_SCHEMA or any(key not in doc for key in RECEIPT_KEYS):
        raise GateError(f"receipt {path} is not a complete {RECEIPT_SCHEMA} document")
    return doc


def python_minor(version: Any) -> str:
    return ".".join(str(version).split(".")[:2])


def check_receipt(methods: Path, result_locator: str, *, role: str, profile: Mapping[str, Any], profile_sha: str,
                  suite_sha: str, policy_digest: str, games: int) -> tuple[dict[str, Any], dict[str, str]]:
    """The receipt next to a result; every bound field must match. Returns the receipt and its evidence entry."""
    receipt_locator = result_locator[: -len(".json")] + ".receipt.json"
    receipt_path = evidence_path(methods, receipt_locator)
    receipt = load_receipt(receipt_path)
    expected: dict[str, Any] = {
        "profile_sha256": profile_sha,
        "suite_sha256": suite_sha,
        "result_sha256": file_sha256(evidence_path(methods, result_locator)),
        "policy_method_tree_sha256": policy_digest,
        "evaluator": profile["evaluator"],
        "metric": profile["metric"],
        "cpu_budget_per_game": profile["confirmation"]["cpu_seconds_per_game"],
        "max_moves": profile["confirmation"]["max_moves"],
        "games": games,
    }
    for key, want in expected.items():
        if receipt.get(key) != want:
            raise GateError(f"{role} receipt {key} does not match: {receipt.get(key)!r} != {want!r}")
    return receipt, {"role": f"receipt-{role}", "locator": receipt_locator, "sha256": file_sha256(receipt_path)}


def check_python_parity(receipts: list[dict[str, Any]]) -> None:
    versions = {python_minor(r["python"]) for r in receipts}
    if len(versions) != 1:
        raise GateError(f"receipts were produced under different Python versions: {sorted(versions)}")


def suite_seeds_in_log(methods: Path, log_lines: list[dict[str, Any]]) -> set[int]:
    """Every seed of every suite an earlier line derived; each suite file is re-checked against its digest."""
    seen: set[int] = set()
    checked: set[str] = set()
    for line in log_lines:
        suite = line.get("suite")
        if not isinstance(suite, dict) or suite["locator"] in checked:
            continue
        path = evidence_path(methods, suite["locator"])
        if not path.is_file() or file_sha256(path) != suite["sha256"]:
            raise GateError(f"suite referenced by line {line['line']} is missing or altered: {suite['locator']}")
        chosen, _ = read_suite(path)
        seen.update(chosen)
        checked.add(suite["locator"])
    return seen


@contextmanager
def log_lock(methods: Path) -> Iterator[None]:
    """Exclusive lock for the read-check-write transaction on one decision log."""
    methods.mkdir(parents=True, exist_ok=True)
    fd = os.open(methods / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def append_line(log_path: Path, line: dict[str, Any]) -> None:
    """One line per ``os.write`` on an ``O_APPEND`` descriptor, then fsync."""
    payload = (json.dumps(line, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        if os.write(fd, payload) != len(payload):
            raise OSError("short write to the decision log")
        os.fsync(fd)
    finally:
        os.close(fd)


def build_replay_line(args: argparse.Namespace, methods: Path, log_lines: list[dict[str, Any]],
                      open_line: dict[str, Any] | None) -> dict[str, Any]:
    """Replay mode: the screening rule with explicit locators; nothing frozen, no suite."""
    if args.confirm is None:
        raise GateError("replay mode requires --confirm inconclusive; a gated run passes --profile instead")
    if args.confirm != "inconclusive":
        raise GateError("--confirm always requires --profile: freezing and fresh suites need the task profile")
    if any(prior.get("profile_sha256") is not None for prior in log_lines):
        raise GateError("this log was written in gated mode; pass the same --profile")
    direction: str = args.direction if args.direction is not None else DEFAULT_DIRECTION
    level: float = args.level if args.level is not None else DEFAULT_LEVEL
    resamples: int = args.resamples if args.resamples is not None else DEFAULT_RESAMPLES
    seed: int = args.seed if args.seed is not None else DEFAULT_SEED
    min_effect: float = args.min_effect if args.min_effect is not None else DEFAULT_MIN_EFFECT
    unit: str = args.unit if args.unit is not None else DEFAULT_UNIT
    if not math.isfinite(min_effect) or min_effect < 0.0:
        raise GateError("min_effect must be a finite number at or above zero")
    if args.replicates is not None:
        parent_locator = args.parent_result or f"results/{args.version}/replication/parent_result.json"
        candidate_locator = args.candidate_result or f"results/{args.version}/replication/candidate_result.json"
        if open_line is None or open_line["version_id"] != args.replicates:
            raise GateError(f"no open provisional decision for {args.replicates} to replicate")
        if open_line["parent_id"] != args.parent:
            raise GateError(f"replication parent {args.parent} differs from the provisional line's parent {open_line['parent_id']}")
    else:
        parent_locator = args.parent_result or f"results/{args.parent}/visible_result.json"
        candidate_locator = args.candidate_result or f"results/{args.version}/visible_result.json"
        check_stacked_provisional(log_lines, args.parent)
    main_measure = measure(methods, parent_locator, candidate_locator, direction=direction, level=level,
                           resamples=resamples, seed=seed, min_effect=min_effect)
    holdout = None
    if args.holdout_parent_result or args.holdout_candidate_result:
        if not (args.holdout_parent_result and args.holdout_candidate_result):
            raise GateError("both held-out result files are required when one is given")
        holdout = measure(methods, args.holdout_parent_result, args.holdout_candidate_result, direction=direction,
                          level=level, resamples=resamples, seed=seed, min_effect=min_effect)
        holdout["evidence"] = [dict(e, role="holdout-" + e["role"]) for e in holdout["evidence"]]
        holdout["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in holdout["evidence"]}
    holdout_verdict = holdout["verdict"] if holdout else None
    if args.replicates is not None:
        disposition = "keep" if main_measure["verdict"] == "clears" and holdout_verdict in (None, "clears") else "revert"
    else:
        disposition = get_disposition(main_measure["verdict"], holdout_verdict, "inconclusive")
        if disposition == "provisional" and open_line is not None:
            raise StackedProvisional(
                f"{open_line['version_id']} already holds the one open provisional decision (line {open_line['line']}); "
                "replicate it before opening another"
            )
    return build_line(line_number=len(log_lines) + 1, version_id=args.version, parent_id=args.parent,
                      replicates=args.replicates, main=main_measure, holdout=holdout, disposition=disposition,
                      unit=unit, direction=direction, resamples=resamples, seed=seed, min_effect=min_effect,
                      confirm_policy="inconclusive", profile_sha256=None, look_index=None, parent_digest=None,
                      candidate_digest=None, sizing=None, suite=None)


def _gated_screening_inputs(methods: Path, parent_id: str, version_id: str, profile: Mapping[str, Any],
                            profile_sha: str, parent_digest: str, candidate_digest: str) -> dict[str, Any]:
    """Load and bind the two visible results of a screening; shared by screening and its re-verification."""
    parent_locator = f"results/{parent_id}/visible_result.json"
    candidate_locator = f"results/{version_id}/visible_result.json"
    parent_scores = load_scores(evidence_path(methods, parent_locator))
    candidate_scores = load_scores(evidence_path(methods, candidate_locator))
    if set(parent_scores) != set(candidate_scores):
        raise GateError("parent and candidate visible results cover different seed sets")
    games = len(parent_scores)
    receipts: list[dict[str, Any]] = []
    entries: list[dict[str, str]] = []
    for role, locator, digest in (("parent", parent_locator, parent_digest), ("candidate", candidate_locator, candidate_digest)):
        receipt, entry = check_receipt(methods, locator, role=role, profile=profile, profile_sha=profile_sha,
                                       suite_sha=profile["visible_suite_sha256"], policy_digest=digest, games=games)
        receipts.append(receipt)
        entries.append(entry)
    check_python_parity(receipts)
    min_effect = resolve_min_effect(profile, parent_scores)
    main_measure = measure(methods, parent_locator, candidate_locator, direction=profile["direction"],
                           level=float(profile["level"]), resamples=int(profile["resamples"]),
                           seed=int(profile["bootstrap_seed"]), min_effect=min_effect)
    main_measure["evidence"] = list(main_measure["evidence"]) + entries
    main_measure["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in main_measure["evidence"]}
    return {"measure": main_measure, "parent_scores": parent_scores, "candidate_scores": candidate_scores,
            "min_effect": min_effect, "receipts": receipts}


def build_gated_line(args: argparse.Namespace, methods: Path, log_lines: list[dict[str, Any]],
                     open_line: dict[str, Any] | None) -> tuple[dict[str, Any], Path | None]:
    """Gated mode. Returns the line and the suite file this call created (to remove if the append fails)."""
    for name in GATED_FIXED_FLAGS:
        if getattr(args, name) is not None:
            raise GateError(f"--{name.replace('_', '-')} is fixed by the profile and may not be passed in gated mode")
    profile, profile_sha = load_profile(args.profile)
    for prior in log_lines:
        if prior.get("profile_sha256") != profile_sha:
            raise GateError(f"line {prior['line']} was written under a different profile or in replay mode; one profile per log")
    conf = profile["confirmation"]
    direction: str = profile["direction"]
    level = float(profile["level"])
    resamples = int(profile["resamples"])
    seed = int(profile["bootstrap_seed"])
    parent_digest = method_tree_sha256(methods / "versions" / args.parent)
    candidate_digest = method_tree_sha256(methods / "versions" / args.version)
    if method_tree_sha256(methods / "main") != candidate_digest:
        raise GateError(f"main/ does not match versions/{args.version}: snapshot main/ before running the gate, "
                        "and do not edit it between screening and confirmation")
    line_number = len(log_lines) + 1

    if args.replicates is None:
        check_stacked_provisional(log_lines, args.parent)
        inputs = _gated_screening_inputs(methods, args.parent, args.version, profile, profile_sha, parent_digest, candidate_digest)
        main_measure, min_effect = inputs["measure"], inputs["min_effect"]
        disposition = get_disposition(main_measure["verdict"], None, "always")
        look_index: int | None = None
        plan: dict[str, Any] | None = None
        derived: dict[str, Any] | None = None
        created: Path | None = None
        if disposition == "provisional":
            if open_line is not None:
                raise StackedProvisional(
                    f"{open_line['version_id']} already holds the one open provisional decision (line {open_line['line']}); "
                    "replicate it before opening another"
                )
            deltas = paired_deltas(inputs["parent_scores"], inputs["candidate_scores"], direction)
            plan = confirmation_size(deltas, min_effect=min_effect, level=level, floor=int(conf["floor"]),
                                     cap=int(conf["max_seeds"]))
            if plan["exploratory"]:
                disposition = "revert"
            else:
                look_index = 1 + sum(1 for prior in log_lines if prior.get("replicates"))
                exclude = set(inputs["parent_scores"]) | suite_seeds_in_log(methods, log_lines)
                chosen = derive_seeds(key_hex=profile["replication_key"], rollout_id=profile["rollout_id"],
                                      candidate_digest=candidate_digest, look_index=look_index,
                                      size=int(plan["size"]), exclude=exclude)
                locator = f"results/{args.version}/replication/{SUITE_NAME}"
                created = evidence_path(methods, locator)
                suite_sha = write_suite(created, chosen, max_moves=int(conf["max_moves"]))
                derived = {"locator": locator, "sha256": suite_sha,
                           "derivation": {"algorithm": SEEDS_ALGORITHM, "rollout_id": profile["rollout_id"],
                                          "candidate_method_tree_sha256": candidate_digest, "look_index": look_index,
                                          "size": int(plan["size"]), "max_moves": int(conf["max_moves"])}}
        line = build_line(line_number=line_number, version_id=args.version, parent_id=args.parent, replicates=None,
                          main=main_measure, holdout=None, disposition=disposition, unit=profile["unit"],
                          direction=direction, resamples=resamples, seed=seed, min_effect=min_effect,
                          confirm_policy="always", profile_sha256=profile_sha, look_index=look_index,
                          parent_digest=parent_digest, candidate_digest=candidate_digest, sizing=plan, suite=derived)
        return line, created

    if args.replicates != args.version:
        raise GateError("a replication line must carry replicates equal to its own version_id")
    if open_line is None or open_line["version_id"] != args.version:
        raise GateError(f"no open provisional decision for {args.version} to replicate")
    if open_line["parent_id"] != args.parent:
        raise GateError(f"replication parent {args.parent} differs from the provisional line's parent {open_line['parent_id']}")
    open_suite = open_line.get("suite")
    open_sizing = open_line.get("sizing")
    if not isinstance(open_suite, dict) or not isinstance(open_sizing, dict) or open_line.get("look_index") is None:
        raise GateError("the open provisional line carries no confirmation plan; gated confirmation needs one")
    suite: dict[str, Any] = open_suite
    sizing: dict[str, Any] = open_sizing
    if open_line.get("parent_method_tree_sha256") != parent_digest:
        raise GateError(f"versions/{args.parent} changed after the screening that froze it")
    if open_line.get("candidate_method_tree_sha256") != candidate_digest:
        raise GateError(f"versions/{args.version} changed after it was frozen")
    # Re-verify the provisional line from its evidence rather than trusting it.
    for entry in open_line["evidence"]:
        if file_sha256(evidence_path(methods, entry["locator"])) != entry["sha256"]:
            raise GateError(f"screening evidence {entry['locator']} changed since the provisional line was written")
    inputs = _gated_screening_inputs(methods, args.parent, args.version, profile, profile_sha, parent_digest, candidate_digest)
    if not math.isclose(inputs["min_effect"], float(open_line["min_effect"]), rel_tol=0.0, abs_tol=1e-9):
        raise GateError("the provisional line's min_effect does not follow from the profile and the parent's visible result")
    deltas = paired_deltas(inputs["parent_scores"], inputs["candidate_scores"], direction)
    expected_sizing = confirmation_size(deltas, min_effect=float(open_line["min_effect"]), level=level,
                                        floor=int(conf["floor"]), cap=int(conf["max_seeds"]))
    if expected_sizing != sizing or sizing["exploratory"]:
        raise GateError("the provisional line's confirmation plan does not follow from its screening deltas")
    earlier = log_lines[: int(open_line["line"]) - 1]
    exclude = set(inputs["parent_scores"]) | suite_seeds_in_log(methods, earlier)
    expected_seeds = derive_seeds(key_hex=profile["replication_key"], rollout_id=profile["rollout_id"],
                                  candidate_digest=candidate_digest, look_index=int(open_line["look_index"]),
                                  size=int(sizing["size"]), exclude=exclude)
    suite_path = evidence_path(methods, suite["locator"])
    if not suite_path.is_file() or file_sha256(suite_path) != suite["sha256"]:
        raise GateError(f"confirmation suite missing or altered: {suite['locator']}")
    suite_seeds, suite_max_moves = read_suite(suite_path)
    if suite_seeds != expected_seeds or suite_max_moves != int(conf["max_moves"]):
        raise GateError("the confirmation suite does not re-derive from the key, the frozen candidate, and the look")
    derivation = suite.get("derivation")
    if derivation != {"algorithm": SEEDS_ALGORITHM, "rollout_id": profile["rollout_id"],
                      "candidate_method_tree_sha256": candidate_digest, "look_index": int(open_line["look_index"]),
                      "size": int(sizing["size"]), "max_moves": int(conf["max_moves"])}:
        raise GateError("the provisional line's suite derivation record does not match")
    min_effect = float(open_line["min_effect"])
    base = f"results/{args.version}/replication/"
    parent_locator, candidate_locator = base + "parent_result.json", base + "candidate_result.json"
    main_measure = measure(methods, parent_locator, candidate_locator, direction=direction, level=level,
                           resamples=resamples, seed=seed, min_effect=min_effect)
    receipts: list[dict[str, Any]] = list(inputs["receipts"])
    entries: list[dict[str, str]] = []
    for role, locator, digest in (("parent", parent_locator, parent_digest), ("candidate", candidate_locator, candidate_digest)):
        scores = load_scores(evidence_path(methods, locator))
        if set(scores) != set(suite_seeds):
            raise GateError(f"{role} confirmation result does not cover exactly the confirmation suite")
        receipt, entry = check_receipt(methods, locator, role=role, profile=profile, profile_sha=profile_sha,
                                       suite_sha=suite["sha256"], policy_digest=digest, games=len(suite_seeds))
        receipts.append(receipt)
        entries.append(entry)
    check_python_parity(receipts)
    main_measure["evidence"] = list(main_measure["evidence"]) + entries
    main_measure["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in main_measure["evidence"]}
    disposition = "keep" if main_measure["verdict"] == "clears" else "revert"
    line = build_line(line_number=line_number, version_id=args.version, parent_id=args.parent, replicates=args.version,
                      main=main_measure, holdout=None, disposition=disposition, unit=profile["unit"],
                      direction=direction, resamples=resamples, seed=seed, min_effect=min_effect,
                      confirm_policy="always", profile_sha256=profile_sha, look_index=int(open_line["look_index"]),
                      parent_digest=parent_digest, candidate_digest=candidate_digest, sizing=sizing, suite=suite)
    return line, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--methods", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--replicates", default=None)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--confirm", choices=CONFIRM_POLICIES, default=None)
    parser.add_argument("--parent-result", default=None)
    parser.add_argument("--candidate-result", default=None)
    parser.add_argument("--holdout-parent-result", default=None)
    parser.add_argument("--holdout-candidate-result", default=None)
    parser.add_argument("--direction", choices=("higher", "lower"), default=None)
    parser.add_argument("--level", type=float, default=None)
    parser.add_argument("--resamples", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--min-effect", type=float, default=None)
    parser.add_argument("--unit", default=None)
    args = parser.parse_args(argv)

    methods: Path = args.methods
    log_path = methods / LOG_NAME
    created: Path | None = None
    try:
        with log_lock(methods):
            log_lines = read_log(log_path)
            open_line = get_open_provisional(log_lines)
            if args.profile is not None:
                line, created = build_gated_line(args, methods, log_lines, open_line)
            else:
                line = build_replay_line(args, methods, log_lines, open_line)
            try:
                append_line(log_path, line)
            except OSError:
                if created is not None and created.exists():
                    created.unlink()
                raise
    except StackedProvisional as exc:
        print(f"gate refused: {exc}", file=sys.stderr)
        return 3
    except INPUT_ERRORS as exc:
        print(f"gate refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(line, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
