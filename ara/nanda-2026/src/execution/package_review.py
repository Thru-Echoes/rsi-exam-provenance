"""Package committed review sources and Git history; no publication or network."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[4]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if git("diff", "HEAD", "--name-only").strip():
        raise SystemExit("Commit reviewed tracked changes before packaging.")
    revision = git("rev-parse", "HEAD").decode().strip()
    branch = git("symbolic-ref", "--short", "HEAD").decode().strip()
    archive = git("archive", "--format=zip", "--prefix=source/", "HEAD")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit("Output exists; choose a new name to preserve review snapshots.")
    with tempfile.TemporaryDirectory(prefix="nanda-package-") as temporary:
        bundle = Path(temporary) / "repository.bundle"
        subprocess.run(["git", "bundle", "create", str(bundle), branch, "HEAD"], cwd=ROOT, check=True)
        entries = {}
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            for item in source.infolist():
                # Keep earlier distributions in Git history, not nested inside
                # the browsable snapshot of every subsequent review archive.
                if item.filename.startswith("source/output/review/") and item.filename.endswith((".zip", ".bundle")):
                    continue
                if not item.is_dir():
                    entries[item.filename] = source.read(item)
        entries["repository.bundle"] = bundle.read_bytes()
        entries["START_HERE.md"] = git("show", "HEAD:ara/nanda-2026/START_HERE.md")
        entries["paper.pdf"] = git("show", "HEAD:output/pdf/nanda-2026-track3-ieee-review.pdf")
        manifest = {"source_revision": revision, "branch": branch,
                    "status": "human-review-only-not-anonymized-not-submitted",
                    "source_snapshot_exclusions": ["output/review/*.zip", "output/review/*.bundle"],
                    "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(entries.items())}}
        entries["CONTENTS.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as result:
            for name, data in sorted(entries.items()):
                result.writestr(name, data)
        with zipfile.ZipFile(args.output) as result:
            assert result.testzip() is None
            for name, digest in manifest["sha256"].items():
                assert hashlib.sha256(result.read(name)).hexdigest() == digest
    print(json.dumps({"path": str(args.output), "revision": revision,
                      "bytes": args.output.stat().st_size,
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      "verified_entries": len(manifest["sha256"])}, indent=2))


if __name__ == "__main__":
    main()
