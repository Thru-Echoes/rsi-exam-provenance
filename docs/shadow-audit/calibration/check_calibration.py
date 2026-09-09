#!/usr/bin/env python3
"""Check the pre-registered false-keep criterion over calibration sidecars. Usage: check_calibration.py <dir> <max> <max_upper>.

Reads every ``<dir>/*best1.json`` and ``<dir>/*best3.json`` (both selection conditions are gated); for rows at effect
multiples 0 and 1 reports the false-keep probability and its exact one-sided 95 percent binomial (Clopper-Pearson) upper
bound, the same bound for every count including zero, and says whether every row is within the criterion. Each bound is
marginal to its cell; no simultaneous coverage across cells is claimed. Reads only; standard library only.
"""
import glob
import json
import math
import sys


def upper_bound(k: int, n: int, alpha: float = 0.05) -> float:
    """Smallest p with P[Binomial(n, p) <= k] <= alpha: the exact one-sided upper confidence bound, by bisection."""
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0

    def cdf(p: float) -> float:
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))

    low, high = k / n, 1.0
    for _ in range(60):
        mid = (low + high) / 2
        if cdf(mid) > alpha:
            low = mid
        else:
            high = mid
    return high


folder, limit, upper_limit = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
worst = 0.0
failures = []
checked = 0
print("| file | distribution | effect | false_keep | exact upper bound | trials | within |")
print("|---|---|---|---|---|---|---|")
for path in sorted(glob.glob(f"{folder}/*best1.json") + glob.glob(f"{folder}/*best3.json")):
    doc = json.load(open(path))
    rows = doc["rows"] if isinstance(doc, dict) else doc
    trials = int((doc.get("params") or {}).get("trials", 0)) if isinstance(doc, dict) else 0
    for row in rows:
        if float(row["effect_multiple"]) not in (0.0, 1.0) or row.get("false_keep") in (None, ""):
            continue
        p = float(row["false_keep"])
        n = trials or int(row.get("trials", 0) or 0)
        k = round(p * n)
        bound = upper_bound(k, n) if n else 1.0
        ok = p <= limit and bound <= upper_limit
        worst = max(worst, bound)
        checked += 1
        if not ok:
            failures.append((path, row["distribution"], row["effect_multiple"]))
        print(f"| {path.rsplit('/', 1)[-1]} | {row['distribution']} | {row['effect_multiple']} | {p:.4f} | {bound:.4f} | {n} | {'yes' if ok else 'NO'} |")
print(f"\ngated cells {checked}; largest exact upper bound {worst:.4f}; criterion {'MET' if not failures else 'NOT MET: ' + str(len(failures)) + ' rows'}")
sys.exit(0 if not failures else 1)
