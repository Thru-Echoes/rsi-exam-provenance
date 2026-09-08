#!/usr/bin/env python3
"""Simulate the gate's rule on synthetic paired deltas and tabulate its operating characteristics.

This is not evidence about any rollout. The deltas are drawn from a distribution the caller names, so
every number describes the rule under stated assumptions: how often the screening interval covers the
true effect, how often screening says clears, below or inconclusive, how often the confirmation plan
exceeds the cap (exploratory, which the gate reverts without confirming), and how often the gate finally
keeps, including when the true effect is under the minimum effect (a false keep). It exists so that a
profile's floor, cap and minimum effect are chosen with their consequences in view, and so that the
bootstrap the gate runs is exercised at the sample sizes it actually sees.

Per trial: draw ``--screening-seeds`` paired deltas from the distribution centred on the true effect;
the screening interval is gate/decide.bootstrap_interval, the code the gate runs, with the contract's
verdict; the confirmation plan is gate/seeds.confirmation_size under the profile's floor and cap; when
the plan is not exploratory, draw ``size`` fresh deltas and compute the confirmation interval; the
disposition follows the gated rule: below at screening reverts, exploratory reverts, a confirmation that
clears keeps, anything else reverts.

Two planning rules can be compared. ``current`` is the contract's rule: the confirmation is planned so
that c * z * s / sqrt(n) < min_effect with c = 2 (the contract writes it as z * s / sqrt(n) <
min_effect / 2). ``estimate-aware`` is a proposed change: the same inequality against
e = max(min_effect, estimate - min_effect), where estimate is the screening mean. ``--margin-factor``
varies c for either rule. Nothing in the gate changes when this script runs; both rules are computed
here through gate/seeds.confirmation_size.

Distributions, each with standard deviation ``--sd`` around the true effect: ``normal``; ``skewed``, a
shifted exponential; ``heavy``, Student t with three degrees of freedom. ``--catastrophe-prob p`` with
``--catastrophe-delta d`` replaces each drawn delta by d with probability p, the seed on which the
candidate collapses. ``--select-best-of K`` draws K screening samples and keeps the one with the
largest mean before planning, the optimistic selection an agent performs on reused visible seeds.
True effects are given as multiples of the minimum effect.

Reported per cell: coverage of the screening interval (the deltas' true mean inside it) and of its
lower bound (the true mean at or above it; with a catastrophe mixture the true mean is not the
nominal effect and the table shows both), the screening verdict probabilities, the probability the
plan was exploratory, the median planned size, the probability of a final keep with its binomial
standard error, and the false-keep probability when the true mean is at or under the minimum effect.

CLI: --min-effect (absolute, in score units), --sd, --level, --resamples, --floor, --cap, --trials,
--seed, --distributions, --effects, --screening-seeds, --rule, --margin-factor, --catastrophe-prob,
--catastrophe-delta, --select-best-of, --output (a markdown table, also printed; a JSON sidecar with
the same rows is written beside it). Standard library only; pure apart from writing the outputs.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decide  # noqa: E402
import seeds  # noqa: E402

DISTRIBUTIONS = ("normal", "skewed", "heavy")
RULES = ("current", "estimate-aware")


def draw(rng: random.Random, distribution: str, sd: float, effect: float, count: int,
         catastrophe_prob: float = 0.0, catastrophe_delta: float = 0.0) -> list[float]:
    """``count`` paired deltas with mean ``effect`` and standard deviation ``sd``, each replaced by the
    catastrophe delta with the given probability. Pure given the rng."""
    if distribution == "normal":
        out = [effect + rng.gauss(0.0, sd) for _ in range(count)]
    elif distribution == "skewed":
        out = [effect + sd * (rng.expovariate(1.0) - 1.0) for _ in range(count)]
    elif distribution == "heavy":
        out = []
        for _ in range(count):
            z = rng.gauss(0.0, 1.0)
            chi = sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(3))
            out.append(effect + (sd / math.sqrt(3.0)) * z / math.sqrt(chi / 3.0))
    else:
        raise ValueError(f"unknown distribution {distribution!r}")
    if catastrophe_prob > 0.0:
        out = [catastrophe_delta if rng.random() < catastrophe_prob else value for value in out]
    return out


def planning_effect(rule: str, min_effect: float, estimate: float) -> float:
    """The effect the confirmation is planned against under each rule. Pure function."""
    if rule == "current":
        return min_effect
    if rule == "estimate-aware":
        return max(min_effect, estimate - min_effect)
    raise ValueError(f"unknown rule {rule!r}")


def binomial_se(p: float, n: float) -> float:
    return math.sqrt(p * (1.0 - p) / n)


def simulate(*, distribution: str, effect_multiple: float, min_effect: float, sd: float, level: float,
             resamples: int, floor: int, cap: int, trials: int, screening_seeds: int, rule: str,
             rng: random.Random, margin_factor: float = 2.0, catastrophe_prob: float = 0.0,
             catastrophe_delta: float = 0.0, select_best_of: int = 1) -> dict[str, Any]:
    """One cell of the table: the rule's operating characteristics at one true effect. Pure given the rng.

    The margin factor c enters through the minimum effect handed to the gate's planning function,
    which applies c = 2: passing 2 * e / c reproduces c * z * s / sqrt(n) < e exactly.
    """
    effect = effect_multiple * min_effect
    # With a catastrophe mixture the deltas' true mean is not the nominal effect; coverage and the
    # false-keep classification compare against the mean the draws actually have.
    true_mean = (1.0 - catastrophe_prob) * effect + catastrophe_prob * catastrophe_delta
    counts: Counter[str] = Counter()
    planned: list[int] = []
    covered = lower_covered = 0
    for _ in range(trials):
        samples = [draw(rng, distribution, sd, effect, screening_seeds, catastrophe_prob, catastrophe_delta)
                   for _ in range(max(1, select_best_of))]
        deltas = max(samples, key=lambda sample: sum(sample))
        low, high = decide.bootstrap_interval(deltas, level=level, resamples=resamples, seed=rng.getrandbits(31))
        covered += int(low <= true_mean <= high)
        lower_covered += int(low <= true_mean)
        verdict = decide.get_verdict((low, high), min_effect)
        counts["screen_" + verdict] += 1
        if verdict == "below":
            counts["revert"] += 1
            continue
        estimate = sum(deltas) / len(deltas)
        target = planning_effect(rule, min_effect, estimate) * 2.0 / margin_factor
        plan = seeds.confirmation_size(deltas, min_effect=target, level=level, floor=floor, cap=cap)
        planned.append(int(plan["planned"]))
        if plan["exploratory"]:
            counts["exploratory"] += 1
            counts["revert"] += 1
            continue
        fresh = draw(rng, distribution, sd, effect, int(plan["size"]), catastrophe_prob, catastrophe_delta)
        low2, high2 = decide.bootstrap_interval(fresh, level=level, resamples=resamples, seed=rng.getrandbits(31))
        verdict2 = decide.get_verdict((low2, high2), min_effect)
        counts["confirm_" + verdict2] += 1
        counts["keep" if verdict2 == "clears" else "revert"] += 1
    n = float(trials)
    p_keep = counts["keep"] / n
    return {
        "distribution": distribution, "effect_multiple": effect_multiple, "true_effect": effect, "true_mean": true_mean,
        "coverage": covered / n, "lower_coverage": lower_covered / n,
        "p_clears": counts["screen_clears"] / n, "p_below": counts["screen_below"] / n,
        "p_inconclusive": counts["screen_inconclusive"] / n, "p_exploratory": counts["exploratory"] / n,
        "median_planned": sorted(planned)[len(planned) // 2] if planned else None,
        "p_keep": p_keep, "p_keep_se": binomial_se(p_keep, n),
        "false_keep": p_keep if true_mean <= min_effect else None,
    }


def render(rows: list[dict[str, Any]], params: dict[str, Any]) -> str:
    """The markdown table with its parameters stated above it. Pure function."""
    head = ("Simulated operating characteristics of the gate rule. Synthetic paired deltas; not evidence about "
            "any rollout. Parameters: " + ", ".join(f"{k} {v}" for k, v in params.items()) + ".\n\n")
    cols = ("distribution", "effect_multiple", "coverage", "lower_coverage", "p_clears", "p_below",
            "p_inconclusive", "p_exploratory", "median_planned", "p_keep", "p_keep_se", "false_keep")
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in rows:
        cells = []
        for col in cols:
            value = row[col]
            cells.append("" if value is None else f"{value:.3f}" if isinstance(value, float) and col != "effect_multiple"
                         else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return head + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-effect", type=float, required=True)
    parser.add_argument("--sd", type=float, required=True)
    parser.add_argument("--level", type=float, default=0.9)
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--floor", type=int, default=16)
    parser.add_argument("--cap", type=int, default=64)
    parser.add_argument("--trials", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--distributions", default="normal,skewed,heavy")
    parser.add_argument("--effects", default="0,1,2,5")
    parser.add_argument("--screening-seeds", type=int, default=8)
    parser.add_argument("--rule", choices=RULES, default="current")
    parser.add_argument("--margin-factor", type=float, default=2.0)
    parser.add_argument("--catastrophe-prob", type=float, default=0.0)
    parser.add_argument("--catastrophe-delta", type=float, default=0.0)
    parser.add_argument("--select-best-of", type=int, default=1)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if (args.min_effect <= 0 or args.sd <= 0 or args.trials < 1 or args.resamples < 1 or args.screening_seeds < 2
            or args.margin_factor <= 0 or not 0.0 <= args.catastrophe_prob < 1.0 or args.select_best_of < 1):
        print("calibrate refused: min_effect, sd and margin factor must be positive, trials and resamples at least "
              "1, screening seeds at least 2, catastrophe probability in [0, 1), select-best-of at least 1",
              file=sys.stderr)
        return 2
    distributions = [d.strip() for d in args.distributions.split(",") if d.strip()]
    effects = [float(e) for e in args.effects.split(",") if e.strip()]
    if any(d not in DISTRIBUTIONS for d in distributions):
        print(f"calibrate refused: distributions must be among {DISTRIBUTIONS}", file=sys.stderr)
        return 2
    rng = random.Random(args.seed)
    rows = [simulate(distribution=d, effect_multiple=e, min_effect=args.min_effect, sd=args.sd, level=args.level,
                     resamples=args.resamples, floor=args.floor, cap=args.cap, trials=args.trials,
                     screening_seeds=args.screening_seeds, rule=args.rule, rng=rng, margin_factor=args.margin_factor,
                     catastrophe_prob=args.catastrophe_prob, catastrophe_delta=args.catastrophe_delta,
                     select_best_of=args.select_best_of)
            for d in distributions for e in effects]
    params = {"rule": args.rule, "margin_factor": args.margin_factor, "min_effect": args.min_effect, "sd": args.sd,
              "level": args.level, "resamples": args.resamples, "floor": args.floor, "cap": args.cap,
              "trials": args.trials, "screening_seeds": args.screening_seeds, "select_best_of": args.select_best_of,
              "catastrophe_prob": args.catastrophe_prob, "catastrophe_delta": args.catastrophe_delta,
              "seed": args.seed, "max_binomial_se": round(0.5 / math.sqrt(args.trials), 4)}
    text = render(rows, params)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        sidecar = args.output.with_suffix(".json")
        sidecar.write_text(json.dumps({"params": params, "rows": rows}, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
