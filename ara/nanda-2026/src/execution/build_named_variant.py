#!/usr/bin/env python3
"""Derive the named (non-anonymous) submission source from the canonical anonymous main.tex.

The canonical ``submission/main.tex`` stays anonymous so the review copy and the repository tests agree.
This script writes ``submission/main-named.tex`` next to it with (1) the author block for the two
co-first authors and (2) the two project references completed with their repository URLs and, for
TRACE, its concept DOI. Nothing else changes, so the two sources differ only where the anonymity
posture requires. Affiliations and emails are arguments, not defaults, so the named source cannot be
produced with a guessed line for either author.

Inputs: submission/main.tex; the four author arguments below.
Output: submission/main-named.tex (side effect: overwrites it). Build it with latexmk in that directory.
Run:
  python3 build_named_variant.py --a1-affil "..." --a1-email "..." --a2-affil "..." --a2-email "..."
"""
from __future__ import annotations

import argparse
from pathlib import Path

SUBMISSION = Path(__file__).resolve().parents[2] / "submission"

ANON_AUTHOR = r"\author{\IEEEauthorblockN{Anonymous Authors}}"
ANON_TRACE = (r"\bibitem{trace} \emph{TRACE: A decision-provenance record for human and AI work}, v0.5.1, "
              r"Apache-2.0, 2026. Repository and DOI withheld for anonymous review.")
ANON_PP = (r"\bibitem{proofpress} \emph{Proofpress: An evidence ledger with separate claim review and governed "
           r"reuse}, v0.4.0, Apache-2.0, 2026. Repository withheld for anonymous review.")
NAMED_TRACE = (r"\bibitem{trace} O. Muellerklein, \emph{TRACE: A decision-provenance record for human and AI work}, "
               r"v0.5.1, Apache-2.0, 2026. [Online]. Available: \url{https://github.com/Thru-Echoes/TRACE}, "
               r"doi: 10.5281/zenodo.21711455.")
NAMED_PP = (r"\bibitem{proofpress} C.-M. Tang, \emph{Proofpress: An evidence ledger with separate claim review and "
            r"governed reuse}, v0.4.0, Apache-2.0, 2026. [Online]. Available: "
            r"\url{https://github.com/chenmingtang830/proofpress}.")


def get_named_author_block(a1_affil: str, a1_email: str, a2_affil: str, a2_email: str, first: str) -> str:
    """Two co-first authors with an equal-contribution note. ``first`` names who is listed first."""
    oliver = (r"\IEEEauthorblockN{Oliver Muellerklein\IEEEauthorrefmark{1}}" "\n"
              r"\IEEEauthorblockA{" + a1_affil.replace(";", r"\\") + r"\\" + a1_email + "}")
    richard = (r"\IEEEauthorblockN{Chen-Ming Tang\IEEEauthorrefmark{1}}" "\n"
               r"\IEEEauthorblockA{" + a2_affil.replace(";", r"\\") + r"\\" + a2_email + "}")
    blocks = [oliver, richard] if first == "muellerklein" else [richard, oliver]
    return (r"\author{" + "\n" + blocks[0] + "\n" + r"\and" + "\n" + blocks[1] + "\n"
            r"\thanks{\IEEEauthorrefmark{1}These authors contributed equally.}}")


def build(args: argparse.Namespace) -> Path:
    src = (SUBMISSION / "main.tex").read_text()
    for needle in (ANON_AUTHOR, ANON_TRACE, ANON_PP):
        if needle not in src:
            raise SystemExit(f"canonical source no longer contains the expected line:\n{needle}")
    out = src.replace(ANON_AUTHOR, get_named_author_block(args.a1_affil, args.a1_email, args.a2_affil, args.a2_email, args.first))
    out = out.replace(ANON_TRACE, NAMED_TRACE).replace(ANON_PP, NAMED_PP)
    out = out.replace(r"\documentclass[conference]{IEEEtran}", r"\documentclass[conference]{IEEEtran}" "\n" r"\IEEEoverridecommandlockouts", 1)
    target = SUBMISSION / "main-named.tex"
    target.write_text(out)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a1-affil", required=True, help="Muellerklein affiliation; use ';' to break lines")
    parser.add_argument("--a1-email", required=True)
    parser.add_argument("--a2-affil", required=True, help="Tang affiliation; use ';' to break lines")
    parser.add_argument("--a2-email", required=True)
    parser.add_argument("--first", choices=["muellerklein", "tang"], default="muellerklein", help="who is listed first (co-first authorship either way)")
    target = build(parser.parse_args())
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
