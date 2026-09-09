#!/usr/bin/env python3
"""Draw the order of one A/B stage's trials: blocks of two, one instrument (I) and one helper (H) trial each, the
orders within blocks counterbalanced (as many I-first as H-first blocks; with an odd number of blocks the last one by
a coin) and shuffled by a seeded generator, recorded in the manifest before the first trial.

Usage: draw_order.py <stage> <blocks> <seed>. Prints the trial labels in run order, one per line, as
``<block>-<arm>`` (for example ``1-H`` then ``1-I``). Pure function of its arguments; standard library only.
"""
import random
import sys


def draw(stage: str, blocks: int, seed: int) -> list[str]:
    rng = random.Random(f"{seed}:{stage}")
    patterns = [("I", "H")] * (blocks // 2) + [("H", "I")] * (blocks // 2)
    if blocks % 2:
        patterns.append(("I", "H") if rng.random() < 0.5 else ("H", "I"))
    rng.shuffle(patterns)
    order: list[str] = []
    for block, (first, second) in enumerate(patterns, start=1):
        order += [f"{block}-{first}", f"{block}-{second}"]
    return order


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: draw_order.py <stage> <blocks> <seed>")
    print("\n".join(draw(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))))
