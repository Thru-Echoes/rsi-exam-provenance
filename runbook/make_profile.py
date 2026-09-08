#!/usr/bin/env python3
"""Write a replay configuration (a task profile, rsi-exam-gate-profile/v1) for game2048_policy_search.

Inputs: --task-dir (the task directory holding environment/evaluate.py, environment/game2048.py and
environment/visible_seeds.json), --rollout-id, --output, and optionally --replication-key-hex (64 hex
characters; a fresh random key is generated when omitted), --max-seeds (the confirmation cap; the default
of 64 is a host CPU budget, four evaluations of at most 64 games each per pair), and --min-effect-fraction
(default 0.025 of the parent's visible mean).

Output: the profile JSON, sorted keys, which gate/task_profile.check_profile accepts, with the evaluator
and visible-suite digests read from the task files and the operator's rule filled in. It is written
exclusively at mode 600 inside a directory made mode 700, because it carries the replication key that
makes a confirmation suite re-derivable. For a shadow replay the profile is written after the rollout, so
the agent never had that key; it is a replay configuration, not a pre-registration. The schema also
requires audit_key_sha256; no audit suite exists, so the field carries the SHA-256 of the documented
literal "unused-shadow-audit-key-v1" and is reserved and non-secret.

Side effects: writes the output file and refuses to overwrite one. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gate"))

import task_profile  # noqa: E402
import treedigest  # noqa: E402

# Operator decisions for the real task. The floor is the sealed suite's size, the documented rule; the
# cap is a flag because it is a CPU budget.
MIN_EFFECT_FRACTION = 0.025
LEVEL = 0.9
RESAMPLES = 5000
BOOTSTRAP_SEED = 20260902
FLOOR = 16
MAX_SEEDS = 64
MAX_MOVES = 10000
CPU_SECONDS_PER_GAME = 225
EVALUATOR_FILES = ("evaluate.py", "game2048.py")
AUDIT_KEY_PLACEHOLDER = b"unused-shadow-audit-key-v1"


def get_profile(task_dir: Path, rollout_id: str, key_hex: str, *, max_seeds: int, min_effect_fraction: float) -> dict:
    """The profile document, with digests read from the task files. Pure apart from file reads."""
    env = task_dir / "environment"
    for name in (*EVALUATOR_FILES, "visible_seeds.json"):
        if not (env / name).is_file():
            raise SystemExit(f"task environment lacks {name}: {env}")
    return {
        "schema": task_profile.PROFILE_SCHEMA,
        "task": "game2048_policy_search",
        "rollout_id": rollout_id,
        "metric": "per_seed_2048_score",
        "unit": "game_score",
        "direction": "higher",
        "min_effect": {"kind": "fraction_of_parent_visible_mean", "fraction": min_effect_fraction},
        "level": LEVEL,
        "resamples": RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "confirm_policy": "always",
        "confirmation": {"floor": FLOOR, "max_seeds": max_seeds, "max_moves": MAX_MOVES,
                         "cpu_seconds_per_game": CPU_SECONDS_PER_GAME},
        "visible_suite_sha256": treedigest.file_sha256(env / "visible_seeds.json"),
        "replication_key": key_hex,
        "audit_key_sha256": hashlib.sha256(AUDIT_KEY_PLACEHOLDER).hexdigest(),
        "evaluator": {name: treedigest.file_sha256(env / name) for name in EVALUATOR_FILES},
    }


def write_private(path: Path, text: str) -> None:
    """Create a file exclusively at mode 600 inside a directory made mode 700. Raises FileExistsError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--rollout-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replication-key-hex", default=None)
    parser.add_argument("--max-seeds", type=int, default=MAX_SEEDS)
    parser.add_argument("--min-effect-fraction", type=float, default=MIN_EFFECT_FRACTION)
    args = parser.parse_args(argv)
    if args.output.exists():
        print(f"refused: output already exists: {args.output}", file=sys.stderr)
        return 2
    key_hex = args.replication_key_hex or secrets.token_hex(32)
    profile = get_profile(args.task_dir, args.rollout_id, key_hex, max_seeds=args.max_seeds,
                          min_effect_fraction=args.min_effect_fraction)
    try:
        task_profile.check_profile(profile)
    except task_profile.ProfileError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    write_private(args.output, json.dumps(profile, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "rollout_id": args.rollout_id, "max_seeds": args.max_seeds,
                      "min_effect_fraction": args.min_effect_fraction}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
