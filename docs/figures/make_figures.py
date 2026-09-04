#!/usr/bin/env python3
"""Emit the five explainer figures as standalone SVG files for the repository.

Inputs: none (geometry inline). Output: docs/figures/*.svg under the repository root given as
argv[1] (default: the repository that contains this script). Run: python3 docs/figures/make_figures.py Side effects: writes five files. Standalone means: xmlns declared, embedded <style>
with literal colours, a white background, a legend inside the drawing, no width/height
attributes (viewBox only), so GitHub renders them from a relative image link.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

INK, MUTED, LINE = "#1f2933", "#5f6b7a", "#d9dee5"
STYLE = f"""<style>
text {{ font: 9pt -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; fill: {INK}; }}
.lbl {{ font-size: 8.5pt; }} .small {{ font-size: 7.5pt; fill: {MUTED}; }} .title {{ font-size: 8.5pt; font-weight: 600; }}
.rsi {{ fill: #eceff3; stroke: #6B7684; stroke-width: 1.3; }}
.ours {{ fill: #dbe6fb; stroke: #3B6FD4; stroke-width: 1.5; }}
.pp {{ fill: #fbe9d3; stroke: #C2731B; stroke-width: 1.5; }}
.keep {{ fill: #ddf1e6; stroke: #1B7F5A; stroke-width: 1.5; }}
.revert {{ fill: #f6dfd8; stroke: #B7472A; stroke-width: 1.5; }}
.panel {{ fill: #fff; stroke: {LINE}; }}
.arrow {{ stroke: {INK}; stroke-width: 1.2; fill: none; marker-end: url(#ah); }}
.arrowd {{ stroke: {MUTED}; stroke-width: 1; fill: none; stroke-dasharray: 3 3; marker-end: url(#ahm); }}
</style>"""
DEFS = ('<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#1f2933"/></marker>'
        '<marker id="ahm" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#5f6b7a"/></marker></defs>')
LEGEND_LABELS = {"rsi": "RSI-Exam, unchanged", "ours": "This repository (standard library)", "pp": "ProofPress",
                 "keep": "Keep", "revert": "Revert"}


def svg_open(width: int, height: int, label: str) -> list[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{label}">',
            STYLE, DEFS, f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>']


def box(x, y, w, h, cls, title, lines, title_dy=18, line_dy=13):
    """A rounded box with a centred title and small lines under it."""
    cx = x + w / 2
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" class="{cls}"/>',
           f'<text x="{cx}" y="{y + title_dy}" text-anchor="middle" class="lbl">{title}</text>']
    for i, line in enumerate(lines):
        out.append(f'<text x="{cx}" y="{y + title_dy + 14 + i * line_dy}" text-anchor="middle" class="small">{line}</text>')
    return "\n".join(out)


def legend(y: int, keys: list[str], x: int = 20) -> str:
    """A row of swatches with labels, drawn inside the figure."""
    out, cursor = [], x
    for key in keys:
        out.append(f'<rect x="{cursor}" y="{y - 9}" width="11" height="11" rx="2" class="{key}"/>')
        label = LEGEND_LABELS[key]
        out.append(f'<text x="{cursor + 16}" y="{y}" class="small">{label}</text>')
        cursor += 16 + int(len(label) * 5.6) + 22
    return "\n".join(out)


def fig_rollout() -> str:
    s = svg_open(700, 300, "RSI-Exam rollout anatomy")
    s.append('<rect x="10" y="20" width="440" height="222" rx="6" class="panel"/>')
    s.append('<text x="20" y="38" class="title">Inside the sandbox (no network, up to 12 h): the agent\'s loop</text>')
    s.append(box(24, 52, 130, 48, "rsi", "methods/main/", ["policy.py, the method"]))
    s.append(box(176, 52, 150, 48, "rsi", "selfcheck.py", ["8 visible seeds, one score each"]))
    s.append(box(348, 52, 90, 48, "rsi", "visible_result", [".json"]))
    s.append('<path d="M154,76 L174,76" class="arrow"/><path d="M326,76 L346,76" class="arrow"/>')
    s.append(box(24, 132, 190, 60, "rsi", "experiment_log.md", ["one line per version:", "parent, score, kept or reverted"]))
    s.append(box(244, 132, 190, 60, "rsi", "versions/vN/", ["a snapshot of main/", "for every logged version"]))
    s.append('<path d="M89,100 L89,130" class="arrow"/><path d="M393,100 L393,130" class="arrow"/>')
    s.append('<path d="M244,162 L214,162" class="arrowd"/>')
    s.append('<text x="24" y="216" class="small">A revert restores main/ from a snapshot. A keep makes vN the parent of everything that follows.</text>')
    s.append('<text x="24" y="230" class="small">Dashed: the log line names the snapshot it describes.</text>')
    s.append('<rect x="466" y="20" width="224" height="222" rx="6" class="panel"/>')
    s.append('<text x="476" y="38" class="title">After the run: the job directory</text>')
    s.append(box(480, 52, 196, 46, "rsi", "artifacts/app/methods/", ["main, versions, log, results"]))
    s.append(box(480, 108, 196, 46, "rsi", "agent/trajectory.json", ["full transcript, bound by digest"]))
    s.append(box(480, 164, 196, 60, "rsi", "verifier/reward.json", ["sealed grader: 16 seeds,", "reward from 0 to 1"]))
    s.append('<path d="M450,131 L464,131" class="arrow"/>')
    s.append('<text x="20" y="266" class="small">Only Python files may live under main/ (anything else scores 0.0); bytecode caches are ignored by the grader.</text>')
    s.append(legend(288, ["rsi"]))
    s.append('</svg>')
    return "\n".join(s)


def fig_reward() -> str:
    # ratio r = score / starter score; reference at r = 4 (illustrative)
    def reward(r):
        if r <= 1:
            return 0.0
        if r <= 4:
            return 0.6 * math.log(r) / math.log(4)
        return 0.6 + 0.4 * (1 - math.exp(-math.log(r / 4)))

    def X(r):
        return 60 + (math.log2(r) + 1) / 5 * 580

    def Y(v):
        return 180 - v * 150

    pts = []
    r = 0.5
    while r <= 16.0001:
        pts.append(f"{X(r):.1f},{Y(reward(r)):.1f}")
        r *= 1.05
    s = svg_open(700, 230, "How a raw score becomes a reward")
    s.append(f'<line x1="60" y1="{Y(0)}" x2="660" y2="{Y(0)}" stroke="{LINE}"/><line x1="60" y1="{Y(0)}" x2="60" y2="{Y(1)}" stroke="{LINE}"/>')
    for v in (0.3, 0.6, 0.8, 1.0):
        s.append(f'<line x1="60" y1="{Y(v):.1f}" x2="660" y2="{Y(v):.1f}" stroke="#eceff3"/>')
        s.append(f'<text x="52" y="{Y(v) + 3:.1f}" text-anchor="end" class="small">{v:g}</text>')
    s.append(f'<text x="52" y="{Y(0) + 3}" text-anchor="end" class="small">0</text>')
    s.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#3B6FD4" stroke-width="2"/>')
    marks = [(1, "starter's score", "0"), (2, "2x", "0.3"), (4, "reference method's score", "0.6"), (8, "8x", "0.8"), (16, "16x", "0.9")]
    for r, xl, yl in marks:
        x, y = X(r), Y(reward(r))
        s.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{Y(0)}" stroke="#8A94A6" stroke-dasharray="3 3"/>')
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#fff" stroke="#3B6FD4" stroke-width="2"/>')
        s.append(f'<text x="{x + 7:.1f}" y="{y - 6:.1f}" class="small">{yl}</text>')
        s.append(f'<text x="{x:.1f}" y="{Y(0) + 14}" text-anchor="middle" class="small">{xl}</text>')
    s.append('<text x="60" y="18" class="title">Reward on one sealed seed, as a function of the raw score (ratio to the starter\'s score, log scale)</text>')
    s.append('<text x="360" y="222" text-anchor="middle" class="small">In this illustration the reference method scores 4 times the starter; each task and seed has its own two anchors.</text>')
    s.append('</svg>')
    return "\n".join(s)


def fig_components() -> str:
    s = svg_open(700, 452, "What this repository adds and how it attaches")
    s.append('<rect x="10" y="14" width="680" height="162" rx="6" class="panel"/>')
    s.append('<text x="20" y="32" class="title">Inside the loop (gated rollouts only): the decision gate</text>')
    s.append(box(24, 46, 140, 46, "rsi", "results/vP/", ["parent's per-seed scores"]))
    s.append(box(24, 110, 140, 46, "rsi", "results/vN/", ["candidate's per-seed scores"]))
    s.append(box(190, 58, 180, 82, "ours", "decide.py (the gate)", ["pair by seed, bootstrap interval,", "rule: keep, revert, or confirm first", "standard library, no network"]))
    s.append('<path d="M164,69 L188,88" class="arrow"/><path d="M164,133 L188,112" class="arrow"/>')
    s.append(box(396, 58, 180, 82, "ours", "decisions.jsonl", ["one line per decision: version,", "parent, interval, verdict, action,", "digests of both result files"]))
    s.append('<path d="M370,99 L394,99" class="arrow"/>')
    s.append(box(600, 58, 88, 82, "rsi", "experiment_log", ["the agent logs", "the gate's action"]))
    s.append('<path d="M576,99 L598,99" class="arrowd"/>')
    s.append('<rect x="10" y="192" width="680" height="238" rx="6" class="panel"/>')
    s.append('<text x="20" y="210" class="title">After the run (any rollout): record, verify, report, share</text>')
    s.append(box(24, 226, 140, 64, "rsi", "job directory", ["snapshots, log, results,", "decisions.jsonl, reward.json"]))
    s.append(box(190, 226, 160, 64, "ours", "build_capsule.py", ["the provenance record: every", "version and decision, by digest"]))
    s.append(box(376, 226, 160, 64, "ours", "verify_capsule.py", ["offline: digests, lineage,", "coverage, recomputed intervals"]))
    s.append(box(562, 226, 126, 64, "ours", "evidence report", ["one table per rollout", "for a human auditor"]))
    s.append('<path d="M164,258 L188,258" class="arrow"/><path d="M350,258 L374,258" class="arrow"/><path d="M536,258 L560,258" class="arrow"/>')
    s.append(box(190, 322, 160, 64, "ours", "trace_from_decisions.py", ["the log as a TRACE session:", "one decision event per line"]))
    s.append(box(376, 322, 160, 64, "ours", "TRACE document", ["agent proposes, gate resolves,", "confidence block per decision"]))
    s.append(box(562, 322, 126, 64, "pp", "ProofPress", ["evidence import keeps", "four fields"]))
    s.append('<path d="M94,290 L94,354 L188,354" class="arrow"/><path d="M350,354 L374,354" class="arrow"/><path d="M536,354 L560,354" class="arrow"/>')
    s.append('<text x="20" y="416" class="small">Dashed: the agent copies the gate\'s action into the experiment log RSI-Exam already requires.</text>')
    s.append(legend(442, ["rsi", "ours", "pp"]))
    s.append('</svg>')
    return "\n".join(s)


def fig_rule() -> str:
    s = svg_open(700, 292, "The gate rule: screening and confirmation")
    s.append(box(10, 20, 186, 62, "rsi", "Screen on the 8 visible seeds", ["paired deltas, bootstrap interval,", "compared with the minimum effect"]))
    s.append(box(228, 20, 130, 62, "ours", "Interval entirely", ["below zero?"], title_dy=28, line_dy=14))
    s.append('<path d="M196,51 L226,51" class="arrow"/>')
    s.append(box(410, 20, 150, 62, "revert", "REVERT", ["an action, not proof of harm"]))
    s.append('<path d="M358,51 L408,51" class="arrow"/><text x="383" y="44" text-anchor="middle" class="small">yes</text>')
    s.append(box(228, 116, 170, 62, "ours", "Freeze the candidate", ["record its method digest;", "derive fresh seeds from it"]))
    s.append('<path d="M293,82 L293,114" class="arrow"/><text x="306" y="101" class="small">no</text>')
    s.append(box(228, 200, 170, 58, "ours", "Confirm on fresh seeds", ["parent vs candidate, paired,", "16 or more seeds"]))
    s.append('<path d="M313,178 L313,198" class="arrow"/>')
    s.append(box(430, 200, 124, 58, "keep", "KEEP", ["clears the minimum effect"]))
    s.append(box(576, 200, 114, 58, "revert", "REVERT", ["inconclusive or below"]))
    s.append('<path d="M398,229 L428,229" class="arrow"/><text x="413" y="222" text-anchor="middle" class="small">clears</text>')
    s.append('<path d="M554,229 L574,229" class="arrow"/><text x="564" y="222" text-anchor="middle" class="small">else</text>')
    s.append(legend(282, ["rsi", "ours", "keep", "revert"]))
    s.append('</svg>')
    return "\n".join(s)


def fig_example() -> str:
    s = svg_open(700, 150, "Eight paired deltas with the bootstrap interval")
    s.append(f'<line x1="60" y1="70" x2="660" y2="70" stroke="{LINE}"/>')
    s.append('<line x1="193" y1="30" x2="193" y2="110" stroke="#8A94A6" stroke-dasharray="3 3"/><text x="193" y="124" text-anchor="middle" class="small">0</text>')
    s.append('<text x="60" y="124" text-anchor="middle" class="small">-400</text><text x="326" y="124" text-anchor="middle" class="small">+400</text><text x="460" y="124" text-anchor="middle" class="small">+800</text><text x="593" y="124" text-anchor="middle" class="small">+1200</text>')
    s.append('<g fill="#3B6FD4"><circle cx="630" cy="70" r="5"/><circle cx="467" cy="70" r="5"/><circle cx="330" cy="70" r="5"/><circle cx="260" cy="70" r="5"/><circle cx="213" cy="70" r="5"/><circle cx="130" cy="70" r="5"/><circle cx="93" cy="70" r="5"/><circle cx="117" cy="61" r="5"/></g>')
    s.append('<rect x="183" y="88" width="205" height="8" rx="2" fill="#3B6FD4" opacity="0.35"/><line x1="280" y1="84" x2="280" y2="100" stroke="#3B6FD4" stroke-width="2"/>')
    s.append('<text x="280" y="112" text-anchor="middle" class="small">mean +260; 90% interval from -30 to +584</text>')
    s.append('<text x="60" y="20" class="title">Eight paired deltas (candidate minus parent, one per seed, in game-score units)</text>')
    s.append('<text x="630" y="52" text-anchor="middle" class="small">+1310</text><text x="467" y="52" text-anchor="middle" class="small">+820</text><text x="112" y="46" text-anchor="middle" class="small">three seeds got worse</text>')
    s.append('</svg>')
    return "\n".join(s)


FIGURES = {
    "rollout-anatomy.svg": fig_rollout,
    "reward-mapping.svg": fig_reward,
    "components.svg": fig_components,
    "gate-rule.svg": fig_rule,
    "worked-example.svg": fig_example,
}


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2]
    out = root / "docs" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        (out / name).write_text(fn() + "\n", encoding="utf-8")
        print("wrote", out / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
