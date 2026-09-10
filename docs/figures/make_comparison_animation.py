#!/usr/bin/env python3
"""Draw the illustration of an agent improving a program alone and with the gate, in three variants.

    lanes   two horizontal lanes, the same four tries in lockstep, cards left to right
    tree    the same story as a branching timeline: rejected tries are pruned branches under a red X
    curves  two charts, what the agent sees on practice games against what the hidden games would say

All three are illustrations, not measured runs; the tries and numbers are invented to be typical. The
real rollouts, rendered from their own files, are in docs/in-motion.md.

Outputs, per variant: docs/figures/with-and-without[-tree|-curves].svg (animated, loops), the same name
with -still.svg (the last frame), and with --gif DIR a GIF rendered through a headless Chromium (needs
the playwright and Pillow packages). Run from the repository root:
    python3 docs/figures/make_comparison_animation.py [--variant lanes|tree|curves|all] [--gif DIR]
Side effects: writes those files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

FADE = 0.35
HOLD = 10.0     # seconds the finished picture stays before the loop restarts

# the tries every variant tells: (short title, what the practice games say, whether the hidden games agree)
TRIES = [
    ("Try 1. a smarter search", "practice games. better", True),
    ("Try 2. a small tweak", "practice games. a bit better", False),
    ("Try 3. a shortcut", "practice games. better", False),
    ("Try 4. a deeper search", "practice games. much better", True),
]
TRIES6 = TRIES + [("Try 5. bigger tables", "practice games. a bit better", False),
                  ("Try 6. tuned search", "practice games. better", True)]

STYLE = ("<style>:root{--surface:#fcfcfb;--card:#ffffff;--line:#e4e3de;--ink:#0b0b0b;--ink2:#52514e;--ink3:#78776f;"
         "--c-keep:#1B7F5A;--c-revert:#B7472A;--c-gate:#3B6FD4;--c-warn:#C2731B;}"
         "@media (prefers-color-scheme:dark){:root{--surface:#1a1a19;--card:#232322;--line:#3a3a37;--ink:#ffffff;--ink2:#c3c2b7;"
         "--ink3:#93928a;--c-keep:#2fb37f;--c-revert:#e0684a;--c-gate:#5b8fe6;--c-warn:#e39a4a;}}"
         "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;}")


def text(x: float, y: float, s: str, fill: str = "var(--ink)", size: float = 12, weight: str = "", anchor: str = "") -> str:
    a = f' font-weight="{weight}"' if weight else ""
    a += f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}"{a} fill="{fill}">{escape(s)}</text>'


def chip(x: float, y: float, label: str, kind: str) -> str:
    w = len(label) * 6.6 + 16
    return (f'<rect x="{x:.1f}" y="{y - 12}" width="{w:.1f}" height="18" rx="9" fill="var(--c-{kind})" fill-opacity="0.13" '
            f'stroke="var(--c-{kind})" stroke-opacity="0.6"/>'
            f'<text x="{x + 8:.1f}" y="{y}" font-size="11" font-weight="650" fill="var(--c-{kind})">{escape(label)}</text>')


def big_x(x: float, y: float, w: float, h: float) -> str:
    """A red X across a box, drawn as two strokes."""
    m = 6
    return (f'<line x1="{x + m}" y1="{y + m}" x2="{x + w - m}" y2="{y + h - m}" stroke="var(--c-revert)" stroke-width="7" stroke-linecap="round" opacity="0.9"/>'
            f'<line x1="{x + w - m}" y1="{y + m}" x2="{x + m}" y2="{y + h - m}" stroke="var(--c-revert)" stroke-width="7" stroke-linecap="round" opacity="0.9"/>')


class Scene:
    def __init__(self, w: int, h: int, label: str) -> None:
        self.w, self.h, self.label = w, h, label
        self.items: list[tuple[float, str]] = []
        self.static: list[str] = []

    def add(self, at: float, svg: str) -> None:
        self.items.append((at, svg))

    def cycle(self) -> float:
        return max(at for at, _ in self.items) + HOLD

    def render(self, when: float | None) -> str:
        cycle = self.cycle()
        css, body = [], list(self.static)
        for i, (at, svg) in enumerate(self.items):
            if when is None:
                a, b, hold = at / cycle * 100, (at + FADE) / cycle * 100, (cycle - 0.5) / cycle * 100
                css.append(f"@keyframes e{i}{{0%,{a:.2f}%{{opacity:0;transform:translateX(-10px)}}"
                           f"{b:.2f}%,{hold:.2f}%{{opacity:1;transform:none}}100%{{opacity:0;transform:translateX(-10px)}}}}")
                body.append(f'<g style="animation:e{i} {cycle}s linear infinite">{svg}</g>')
            else:
                alpha = min(1.0, max(0.0, (when - at) / FADE))
                if alpha > 0:
                    body.append(f'<g style="opacity:{alpha:.2f};transform:translateX({-10 * (1 - alpha):.1f}px)">{svg}</g>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" role="img" '
                f'aria-label="{escape(self.label)}">{STYLE}{"".join(css)}</style>'
                f'<rect width="{self.w}" height="{self.h}" fill="var(--surface)"/>' + "".join(body) + "</svg>")


def header(s: Scene, pad: int, title: str, lines: list[str]) -> None:
    s.static.append(text(pad, 52, title, size=25, weight="700"))
    for i, ln in enumerate(lines):
        s.static.append(text(pad, 78 + i * 18, ln, fill="var(--ink2)", size=13))


def footer(s: Scene, pad: int, at: float, lines: list[str]) -> None:
    for i, ln in enumerate(lines):
        s.add(at + i * 0.6, text(pad, s.h - 44 + i * 18, ln, size=12.5))


# ------------------------------------------------------------------ lanes ---

def build_lanes() -> Scene:
    W, H, PAD = 1320, 500, 40
    LANE_X, STEP_W, CARD_W = 250, 214, 200
    lanes = {"alone": 138, "gate": 330}
    s = Scene(W, H, "An agent improving a program alone, and the same tries with the gate")
    header(s, PAD, "The same agent, the same four tries. Alone, and with the gate.",
           ["The agent has a few hours to improve a program. It can only score itself on practice games it sees again and again.",
            "The final exam is on hidden games. Fresh games are new ones the gate draws to check a claim. An illustration, not a measured run."])
    for name, y in lanes.items():
        s.static.append(text(PAD, y - 4, "ALONE" if name == "alone" else "WITH THE GATE", fill="var(--ink3)", size=11, weight="700"))
        s.static.append(text(PAD, y + 14, "keeps what looks better" if name == "alone" else "keeps only what fresh games confirm", fill="var(--ink3)", size=11))
        s.static.append(f'<line x1="{LANE_X - 16}" y1="{y + 50}" x2="{W - PAD}" y2="{y + 50}" stroke="var(--line)" stroke-width="2"/>')
        s.static.append(f'<path d="M {W - PAD - 8} {y + 45} L {W - PAD} {y + 50} L {W - PAD - 8} {y + 55}" fill="none" stroke="var(--line)" stroke-width="2"/>')
    t = 0.6
    for i, (title, practice, real) in enumerate(TRIES):
        x = LANE_X + i * STEP_W
        for name, y in lanes.items():
            at = t + i * 1.7 + (0.25 if name == "gate" else 0)
            s.add(at, f'<rect x="{x}" y="{y - 22}" width="{CARD_W}" height="112" rx="10" fill="var(--card)" stroke="var(--line)"/>'
                  + text(x + 12, y, title, weight="650") + text(x + 12, y + 20, practice, fill="var(--ink2)", size=11.5))
            if name == "alone":
                s.add(at + 0.4, chip(x + 12, y + 46, "kept", "keep"))
                if not real:
                    s.add(11.2, text(x + 12, y + 74, "hidden games say worse", fill="var(--c-warn)", size=11, weight="650"))
            else:
                s.add(at + 0.7, text(x + 12, y + 40, "fresh games agree" if real else "fresh games say no", fill="var(--c-gate)", size=11.5, weight="650"))
                s.add(at + 1.1, chip(x + 12, y + 66, "kept" if real else "thrown away", "keep" if real else "revert")
                      + ("" if real else big_x(x, y - 22, CARD_W, 112)))
        s.add(t + i * 1.7, text(x + CARD_W / 2, lanes["gate"] - 34, "same try", fill="var(--ink3)", size=10, anchor="middle"))
    xe = LANE_X + 4 * STEP_W + 6
    t_end = t + 4 * 1.7 + 0.6
    for name, y in lanes.items():
        s.add(t_end + (0.25 if name == "gate" else 0), text(xe, y, "Time is up", weight="650")
              + text(xe, y + 20, "submits the last version" if name == "alone" else "safety check, then submits", fill="var(--ink2)", size=11.5))
    t_reveal = t_end + 1.6
    for name, y in lanes.items():
        good = name == "gate"
        h, color = (62, "var(--c-keep)") if good else (30, "var(--c-warn)")
        s.add(t_reveal, f'<rect x="{xe}" y="{y + 88 - h}" width="22" height="{h}" rx="3" fill="{color}" fill-opacity="0.85"/>'
              + text(xe + 30, y + 78, "hidden games", fill="var(--ink3)", size=10.5)
              + text(xe + 30, y + 92, "its best version" if good else "worse than try 1", fill=color, size=11.5, weight="650"))
    footer(s, PAD, t_reveal + 0.8, ["Two of the four keeps were luck. Alone, they stayed and everything after was built on them.",
                                    "With the gate, each ruling is written down with a fingerprint of the code and the games it ran on. Anyone can check it later."])
    return s


# ------------------------------------------------------------------- tree ---

def build_tree() -> Scene:
    W, H, PAD = 1320, 600, 40
    NODE_W, NODE_H = 150, 46
    s = Scene(W, H, "The same six tries as a chain when the agent decides alone, and as a pruned tree under the gate")
    header(s, PAD, "Six tries. Alone they chain. With the gate, the bad ones get pruned.",
           ["Every try starts from the version the agent currently trusts. Alone, that is always the last one it kept.",
            "With the gate, a try the fresh games reject is thrown away, and the next try starts again from the last confirmed version."])
    cols = [262 + k * 132 for k in range(8)]          # start, six tries, submit
    y_alone, y_gate = 168, 400
    for name, y in (("alone", y_alone), ("gate", y_gate)):
        s.static.append(text(PAD, y - 40, "ALONE" if name == "alone" else "WITH THE GATE", fill="var(--ink3)", size=11, weight="700"))
        s.static.append(text(PAD, y - 22, "one long chain" if name == "alone" else "a tree with pruned branches", fill="var(--ink3)", size=11))

    def node(x: float, y: float, title: str, sub: str, kind: str) -> str:
        return (f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="9" fill="var(--card)" stroke="var(--c-{kind})" stroke-width="2"/>'
                + text(x + 10, y + 19, title, size=11.5, weight="650") + text(x + 10, y + 36, sub, fill="var(--ink2)", size=10.5))

    def edge(x1: float, y1: float, x2: float, y2: float, kind: str = "line") -> str:
        c = "var(--line)" if kind == "line" else f"var(--c-{kind})"
        return f'<path d="M {x1} {y1} C {x1 + 40} {y1}, {x2 - 40} {y2}, {x2} {y2}" fill="none" stroke="{c}" stroke-width="2.5"/>'

    # the start node in both lanes
    for y in (y_alone, y_gate):
        s.static.append(node(cols[0] - 60, y - NODE_H / 2, "Start", "the weak program", "gate"))
    t = 0.6
    # alone: a chain through every try
    prev_x = cols[0] - 60 + NODE_W
    for i, (title, _practice, real) in enumerate(TRIES6):
        x = cols[i + 1] - 60
        at = t + i * 1.5
        s.add(at, edge(prev_x, y_alone, x, y_alone) + node(x, y_alone - NODE_H / 2, title.split(". ")[0], title.split(". ")[1], "keep"))
        if not real:
            s.add(11.4, text(x + NODE_W / 2, y_alone + 44, "hidden games. worse", fill="var(--c-warn)", size=10.5, weight="650", anchor="middle"))
        prev_x = x + NODE_W
    # gate: a trunk of confirmed tries, rejected ones as pruned branches
    trunk_x = cols[0] - 60 + NODE_W
    trunk_y = y_gate
    branch_slot = 0
    for i, (title, _practice, real) in enumerate(TRIES6):
        x = cols[i + 1] - 60
        at = t + i * 1.5 + 0.25
        if real:
            y = trunk_y
            s.add(at, edge(trunk_x, trunk_y, x, y) + node(x, y - NODE_H / 2, title.split(". ")[0], title.split(". ")[1], "keep"))
            s.add(at + 0.7, text(x + NODE_W / 2, y + 44, "fresh games agree. kept", fill="var(--c-keep)", size=10.5, weight="650", anchor="middle"))
            trunk_x = x + NODE_W
        else:
            y = trunk_y - 92 if branch_slot % 2 == 0 else trunk_y + 92
            branch_slot += 1
            s.add(at, edge(trunk_x, trunk_y, x, y) + node(x, y - NODE_H / 2, title.split(". ")[0], title.split(". ")[1], "revert"))
            s.add(at + 0.7, big_x(x, y - NODE_H / 2, NODE_W, NODE_H)
                  + text(x + NODE_W / 2, y + (44 if y > trunk_y else -34), "fresh games say no. thrown away", fill="var(--c-revert)", size=10.5, weight="650", anchor="middle"))
    # submit
    xs = cols[7] - 60
    t_end = t + 6 * 1.5 + 0.8
    for name, y, from_x in (("alone", y_alone, cols[6] - 60 + NODE_W), ("gate", y_gate, trunk_x)):
        s.add(t_end + (0.25 if name == "gate" else 0), edge(from_x, y, xs, y) + node(xs, y - NODE_H / 2, "Submit", "time is up", "gate"))
    t_reveal = t_end + 1.6
    for name, y in (("alone", y_alone), ("gate", y_gate)):
        good = name == "gate"
        color = "var(--c-keep)" if good else "var(--c-warn)"
        s.add(t_reveal, text(xs + NODE_W / 2, y - 34, "hidden games. its best version" if good else "hidden games. worse than try 4",
                             fill=color, size=10.5, weight="650", anchor="middle"))
    footer(s, PAD, t_reveal + 0.8, ["Alone, three of the six keeps were luck, and tries 5 and 6 were built on top of them.",
                                    "With the gate, the three bad tries never became anyone's parent. Every ruling is written down with a fingerprint of the code."])
    return s


# ----------------------------------------------------------------- curves ---

def build_curves() -> Scene:
    W, H, PAD = 1320, 660, 40
    s = Scene(W, H, "Two charts, what the agent sees on practice games and what the hidden games would say, alone and with the gate")
    header(s, PAD, "What the agent sees, and what is real.",
           ["Grey. the score on the practice games, the only number the agent can see. Colour. what the hidden games would say at that moment.",
            "Alone, the two drift apart at every lucky keep. With the gate, a try the fresh games reject never moves either line."])
    # chart geometry
    x0, x1 = 260, W - 120
    charts = {"alone": (150, 330), "gate": (390, 570)}   # (top, bottom) in px
    steps = 7                                             # start plus six tries
    xs = [x0 + k * (x1 - x0) / (steps - 1) for k in range(steps)]
    # visible and real scores per step, 0..1 of the chart height
    seen_alone = [0.10, 0.35, 0.42, 0.50, 0.72, 0.78, 0.86]
    real_alone = [0.10, 0.35, 0.30, 0.22, 0.48, 0.42, 0.52]
    seen_gate = [0.10, 0.35, 0.35, 0.35, 0.68, 0.68, 0.82]
    real_gate = [0.10, 0.35, 0.35, 0.35, 0.62, 0.62, 0.76]
    verdict_gate = [None, True, False, False, True, False, True]

    def ypx(chart: tuple[int, int], v: float) -> float:
        top, bottom = chart
        return bottom - v * (bottom - top)

    for name, chart in charts.items():
        top, bottom = chart
        s.static.append(text(PAD, top + 6, "ALONE" if name == "alone" else "WITH THE GATE", fill="var(--ink3)", size=11, weight="700"))
        s.static.append(text(PAD, top + 24, "keeps what looks better" if name == "alone" else "keeps only what fresh games confirm", fill="var(--ink3)", size=11))
        s.static.append(f'<line x1="{x0 - 10}" y1="{bottom}" x2="{x1 + 10}" y2="{bottom}" stroke="var(--line)" stroke-width="2"/>')
        s.static.append(f'<line x1="{x0 - 10}" y1="{top - 6}" x2="{x0 - 10}" y2="{bottom}" stroke="var(--line)" stroke-width="2"/>')
        s.static.append(text(x0 - 16, top + 4, "score", fill="var(--ink3)", size=10.5, anchor="end"))
        for k in range(1, steps):
            s.static.append(text(xs[k], bottom + 16, f"try {k}", fill="var(--ink3)", size=10.5, anchor="middle"))
    t = 0.6
    for k in range(1, steps):
        at = t + (k - 1) * 1.6
        for name, chart in charts.items():
            seen = seen_alone if name == "alone" else seen_gate
            real = real_alone if name == "alone" else real_gate
            a = at + (0.25 if name == "gate" else 0)
            color = "var(--c-keep)" if name == "gate" else "var(--c-warn)"
            s.add(a, f'<line x1="{xs[k-1]:.1f}" y1="{ypx(chart, seen[k-1]):.1f}" x2="{xs[k]:.1f}" y2="{ypx(chart, seen[k]):.1f}" stroke="var(--ink3)" stroke-width="3" stroke-dasharray="6 5"/>')
            s.add(a + 0.35, f'<line x1="{xs[k-1]:.1f}" y1="{ypx(chart, real[k-1]):.1f}" x2="{xs[k]:.1f}" y2="{ypx(chart, real[k]):.1f}" stroke="{color}" stroke-width="3.5"/>')
            if name == "gate":
                ok = verdict_gate[k]
                if ok:
                    s.add(a + 0.7, f'<circle cx="{xs[k]:.1f}" cy="{ypx(chart, seen[k]):.1f}" r="9" fill="var(--c-keep)"/>'
                          + text(xs[k], ypx(chart, seen[k]) - 16, "confirmed", fill="var(--c-keep)", size=10.5, weight="650", anchor="middle"))
                else:
                    cx, cy = xs[k], ypx(chart, seen[k]) - 40
                    s.add(a + 0.7, big_x(cx - 16, cy - 16, 32, 32) + text(cx, cy - 24, "fresh games say no", fill="var(--c-revert)", size=10.5, weight="650", anchor="middle"))
            else:
                s.add(a + 0.5, f'<circle cx="{xs[k]:.1f}" cy="{ypx(chart, seen[k]):.1f}" r="7" fill="var(--ink3)"/>')
    t_reveal = t + 6 * 1.6 + 0.6
    for name, chart in charts.items():
        seen = seen_alone if name == "alone" else seen_gate
        real = real_alone if name == "alone" else real_gate
        color = "var(--c-keep)" if name == "gate" else "var(--c-warn)"
        gap = ypx(chart, real[-1]) - ypx(chart, seen[-1])
        s.add(t_reveal, text(x1 + 14, ypx(chart, seen[-1]) + (0 if gap > 14 else -4), "what it sees", fill="var(--ink3)", size=10.5)
              + text(x1 + 14, ypx(chart, real[-1]) + (8 if gap > 14 else 12), "what is real", fill=color, size=10.5, weight="650"))
    footer(s, PAD, t_reveal + 0.8, ["Alone, the agent watches its number climb while the real score slips at every lucky keep.",
                                    "With the gate, the lines stay together, because a keep only sticks when fresh games agree. Each ruling carries a fingerprint of the code."])
    return s


BUILDERS = {"lanes": ("with-and-without", build_lanes), "tree": ("with-and-without-tree", build_tree), "curves": ("with-and-without-curves", build_curves)}


def write_gif(scene: Scene, path: Path) -> None:
    from io import BytesIO
    from PIL import Image  # type: ignore[import-not-found]
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    cycle = scene.cycle()
    times = sorted({at + d for at, _ in scene.items for d in (FADE * 0.5, FADE)})
    frames = [(scene.render(0.0), 400)]
    for i, tm in enumerate(times):
        nxt = times[i + 1] if i + 1 < len(times) else tm + HOLD
        frames.append((scene.render(tm), max(60, int((nxt - tm) * 1000))))
    images = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": scene.w, "height": scene.h})
        for svg, _ in frames:
            page.set_content(f'<html><body style="margin:0;background:#fcfcfb">{svg}</body></html>')
            images.append(Image.open(BytesIO(page.screenshot())).convert("RGB"))
        browser.close()
    pal = images[-1].quantize(colors=96)
    q = [im.quantize(palette=pal) for im in images]
    q[0].save(path, save_all=True, append_images=q[1:], duration=[d for _, d in frames], loop=0, optimize=True)
    print(f"wrote {path} ({len(frames)} frames, {cycle:.0f} s cycle)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", choices=(*BUILDERS, "all"), default="all")
    ap.add_argument("-o", "--out", default="docs/figures")
    ap.add_argument("--gif", default=None)
    args = ap.parse_args()
    out = Path(args.out)
    for key, (name, builder) in BUILDERS.items():
        if args.variant not in (key, "all"):
            continue
        scene = builder()
        (out / f"{name}.svg").write_text(scene.render(None), encoding="utf-8")
        (out / f"{name}-still.svg").write_text(scene.render(float("inf")), encoding="utf-8")
        print(f"wrote {out / (name + '.svg')} and the still ({scene.cycle():.0f} s cycle)")
        if args.gif:
            write_gif(scene, Path(args.gif) / f"{name}.gif")
    return 0


if __name__ == "__main__":
    sys.exit(main())
