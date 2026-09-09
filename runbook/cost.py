#!/usr/bin/env python3
"""Price a finished harbor job from the harness's own per-message usage records.

Input: one or more harbor job directories. Reads every ``agent/sessions/**/*.jsonl`` under each
(the claude-code adapter's session records, the only files this script prices), sums the token
usage of every assistant record, and prices it at the rate card named by the ``RATES`` environment
variable: ``haiku``, ``sonnet`` or ``opus``, no default and nothing else. Output: a per-job table with token
totals, cost, agent wall clock from the records' timestamps, and cost per minute, then a total.

Fail loud, because the plan uses this number to stop a campaign: an unknown rate card, an
unreadable session file, a usage-bearing record that is not JSON or whose token counts are not
integers, a malformed timestamp, or a job with no usage records at all is a refusal with a named
reason and a non-zero exit. Nothing is skipped in silence.

Side effects: none. Reads only. Standard library only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

# USD per million tokens, (input, output), published rates as of RATE_CARD_DATE. Cache write is 1.25x
# input and cache read 0.10x input.
RATE_CARD_DATE = "2026-09-09"
RATE_CARDS = {"haiku": (1.00, 5.00), "sonnet": (2.00, 10.00), "opus": (5.00, 25.00)}
SESSION_GLOB = "**/agent/sessions/**/*.jsonl"
TOKEN_KEYS = {"input": "input_tokens", "output": "output_tokens", "cache_write": "cache_creation_input_tokens",
              "cache_read": "cache_read_input_tokens"}


class CostError(ValueError):
    """The job cannot be priced as asked. Exit 2."""


def get_usage(job_dir: Path) -> dict[str, Any]:
    """Sum token usage and collect timestamps across a job's session records. Raises CostError. Reads only."""
    totals = {key: 0 for key in TOKEN_KEYS}
    messages = 0
    stamps: list[dt.datetime] = []
    files = sorted(job_dir.glob(SESSION_GLOB))
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CostError(f"unreadable session file {path}: {exc.__class__.__name__}") from exc
        for number, line in enumerate(text.splitlines(), start=1):
            if '"usage"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CostError(f"{path}:{number}: usage-bearing line is not JSON") from exc
            if not isinstance(record, dict) or record.get("type") != "assistant":
                continue
            usage = (record.get("message") or {}).get("usage")
            if not isinstance(usage, dict):
                continue
            messages += 1
            for key, field in TOKEN_KEYS.items():
                value = usage.get(field, 0)
                if value is None:
                    value = 0
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise CostError(f"{path}:{number}: {field} is not a non-negative integer: {value!r}")
                totals[key] += value
            stamp = record.get("timestamp")
            if stamp is not None:
                try:
                    stamps.append(dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")))
                except ValueError as exc:
                    raise CostError(f"{path}:{number}: malformed timestamp {stamp!r}") from exc
    return {"tokens": totals, "messages": messages, "stamps": stamps, "files": len(files)}


def get_cost(tokens: dict[str, int], rates: str) -> float:
    """Price a token dict in USD under a named rate card. Pure function; raises CostError on an unknown card."""
    if rates not in RATE_CARDS:
        raise CostError(f"unknown RATES {rates!r}; choose one of {sorted(RATE_CARDS)}")
    rate_in, rate_out = RATE_CARDS[rates]
    return (tokens["input"] * rate_in + tokens["output"] * rate_out + tokens["cache_write"] * rate_in * 1.25
            + tokens["cache_read"] * rate_in * 0.10) / 1_000_000


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    try:
        rates = os.environ.get("RATES")
        if rates is None:
            raise CostError("set RATES to haiku, sonnet or opus; there is no default rate card")
        grand = 0.0
        for arg in argv:
            job = Path(arg)
            if not job.is_dir():
                raise CostError(f"not a directory: {job}")
            usage = get_usage(job)
            if not usage["messages"]:
                raise CostError(f"no assistant usage records under {job} ({usage['files']} session files)")
            cost = get_cost(usage["tokens"], rates)
            grand += cost
            print(f"\n=== {job} ===")
            print(f"  rate card          : {rates} (rates as of {RATE_CARD_DATE})")
            print(f"  session files      : {usage['files']}")
            print(f"  assistant messages : {usage['messages']:,}")
            for key in TOKEN_KEYS:
                print(f"  {key:19}: {usage['tokens'][key]:,}")
            print(f"  COST               : ${cost:.4f}")
            stamps = usage["stamps"]
            if len(stamps) >= 2:
                span = (max(stamps) - min(stamps)).total_seconds()
                if span > 0:
                    print(f"  agent wall clock   : {span / 60:.1f} min")
                    print(f"  RATE               : ${cost / (span / 60):.4f} / min  (${cost / (span / 3600):.2f} / hour)")
        print(f"\nTOTAL: ${grand:.4f}")
    except CostError as exc:
        print(f"cost refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
