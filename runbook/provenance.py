#!/usr/bin/env python3
"""Cooperative bookkeeping for one RSI-Exam rollout, mounted read-only into the agent's container.

The agent runs this file instead of copying snapshot directories and appending log entries by hand.
Every evaluated candidate becomes a snapshot with a log block the record producer can read, in one
command, and ``main/`` equals a snapshot at every moment except the microseconds between two
filesystem operations and the stretch while the agent edits ``main/`` before evaluating it.

Commands (``python3 /app/provenance.py <command> ...``; ``PROVENANCE_ROOT`` defaults to ``/app``):

    init [--no-evaluate] [--change TEXT]      snapshot the inherited main/ as v0, log it, measure it
    evaluate [--from PATH] [--parent vK] [--change TEXT]
                                              snapshot main/ as the next v<N>, log it as reverted
                                              until decided, run the task's self-check, log the score
    decide v<N> kept|reverted [--no-restore]  record the decision; a revert restores the head into main/
    restore v<K>                              put a snapshot back into main/ and make it the head
    finalize [--keep v<N>]                    settle a pending candidate and leave main/ equal to the head
    status                                    the versions, the head, the pending candidate, main/

Layout under ``<root>/methods``: ``main/`` (the graded directory), ``versions/v<N>/`` (snapshots),
``experiment_log.md`` (one block per version: ``## v<N>``, ``- parent:``, ``- status:``,
``- change:``, ``- score:``), ``results/v<N>/selfcheck.json`` (the self-check's output, evidence that
never enters a policy tree), ``.provenance/state.json`` (head, pending, staging area).

Ordering and its windows. A snapshot is copied into a staging directory, renamed into
``versions/`` (atomic on one filesystem), and then its block is appended to the log with a single
write. A stop between the rename and the append leaves a snapshot without a block, which the record
producer refuses as ``log_missing_version``; that window is one system call wide. A stop while the
agent is editing ``main/`` before ``evaluate`` leaves ``main/`` equal to no snapshot, which the
producer refuses as ``submitted_not_snapshotted``; ``evaluate --from PATH`` shrinks that window to
one file replacement, and ``finalize`` closes it by restoring the head. Status is written as
``reverted`` when a candidate is snapshotted and rewritten in place (atomic replace of the log) when
the agent decides, so a candidate the agent never decided reads as reverted, never as kept.

Side effects: every command writes under ``<root>/methods`` and ``evaluate`` runs
``<root>/selfcheck.py``, which writes ``<root>/visible_result.json``. Nothing here reads or
writes outside ``<root>``. Standard library only. Exit status 0 on success, 2 on a refusal that
names its reason, 3 when the test hook ``PROVENANCE_KILL_AFTER=<checkpoint>`` stops the process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

VERSION_ID = re.compile(r"^v[0-9]+$")
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


class Rollout:
    """Paths and state for one rollout root. Every method that changes disk says so."""

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
        rels: list[str] = []
        for child in tree.rglob("*"):
            rel = child.relative_to(tree)
            if EXCLUDED_DIR in rel.parts or child.suffix in EXCLUDED_SUFFIXES:
                continue
            if child.is_dir():
                continue
            if child.suffix != ".py":
                raise Refusal(f"non_python_file_in_tree:{rel.as_posix()}")
            rels.append(rel.as_posix())
        if not rels:
            raise Refusal(f"no_python_files:{tree}")
        lines = [f"{self.file_sha256(tree / rel)}  {rel}\n" for rel in sorted(rels)]
        return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()

    # ----- state ---------------------------------------------------------------------------

    def load_state(self) -> dict:
        """The saved state, reconciled with the disk: a snapshot the log never named (a stop between the
        rename and the append) is adopted as the pending candidate, and every snapshot has a digest.
        Side effect: may append one log block and rewrite state.json."""
        if not self.state_path.is_file():
            raise Refusal("not_initialized: run `python3 /app/provenance.py init` first")
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        digests: dict[str, str] = state.setdefault("digests", {})
        declared = set(self.declared_ids())
        changed = False
        for version_id in self.snapshot_ids():
            if version_id not in digests:
                # The state never learned of this snapshot: an evaluate stopped after the rename (and
                # perhaps after the append) but before the state was saved. It is the undecided candidate.
                digests[version_id] = self.method_tree_sha256(self.versions / version_id)
                if state.get("pending") is None and version_id != state.get("head"):
                    state["pending"] = version_id
                changed = True
            if version_id not in declared:
                self.append_log(f"## {version_id}\n- parent: {state['head']}\n- status: reverted\n"
                                f"- change: adopted by the helper after an interrupted evaluate; not described\n"
                                f"- method tree sha256: {digests[version_id]}\n"
                                f"- score: not measured (the interrupted evaluate did not finish)\n")
                declared.add(version_id)
                changed = True
        if changed:
            self.save_state(state)
        return state

    def save_state(self, state: dict) -> None:
        """Side effect: atomically replaces state.json."""
        self.private.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.state_path)
        checkpoint("state_saved")

    # ----- log -----------------------------------------------------------------------------

    def append_log(self, text: str) -> None:
        """Side effect: appends text to experiment_log.md in one write."""
        fd = os.open(self.log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)

    def log_lines(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.is_file() else []

    def declared_ids(self) -> list[str]:
        ids: list[str] = []
        for line in self.log_lines():
            match = DECLARATION.match(line)
            if match and match.group(1) not in ids:
                ids.append(match.group(1))
        return ids

    def rewrite_status(self, version_id: str, status: str) -> None:
        """Side effect: atomically replaces the log with the version's status line rewritten."""
        lines = self.log_lines()
        start = next((i for i, l in enumerate(lines)
                      if (m := DECLARATION.match(l)) and m.group(1) == version_id), None)
        if start is None:
            raise Refusal(f"log_missing_version:{version_id}")
        end = next((i for i in range(start + 1, len(lines)) if DECLARATION.match(lines[i])), len(lines))
        for i in range(start, end):
            if STATUS_LINE.match(lines[i]):
                lines[i] = f"- status: {status}"
                break
        else:
            raise Refusal(f"log_has_no_status_line:{version_id}")
        tmp = self.log.with_suffix(".md.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, self.log)
        checkpoint("status_rewritten")

    # ----- snapshots -----------------------------------------------------------------------

    def snapshot_ids(self) -> list[str]:
        if not self.versions.is_dir():
            return []
        return sorted((c.name for c in self.versions.iterdir() if c.is_dir() and VERSION_ID.match(c.name)),
                      key=lambda v: int(v[1:]))

    def next_id(self) -> str:
        used = {int(v[1:]) for v in self.snapshot_ids()}
        used |= {int(v[1:]) for v in self.declared_ids() if VERSION_ID.match(v)}
        return f"v{max(used) + 1}" if used else "v0"

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
        """Side effect: swaps main/ for a copy of the snapshot, through the staging area."""
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

    def store_result(self, version_id: str, result: dict | None, digest: str) -> str:
        """Side effect: writes results/<version>/selfcheck.json. Returns the log's score line."""
        target = self.results / version_id
        target.mkdir(parents=True, exist_ok=True)
        payload = {"version_id": version_id, "method_tree_sha256": digest,
                   "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "selfcheck": result}
        (target / "selfcheck.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not result or not isinstance(result.get("mean_score"), (int, float)):
            return "- score: not measured (the self-check did not return a mean score)"
        extras = []
        for key, label in (("median_score", "median"), ("mean_max_tile", "mean max tile"),
                           ("cpu_seconds_per_game", "cpu s per game"), ("valid_fraction", "valid fraction")):
            if isinstance(result.get(key), (int, float)):
                extras.append(f"{label} {result[key]}")
        tail = f" ({'; '.join(extras)})" if extras else ""
        return f"- score: {result['mean_score']} mean over the public suite{tail}"

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
            print("provenance: already initialized")
            return self.cmd_status()
        if not self.main.is_dir():
            raise Refusal(f"missing_main:{self.main}")
        snapshots, declared = self.snapshot_ids(), self.declared_ids()
        if snapshots not in ([], ["v0"]) or any(v != "v0" for v in declared):
            raise Refusal("init_after_changes: versions/ or the log already has entries; init must come first")
        if snapshots == ["v0"]:
            # A stop between the rename and the log append, or between the append and the state save:
            # finish the init from what is on disk rather than refusing forever.
            digest = self.method_tree_sha256(self.versions / "v0")
            print("provenance: finishing an interrupted init from the existing v0")
        else:
            digest = self.method_tree_sha256(self.main)
            staged = self.stage_snapshot("v0")
            self.commit_snapshot(staged, "v0")
        if "v0" not in declared:
            self.append_log("## v0\n- parent: none\n- status: baseline\n"
                            f"- change: {sanitize(change) or 'inherited starter policy, unchanged'}\n"
                            f"- method tree sha256: {digest}\n")
            checkpoint("appended")
        self.save_state({"head": "v0", "pending": None, "digests": {"v0": digest}})
        if evaluate and not (self.results / "v0" / "selfcheck.json").is_file():
            result = self.run_selfcheck()
            self.append_log(self.store_result("v0", result, digest) + "\n")
            checkpoint("scored")
        print(f"provenance: v0 snapshotted and logged from main/ (method tree {digest[:12]}); head v0")
        print(f"provenance: {self.window_line()}")
        return 0

    def cmd_evaluate(self, source: Path | None, parent: str | None, change: str | None) -> int:
        state = self.load_state()
        if state.get("pending"):
            raise Refusal(f"pending_decision:{state['pending']}: run `decide {state['pending']} kept` or "
                          f"`decide {state['pending']} reverted` before evaluating another candidate")
        if not self.main.is_dir():
            raise Refusal("missing_main: run `finalize` (or `restore v<K>`) to put a snapshot back into main/")
        if source is not None:
            if not source.is_file():
                raise Refusal(f"missing_candidate:{source}")
            target = self.main / "policy.py"
            tmp = self.main / ".policy.py.tmp"
            shutil.copyfile(source, tmp)
            os.replace(tmp, target)
            checkpoint("candidate_placed")
        digest = self.method_tree_sha256(self.main)
        head = state["head"]
        parent = parent or head
        if parent not in self.snapshot_ids() and parent not in self.declared_ids():
            raise Refusal(f"unknown_parent:{parent}")
        digests: dict[str, str] = state.get("digests", {})
        if digests.get(head) == digest:
            print(f"provenance: main/ is identical to the head {head}; nothing new to evaluate. "
                  f"Edit main/ (or pass --from PATH) and run evaluate again.")
            return 0
        same = [v for v, d in digests.items() if d == digest]
        if same:
            raise Refusal(f"main_equals_snapshot:{same[0]}: restore it with `restore {same[0]}` instead")
        version_id = self.next_id()
        staged = self.stage_snapshot(version_id)
        self.commit_snapshot(staged, version_id)
        self.append_log(f"## {version_id}\n- parent: {parent}\n- status: reverted\n"
                        f"- change: {sanitize(change) or 'not described'}\n"
                        f"- method tree sha256: {digest}\n")
        checkpoint("appended")
        state["pending"] = version_id
        digests[version_id] = digest
        state["digests"] = digests
        self.save_state(state)
        result = self.run_selfcheck()
        self.append_log(self.store_result(version_id, result, digest) + "\n")
        checkpoint("scored")
        mean = result.get("mean_score") if result else None
        print(f"provenance: {version_id} (parent {parent}) snapshotted and logged; self-check mean "
              f"{mean if mean is not None else 'not measured'}. Status reads reverted until you run "
              f"`decide {version_id} kept` or `decide {version_id} reverted`.")
        return 0

    def cmd_decide(self, version_id: str, status: str, restore: bool) -> int:
        state = self.load_state()
        if state.get("pending") != version_id:
            raise Refusal(f"not_pending:{version_id}: only the candidate awaiting a decision can be decided"
                          + (f" (pending: {state['pending']})" if state.get("pending") else ""))
        self.rewrite_status(version_id, status)
        state["pending"] = None
        if status == "kept":
            state["head"] = version_id
            self.save_state(state)
            print(f"provenance: {version_id} kept; head is now {version_id}")
            return 0
        self.save_state(state)
        if restore:
            self.replace_main(state["head"])
            print(f"provenance: {version_id} reverted; main/ restored to the head {state['head']}")
        else:
            print(f"provenance: {version_id} reverted; main/ left as it is (head {state['head']})")
        return 0

    def cmd_restore(self, version_id: str) -> int:
        state = self.load_state()
        if state.get("pending"):
            raise Refusal(f"pending_decision:{state['pending']}: decide it before restoring")
        if version_id not in self.snapshot_ids():
            raise Refusal(f"unknown_version:{version_id}")
        self.replace_main(version_id)
        state["head"] = version_id
        self.save_state(state)
        print(f"provenance: main/ restored to {version_id}; head is now {version_id}")
        return 0

    def cmd_finalize(self, keep: str | None) -> int:
        state = self.load_state()
        pending = state.get("pending")
        if pending:
            if keep == pending:
                self.cmd_decide(pending, "kept", restore=False)
            else:
                self.cmd_decide(pending, "reverted", restore=True)
            state = self.load_state()
        elif keep and keep != state["head"]:
            raise Refusal(f"not_pending:{keep}: only a pending candidate can be kept at finalize")
        head = state["head"]
        digest = self.method_tree_sha256(self.main) if self.main.is_dir() else ""
        if state.get("digests", {}).get(head) != digest:
            print(f"provenance: main/ (method tree {digest[:12]}) differs from the head {head}; restoring "
                  f"the head. Edits made after the last decision are not part of any version.")
            self.replace_main(head)
        print(f"provenance: finalized; main/ equals {head}. Do not edit main/ after this.")
        return 0

    def cmd_status(self) -> int:
        state = self.load_state()
        ids = self.snapshot_ids()
        declared = set(self.declared_ids())
        lines = self.log_lines()
        statuses: dict[str, str] = {}
        current = None
        for line in lines:
            match = DECLARATION.match(line)
            if match:
                current = match.group(1)
                continue
            if current and STATUS_LINE.match(line):
                statuses[current] = STATUS_LINE.match(line).group(1)  # type: ignore[union-attr]
        main_digest = self.method_tree_sha256(self.main) if self.main.is_dir() else ""
        print("| version | logged | status | method tree |")
        print("|---|---|---|---|")
        for v in ids:
            print(f"| {v} | {'yes' if v in declared else 'NO'} | {statuses.get(v, '?')} | "
                  f"{state.get('digests', {}).get(v, '')[:12]} |")
        matching = [v for v, d in state.get("digests", {}).items() if d == main_digest]
        print(f"head {state['head']}; pending {state.get('pending') or 'none'}; main/ equals "
              f"{matching[0] if matching else 'no snapshot (edits in progress)'}")
        print(f"provenance: {self.window_line()}")
        return 0


def sanitize(text: str | None) -> str:
    """One line, no pipes or leading markers that the log reader could take for a declaration."""
    if not text:
        return ""
    flat = " ".join(text.split())
    return flat.replace("|", "/").strip("#-*+ ")[:400]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="provenance.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("PROVENANCE_ROOT", "/app")))
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--no-evaluate", action="store_true")
    p_init.add_argument("--change", default=None)
    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--from", dest="source", type=Path, default=None)
    p_eval.add_argument("--parent", default=None)
    p_eval.add_argument("--change", default=None)
    p_dec = sub.add_parser("decide")
    p_dec.add_argument("version_id")
    p_dec.add_argument("status", choices=("kept", "reverted"))
    p_dec.add_argument("--no-restore", action="store_true")
    p_res = sub.add_parser("restore")
    p_res.add_argument("version_id")
    p_fin = sub.add_parser("finalize")
    p_fin.add_argument("--keep", default=None)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    rollout = Rollout(args.root)
    try:
        if args.command == "init":
            return rollout.cmd_init(not args.no_evaluate, args.change)
        if args.command == "evaluate":
            return rollout.cmd_evaluate(args.source, args.parent, args.change)
        if args.command == "decide":
            return rollout.cmd_decide(args.version_id, args.status, not args.no_restore)
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
