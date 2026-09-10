#!/usr/bin/env python3
"""Method-tree digests: the grader's view of a policy directory.

Exports ``file_sha256(path)``, ``method_files(root)``, and ``method_tree_sha256(root)``. A method
tree is what the RSI-Exam grader stages from ``methods/main/``: regular ``.py`` files only. This
module applies the same rules the grader's ``policy_sandbox.py`` applies before it copies a tree:
``__pycache__`` directories and ``*.pyc`` / ``*.pyo`` files are ignored first, because they drift
on every import and because the grader skips them before it tests anything else; then a symlink is
refused, and a regular file that is not ``.py`` is refused (the grader raises on it, and such a
submission scores 0.0). The ordering is the grader's: nothing under ``__pycache__`` can raise. The digest is SHA-256 over the lines
``<sha256 of file><two spaces><posix relpath>\\n`` sorted by relpath, the same line format the
provenance record uses for full-tree digests, so a Python-only tree without caches has the same
digest under both. Pure functions; no side effects; standard library only.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

EXCLUDED_DIR = "__pycache__"
EXCLUDED_SUFFIXES = (".pyc", ".pyo")


class TreeDigestError(ValueError):
    """The tree is not a method tree the grader would accept, or cannot be read."""


def file_sha256(path: Path) -> str:
    """Hex SHA-256 of a file's bytes, streamed in 1 MiB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def method_files(root: Path) -> list[str]:
    """Sorted POSIX relpaths of the ``.py`` files the digest covers; refuses symlinks and non-Python files."""
    if root.is_symlink():
        raise TreeDigestError(f"method tree is a symlink: {root}")
    if not root.is_dir():
        raise TreeDigestError(f"method tree is not a directory: {root}")
    rels: list[str] = []
    for child in root.rglob("*"):
        rel = child.relative_to(root)
        # Exclusions first, in the grader's own order: it skips these before it tests anything
        # else, so nothing under __pycache__ can raise.
        if EXCLUDED_DIR in rel.parts or child.suffix in EXCLUDED_SUFFIXES:
            continue
        if child.is_symlink():
            raise TreeDigestError(f"method tree contains a symlink: {rel.as_posix()}")
        if child.is_dir():
            continue
        if child.suffix != ".py":
            raise TreeDigestError(f"method tree contains a non-Python file the grader would reject: {rel.as_posix()}")
        if not child.is_file():
            # A FIFO, socket or device named *.py is not a regular file: the grader refuses it, and opening it to
            # hash it could block forever.
            raise TreeDigestError(f"method tree contains a non-regular file: {rel.as_posix()}")
        rels.append(rel.as_posix())
    if not rels:
        raise TreeDigestError(f"method tree has no Python files: {root}")
    return sorted(rels)


def method_tree_sha256(root: Path) -> str:
    """Canonical cache-free digest of a method tree (see the module docstring)."""
    lines = [f"{file_sha256(root / rel)}  {rel}\n" for rel in method_files(root)]
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
