"""Render the review Markdown with title, abstract, and stable citation labels."""
import argparse
from pathlib import Path
import re
import subprocess

ARA = Path(__file__).resolve().parents[2]


def render():
    tex = (ARA / "submission/main.tex").read_text()
    title = re.search(r"\\title\{(.*?)\}\n", tex, re.S).group(1).replace("\\\\", " ")
    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S).group(1).strip()
    body = tex.split(r"\section{Introduction}", 1)[1].split(r"\begin{thebibliography}", 1)[0]
    body = r"\section{Introduction}" + body
    body = re.sub(r"\\cite\{([^}]+)\}", lambda m: "[" + m.group(1) + "]", body)
    body = body.replace(r"\ref{tab:example}", "1").replace(r"\ref{tab:faults}", "2")
    bibliography = tex.split(r"\begin{thebibliography}{00}", 1)[1].split(r"\end{thebibliography}", 1)[0]
    bibliography = re.sub(r"\\bibitem\{([^}]+)\}", lambda m: "\n\n[" + m.group(1) + "] ", bibliography)
    text = r"\section*{Abstract}" + "\n" + abstract + "\n" + body + r"\section*{References}" + "\n" + bibliography
    result = subprocess.run(["pandoc", "-f", "latex", "-t", "gfm", "--wrap=none"],
                            input=text, text=True, check=True, capture_output=True).stdout
    return "# " + title + "\n\nAnonymous human-review draft. The IEEE PDF is the layout-authoritative copy.\n\n" + result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = render()
    if args.check:
        if result != (ARA / "submission/manuscript.md").read_text():
            raise SystemExit("Readable manuscript is stale.")
        print("Readable manuscript matches TeX, including abstract and citation labels.")
    else:
        print(result, end="")
