#!/usr/bin/env python3
"""Decision gate for RSI-Exam rollouts: a paired bootstrap interval on per-seed deltas.

Reads the task self-check result files for a parent version and a candidate
version, pairs the per-seed scores, bootstraps a confidence interval on the
mean delta, applies the keep / revert / provisional rule, and appends one JSON
line to ``<methods>/decisions.jsonl`` (contract: docs/decision-log-contract.md,
schema id ``rsi-exam-decision-log/v1``).

Inputs (CLI): ``--methods`` (the methods directory), ``--version``, ``--parent``,
optional ``--replicates`` (equal to ``--version``; resolves that version's open
provisional decision on fresh evidence), ``--parent-result`` and
``--candidate-result`` (locators relative to the methods directory; defaults are
``results/<id>/visible_result.json``, or ``results/<version>/replication/
{parent,candidate}_result.json`` for a replication), ``--holdout-parent-result``
and ``--holdout-candidate-result`` (optional second suite; defaults under
``results/<version>/holdout/``). Evidence never lives under ``versions/`` or
``main/``: the sealed grader rejects any non-Python file in the policy tree,
so result files must stay outside every snapshot and outside ``main/``, ``--direction`` (``higher`` or ``lower``:
the metric's native sense; deltas are oriented so a positive value favours
the candidate), ``--level``, ``--resamples``, ``--seed``, ``--min-effect``
(must be at or above zero), ``--unit``.

Outputs: exit 0 with the appended line printed to stdout; exit 2 on a missing
or malformed input or a contract violation (nothing written); exit 3 when the
log already carries an unresolved provisional decision that this line would
build on or duplicate (nothing written).

Side effects: appends to ``<methods>/decisions.jsonl``. Standard library only.
The environment variable ``DECIDE_FIXED_TIMESTAMP`` overrides the timestamp so
fixtures are reproducible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
from datetime import UTC, datetime
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA = "rsi-exam-decision-log/v1"
LOG_NAME = "decisions.jsonl"
METHOD_NAME = "percentile_bootstrap"
ALGORITHM = "rsi-exam-gate/percentile-bootstrap/1"
STATISTIC = "mean_paired_delta"


class GateError(ValueError):
    """A gate input is missing, malformed, or inconsistent. Nothing is written (exit 2)."""


class StackedProvisional(GateError):
    """The log holds an unresolved provisional decision this line would stack on (exit 3)."""


def sha256_of(path: Path) -> str:
    """Hex SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_locator(locator: str) -> str:
    """A locator is a canonical relative POSIX path outside the policy trees.

    Rules: no leading slash, no backslash, no percent escape, no drive prefix, no ``..`` or empty
    segment, no control characters, and never under ``versions/`` or ``main/`` (the sealed grader
    rejects non-Python files in the policy tree, so evidence must stay out of every snapshot).
    """
    bad = (not locator or locator.startswith("/") or "\\" in locator or "%" in locator or ":" in locator
           or any(ord(c) < 32 for c in locator) or any(part in ("..", "", ".") for part in locator.split("/")))
    if bad:
        raise GateError(f"bad locator: {locator!r}")
    top = locator.split("/", 1)[0]
    if top in ("versions", "main"):
        raise GateError(f"evidence locator must not live in the policy tree: {locator!r}")
    return locator


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
    alpha = (1.0 - level) / 2.0
    low = means[int(alpha * resamples)]
    high = means[int((1.0 - alpha) * resamples) - 1]
    return low, high


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


def get_disposition(verdict: str, holdout_verdict: str | None) -> str:
    """Keep only a clear win that also clears on the held-out set when one was supplied."""
    if verdict == "below":
        return "revert"
    if verdict == "clears" and holdout_verdict in (None, "clears"):
        return "keep"
    return "provisional"


def read_log(path: Path) -> list[dict[str, Any]]:
    """Existing decision-log lines, validated as JSON objects of this schema with consecutive line numbers."""
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
    parent_path = methods / check_locator(parent_locator)
    candidate_path = methods / check_locator(candidate_locator)
    deltas = paired_deltas(load_scores(parent_path), load_scores(candidate_path), direction)
    low, high = bootstrap_interval(deltas, level=level, resamples=resamples, seed=seed)
    estimate = sum(deltas) / len(deltas)
    evidence = [
        {"role": "parent", "locator": parent_locator, "sha256": sha256_of(parent_path)},
        {"role": "candidate", "locator": candidate_locator, "sha256": sha256_of(candidate_path)},
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
               main: dict[str, Any], holdout: dict[str, Any] | None, unit: str, direction: str,
               resamples: int, seed: int, min_effect: float) -> dict[str, Any]:
    """Assemble one decision-log line from a measurement (and an optional held-out measurement)."""
    holdout_verdict = holdout["verdict"] if holdout else None
    if replicates is not None:
        if replicates != version_id:
            raise GateError("a replication line must carry replicates equal to its own version_id")
        disposition = "keep" if main["verdict"] == "clears" and holdout_verdict in (None, "clears") else "revert"
    else:
        disposition = get_disposition(main["verdict"], holdout_verdict)
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
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--methods", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--replicates", default=None)
    parser.add_argument("--parent-result", default=None)
    parser.add_argument("--candidate-result", default=None)
    parser.add_argument("--holdout-parent-result", default=None)
    parser.add_argument("--holdout-candidate-result", default=None)
    parser.add_argument("--direction", choices=("higher", "lower"), default="higher")
    parser.add_argument("--level", type=float, default=0.9)
    parser.add_argument("--resamples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--min-effect", type=float, default=0.0)
    parser.add_argument("--unit", default="game_score")
    args = parser.parse_args(argv)

    methods: Path = args.methods
    if args.replicates is not None:
        parent_locator = args.parent_result or f"results/{args.version}/replication/parent_result.json"
        candidate_locator = args.candidate_result or f"results/{args.version}/replication/candidate_result.json"
    else:
        parent_locator = args.parent_result or f"results/{args.parent}/visible_result.json"
        candidate_locator = args.candidate_result or f"results/{args.version}/visible_result.json"
    log_path = methods / LOG_NAME
    try:
        if not math.isfinite(args.min_effect) or args.min_effect < 0.0:
            raise GateError("min_effect must be a finite number at or above zero")
        log_lines = read_log(log_path)
        open_line = get_open_provisional(log_lines)
        if args.replicates is not None:
            if open_line is None or open_line["version_id"] != args.replicates:
                raise GateError(f"no open provisional decision for {args.replicates} to replicate")
            if open_line["parent_id"] != args.parent:
                raise GateError(f"replication parent {args.parent} differs from the provisional line's parent {open_line['parent_id']}")
        else:
            check_stacked_provisional(log_lines, args.parent)
        main_measure = measure(methods, parent_locator, candidate_locator, direction=args.direction,
                               level=args.level, resamples=args.resamples, seed=args.seed,
                               min_effect=args.min_effect)
        holdout = None
        if args.holdout_parent_result or args.holdout_candidate_result:
            if not (args.holdout_parent_result and args.holdout_candidate_result):
                raise GateError("both held-out result files are required when one is given")
            holdout = measure(methods, args.holdout_parent_result, args.holdout_candidate_result,
                              direction=args.direction, level=args.level, resamples=args.resamples,
                              seed=args.seed, min_effect=args.min_effect)
            holdout["evidence"] = [dict(e, role="holdout-" + e["role"]) for e in holdout["evidence"]]
            holdout["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in holdout["evidence"]}
        line = build_line(line_number=len(log_lines) + 1, version_id=args.version, parent_id=args.parent,
                          replicates=args.replicates, main=main_measure, holdout=holdout, unit=args.unit,
                          direction=args.direction, resamples=args.resamples, seed=args.seed,
                          min_effect=args.min_effect)
        if args.replicates is None and line["disposition"] == "provisional" and open_line is not None:
            raise StackedProvisional(
                f"{open_line['version_id']} already holds the one open provisional decision (line {open_line['line']}); "
                "replicate it before opening another"
            )
    except StackedProvisional as exc:
        print(f"gate refused: {exc}", file=sys.stderr)
        return 3
    except GateError as exc:
        print(f"gate refused: {exc}", file=sys.stderr)
        return 2

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, sort_keys=True) + "\n")
    print(json.dumps(line, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
