#!/usr/bin/env python3
"""Render one rollout's decisions as an animated SVG, a still SVG and, on request, a GIF.

Two modes share one renderer:

    before  the agent decided alone; the record was built and verified after the run and the sealed
            retrospective, scored afterwards, says which decisions the sealed seeds disagreed with
    now     the rollout ran under the instrument: every keep the agent proposed was screened on the public
            seeds and confirmed on fresh seeds or overruled as it happened, then finalize checked safety

Inputs are captured files; nothing in the figure is invented for it:

    --sealed      the rollout's sealed-retrospective report (schema rsi-exam-sealed-retrospective/v1):
                  versions with their recorded status, parent, sealed delta against the parent and reward
    --helper-log  the helper's methods/experiment_log.md (instrument rollouts): the agent's change lines, the
                  public-suite scores, the gate's lines and the agent's proposals, copied verbatim
    --rollout, --model, --program, --window, --date, --finalize, --record-verified: caption facts

Each ruling gets a plain-language line rendered from the fields of the gate's recorded line (verdict, estimate,
interval, seeds, plan and cap), with the gate's own line shown beneath it.

Outputs: <out>/<name>.svg (animated, loops; light and dark styling), <out>/<name>-still.svg (the last frame),
and with --gif <gif-dir>/<name>.gif rendered through a headless Chromium (needs the playwright and Pillow
packages; the SVGs need only the standard library).

Side effects: writes the files named above. Run from the repository root:
    python3 docs/figures/make_instrument_animation.py --mode now --sealed <report.json> --helper-log <log.md> ...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

W = 1200
PAD = 44
LEFT_W = 300
AXIS_X = PAD + LEFT_W + 30
TEXT_X = AXIS_X + 26
SEALED_X = W - PAD - 196
ROW_TOP = 248
LINE = 17
CHAR = 6.3            # average glyph width at 12 px, used to fit text before a chip
FADE_IN = 0.35
MIN_EFFECT_FRACTION = 0.025


@dataclass
class Row:
    """One version of the rollout, every value read from the inputs."""

    version: str
    parent: str
    status: str
    change: str
    visible: float | None
    parent_visible: float | None
    proposal: str
    gate: str
    note: str
    delta: float | None
    pos: int | None
    neg: int | None
    reward: float | None
    parent_sealed: float | None

    @property
    def gate_kind(self) -> str:
        if self.gate.startswith("keep"):
            return "keep"
        if self.gate.startswith("revert") or self.gate.startswith("not consulted;"):
            return "revert"
        return "none"

    @property
    def decided(self) -> str:
        """The disposition that held: the gate's when it ruled, else the recorded status."""
        if self.gate_kind != "none":
            return self.gate_kind
        return "revert" if self.status == "reverted" else "keep"

    @property
    def sealed_kind(self) -> str:
        """agrees | disagrees | within | none: the sealed delta read against the disposition that held."""
        if self.delta is None or self.parent_sealed is None:
            return "none"
        threshold = MIN_EFFECT_FRACTION * self.parent_sealed
        if abs(self.delta) <= threshold:
            return "within"
        favourable = self.delta > 0
        return "agrees" if favourable == (self.decided == "keep") else "disagrees"


def parse_helper_log(text: str) -> dict[str, dict[str, str]]:
    """Sections `## vN` with `- key: value` lines, verbatim."""
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in text.splitlines():
        head = re.match(r"^## (\S+)\s*$", line)
        if head:
            current = sections.setdefault(head.group(1), {})
            continue
        item = re.match(r"^- ([a-z][a-z0-9 ]*?): (.*)$", line)
        if item and current is not None:
            current[item.group(1)] = item.group(2).strip()
    return sections


def score_of(log: dict[str, str]) -> float | None:
    """The public-suite mean from a helper log section's score line, when present."""
    if "score" not in log:
        return None
    try:
        return float(log["score"].split()[0])
    except ValueError:
        return None


def get_rows(report: dict, helper: dict[str, dict[str, str]]) -> list[Row]:
    """Project the report's versions (and the helper's lines for them) into rows, baseline excluded."""
    means = {v["version_id"]: v.get("sealed_mean") for v in report["versions"]}
    visible = {v["version_id"]: v.get("visible_score") for v in report["versions"]}
    rows: list[Row] = []
    for v in report["versions"]:
        if v.get("status") == "baseline":
            continue
        parents = v.get("parent_ids") or []
        parent = parents[0] if parents else ""
        log = helper.get(v["version_id"], {})
        delta = v.get("delta_vs_parent") or {}
        change = re.sub(r"^v\d+[a-z]?:\s*", "", log.get("change", ""))
        vis = score_of(log)
        pvis = score_of(helper.get(parent, {})) if parent else None
        rows.append(Row(
            version=v["version_id"], parent=parent, status=v.get("status", ""),
            change=change, visible=vis if vis is not None else visible.get(v["version_id"]),
            parent_visible=pvis if pvis is not None else (visible.get(parent) if parent else None),
            proposal=log.get("agent proposed", ""), gate=log.get("gate", ""), note=log.get("agent note", ""),
            delta=delta.get("mean"), pos=delta.get("positive"), neg=delta.get("negative"),
            reward=v.get("reward"), parent_sealed=means.get(parent) if parent else None,
        ))
    if not rows:
        raise ValueError("the report has no versions beyond the baseline; refusing to draw an empty timeline")
    return rows


def wrap(text: str, limit: int) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > limit:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return lines


def fit(text: str, width: float) -> str:
    """Cut text to the given width at a word boundary, marking the cut."""
    limit = int(width / CHAR)
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(" ", 1)[0]
    return cut + "…"


def fmt(x: float | None, signed: bool = False) -> str:
    if x is None:
        return "not measured"
    s = f"{abs(x):,.0f}"
    if signed:
        return ("+" if x >= 0 else "-") + s
    return ("-" if x < 0 else "") + s


def gloss(gate: str) -> str:
    """A plain-language line rendered from the fields of the gate's recorded line; empty when there is no ruling."""
    m = re.search(r"estimate ([+-]?[\d.]+), interval \[([-\d.]+), ([-\d.]+)\], minimum effect [\d.]+, (\d+) seeds", gate)
    numbers = ""
    if m:
        est, lo, hi, seeds = float(m.group(1)), float(m.group(2)), float(m.group(3)), int(m.group(4))
        numbers = f"mean {fmt(est, signed=True)}, interval {fmt(lo)} to {fmt(hi)} over {seeds} seeds"
    plan = re.search(r"the plan needs (\d+) fresh seeds and the cap is (\d+)", gate)
    if gate.startswith("revert at screening"):
        if plan:
            return (f"Too close to call on the public seeds ({numbers}): confirming it would need {int(plan.group(1)):,} fresh "
                    f"seeds and the cap is {plan.group(2)}. Reverted.")
        return f"Worse on the public seeds ({numbers}). Reverted."
    if gate.startswith("keep, confirmed"):
        return f"Better on the public seeds, then confirmed on fresh seeds the agent never saw ({numbers}). Kept."
    if gate.startswith("revert at confirmation"):
        return f"Looked better on the public seeds, but the fresh seeds did not confirm it ({numbers}). Reverted."
    if gate.startswith("not consulted (the agent reverted)"):
        return "The agent reverted on its own after reading the gate's preview."
    if "refused for safety" in gate:
        reason = re.search(r"\((.*)\)", gate)
        return f"Refused before any ruling: the policy failed the safety check ({reason.group(1) if reason else 'see below'}). Reverted."
    if "would run past the close-out mark" in gate:
        return "Refused: its confirmation would not finish before the window closes. Reverted."
    return ""


def chip_width(label: str, fs: int = 11) -> float:
    return len(label) * fs * 0.6 + 16


def chip(x: float, y: float, label: str, kind: str, mono: bool = False) -> tuple[str, float]:
    fs = 11
    w = chip_width(label, fs)
    cls = ' class="mono"' if mono else ""
    svg = (f'<g><rect x="{x:.1f}" y="{y - fs - 1}" width="{w:.1f}" height="{fs + 7}" rx="{(fs + 7) / 2}" '
           f'fill="var(--c-{kind})" fill-opacity="0.13" stroke="var(--c-{kind})" stroke-opacity="0.6" stroke-width="1"/>'
           f'<text x="{x + 8:.1f}" y="{y}" font-size="{fs}" font-weight="650"{cls} fill="var(--c-{kind})">{escape(label)}</text></g>')
    return svg, w


def text(x: float, y: float, s: str, fill: str = "var(--ink)", size: float = 12, weight: str = "", cls: str = "", anchor: str = "") -> str:
    attrs = f' font-weight="{weight}"' if weight else ""
    attrs += f' class="{cls}"' if cls else ""
    attrs += f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}"{attrs} fill="{fill}">{escape(s)}</text>'


class Scene:
    """Elements with the second they appear; renders as an animated SVG, a still, or a frame at a time."""

    def __init__(self) -> None:
        self.items: list[tuple[float, str]] = []
        self.static: list[str] = []

    def add(self, at: float, svg: str) -> None:
        self.items.append((at, svg))

    def events(self) -> list[float]:
        return sorted({at for at, _ in self.items})

    def render(self, head: str, height: int, when: float | None, cycle: float) -> str:
        """when=None: the looping animation; when=inf: the still; a number: the frame at that second."""
        css: list[str] = []
        body: list[str] = list(self.static)
        for i, (at, svg) in enumerate(self.items):
            if when is None:
                a = at / cycle * 100
                b = (at + FADE_IN) / cycle * 100
                hold = (cycle - 0.5) / cycle * 100
                css.append(f"@keyframes e{i}{{0%,{a:.2f}%{{opacity:0;transform:translateX(-14px)}}"
                           f"{b:.2f}%,{hold:.2f}%{{opacity:1;transform:none}}100%{{opacity:0;transform:translateX(-14px)}}}}")
                body.append(f'<g style="animation:e{i} {cycle}s linear infinite">{svg}</g>')
            else:
                alpha = min(1.0, max(0.0, (when - at) / FADE_IN))
                if alpha <= 0:
                    continue
                shift = -14 * (1 - alpha)
                body.append(f'<g style="opacity:{alpha:.2f};transform:translateX({shift:.1f}px)">{svg}</g>')
        style = ("<style>:root{--surface:#fcfcfb;--card:#ffffff;--line:#e4e3de;--ink:#0b0b0b;--ink2:#52514e;--ink3:#78776f;"
                 "--c-keep:#1B7F5A;--c-revert:#B7472A;--c-gate:#3B6FD4;--c-agent:#6b6a63;--c-sealed:#C2731B;--c-within:#78776f;--c-version:#52514e;}"
                 "@media (prefers-color-scheme:dark){:root{--surface:#1a1a19;--card:#232322;--line:#3a3a37;--ink:#ffffff;--ink2:#c3c2b7;"
                 "--ink3:#93928a;--c-keep:#2fb37f;--c-revert:#e0684a;--c-gate:#5b8fe6;--c-agent:#a3a29a;--c-sealed:#e39a4a;--c-within:#93928a;--c-version:#c3c2b7;}}"
                 "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;}"
                 ".mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}" + "".join(css) + "</style>")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" role="img" '
                f'aria-label="{escape(head)}">{style}<rect width="{W}" height="{height}" fill="var(--surface)"/>' + "".join(body) + "</svg>")


def disposition_label(r: Row) -> str:
    label = {"keep": "KEPT", "revert": "REVERTED"}[r.decided]
    if r.gate_kind == "keep":
        return label + " · confirmed on fresh seeds"
    if r.gate_kind == "revert" and "(overruled)" in r.proposal:
        return label + " · the agent's keep overruled"
    if r.gate_kind == "revert":
        return label + " · by the gate"
    if r.decided == "revert":
        return label + " · by the agent itself"
    return label


def sealed_tag(r: Row) -> str:
    kind, kept = r.sealed_kind, r.decided == "keep"
    if kind == "agrees":
        return "the keep was right" if kept else "the revert was right"
    if kind == "disagrees":
        return "this keep made it worse" if kept else "this revert lost a real gain"
    if kind == "within":
        return "too small to matter either way"
    return ""


def build(mode: str, rows: list[Row], args: argparse.Namespace) -> tuple[Scene, int, float, str]:
    """Lay the figure out; returns the scene, its height, the cycle length and the aria label."""
    s = Scene()
    now = mode == "now"
    if now:
        title = "Now: the instrument checks every keep during the run."
        sub = (f"{args.model} under the instrument, {args.date} ({args.rollout}). The agent still writes the versions and still "
               "decides what to try next; what changes is that a keep only sticks once it has been measured.")
        steps = ["1  The agent writes a new version, scores it on the 8 public seeds, and proposes to keep it.",
                 "2  The gate checks the improvement on those seeds, then on fresh seeds the agent never saw.",
                 "3  Only a confirmed improvement stays; every ruling is logged; finalize checks safety before submission."]
    else:
        title = "Before: the agent decided alone; the record could only report afterwards."
        sub = (f"{args.model} under {args.program}, {args.date} ({args.rollout}). Each version the agent kept became the new "
               "starting point for the next one, checked by nobody during the run.")
        steps = ["1  The agent writes a new version and decides on its own to keep it.",
                 "2  Nothing checks that decision while the run is going; the record only writes it down.",
                 "3  After the run, the hidden seeds show which keeps actually made the policy worse."]
    s.static.append(text(PAD, PAD + 28, title, size=26, weight="700"))
    for i, line in enumerate(wrap(sub, 138)):
        s.static.append(text(PAD, PAD + 56 + i * 19, line, fill="var(--ink2)", size=13.5))
    s.static.append(f'<text x="{PAD}" y="{PAD + 106}" font-size="11" font-weight="700" fill="var(--ink3)" letter-spacing="1.2">HOW TO READ THIS</text>')
    for i, line in enumerate(steps):
        s.static.append(text(PAD, PAD + 126 + i * 18, line, size=12.5))

    right_edge = SEALED_X - 14
    y = ROW_TOP
    gap = 1.9 if now else 0.62
    t = 0.5
    y_of: dict[str, float] = {}
    at = t
    for i, r in enumerate(rows):
        y_of[r.version] = y
        at = t + i * gap
        used = 1
        g: list[str] = [f'<circle cx="{AXIS_X}" cy="{y - 5}" r="6.5" fill="var(--surface)" stroke="var(--c-{r.decided})" stroke-width="3"/>']
        x = TEXT_X
        c, cw = chip(x, y, r.version, "version", mono=True)
        g.append(c)
        x += cw + 8
        if now:
            proposal = r.proposal.replace(" (overruled)", "")
            verb = {"kept": "agent proposes: keep", "reverted": "agent decides: revert"}.get(proposal, f"agent: {proposal or r.status}")
        else:
            verb = f"agent decides: {'keep' if r.status == 'kept' else r.status}"
        c, cw = chip(x, y, verb, "agent")
        g.append(c)
        x += cw + 10
        evidence = f"parent {r.parent}" if r.parent else "parent not snapshotted"
        if r.visible is not None:
            evidence += f" · scores {fmt(r.visible)} on the public seeds" + (f" (parent {fmt(r.parent_visible)})" if r.parent_visible is not None else "")
        if now:
            g.append(text(x, y, fit(r.change or evidence, right_edge - x)))
            g.append(text(TEXT_X, y + LINE, fit(evidence, right_edge - TEXT_X), fill="var(--ink2)"))
            used += 1
            s.add(at, "".join(g))
            gate_y = y + 2 * LINE + 4
            gc, gw = chip(TEXT_X, gate_y, "gate", "gate")
            plain = wrap(gloss(r.gate), 82) if r.gate else []
            verbatim = wrap(r.gate, 86) if r.gate else []
            block = [gc]
            yy = gate_y
            for ln in plain:
                yy += LINE
                block.append(text(TEXT_X, yy, ln))
            for ln in verbatim:
                yy += 14
                block.append(text(TEXT_X, yy, ln, fill="var(--ink3)", size=10.5, cls="mono"))
            if r.note:
                yy += 14
                block.append(text(TEXT_X, yy, f"agent's note: {r.note}", fill="var(--ink3)", size=11))
            s.add(at + 0.6, "".join(block))
            s.add(at + (1.2 if r.gate_kind != "none" else 0.6), chip(TEXT_X + gw + 8, gate_y, disposition_label(r), r.decided)[0])
            y = yy + 12 + LINE
        else:
            label = "KEPT" if r.status == "kept" else r.status.upper()
            cx = right_edge - chip_width(label)
            g.append(text(x, y, fit(evidence, cx - 10 - x), fill="var(--ink2)"))
            g.append(chip(cx, y, label, r.decided)[0])
            s.add(at, "".join(g))
            y += 12 + used * LINE

    finalize_t = at + (2.0 if now else 0.7)
    if now and args.finalize:
        s.add(finalize_t, f'<circle cx="{AXIS_X}" cy="{y - 5}" r="6.5" fill="var(--surface)" stroke="var(--c-gate)" stroke-width="3"/>'
              + chip(TEXT_X, y, "finalize", "gate")[0] + text(TEXT_X + chip_width("finalize") + 8, y, fit(args.finalize, right_edge - TEXT_X - 70)))
        y += 12 + LINE
    axis_bottom = y - 8

    # the sealed column, revealed last
    sealed_t = finalize_t + 1.4
    head_y = ROW_TOP - 30
    s.add(sealed_t, text(SEALED_X, head_y, "HIDDEN SEEDS, SCORED LATER", fill="var(--ink3)", size=11, weight="700")
          + text(SEALED_X, head_y + 15, "new version minus its parent, 16 seeds", fill="var(--ink3)", size=11))
    for j, r in enumerate(rows):
        yy = y_of[r.version]
        if r.delta is None:
            txt, kind = "no measured parent", "within"
        else:
            txt = f"{fmt(r.delta, signed=True)} · {r.pos} up, {r.neg} down"
            kind = {"agrees": "keep", "disagrees": "sealed", "within": "within"}[r.sealed_kind]
        tag = sealed_tag(r)
        s.add(sealed_t + 0.25 + j * 0.16, text(SEALED_X, yy, txt, fill=f"var(--c-{kind})", size=12.5, weight="650", cls="mono")
              + (text(SEALED_X, yy + 14, tag, fill=f"var(--c-{kind})", size=10.5) if tag else ""))
    end_t = sealed_t + 0.25 + len(rows) * 0.16
    submitted = [r for r in rows if r.status == "submitted"]
    if submitted and submitted[0].reward is not None:
        end_t += 0.6
        sy = axis_bottom + 26
        s.add(end_t, text(SEALED_X, sy, f"submitted: {submitted[0].version}", weight="650")
              + text(SEALED_X, sy + 16, f"exam reward {submitted[0].reward:.4f}", weight="650"))
        axis_bottom = max(axis_bottom, sy + 8)

    # left card: the captured facts and the ledger
    kept = [r for r in rows if r.decided == "keep"]
    measured = [r for r in kept if r.delta is not None]
    disagree = [r for r in rows if r.sealed_kind == "disagrees"]
    if now:
        ledger = [("keeps the agent asked for", str(sum(1 for r in rows if r.proposal.startswith("kept")))),
                  ("confirmed on fresh seeds", str(sum(1 for r in rows if r.gate_kind == "keep"))),
                  ("overruled by the gate", str(sum(1 for r in rows if "(overruled)" in r.proposal))),
                  ("reverted by the agent itself", str(sum(1 for r in rows if r.gate_kind == "none" and r.status == "reverted"))),
                  ("rulings in the decision log", str(sum(1 for r in rows if r.gate_kind != "none"))),
                  ("record verified offline", "yes" if args.record_verified else "no"),
                  ("hidden seeds disagreed", f"{len(disagree)} of {len(rows)}")]
    else:
        ledger = [("decisions the agent made", str(len(rows))),
                  ("kept or submitted", str(len(kept))),
                  ("reverted", str(len(rows) - len(kept))),
                  ("checked during the run", "0"),
                  ("record verified offline", "yes" if args.record_verified else "no"),
                  ("keeps that made it worse", f"{len(disagree)} of {len(measured)}")]
    facts: list[str] = []
    for f in (f"{args.model} · {args.date}", args.program, args.window):
        facts.extend(wrap(f, 40))
    ly = ROW_TOP - 26
    lgy = ly + 82 + len(facts) * 17 + 18
    card_h = (lgy + 30 + len(ledger) * 24) - ly + 4
    s.static.append(f'<rect x="{PAD}" y="{ly}" width="{LEFT_W}" height="{card_h}" rx="14" fill="var(--card)" stroke="var(--line)" stroke-width="1.25"/>')
    s.static.append(f'<text x="{PAD + 20}" y="{ly + 28}" font-size="11" font-weight="700" fill="var(--ink3)" letter-spacing="1.2">THE ROLLOUT</text>')
    s.static.append(text(PAD + 20, ly + 52, args.rollout, size=14, weight="650", cls="mono"))
    for i, f in enumerate(facts):
        s.static.append(text(PAD + 20, ly + 76 + i * 17, f, fill="var(--ink2)"))
    s.static.append(f'<line x1="{PAD + 20}" y1="{lgy - 12}" x2="{PAD + LEFT_W - 20}" y2="{lgy - 12}" stroke="var(--line)"/>')
    s.static.append(f'<text x="{PAD + 20}" y="{lgy + 8}" font-size="11" font-weight="700" fill="var(--ink3)" letter-spacing="1.2">IN NUMBERS</text>')
    for i, (label, value) in enumerate(ledger):
        yy = lgy + 34 + i * 24
        s.static.append(text(PAD + 20, yy, label))
        s.static.append(text(PAD + LEFT_W - 20, yy, value, fill="var(--ink2)", size=12.5, weight="650", cls="mono", anchor="end"))
    s.static.append(f'<line x1="{AXIS_X}" y1="{ROW_TOP - 26}" x2="{AXIS_X}" y2="{axis_bottom}" stroke="var(--line)" stroke-width="2"/>')

    height = max(axis_bottom + 30, ly + card_h + 20) + 40
    if now:
        foot = ("Every row is an event from the rollout's own files (the helper's log, the decision log, the sealed retrospective). The plain "
                "line under each ruling is rendered from the recorded fields; the gate's own line is printed beneath it. The hidden seeds are "
                "analysis data and never tune the rule.")
    else:
        foot = ("Every row is an event from the rollout's own files: the record built after the run and the sealed retrospective. "
                "The hidden seeds are analysis data; they check decisions after the fact and never tune the rule.")
    for i, ln in enumerate(wrap(foot, 150)):
        s.static.append(text(PAD, height - 30 + i * 15, ln, fill="var(--ink3)", size=11.5))
    cycle = end_t + 5.0
    return s, height, cycle, title


def render_gif(frames: list[tuple[str, int]], path: Path, height: int) -> None:
    """Rasterise each (svg, duration ms) frame in a headless Chromium and assemble a looping GIF with one shared palette."""
    from io import BytesIO
    from PIL import Image  # type: ignore[import-not-found]
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    images = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": height}, device_scale_factor=1)
        for svg, _ in frames:
            page.set_content(f'<html><body style="margin:0;background:#fcfcfb">{svg}</body></html>')
            images.append(Image.open(BytesIO(page.screenshot())).convert("RGB"))
        browser.close()
    palette = images[-1].quantize(colors=96)
    quantised = [im.quantize(palette=palette) for im in images]
    quantised[0].save(path, save_all=True, append_images=quantised[1:], duration=[d for _, d in frames], loop=0, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("before", "now"), required=True)
    ap.add_argument("--sealed", required=True, help="sealed-retrospective report.json")
    ap.add_argument("--helper-log", default=None, help="the helper's methods/experiment_log.md (instrument rollouts)")
    ap.add_argument("--name", required=True, help="output basename")
    ap.add_argument("-o", "--out", default="docs/figures")
    ap.add_argument("--gif", default=None, help="directory for the GIF (needs playwright and Pillow)")
    ap.add_argument("--rollout", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--program", required=True)
    ap.add_argument("--window", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--finalize", default="", help="what finalize recorded (now mode), one line")
    ap.add_argument("--record-verified", action="store_true", help="the offline verifier passed the rollout's record")
    args = ap.parse_args()

    report = json.loads(Path(args.sealed).read_text(encoding="utf-8"))
    if report.get("schema") != "rsi-exam-sealed-retrospective/v1":
        print(f"error: {args.sealed} is not a rsi-exam-sealed-retrospective/v1 report", file=sys.stderr)
        return 2
    helper = parse_helper_log(Path(args.helper_log).read_text(encoding="utf-8")) if args.helper_log else {}
    rows = get_rows(report, helper)
    scene, height, cycle, label = build(args.mode, rows, args)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.name}.svg").write_text(scene.render(label, height, None, cycle), encoding="utf-8")
    (out / f"{args.name}-still.svg").write_text(scene.render(label, height, float("inf"), cycle), encoding="utf-8")
    print(f"wrote {out / (args.name + '.svg')} and the still ({len(rows)} versions, {height} px, {cycle:.1f} s cycle)")
    if args.gif:
        times: list[float] = []
        for e in scene.events():
            times.extend([e + FADE_IN * 0.5, e + FADE_IN])
        times = sorted(set(times))
        frames: list[tuple[str, int]] = [(scene.render(label, height, 0.0, cycle), 400)]
        for i, tm in enumerate(times):
            nxt = times[i + 1] if i + 1 < len(times) else tm + 4.5
            frames.append((scene.render(label, height, tm, cycle), max(60, int((nxt - tm) * 1000))))
        gif = Path(args.gif) / f"{args.name}.gif"
        gif.parent.mkdir(parents=True, exist_ok=True)
        render_gif(frames, gif, height)
        print(f"wrote {gif} ({len(frames)} frames, {gif.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
