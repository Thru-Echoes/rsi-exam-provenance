#!/usr/bin/env python3
"""Build the NANDA paper's bounded primary-result snapshot.

# Grounding: reconstructed

The parser is grounded in the committed A/B sources named by
``docs/campaign/2026-09-instrument-ab/manifest.md``. Haiku and Sonnet use the
machine-generated block tables in ``docs/shadow-audit/instrument-ab``. The
Opus block 1 uses the digest-bound hidden-evaluation rewards in its two
committed capsules. Opus blocks 2 and 3 use the pre-probe committed summary at
``docs/shadow-audit/pilots/pilot-8-preregistration.md:5-6`` because their
capsules and the Opus endpoint table were never committed. Record yield is
recomputed from the three stage ``records.md`` tables.

The script deliberately does not reconstruct missing Opus secondary results.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[4]
RESULTS_DIR = REPO / "ara" / "nanda-2026" / "evidence" / "results"

ENDPOINT_SOURCES = {
    "haiku": "docs/shadow-audit/instrument-ab/haiku/endpoints.md",
    "sonnet": "docs/shadow-audit/instrument-ab/sonnet/endpoints.md",
}
OPUS_SOURCE = "docs/shadow-audit/pilots/pilot-8-preregistration.md"
OPUS_BLOCK_1_CAPSULES = {
    "instrument": "docs/figures/sources/ab-opus-1-I/capsule.json",
    "helper": "docs/figures/sources/ab-opus-1-H/capsule.json",
}
RECORD_SOURCES = {
    stage: f"docs/shadow-audit/instrument-ab/{stage}/records.md"
    for stage in ("haiku", "sonnet", "opus")
}
STAGES_SOURCE = "docs/campaign/2026-09-instrument-ab/stages.json"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _read(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


def _source_entry(path: str, evidence_class: str) -> dict[str, str]:
    return {
        "path": path,
        "sha256": _sha256((REPO / path).read_bytes()),
        "evidence_class": evidence_class,
    }


def _verify_revision(paths: list[str], source_revision: str) -> None:
    for path in paths:
        completed = subprocess.run(
            ["git", "show", f"{source_revision}:{path}"],
            cwd=REPO,
            check=True,
            capture_output=True,
        )
        current = (REPO / path).read_bytes()
        if completed.stdout != current:
            raise ValueError(
                f"{path} does not match pinned source revision {source_revision}"
            )


def _table_rows(text: str, first_header: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    start = next(
        index for index, line in enumerate(lines)
        if line.strip().startswith(f"| {first_header} |")
    )
    headers = [cell.strip() for cell in lines[start].strip().strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[start + 2:]:
        if not line.strip().startswith("|"):
            break
        values = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(values) != len(headers):
            raise ValueError(f"table row has {len(values)} cells, expected {len(headers)}")
        rows.append(dict(zip(headers, values, strict=True)))
    return rows


def _endpoint_blocks(stage: str, path: str) -> list[dict[str, Any]]:
    rows = _table_rows(_read(path), "block")
    blocks: list[dict[str, Any]] = []
    for row in rows:
        instrument = Decimal(row["reward I"])
        helper = Decimal(row["reward H"])
        difference = instrument - helper
        blocks.append({
            "stage": stage,
            "block": int(row["block"]),
            "instrument_trial": row["instrument trial"],
            "helper_trial": row["helper trial"],
            "instrument_reward": str(instrument),
            "helper_reward": str(helper),
            "instrument_minus_helper": str(difference),
            "favors": "instrument" if difference > 0 else "helper" if difference < 0 else "tie",
            "evidence_path": path,
            "evidence_class": "machine_generated_endpoint_table",
            "precision": "source_precision",
        })
    return blocks


def _opus_blocks() -> list[dict[str, Any]]:
    text = _read(OPUS_SOURCE)
    match = re.search(
        r"instrument ([0-9.]+), ([0-9.]+), ([0-9.]+) against "
        r"([0-9.]+), ([0-9.]+), ([0-9.]+)",
        text,
    )
    if match is None:
        raise ValueError("Opus primary-reward summary not found")
    instrument = [Decimal(value) for value in match.groups()[:3]]
    helper = [Decimal(value) for value in match.groups()[3:]]
    blocks: list[dict[str, Any]] = []
    for index, (reward_i, reward_h) in enumerate(zip(instrument, helper, strict=True), 1):
        evidence_path = OPUS_SOURCE
        evidence_class = "committed_pre_probe_summary"
        precision = "rounded_to_3_decimals_in_source"
        extra_evidence: dict[str, Any] = {}
        if index == 1:
            capsules = {
                arm: json.loads(_read(path))
                for arm, path in OPUS_BLOCK_1_CAPSULES.items()
            }
            hidden = {
                arm: capsule["hidden_evaluation"]
                for arm, capsule in capsules.items()
            }
            for arm, evaluation in hidden.items():
                if evaluation.get("reward_locator") != "verifier/reward.json":
                    raise ValueError(f"Opus block 1 {arm} capsule lacks reward locator")
                if re.fullmatch(r"[0-9a-f]{64}", str(evaluation.get("reward_sha256", ""))) is None:
                    raise ValueError(f"Opus block 1 {arm} capsule lacks reward digest")
            reward_i = Decimal(str(hidden["instrument"]["reward"]))
            reward_h = Decimal(str(hidden["helper"]["reward"]))
            evidence_path = OPUS_BLOCK_1_CAPSULES["instrument"]
            evidence_class = "digest_bound_capsule_hidden_evaluation"
            precision = "source_precision"
            extra_evidence = {
                "paired_evidence_path": OPUS_BLOCK_1_CAPSULES["helper"],
                "instrument_reward_receipt_sha256": "sha256:" + hidden["instrument"]["reward_sha256"],
                "helper_reward_receipt_sha256": "sha256:" + hidden["helper"]["reward_sha256"],
            }
        difference = reward_i - reward_h
        blocks.append({
            "stage": "opus",
            "block": index,
            "instrument_trial": f"ab-opus-{index}-I",
            "helper_trial": f"ab-opus-{index}-H",
            "instrument_reward": str(reward_i),
            "helper_reward": str(reward_h),
            "instrument_minus_helper": str(difference),
            "favors": "instrument" if difference > 0 else "helper" if difference < 0 else "tie",
            "evidence_path": evidence_path,
            "evidence_class": evidence_class,
            "precision": precision,
            **extra_evidence,
        })
    return blocks


def _record_rows(stage: str, path: str) -> list[dict[str, Any]]:
    rows = _table_rows(_read(path), "rollout")
    result = []
    for row in rows:
        outcome = row["producer and verifier"]
        result.append({
            "stage": stage,
            "rollout": row["rollout"],
            "arm": row["arm"],
            "verified": outcome.startswith("integrity=pass coverage=complete"),
            "outcome": outcome,
            "evidence_path": path,
        })
    return result


def _mean_difference(blocks: list[dict[str, Any]]) -> str:
    values = [Decimal(block["instrument_minus_helper"]) for block in blocks]
    return str(sum(values) / Decimal(len(values)))


def build(source_revision: str, *, verify_revision: bool = True) -> dict[str, Any]:
    paths = [
        *ENDPOINT_SOURCES.values(),
        OPUS_SOURCE,
        *OPUS_BLOCK_1_CAPSULES.values(),
        *RECORD_SOURCES.values(),
        STAGES_SOURCE,
    ]
    if verify_revision:
        _verify_revision(paths, source_revision)

    stages_config = json.loads(_read(STAGES_SOURCE))
    blocks = [
        *_endpoint_blocks("haiku", ENDPOINT_SOURCES["haiku"]),
        *_endpoint_blocks("sonnet", ENDPOINT_SOURCES["sonnet"]),
        *_opus_blocks(),
    ]
    records = [
        row
        for stage, path in RECORD_SOURCES.items()
        for row in _record_rows(stage, path)
    ]

    stage_summaries: dict[str, Any] = {}
    for stage in ("haiku", "sonnet", "opus"):
        stage_blocks = [block for block in blocks if block["stage"] == stage]
        stage_summaries[stage] = {
            "planned_blocks": stages_config[stage]["blocks"],
            "observed_blocks": len(stage_blocks),
            "favors_instrument": sum(block["favors"] == "instrument" for block in stage_blocks),
            "favors_helper": sum(block["favors"] == "helper" for block in stage_blocks),
            "ties": sum(block["favors"] == "tie" for block in stage_blocks),
            "mean_instrument_minus_helper": _mean_difference(stage_blocks),
            "mean_precision": "approximate_from_mixed_precision_inputs" if stage == "opus" else "source_precision",
        }

    verified = [record for record in records if record["verified"]]
    failures = [record for record in records if not record["verified"]]
    arms: dict[str, Any] = {}
    for arm, name in (("I", "instrument"), ("H", "helper")):
        arm_records = [record for record in records if record["arm"] == arm]
        arms[name] = {
            "trials": len(arm_records),
            "verified_records": sum(record["verified"] for record in arm_records),
        }

    return {
        "schema_version": "rsi-exam-provenance/nanda-paper-results/v1",
        "status": "provisional_primary_complete_secondary_partial",
        "source_revision": source_revision,
        "generated_by": "ara/nanda-2026/src/execution/build_paper_results.py",
        "sources": [
            *(_source_entry(path, "machine_generated_endpoint_table") for path in ENDPOINT_SOURCES.values()),
            *(_source_entry(path, "digest_bound_capsule_hidden_evaluation")
              for path in OPUS_BLOCK_1_CAPSULES.values()),
            _source_entry(OPUS_SOURCE, "committed_pre_probe_summary"),
            *(_source_entry(path, "machine_generated_record_table") for path in RECORD_SOURCES.values()),
            _source_entry(STAGES_SOURCE, "preregistered_stage_configuration"),
        ],
        "study_boundary": {
            "task": "game2048_policy_search",
            "design": "blocked instrument-versus-helper comparison",
            "program_status": "modified-program reduced-window runs",
            "official_rsi_exam_result": False,
            "population_rate_claimed": False,
        },
        "blocks": blocks,
        "primary_summary": {
            "blocks": len(blocks),
            "favors_instrument": sum(block["favors"] == "instrument" for block in blocks),
            "favors_helper": sum(block["favors"] == "helper" for block in blocks),
            "ties": sum(block["favors"] == "tie" for block in blocks),
            "aggregate_mean_instrument_minus_helper": _mean_difference(blocks),
            "aggregate_mean_precision": "approximate_because_opus_inputs_are_rounded",
            "by_stage": stage_summaries,
        },
        "record_yield": {
            "trials": len(records),
            "verified_records": len(verified),
            "arms": arms,
            "failures": failures,
        },
        "release_blockers": [
            "Opus blocks 2 and 3 remain summary-backed and rounded; bind their raw reward receipts before the final freeze.",
            "Opus secondary endpoint, spend, and complete sealed-retrospective tables are not committed.",
            "Do not convert the ten observed blocks into an efficacy, significance, or population-rate claim.",
        ],
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["primary_summary"]
    record_yield = result["record_yield"]
    lines = [
        "# Generated paper results",
        "",
        f"**Status:** `{result['status']}`",
        "",
        f"**Pinned input revision:** `{result['source_revision']}`",
        "",
        "The primary direction count covers all ten preregistered blocks. Haiku and Sonnet come from machine-generated endpoint tables. Opus block 1 comes from digest-bound capsule hidden-evaluation fields; Opus blocks 2 and 3 come from a committed pre-probe summary rounded to three decimals. Their raw reward receipts and the remaining Opus secondary tables remain freeze blockers.",
        "",
        "## Primary endpoint by block",
        "",
        "| Stage | Block | Instrument reward | Helper reward | I - H | Favors | Evidence class |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for block in result["blocks"]:
        lines.append(
            f"| {block['stage'].title()} | {block['block']} | {block['instrument_reward']} | "
            f"{block['helper_reward']} | {block['instrument_minus_helper']} | {block['favors']} | "
            f"{block['evidence_class']} |"
        )
    lines.extend([
        "",
        "## Bounded summary",
        "",
        f"- Observed blocks: {summary['blocks']}.",
        f"- Favor instrument: {summary['favors_instrument']}.",
        f"- Favor helper: {summary['favors_helper']}.",
        f"- Ties: {summary['ties']}.",
        "- Interpretation: direction counts for these modified-program, reduced-window runs; no rate, efficacy, or significance claim.",
        "",
        "## Record yield recomputed from per-trial tables",
        "",
        f"- All arms: {record_yield['verified_records']} verified records from {record_yield['trials']} started trials.",
        f"- Instrument: {record_yield['arms']['instrument']['verified_records']} of {record_yield['arms']['instrument']['trials']}.",
        f"- Helper: {record_yield['arms']['helper']['verified_records']} of {record_yield['arms']['helper']['trials']}.",
        "- Explicit refusals:",
    ])
    for failure in record_yield["failures"]:
        lines.append(f"  - `{failure['rollout']}` ({failure['arm']}): `{failure['outcome']}`.")
    lines.extend([
        "",
        "## Release blockers",
        "",
        *(f"- {blocker}" for blocker in result["release_blockers"]),
        "",
        "This file is generated. Do not edit aggregate values by hand.",
    ])
    return "\n".join(lines)


def _serialized(result: dict[str, Any]) -> tuple[str, str]:
    return json.dumps(result, indent=2, sort_keys=True) + "\n", render_markdown(result) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = build(args.source_revision)
    json_text, markdown_text = _serialized(result)
    outputs = {
        RESULTS_DIR / "paper-results.json": json_text,
        RESULTS_DIR / "paper-results.md": markdown_text,
    }
    if args.check:
        stale = [str(path.relative_to(REPO)) for path, content in outputs.items()
                 if not path.exists() or path.read_text(encoding="utf-8") != content]
        if stale:
            print("stale generated outputs: " + ", ".join(stale), file=sys.stderr)
            return 1
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
