"""Print or check a content-bound snapshot; never infer a clean committed tree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
TARGET = ROOT / "ara/nanda-2026/evidence/snapshot-manifest.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    previous = json.loads(TARGET.read_text())
    paths = {item["path"] for item in previous["files"]}
    for folder in ("ara/nanda-2026", "studies/decision-audit", "profile", "gate",
                   "fixtures/gated", "tests"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                paths.add(path.relative_to(ROOT).as_posix())
    paths.discard(TARGET.relative_to(ROOT).as_posix())
    paths.add("output/pdf/nanda-2026-track3-ieee-review.pdf")
    files = [{"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
             for path in sorted(paths)]
    if args.check:
        expected = [{"path": item["path"], "sha256": item["sha256"]}
                    for item in previous["files"]]
        if expected != files:
            raise SystemExit("Snapshot differs: regenerate only after reviewing changes.")
        print(f"Verified {len(files)} content bindings; not an authenticity attestation.")
    else:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        print(json.dumps({"schema_version": 2, "base_git_commit": head,
                          "status": "local-review-snapshot",
                          "identity": "Exact file hashes include working-tree changes; base commit is not a clean-tree claim.",
                          "exclusions": ["snapshot-manifest.json (self)", "private external job directories", "Python caches"],
                          "files": files}, indent=2))


if __name__ == "__main__":
    main()
