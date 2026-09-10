#!/usr/bin/env python3
"""Draw one illustration: an agent improving a program alone, and the same tries under the gate.

Two horizontal lanes, left to right, step by step in lockstep. The story is an illustration, not a
measured comparison; the numbers and the tries are invented to be typical. The real rollouts,
rendered from their own files, are in docs/in-motion.md.

Outputs: docs/figures/with-and-without.svg (animated, loops), with-and-without-still.svg, and with --gif
a GIF rendered through a headless Chromium (needs the playwright and Pillow packages).
Run from the repository root: python3 docs/figures/make_comparison_animation.py [--gif DIR]
Side effects: writes those files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

W, H = 1200, 500
PAD = 40
LANE_X = 250          # where the step cards start
STEP_W = 178
CARD_W = 164
LANES = {"alone": 138, "gate": 330}
FADE = 0.35

# (title, what the practice games say) for the four tries; the gate's verdict on fresh games; whether the
# hidden games later agree with keeping it
TRIES = [
    ("Try 1. a smarter search", "practice games. better", "fresh games agree", True),
    ("Try 2. a small tweak", "practice games. a bit better", "fresh games say no", False),
    ("Try 3. a shortcut", "practice games. better", "fresh games say no", False),
    ("Try 4. a deeper search", "practice games. much better", "fresh games agree", True),
]


def text(x: float, y: float, s: str, fill: str = "var(--ink)", size: float = 12, weight: str = "", anchor: str = "") -> str:
    a = f' font-weight="{weight}"' if weight else ""
    a += f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}"{a} fill="{fill}">{escape(s)}</text>'


def chip(x: float, y: float, label: str, kind: str) -> str:
    w = len(label) * 6.6 + 16
    return (f'<rect x="{x:.1f}" y="{y - 12}" width="{w:.1f}" height="18" rx="9" fill="var(--c-{kind})" fill-opacity="0.13" '
            f'stroke="var(--c-{kind})" stroke-opacity="0.6"/>'
            f'<text x="{x + 8:.1f}" y="{y}" font-size="11" font-weight="650" fill="var(--c-{kind})">{escape(label)}</text>')


class Scene:
    def __init__(self) -> None:
        self.items: list[tuple[float, str]] = []
        self.static: list[str] = []

    def add(self, at: float, svg: str) -> None:
        self.items.append((at, svg))

    def render(self, when: float | None, cycle: float) -> str:
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
        style = ("<style>:root{--surface:#fcfcfb;--card:#ffffff;--line:#e4e3de;--ink:#0b0b0b;--ink2:#52514e;--ink3:#78776f;"
                 "--c-keep:#1B7F5A;--c-revert:#B7472A;--c-gate:#3B6FD4;--c-warn:#C2731B;}"
                 "@media (prefers-color-scheme:dark){:root{--surface:#1a1a19;--card:#232322;--line:#3a3a37;--ink:#ffffff;--ink2:#c3c2b7;"
                 "--ink3:#93928a;--c-keep:#2fb37f;--c-revert:#e0684a;--c-gate:#5b8fe6;--c-warn:#e39a4a;}}"
                 "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;}" + "".join(css) + "</style>")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
                f'aria-label="An agent improving a program alone, and the same tries with the gate">{style}'
                f'<rect width="{W}" height="{H}" fill="var(--surface)"/>' + "".join(body) + "</svg>")


def build() -> tuple[Scene, float]:
    s = Scene()
    s.static.append(text(PAD, 52, "The same agent, the same four tries. Alone, and with the gate.", size=25, weight="700"))
    s.static.append(text(PAD, 78, "The agent has a few hours to improve a program. It can only score itself on practice games it sees again and again.", fill="var(--ink2)", size=13))
    s.static.append(text(PAD, 96, "The final exam is on hidden games. Fresh games are new ones the gate draws to check a claim. An illustration, not a measured run.", fill="var(--ink2)", size=13))
    for name, y in LANES.items():
        label = "ALONE" if name == "alone" else "WITH THE GATE"
        s.static.append(text(PAD, y - 4, label, fill="var(--ink3)", size=11, weight="700"))
        s.static.append(text(PAD, y + 14, "keeps what looks better" if name == "alone" else "keeps only what fresh games confirm", fill="var(--ink3)", size=11))
        s.static.append(f'<line x1="{LANE_X - 16}" y1="{y + 50}" x2="{W - PAD}" y2="{y + 50}" stroke="var(--line)" stroke-width="2"/>')
        s.static.append(f'<path d="M {W - PAD - 8} {y + 45} L {W - PAD} {y + 50} L {W - PAD - 8} {y + 55}" fill="none" stroke="var(--line)" stroke-width="2"/>')

    t = 0.6
    for i, (title, practice, fresh, real) in enumerate(TRIES):
        x = LANE_X + i * STEP_W
        for name, y in LANES.items():
            at = t + i * 1.7 + (0.25 if name == "gate" else 0)
            card = [f'<rect x="{x}" y="{y - 22}" width="{CARD_W}" height="112" rx="10" fill="var(--card)" stroke="var(--line)"/>',
                    text(x + 12, y, title, weight="650"),
                    text(x + 12, y + 20, practice, fill="var(--ink2)", size=11.5)]
            s.add(at, "".join(card))
            if name == "alone":
                s.add(at + 0.4, chip(x + 12, y + 46, "kept", "keep"))
                if not real:
                    s.add(11.2, text(x + 12, y + 74, "hidden games say worse", fill="var(--c-warn)", size=11, weight="650"))
            else:
                s.add(at + 0.7, text(x + 12, y + 40, fresh, fill="var(--c-gate)", size=11.5, weight="650"))
                s.add(at + 1.1, chip(x + 12, y + 66, "kept" if real else "thrown away", "keep" if real else "revert"))
        # a small connector between the lanes: the same try
        s.add(t + i * 1.7, text(x + CARD_W / 2, LANES["gate"] - 34, "same try", fill="var(--ink3)", size=10, anchor="middle"))

    # the end of the window and the hidden-game result
    xe = LANE_X + 4 * STEP_W + 6
    t_end = t + 4 * 1.7 + 0.6
    for name, y in LANES.items():
        at = t_end + (0.25 if name == "gate" else 0)
        s.add(at, text(xe, y, "Time is up", weight="650") + text(xe, y + 20, "submits the last version" if name == "alone" else "safety check, then submits", fill="var(--ink2)", size=11.5))
    t_reveal = t_end + 1.6
    for name, y in LANES.items():
        good = name == "gate"
        h = 62 if good else 30
        color = "var(--c-keep)" if good else "var(--c-warn)"
        s.add(t_reveal, f'<rect x="{xe}" y="{y + 88 - h}" width="22" height="{h}" rx="3" fill="{color}" fill-opacity="0.85"/>'
              + text(xe + 30, y + 78, "hidden games", fill="var(--ink3)", size=10.5)
              + text(xe + 30, y + 92, "its best version" if good else "worse than try 1", fill=color, size=11.5, weight="650"))
    s.add(t_reveal + 0.8, text(PAD, H - 44, "Two of the four keeps were luck. Alone, they stayed and everything after was built on them.", fill="var(--ink)", size=12.5))
    s.add(t_reveal + 1.4, text(PAD, H - 26, "With the gate, each ruling is written down with a fingerprint of the code and the games it ran on. Anyone can check it later.", fill="var(--ink)", size=12.5))
    return s, t_reveal + 6.5


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", default="docs/figures")
    ap.add_argument("--gif", default=None)
    args = ap.parse_args()
    scene, cycle = build()
    out = Path(args.out)
    (out / "with-and-without.svg").write_text(scene.render(None, cycle), encoding="utf-8")
    (out / "with-and-without-still.svg").write_text(scene.render(float("inf"), cycle), encoding="utf-8")
    print(f"wrote {out / 'with-and-without.svg'} and the still ({cycle:.1f} s cycle)")
    if args.gif:
        from io import BytesIO
        from PIL import Image  # type: ignore[import-not-found]
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        times = sorted({at + d for at, _ in scene.items for d in (FADE * 0.5, FADE)})
        frames = [(scene.render(0.0, cycle), 400)] + [(scene.render(tm, cycle), max(60, int(((times[i + 1] if i + 1 < len(times) else tm + 4.5) - tm) * 1000))) for i, tm in enumerate(times)]
        images = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": W, "height": H})
            for svg, _ in frames:
                page.set_content(f'<html><body style="margin:0;background:#fcfcfb">{svg}</body></html>')
                images.append(Image.open(BytesIO(page.screenshot())).convert("RGB"))
            browser.close()
        pal = images[-1].quantize(colors=96)
        q = [im.quantize(palette=pal) for im in images]
        gif = Path(args.gif) / "with-and-without.gif"
        q[0].save(gif, save_all=True, append_images=q[1:], duration=[d for _, d in frames], loop=0, optimize=True)
        print(f"wrote {gif} ({len(frames)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
