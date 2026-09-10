#!/usr/bin/env python3
"""The task profile: the per-rollout file that fixes what the agent may not choose.

Schema ``rsi-exam-gate-profile/v1``. The profile fixes the metric's direction and unit, the minimum
effect (absolute, or a fraction of the parent's visible mean resolved at screening), the interval
level, the bootstrap resamples and seed, the confirmation suite bounds, the digest of the task's
visible seed file, the replication key, the digest of the audit key kept outside the sandbox, and
the digests of the two evaluator files. A profile always means confirmation on fresh seeds
(``confirm_policy`` is ``always``); the weaker screening-only rule exists only in replay mode,
without a profile. The gate records the profile's file digest on every line, and the post-rollout
verifier compares it with the digest the operator mounted, so a substituted profile is visible.

Exports ``check_profile(profile)`` (returns the same dict, raises ``ProfileError``),
``load_profile(path) -> (profile, sha256_hex)``, and ``resolve_min_effect(profile, parent_scores)``.
Pure functions; standard library only.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeGuard

from treedigest import file_sha256

PROFILE_SCHEMA = "rsi-exam-gate-profile/v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROFILE_CONFIRM_POLICY = "always"
MIN_EFFECT_KINDS = ("absolute", "fraction_of_parent_visible_mean")
DIRECTIONS = ("higher", "lower")
EVALUATOR_FILES = ("evaluate.py", "game2048.py")
CONFIRMATION_KEYS = ("floor", "max_seeds", "max_moves", "cpu_seconds_per_game")
PLANNING_RULES = ("min-effect", "estimate-aware")   # profile.confirmation.planning_rule; absent means min-effect


class ProfileError(ValueError):
    """The profile is missing, malformed, or violates a rule. Nothing proceeds."""


def _is_number(value: object) -> TypeGuard[float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_hex64(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and HEX64.match(value) is not None


def check_profile(profile: Any) -> dict[str, Any]:
    """Validate every rule of the schema; return the profile unchanged. Raises ``ProfileError``."""
    if not isinstance(profile, dict):
        raise ProfileError("profile must be a JSON object")
    p: dict[str, Any] = profile
    if p.get("schema") != PROFILE_SCHEMA:
        raise ProfileError(f"profile.schema must be {PROFILE_SCHEMA}")
    for key in ("task", "rollout_id", "metric", "unit"):
        text = p.get(key)
        if not isinstance(text, str) or not text.strip():
            raise ProfileError(f"profile.{key} must be a non-empty string")
    if p.get("direction") not in DIRECTIONS:
        raise ProfileError("profile.direction must be 'higher' or 'lower'")
    min_effect = p.get("min_effect")
    if not isinstance(min_effect, dict) or min_effect.get("kind") not in MIN_EFFECT_KINDS:
        raise ProfileError("profile.min_effect.kind must be 'absolute' or 'fraction_of_parent_visible_mean'")
    if min_effect["kind"] == "absolute":
        value = min_effect.get("value")
        if not _is_number(value) or value <= 0.0:
            raise ProfileError("profile.min_effect.value must be a finite number above zero")
    else:
        fraction = min_effect.get("fraction")
        if not _is_number(fraction) or not 0.0 < fraction < 1.0:
            raise ProfileError("profile.min_effect.fraction must lie strictly between 0 and 1")
    level = p.get("level")
    if not _is_number(level) or not 0.0 < level < 1.0:
        raise ProfileError("profile.level must lie strictly between 0 and 1")
    resamples = p.get("resamples")
    if not _is_int(resamples) or resamples < 1000:
        raise ProfileError("profile.resamples must be an integer of at least 1000")
    if not _is_int(p.get("bootstrap_seed")):
        raise ProfileError("profile.bootstrap_seed must be an integer")
    if p.get("confirm_policy") != PROFILE_CONFIRM_POLICY:
        raise ProfileError("profile.confirm_policy must be 'always'; the screening-only rule exists only in replay mode")
    confirmation = p.get("confirmation")
    if not isinstance(confirmation, dict) or set(confirmation) - {"planning_rule"} != set(CONFIRMATION_KEYS):
        raise ProfileError(f"profile.confirmation must have exactly the keys {', '.join(CONFIRMATION_KEYS)}"
                           " (and optionally planning_rule)")
    if confirmation.get("planning_rule", PLANNING_RULES[0]) not in PLANNING_RULES:
        raise ProfileError(f"profile.confirmation.planning_rule must be one of {', '.join(PLANNING_RULES)}")
    bounds: dict[str, int] = {}
    for key in CONFIRMATION_KEYS:
        count = confirmation.get(key)
        if not _is_int(count) or count < 1:
            raise ProfileError(f"profile.confirmation.{key} must be a positive integer")
        bounds[key] = count
    if bounds["floor"] < 2:
        raise ProfileError("profile.confirmation.floor must be at least 2")
    if bounds["max_seeds"] < bounds["floor"]:
        raise ProfileError("profile.confirmation.max_seeds must be at least the floor")
    if not _is_hex64(p.get("visible_suite_sha256")):
        raise ProfileError("profile.visible_suite_sha256 must be 64 lowercase hex characters")
    if not _is_hex64(p.get("replication_key")):
        raise ProfileError("profile.replication_key must be 64 lowercase hex characters")
    if not _is_hex64(p.get("audit_key_sha256")):
        raise ProfileError("profile.audit_key_sha256 must be 64 lowercase hex characters")
    evaluator = p.get("evaluator")
    if (not isinstance(evaluator, dict) or set(evaluator) != set(EVALUATOR_FILES)
            or not all(_is_hex64(v) for v in evaluator.values())):
        raise ProfileError("profile.evaluator must map exactly evaluate.py and game2048.py to 64-hex digests")
    return p


def load_profile(path: Path) -> tuple[dict[str, Any], str]:
    """Read, validate, and digest a profile file. Raises ``ProfileError`` on any problem."""
    if not path.is_file():
        raise ProfileError(f"profile not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError(f"profile is not valid JSON: {path}: {exc}") from exc
    return check_profile(data), file_sha256(path)


def resolve_min_effect(profile: Mapping[str, Any], parent_scores: Mapping[int, float]) -> float:
    """The minimum effect in the metric's units for one decision.

    ``absolute`` returns the profile's value. ``fraction_of_parent_visible_mean`` multiplies the
    fraction by the mean of the parent's visible per-seed scores, which must be positive; the
    resolved number is recorded on the screening line and reused unchanged by its confirmation.
    """
    rule = profile["min_effect"]
    if rule["kind"] == "absolute":
        return float(rule["value"])
    if not parent_scores:
        raise ProfileError("fraction_of_parent_visible_mean needs parent scores")
    mean = sum(parent_scores.values()) / len(parent_scores)
    if not math.isfinite(mean) or mean <= 0.0:
        raise ProfileError("fraction_of_parent_visible_mean needs a positive parent mean")
    return float(rule["fraction"]) * mean


def resolve_planning_rule(profile: Mapping[str, Any]) -> str:
    """The planning rule the profile selects; ``min-effect`` when it names none. Pure function."""
    rule = profile["confirmation"].get("planning_rule", PLANNING_RULES[0])
    if rule not in PLANNING_RULES:
        raise ProfileError(f"profile.confirmation.planning_rule must be one of {', '.join(PLANNING_RULES)}")
    return str(rule)
