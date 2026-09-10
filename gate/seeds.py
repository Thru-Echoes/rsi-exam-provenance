#!/usr/bin/env python3
"""Fresh confirmation suites and the confirmation-size planning rule.

Algorithm ``rsi-exam-gate/hmac-seeds/1``: seed_k is the first four bytes of
HMAC-SHA256(key, "<rollout_id>|<candidate_method_tree_sha256>|<look_index>|<counter>") read as a
big-endian integer with the top bit cleared (1 <= seed < 2**31), for counter = 0, 1, 2, ...; a value
of zero, a value already in the suite, or a value in the exclusion set is skipped and the counter
advances. A suite is therefore a deterministic function of the committed key, the rollout, the
frozen candidate, and the look, and the gate re-derives it at confirmation. Anyone holding the key
can re-derive it, including the rollout agent: the derivation makes freshness checkable after the
fact, it does not hide the seeds. Compliance is measured, not assumed.

Planning rule: with s the sample standard deviation of the screening deltas and z the normal
quantile for the interval level, the planned suite size is the smallest n with z * s / sqrt(n)
below half the planning effect, at least ``floor``. Under the accepted rule (``min-effect``) the
planning effect is the minimum effect. Under the ``estimate-aware`` rule, which a profile may
select, it is the larger of the minimum effect and the screening mean less the minimum effect, so
a candidate whose screening estimate is far above the minimum effect plans the size needed to
tell that estimate from the minimum effect rather than the size needed to resolve the minimum
effect itself. Either way it is a normal-approximation planning size computed from screening data,
not a guarantee about the realized bootstrap interval. When the profile's cap is below the
planned size the plan is ``exploratory`` and the gate does not open a confirmation: an
under-planned confirmation is never allowed to keep.

Exports ``derive_seeds``, ``confirmation_size`` (with ``PLANNING_RULES``), ``write_suite`` (creates one file exclusively),
``read_suite``, and a CLI. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any

SEEDS_ALGORITHM = "rsi-exam-gate/hmac-seeds/1"
SIZING_RULE = "normal-approximation planning size from screening SD: smallest n with z*s/sqrt(n) < min_effect/2"
ESTIMATE_AWARE_RULE = ("normal-approximation planning size from screening SD against e = max(min_effect, "
                       "screening_mean - min_effect): smallest n with z*s/sqrt(n) < e/2")
PLANNING_RULES = ("min-effect", "estimate-aware")
MAX_COUNTER = 1_000_000


class SeedsError(ValueError):
    """A suite cannot be derived, sized, written, or read as asked."""


def derive_seeds(*, key_hex: str, rollout_id: str, candidate_digest: str, look_index: int, size: int,
                 exclude: set[int]) -> list[int]:
    """The confirmation seeds for one look (see the module docstring)."""
    if size < 1:
        raise SeedsError("size must be at least 1")
    if look_index < 1:
        raise SeedsError("look_index must be at least 1")
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise SeedsError("key must be hexadecimal") from exc
    prefix = f"{rollout_id}|{candidate_digest}|{look_index}|".encode("utf-8")
    seeds: list[int] = []
    counter = 0
    while len(seeds) < size:
        if counter >= MAX_COUNTER:
            raise SeedsError("seed derivation did not converge; the exclusion set is too large")
        digest = hmac.new(key, prefix + str(counter).encode("utf-8"), hashlib.sha256).digest()
        counter += 1
        seed = int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
        if seed == 0 or seed in exclude or seed in seeds:
            continue
        seeds.append(seed)
    return seeds


def confirmation_size(deltas: list[float], *, min_effect: float, level: float, floor: int, cap: int,
                      rule: str = "min-effect") -> dict[str, Any]:
    """The planning size and whether the cap makes the plan exploratory; every input and output is recorded.

    ``rule`` is ``min-effect`` (the accepted rule; the output is exactly what it always was) or
    ``estimate-aware`` (the output also carries ``planning_rule``, ``planning_effect`` and
    ``screening_mean``, so a reader can tell the two plans apart and recompute either).
    """
    if rule not in PLANNING_RULES:
        raise SeedsError(f"unknown planning rule {rule!r}; choose one of {', '.join(PLANNING_RULES)}")
    if not min_effect > 0.0:
        raise SeedsError("min_effect must be above zero to size a confirmation suite")
    if floor < 2 or cap < floor:
        raise SeedsError("floor must be at least 2 and cap at least floor")
    if not 0.0 < level < 1.0:
        raise SeedsError("level must lie strictly between 0 and 1")
    sd = statistics.stdev(deltas) if len(deltas) >= 2 else 0.0
    mean = statistics.fmean(deltas) if deltas else 0.0
    effect = min_effect if rule == "min-effect" else max(min_effect, mean - min_effect)
    z = statistics.NormalDist().inv_cdf(0.5 + level / 2.0)
    planned = floor if sd == 0.0 else max(floor, math.floor((2.0 * z * sd / effect) ** 2) + 1)
    size = min(planned, cap)
    out: dict[str, Any] = {"rule": SIZING_RULE if rule == "min-effect" else ESTIMATE_AWARE_RULE, "size": size,
                           "planned": planned, "floor": floor, "cap": cap, "exploratory": size < planned,
                           "screening_sd": sd, "z": z}
    if rule != "min-effect":
        out.update({"planning_rule": rule, "planning_effect": effect, "screening_mean": mean})
    return out


def suite_bytes(seeds: list[int], *, max_moves: int) -> bytes:
    """The canonical bytes of a suite file."""
    return (json.dumps({"max_moves": max_moves, "seeds": seeds}, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_suite(path: Path, seeds: list[int], *, max_moves: int) -> str:
    """Create the suite file exclusively (never overwrite); return the hex SHA-256 of its bytes."""
    payload = suite_bytes(seeds, max_moves=max_moves)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise SeedsError(f"suite file already exists: {path}") from exc
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    return hashlib.sha256(payload).hexdigest()


def read_suite(path: Path) -> tuple[list[int], int]:
    """Seeds and max_moves of a suite file, in the shape the task evaluator reads."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        seeds = [int(s) for s in data["seeds"]]
        max_moves = int(data.get("max_moves", 10000))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise SeedsError(f"malformed suite file {path}: {exc}") from exc
    if not seeds or len(set(seeds)) != len(seeds):
        raise SeedsError(f"suite must contain unique seeds: {path}")
    return seeds, max_moves


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive and write a fresh seed suite (rsi-exam-gate/hmac-seeds/1).")
    parser.add_argument("--key-hex", required=True)
    parser.add_argument("--rollout", required=True)
    parser.add_argument("--candidate-digest", required=True)
    parser.add_argument("--look-index", type=int, required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--max-moves", type=int, default=10000)
    parser.add_argument("--exclude", type=int, nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        chosen = derive_seeds(key_hex=args.key_hex, rollout_id=args.rollout, candidate_digest=args.candidate_digest,
                              look_index=args.look_index, size=args.size, exclude=set(args.exclude))
        digest = write_suite(args.output, chosen, max_moves=args.max_moves)
    except SeedsError as exc:
        print(f"seeds refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"algorithm": SEEDS_ALGORITHM, "size": len(chosen), "sha256": digest, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
