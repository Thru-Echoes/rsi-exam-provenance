#!/usr/bin/env python3
"""Restore ``methods/main/`` from a snapshot without nesting it.

The autoresearch program's literal revert command, ``cp -r versions/v<K> main``, nests the
snapshot inside ``main/`` when ``main/`` already exists, which leaves the old policy in place and
makes the next gate call refuse (``main/`` no longer matches any snapshot). This helper copies the
snapshot's Python files to a sibling staging directory, removes ``main/``, renames the staging
directory into place, and checks that the restored tree's method-tree digest equals the
snapshot's. Bytecode caches are not copied.

CLI: ``--methods <methods dir> --version v<K>``. Exit 0 with the digest on stdout; exit 2 when the
snapshot is missing or is not a Python-only tree, or when the restored tree does not match. Side
effects: replaces ``methods/main/``; removes a stale ``methods/main.restoring/`` if one exists.
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from treedigest import TreeDigestError, method_tree_sha256

STAGING_NAME = "main.restoring"


class RestoreError(ValueError):
    """The restore could not be completed as asked."""


def restore(methods: Path, version: str) -> str:
    """Replace ``methods/main`` with the contents of ``methods/versions/<version>``; return the digest."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version) or version in (".", ".."):
        raise RestoreError(f"version must be a single path segment, got {version!r}")
    snapshot = methods / "versions" / version
    try:
        expected = method_tree_sha256(snapshot)
    except TreeDigestError as exc:
        raise RestoreError(str(exc)) from exc
    staging = methods / STAGING_NAME
    main = methods / "main"
    if staging.exists() or staging.is_symlink():
        shutil.rmtree(staging)
    shutil.copytree(snapshot, staging, symlinks=False, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    if main.exists() or main.is_symlink():
        shutil.rmtree(main)
    staging.rename(main)
    actual = method_tree_sha256(main)
    if actual != expected:
        raise RestoreError(f"restored main/ digest {actual} does not match snapshot {version} digest {expected}")
    return actual


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--methods", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        digest = restore(args.methods, args.version)
    except RestoreError as exc:
        print(f"restore refused: {exc}", file=sys.stderr)
        return 2
    print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
