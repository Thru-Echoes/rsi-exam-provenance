#!/usr/bin/env python3
"""Cooperative bookkeeping for one RSI-Exam rollout, mounted read-only into the agent's container.

The agent runs this file instead of copying snapshot directories and appending log entries by hand.
Every evaluated candidate becomes a snapshot with a log block the record producer can read, in one
command, and the helper repairs itself from whatever an abrupt stop left on disk.

Commands (``python3 /app/provenance.py <command> ...``; ``PROVENANCE_ROOT`` defaults to ``/app``):

    init [--no-evaluate] [--change TEXT]   snapshot the inherited main/ as v0, log it, measure it,
                                           print the run window; finishes an interrupted init
    evaluate [--from PATH] [--change TEXT] snapshot main/ as the next v<N>, log it as reverted until
                                           decided, run the task's self-check, log the score
    decide v<N> kept|reverted              record the decision; a revert restores the head into main/
    restore v<K>                           put a snapshot back into main/ and make it the head
    finalize [--keep v<N>]                 settle a pending candidate and leave main/ equal to the head
    status                                 the versions, the head, the pending candidate, main/

Layout under ``<root>/methods``: ``main/`` (the graded directory), ``versions/v<N>/`` (snapshots),
``experiment_log.md`` (one block per version: ``## v<N>``, ``- parent:``, ``- status:``,
``- change:``, ``- method tree sha256:``, ``- score:``), ``results/v<N>/selfcheck.json`` (the
self-check's output, evidence that never enters a policy tree), ``.provenance/`` (state, lock,
staging area). The helper owns everything under ``methods/`` except ``main/``.

Ordering and its windows. A snapshot is copied into the staging area and renamed into ``versions/``
(atomic on one filesystem); its block is then appended to the log; the state is saved last. The
interval between the rename and the appended block is a few operations wide; a stop inside it leaves
a snapshot without a block, and the next command adopts that snapshot as the pending candidate with
the parent the state recorded before staging. A decision saves the state before it rewrites the log,
so a stop between the two leaves a log line the next command reconciles from the state; a candidate
reads as ``reverted`` until its decision is durable, so an undecided candidate never reads as kept.
``main/`` equals a snapshot at every moment except while the agent edits it before ``evaluate``
(``evaluate --from PATH`` shrinks that to one file replacement plus the copy into staging) and inside
a restore's swap of two directories; a stop there is closed by ``finalize``, which restores the head
even when ``main/`` cannot be hashed. A partial log write that leaves a block without its status line
is repaired to ``reverted``. A stop before a candidate was measured is repaired at ``decide`` when
``main/`` still holds that candidate. The helper cannot run twice at once: a lock under
``.provenance/`` refuses the second invocation.

Side effects: every command writes under ``<root>/methods``; ``init``, ``evaluate`` and ``decide``
may run ``<root>/selfcheck.py``, which writes ``<root>/visible_result.json``; ``evaluate --from PATH``
reads the given file. Standard library only. Exit status 0 on success, 2 on a refusal that names its
reason, 3 when the test hook ``PROVENANCE_KILL_AFTER=<checkpoint>`` stops the process.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

VERSION_DIR = re.compile(r"^v[0-9]+[a-z0-9_]*$")          # what the record producer recognizes
DECLARATION = re.compile(r"^\s*(?:#{1,6}\s+)?(?:[-*+]\s+)?[*_]{0,2}(v[0-9]+[a-z0-9_]*)\b")
STATUS_LINE = re.compile(r"^- status: (baseline|kept|reverted)$")
EXCLUDED_DIR = "__pycache__"
EXCLUDED_SUFFIXES = (".pyc", ".pyo")


class Refusal(Exception):
    """A named reason the command did not run; printed and exit status 2."""


def checkpoint(name: str) -> None:
    """Test hook: stop the process right after the named step when PROVENANCE_KILL_AFTER names it."""
    if os.environ.get("PROVENANCE_KILL_AFTER") == name:
        sys.stdout.flush()
        os._exit(3)


def sanitize(text: str | None) -> str:
    """One line, no pipes or leading markers that the log reader could take for a declaration."""
    if not text:
        return ""
    flat = " ".join(text.split())
    return flat.replace("|", "/").strip("#-*+ ")[:400]


def numeric(version_id: str) -> int:
    match = re.match(r"^v([0-9]+)", version_id)
    return int(match.group(1)) if match else -1


class Rollout:
    """Paths and state for one rollout root. Every method that changes disk says so in its docstring."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.methods = root / "methods"
        self.main = self.methods / "main"
        self.versions = self.methods / "versions"
        self.log = self.methods / "experiment_log.md"
        self.results = self.methods / "results"
        self.private = self.methods / ".provenance"
        self.staging = self.private / "staging"
        self.state_path = self.private / "state.json"
        self.lock_path = self.private / "lock"
        self._lock_fd: int | None = None

    # ----- lock ----------------------------------------------------------------------------

    def lock(self) -> None:
        """Side effect: takes the rollout lock; refuses when another helper command holds it."""
        self.private.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise Refusal("busy: another provenance command is still running; wait for it to finish")
        self._lock_fd = fd

    # ----- digests -------------------------------------------------------------------------

    @staticmethod
    def file_sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def method_tree_sha256(self, tree: Path) -> str:
        """The record producer's cache-free Python-only digest of a method tree."""
        if not tree.is_dir():
            raise Refusal(f"missing_tree:{tree}")
        rels: list[str] = []
        for child in tree.rglob("*"):
            rel = child.relative_to(tree)
            if EXCLUDED_DIR in rel.parts or child.suffix in EXCLUDED_SUFFIXES:
                continue
            if child.is_symlink():
                raise Refusal(f"symlink_in_tree:{rel.as_posix()}")
            if child.is_dir():
                continue
            if child.suffix != ".py":
                raise Refusal(f"non_python_file_in_tree:{rel.as_posix()}")
            rels.append(rel.as_posix())
        if not rels:
            raise Refusal(f"no_python_files:{tree}")
        lines = [f"{self.file_sha256(tree / rel)}  {rel}\n" for rel in sorted(rels)]
        return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()

    def main_digest(self) -> str | None:
        """main/'s digest, or None when main/ is missing or cannot be hashed (mid-edit, foreign files)."""
        try:
            return self.method_tree_sha256(self.main)
        except Refusal:
            return None

    # ----- log -----------------------------------------------------------------------------

    def log_lines(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.is_file() else []

    def append_log(self, text: str) -> None:
        """Side effect: appends text to experiment_log.md on a fresh line, writing until every byte is out."""
        data = text.encode("utf-8")
        if self.log.is_file() and self.log.stat().st_size > 0:
            with self.log.open("rb") as stream:
                stream.seek(-1, os.SEEK_END)
                if stream.read(1) != b"\n":
                    data = b"\n" + data
        fd = os.open(self.log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                view = view[written:]
        finally:
            os.close(fd)

    def blocks(self) -> dict[str, tuple[int, int]]:
        """version id -> (declaration line index, end index) of the block it owns; the first declaration wins."""
        lines = self.log_lines()
        starts = [(i, m.group(1)) for i, l in enumerate(lines) if (m := DECLARATION.match(l))]
        out: dict[str, tuple[int, int]] = {}
        for pos, (i, vid) in enumerate(starts):
            end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
            out.setdefault(vid, (i, end))
        return out

    def log_status(self, version_id: str) -> str | None:
        """The block's status word; None when the version has no block; '' when the block has no status line."""
        span = self.blocks().get(version_id)
        if span is None:
            return None
        lines = self.log_lines()
        for i in range(span[0] + 1, span[1]):
            match = STATUS_LINE.match(lines[i])
            if match:
                return match.group(1)
        return ""

    def set_status(self, version_id: str, status: str) -> None:
        """Side effect: atomically replaces the log with the version's status line set (inserted if missing)."""
        lines = self.log_lines()
        span = self.blocks().get(version_id)
        if span is None:
            raise Refusal(f"log_missing_version:{version_id}")
        for i in range(span[0] + 1, span[1]):
            if STATUS_LINE.match(lines[i]):
                lines[i] = f"- status: {status}"
                break
        else:
            lines.insert(span[0] + 1, f"- status: {status}")
        tmp = self.log.with_suffix(".md.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, self.log)
        checkpoint("status_rewritten")

    @staticmethod
    def block_text(version_id: str, parent: str, status: str, change: str | None, digest: str) -> str:
        return (f"## {version_id}\n- parent: {parent}\n- status: {status}\n"
                f"- change: {sanitize(change) or 'not described'}\n- method tree sha256: {digest}\n")

    def is_newest_block(self, version_id: str) -> bool:
        spans = self.blocks()
        return bool(spans) and max(spans, key=lambda v: spans[v][0]) == version_id

    # ----- state ---------------------------------------------------------------------------

    def read_state(self) -> dict:
        if not self.state_path.is_file():
            raise Refusal("not_initialized: run `python3 /app/provenance.py init` first")
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save_state(self, state: dict, name: str = "state_saved") -> None:
        """Side effect: atomically replaces state.json; ``name`` is the checkpoint the test hook sees."""
        self.private.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.state_path)
        checkpoint(name)

    def snapshot_ids(self) -> list[str]:
        if not self.versions.is_dir():
            return []
        return sorted((c.name for c in self.versions.iterdir() if c.is_dir() and VERSION_DIR.match(c.name)),
                      key=lambda v: (numeric(v), v))

    def next_id(self) -> str:
        used = {numeric(v) for v in self.snapshot_ids()} | {numeric(v) for v in self.blocks()}
        used.discard(-1)
        return f"v{max(used) + 1}" if used else "v0"

    def load_state(self) -> dict:
        """The saved state reconciled with the disk. Side effects: may append or rewrite log blocks and
        rewrite state.json.

        Reconciliation, in order: every snapshot's digest is recomputed and a changed snapshot is refused
        (snapshots are never edited); a snapshot the state never learned of is the pending candidate (an
        evaluate stopped before its state save), with the parent the state recorded as its intent; a
        snapshot without a log block gets one, status reverted; a block without a status line gets
        ``reverted``; the head's block reads ``kept`` (``baseline`` for the first version).
        """
        state = self.read_state()
        digests: dict[str, str] = state.setdefault("digests", {})
        intent = state.get("intent") or {}
        changed = False
        for version_id in self.snapshot_ids():
            digest = self.method_tree_sha256(self.versions / version_id)
            if version_id in digests and digests[version_id] != digest:
                raise Refusal(f"snapshot_modified:{version_id}: snapshots are never edited; use restore or evaluate")
            if version_id not in digests:
                digests[version_id] = digest
                if state.get("pending") is None and version_id != state.get("head"):
                    state["pending"] = version_id
                changed = True
            if version_id not in self.blocks():
                own = intent.get("version_id") == version_id
                self.append_log(self.block_text(
                    version_id, intent["parent"] if own else state["head"], "reverted",
                    intent.get("change") if own else "adopted after an interrupted evaluate; not described",
                    digest))
                self.append_log("- score: not measured (the interrupted evaluate did not finish)\n")
                changed = True
            elif self.log_status(version_id) == "":
                self.set_status(version_id, "reverted")
        if intent and intent.get("version_id") in digests:
            state["intent"] = None
            changed = True
        head = state["head"]
        expected = "baseline" if head == state.get("first") else "kept"
        if head in self.blocks() and self.log_status(head) != expected:
            self.set_status(head, expected)
        if changed:
            self.save_state(state)
        return state

    # ----- snapshots and main/ -------------------------------------------------------------

    def copy_tree(self, source: Path, target: Path) -> None:
        """Side effect: copies a method tree without bytecode caches into a fresh target."""
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns(EXCLUDED_DIR, "*.pyc", "*.pyo"))

    def stage_snapshot(self, version_id: str) -> Path:
        """Side effect: copies main/ into the staging area under the version's name."""
        self.staging.mkdir(parents=True, exist_ok=True)
        staged = self.staging / version_id
        self.copy_tree(self.main, staged)
        checkpoint("staged")
        return staged

    def commit_snapshot(self, staged: Path, version_id: str) -> None:
        """Side effect: renames the staged copy into versions/ (atomic on one filesystem)."""
        self.versions.mkdir(parents=True, exist_ok=True)
        target = self.versions / version_id
        if target.exists():
            raise Refusal(f"snapshot_exists:{version_id}")
        os.rename(staged, target)
        checkpoint("renamed")

    def replace_main(self, version_id: str) -> None:
        """Side effect: swaps main/ for a copy of the snapshot through the staging area; tolerates a
        missing or unhashable main/."""
        source = self.versions / version_id
        if not source.is_dir():
            raise Refusal(f"unknown_version:{version_id}")
        fresh = self.staging / "main.next"
        self.copy_tree(source, fresh)
        old = self.staging / "main.previous"
        if old.exists():
            shutil.rmtree(old)
        if self.main.exists():
            os.rename(self.main, old)
            checkpoint("main_moved_aside")
        os.rename(fresh, self.main)
        checkpoint("restored")
        shutil.rmtree(old, ignore_errors=True)

    # ----- self-check ----------------------------------------------------------------------

    def run_selfcheck(self) -> dict | None:
        """Side effect: runs <root>/selfcheck.py (which writes visible_result.json); echoes its output."""
        script = self.root / "selfcheck.py"
        if not script.is_file():
            print(f"provenance: no self-check at {script}; score not measured")
            return None
        result_path = self.root / "visible_result.json"
        if result_path.exists():
            result_path.unlink()
        proc = subprocess.run([sys.executable, str(script)], cwd=self.root, capture_output=True, text=True)
        sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        if proc.returncode != 0 or not result_path.is_file():
            first = (proc.stderr.strip() or proc.stdout.strip()).splitlines()
            print(f"provenance: self-check failed (exit {proc.returncode}): {first[0] if first else 'no output'}")
            return None
        try:
            return json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("provenance: self-check wrote unreadable JSON; score not measured")
            return None

    @staticmethod
    def plain(value: object) -> str | None:
        """A finite number as a plain decimal the log reader parses; None for anything else."""
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text if text not in ("", "-", "-0") else "0"

    def score_line(self, result: dict | None) -> str:
        mean = self.plain(result.get("mean_score")) if result else None
        if mean is None:
            return "- score: not measured (the self-check did not return a mean score)"
        extras = []
        for key, label in (("median_score", "median"), ("mean_max_tile", "mean max tile"),
                           ("cpu_seconds_per_game", "cpu s per game"), ("valid_fraction", "valid fraction")):
            value = self.plain((result or {}).get(key))
            if value is not None:
                extras.append(f"{label} {value}")
        tail = f" ({'; '.join(extras)})" if extras else ""
        return f"- score: {mean} mean over the public suite{tail}"

    def measure(self, version_id: str, digest: str) -> dict | None:
        """Side effects: runs the self-check on main/, writes results/<version>/selfcheck.json, appends the
        score line to the version's block (it is the newest block, so an append lands in it)."""
        result = self.run_selfcheck()
        target = self.results / version_id
        target.mkdir(parents=True, exist_ok=True)
        payload = {"version_id": version_id, "method_tree_sha256": digest,
                   "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "selfcheck": result}
        (target / "selfcheck.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.append_log(self.score_line(result) + "\n")
        checkpoint("scored")
        return result

    def measured(self, version_id: str) -> bool:
        return (self.results / version_id / "selfcheck.json").is_file()

    def measure_if_needed(self, version_id: str, state: dict) -> None:
        """Side effect: measures a version that was never measured, when main/ still holds it and its block
        is the newest (so the score line lands in it)."""
        if self.measured(version_id) or not self.is_newest_block(version_id):
            return
        if self.main_digest() != state["digests"].get(version_id):
            return
        print(f"provenance: {version_id} was never measured; running the self-check first")
        self.measure(version_id, state["digests"][version_id])

    # ----- commands ------------------------------------------------------------------------

    def window_line(self) -> str:
        seconds = os.environ.get("ARB_AGENT_TIMEOUT_SEC")
        try:
            value = float(seconds) if seconds else 0.0
        except ValueError:
            value = 0.0
        if value <= 0:
            return "run window: not stated by the harness"
        return f"run window: {value:.0f} s of wall clock (about {value / 60:.0f} min) for the whole run"

    def cmd_init(self, evaluate: bool, change: str | None) -> int:
        if self.state_path.is_file():
            state = self.load_state()
            if evaluate:
                self.measure_if_needed("v0", state)
            print("provenance: already initialized")
            return self.cmd_status()
        if not self.main.is_dir():
            raise Refusal(f"missing_main:{self.main}")
        snapshots, declared = self.snapshot_ids(), list(self.blocks())
        if snapshots not in ([], ["v0"]) or any(v != "v0" for v in declared):
            raise Refusal("init_after_changes: versions/ or the log already has entries; init must come first")
        if snapshots == ["v0"]:
            digest = self.method_tree_sha256(self.versions / "v0")
            print("provenance: finishing an interrupted init from the existing v0")
        else:
            digest = self.method_tree_sha256(self.main)
            staged = self.stage_snapshot("v0")
            self.commit_snapshot(staged, "v0")
        if "v0" not in declared:
            self.append_log(self.block_text("v0", "none", "baseline",
                                            change or "inherited starter policy, unchanged", digest))
            checkpoint("appended")
        elif self.log_status("v0") == "":
            self.set_status("v0", "baseline")
        state = {"head": "v0", "first": "v0", "pending": None, "intent": None, "digests": {"v0": digest}}
        self.save_state(state)
        if evaluate:
            self.measure_if_needed("v0", state)
        print(f"provenance: v0 snapshotted and logged from main/ (method tree {digest[:12]}); head v0")
        print(f"provenance: {self.window_line()}")
        return 0

    def cmd_evaluate(self, source: Path | None, change: str | None) -> int:
        state = self.load_state()
        if state.get("pending"):
            raise Refusal(f"pending_decision:{state['pending']}: run `decide {state['pending']} kept` or "
                          f"`decide {state['pending']} reverted` before evaluating another candidate")
        if not self.main.is_dir():
            raise Refusal("missing_main: run `finalize` to put the head back into main/")
        if source is not None:
            if not source.is_file():
                raise Refusal(f"missing_candidate:{source}")
            self.staging.mkdir(parents=True, exist_ok=True)
            tmp = self.staging / "candidate.py"
            shutil.copyfile(source, tmp)
            os.replace(tmp, self.main / "policy.py")
            checkpoint("candidate_placed")
        digest = self.method_tree_sha256(self.main)
        head = state["head"]
        digests: dict[str, str] = state["digests"]
        if digests.get(head) == digest:
            print(f"provenance: main/ is identical to the head {head}; nothing new to evaluate. "
                  f"Edit main/ (or pass --from PATH) and run evaluate again.")
            return 0
        same = [v for v, d in digests.items() if d == digest]
        if same:
            raise Refusal(f"main_equals_snapshot:{same[0]}: main/ already is that snapshot; restore it with "
                          f"`restore {same[0]}` if you want it as the head")
        version_id = self.next_id()
        state["intent"] = {"version_id": version_id, "parent": head, "change": sanitize(change) or "not described"}
        self.save_state(state, "intent_saved")
        staged = self.stage_snapshot(version_id)
        self.commit_snapshot(staged, version_id)
        self.append_log(self.block_text(version_id, head, "reverted", change, digest))
        checkpoint("appended")
        state["pending"] = version_id
        state["intent"] = None
        digests[version_id] = digest
        self.save_state(state)
        result = self.measure(version_id, digest)
        mean = result.get("mean_score") if result else None
        print(f"provenance: {version_id} (parent {head}) snapshotted and logged; self-check mean "
              f"{mean if mean is not None else 'not measured'}. Status reads reverted until you run "
              f"`decide {version_id} kept` or `decide {version_id} reverted`.")
        return 0

    def cmd_decide(self, version_id: str, status: str) -> int:
        state = self.load_state()
        if state.get("pending") != version_id:
            raise Refusal(f"not_pending:{version_id}: only the candidate awaiting a decision can be decided"
                          + (f" (pending: {state['pending']})" if state.get("pending") else ""))
        self.measure_if_needed(version_id, state)
        state["pending"] = None
        if status == "kept":
            state["head"] = version_id
        self.save_state(state)
        self.set_status(version_id, status)
        if status == "kept":
            print(f"provenance: {version_id} kept; head is now {version_id}")
            return 0
        self.replace_main(state["head"])
        print(f"provenance: {version_id} reverted; main/ restored to the head {state['head']}")
        return 0

    def cmd_restore(self, version_id: str) -> int:
        state = self.load_state()
        if state.get("pending"):
            raise Refusal(f"pending_decision:{state['pending']}: decide it before restoring")
        if version_id not in self.snapshot_ids():
            raise Refusal(f"unknown_version:{version_id}")
        state["head"] = version_id
        self.save_state(state)
        self.replace_main(version_id)
        print(f"provenance: main/ restored to {version_id}; head is now {version_id}")
        return 0

    def cmd_finalize(self, keep: str | None) -> int:
        state = self.load_state()
        pending = state.get("pending")
        if pending:
            self.cmd_decide(pending, "kept" if keep == pending else "reverted")
            state = self.read_state()
        elif keep and keep != state["head"]:
            raise Refusal(f"not_pending:{keep}: only a pending candidate can be kept at finalize")
        head = state["head"]
        digest = self.main_digest()
        if digest != state["digests"].get(head):
            what = f"method tree {digest[:12]}" if digest else "not a clean method tree"
            print(f"provenance: main/ ({what}) differs from the head {head}; restoring the head. "
                  f"Edits made after the last decision are not part of any version.")
            self.replace_main(head)
        print(f"provenance: finalized; main/ equals {head}. Do not edit main/ after this.")
        return 0

    def cmd_status(self) -> int:
        state = self.load_state()
        digests = state["digests"]
        main_digest = self.main_digest()
        print("| version | logged | status | measured | method tree |")
        print("|---|---|---|---|---|")
        for v in self.snapshot_ids():
            status = self.log_status(v)
            print(f"| {v} | {'yes' if status is not None else 'NO'} | {status or '?'} | "
                  f"{'yes' if self.measured(v) else 'no'} | {digests.get(v, '')[:12]} |")
        matching = [v for v, d in digests.items() if d == main_digest] if main_digest else []
        print(f"head {state['head']}; pending {state.get('pending') or 'none'}; main/ equals "
              f"{matching[0] if matching else 'no snapshot (edits in progress)'}")
        print(f"provenance: {self.window_line()}")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="provenance.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("PROVENANCE_ROOT", "/app")))
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--no-evaluate", action="store_true")
    p_init.add_argument("--change", default=None)
    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--from", dest="source", type=Path, default=None)
    p_eval.add_argument("--change", default=None)
    p_dec = sub.add_parser("decide")
    p_dec.add_argument("version_id")
    p_dec.add_argument("status", choices=("kept", "reverted"))
    p_res = sub.add_parser("restore")
    p_res.add_argument("version_id")
    p_fin = sub.add_parser("finalize")
    p_fin.add_argument("--keep", default=None)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    rollout = Rollout(args.root)
    try:
        rollout.lock()
        if args.command == "init":
            return rollout.cmd_init(not args.no_evaluate, args.change)
        if args.command == "evaluate":
            return rollout.cmd_evaluate(args.source, args.change)
        if args.command == "decide":
            return rollout.cmd_decide(args.version_id, args.status)
        if args.command == "restore":
            return rollout.cmd_restore(args.version_id)
        if args.command == "finalize":
            return rollout.cmd_finalize(args.keep)
        return rollout.cmd_status()
    except Refusal as exc:
        print(f"provenance refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
