# Milestone 1: Gate Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the decision gate from a screening-only tool into the screening-and-confirmation gate the contract describes. A task profile fixes what the agent may not choose. Every evaluation runs in a child interpreter that loads the pinned evaluator before the policy can shadow it, and leaves a receipt binding the result to a method tree, a suite, and an evaluator by digest. A screening that does not revert freezes both snapshots, plans its confirmation, and reverts when the plan does not fit the profile's cap. A confirmation re-derives that plan and that suite from the evidence before it resolves. The decision log, the converter, and the contract carry the seven gated keys, and a restore helper puts a reverted snapshot back without nesting it.

**Architecture:** Five new standard-library modules under `gate/` (`treedigest.py`, `task_profile.py`, `seeds.py`, `evaluate_suite.py`, `restore.py`), a rewritten `gate/decide.py` with two modes (gated, `--profile`; replay, `--confirm inconclusive`), and a rewritten `gate/trace_from_decisions.py` that re-checks the gated rules and carries the new keys in the TRACE block as uninterpreted extras. The test modules share `tests/gate_fixtures.py`. Nothing under `profile/` changes in this milestone; the verifier's decision checks are Milestone 2, and mounting the gate into a real rollout is Milestone 3.

**Tech Stack:** Python 3.12 locally, 3.13 in the RSI-Exam sandbox (`python:3.13-slim`); standard library only; `unittest`; `pyright` basic mode.

**Spec:** `docs/ROADMAP.md` (Milestone 1), `docs/decision-log-contract.md` (the contract and its planned additions), `docs/overview.md` section 4 (the rule), and `CLAUDE.md` (working rules). The real task files this plan was written against: dataset `RSI-Exam/RSI-Exam` at revision `956025d7ecf6`, task `game2048_policy_search` (`environment/evaluate.py`, `environment/game2048.py`, `environment/selfcheck.py`, `environment/visible_seeds.json`, `tests/policy_sandbox.py`, `instruction.md`, `task.toml`).

## Global Constraints

Copied from `CLAUDE.md`; every task's requirements include these.

- **Standard library only** in `gate/`, `profile/`, and their tests. No third-party imports anywhere in this plan.
- **Fail loud.** A missing file, a seed-set mismatch, a malformed line, a digest mismatch, or a contract violation raises or returns a named error with a non-zero exit. Nothing warns and proceeds. No silent defaults for policy-bearing flags.
- **Evidence never lives in the policy tree.** Result files, suites, and receipts go under `methods/results/<version>/`, never under `methods/versions/<version>/` or `methods/main/`. The grader (`tests/policy_sandbox.py::_stage_policy`) rejects any non-`.py` regular file under `main/` and the submission scores 0.0.
- **Digests of a method cover Python files only and exclude bytecode caches** (`__pycache__/`, `*.pyc`, `*.pyo`), as the grader does; a symlink anywhere in a method tree is refused.
- **Vocabulary.** Tamper-evident, never tamper-proof, immutable, trustless, notarized, or independent. Verdict (`clears`, `below`, `inconclusive`) is statistics; disposition (`keep`, `revert`, `provisional`) is the action. An interval is never the probability a decision was right.
- **The log carries numbers, identifiers, locators, and digests only.** No prompts, transcripts, or reasoning.
- **Git:** work on the branches named in this plan; one commit per task; commit messages `type(scope): summary` with a body that states what changed and why; **no assistant attribution footers, no session narrative**; `python3 -m unittest discover -s tests -t .` and `pyright gate profile tests` clean before every push; pull requests with Summary / Why / Verification.
- **Compatibility:** code must run on Python 3.12 and 3.13. `datetime.UTC`, `statistics.NormalDist`, `hmac`, `fcntl`, `resource`, `signal` are all available on both.

## STOP conditions (apply at every step)

Stop, do not improvise, and report to the operator when any of these happens:

1. A step says "Expected: PASS" and the run does not pass after one honest fix attempt.
2. `pyright gate profile tests` reports any error on the files you touched.
3. A downloaded fixture file's SHA-256 does not match the digest the Task 4 fetch script pins (the script exits non-zero and prints the mismatch).
4. The task's `evaluate.py` interface differs from what Task 4 states (`evaluate(policy_path: Path, suite_path: Path) -> dict` with keys `mean_score`, `median_score`, `mean_max_tile`, `valid_fraction`, `instances`, and each instance carrying `seed`, `score`, and `error`).
5. You find yourself about to write a result, suite, or receipt under `versions/` or `main/`, or to change anything under `profile/`.
6. `resource.setrlimit`, `signal.SIGXCPU`, or `fcntl.flock` is unavailable on your platform (this plan assumes macOS or Linux).
7. Any step would add a third-party runtime or test dependency to the repository. Task 0 is an operator runbook and may use operator tooling (Docker, `uvx`, `harbor`, `gh`) that nothing in this repository imports; that tooling is exempt from this rule and from nothing else.

## Decisions the operator must make before the first gated run (not blockers for the code)

These are values in the task profile, not code. The code in this plan accepts any valid values; the test profile uses small ones.

- **`min_effect`.** The rule supports `{"kind": "absolute", "value": V}` and `{"kind": "fraction_of_parent_visible_mean", "fraction": F}`. The fraction is resolved once, at screening, against the mean of the parent's visible per-seed scores; the resolved absolute number is recorded on the line and reused unchanged by the confirmation, so a later parent measurement cannot move the line. The value drives the confirmation plan: with the worked-example screening deltas (`[1310, 820, 410, 200, 60, -190, -300, -230]`, sample standard deviation 565.5) and `min_effect` 103 (2.5 percent of a 4120 parent mean) the rule plans 327 confirmation games per policy; at 10 percent (412) it plans 21.
- **`confirmation.max_seeds`** (the cap) and **`confirmation.floor`**. When the planned size exceeds the cap the gate does not open an under-powered confirmation and does not label one: the candidate reverts on the screening line with its plan recorded. A cap chosen too low therefore turns every noisy candidate into a revert, and a minimum effect chosen too small does the same; choose the fraction and the cap together. A confirmation costs two evaluations of `size` games each; the weak baseline plays eight games in about a tenth of a second, a strong policy can take seconds per game.
- **`visible_suite_sha256`**, the digest of the task's visible seed file. Every screening receipt must carry it, so a screening measured on some other seed set is refused.
- **`replication_key`** (32 random bytes as 64 hex) and **`audit_key_sha256`** (the digest of a separate audit key kept outside the sandbox; Milestone 3's audit suite uses the key itself). The replication key is mounted with the profile, so the confirmation seeds are re-derivable by anyone holding it, including the agent; the derivation makes freshness checkable after the fact, it does not hide the seeds. Agent compliance is measured, not assumed.
- **`rollout_id`**, one per run, written into that run's profile.
- **The profile file's own digest.** The gate records it on every line and the runner records it in every receipt. Keep the digest of the profile you mounted: the post-rollout verifier (Milestone 2) compares it with the one the log carries, which is what makes a substituted profile visible.

## Known numbers used by tests (computed against the real task files)

- Weak baseline policy on the visible suite (8 seeds, `max_moves` 10000): mean 2060.0; per seed `[(104729, 1276), (130363, 2320), (155921, 1688), (181081, 1040), (205759, 1604), (232003, 1480), (260003, 2900), (287117, 4172)]`.
- Variant policy (order `LEFT, DOWN, UP, RIGHT`) on the visible suite: mean 2386.5; per seed `[(104729, 3412), (130363, 1652), (155921, 1876), (181081, 3236), (205759, 2780), (232003, 2576), (260003, 1588), (287117, 1972)]`.
- Weak baseline on `{"max_moves": 300, "seeds": [11, 22]}`: mean 1400.0; seed 11 scores 1892 in 192 moves.
- Seed derivation vectors (key `"00" * 32`, rollout `demo-rollout`, candidate digest `"a" * 64`): look 1, size 3 -> `[976793988, 1809094229, 1101487377]`; same with the first value excluded -> `[1809094229, 1101487377, 456647843]`; look 2, size 3 -> `[1836097249, 1878888563, 1379785594]`.
- Planning rule on the worked-example deltas with `min_effect` 103.0, level 0.9, floor 16, cap 64 -> `size 64, planned 327, exploratory True, screening_sd 565.4833583505606, z 1.6448536269514715`; with cap 32 -> `size 32`; with all-zero deltas -> `size 16, planned 16, exploratory False`.
- End-to-end, identical candidate (Task 8): every paired delta 0, estimate 0.0, 90 percent interval `[0.0, 0.0]`, verdict `inconclusive`, `min_effect` 51.5, `screening_sd` 0.0, planned 4 (the floor), not exploratory, disposition `provisional`, look 1, a four-seed suite disjoint from the visible seeds; the confirmation on that suite gives estimate 0.0, sample size 4, verdict `inconclusive`, disposition `revert`.
- End-to-end, variant candidate (Task 8): deltas `[2136, -668, 188, 2196, 1176, 1096, -1312, -2200]`, estimate 326.5, 90 percent interval `[-569.5, 1191.0]`, verdict `inconclusive`, `min_effect` 51.5, `screening_sd` 1610.64, planned 10586 against a cap of 8, so `exploratory` is true, the disposition is `revert`, and no suite and no look index are recorded.
- Fixture file digests (dataset revision `956025d7ecf6`): `evaluate.py` `642d194eab0c4f1e116a70d7d78d8b5e13197cbfb92e0d6a09dbba6c2a494c86`; `game2048.py` `3c1059f3a26b5d5ee014ae51f19147e05a31ddf60fd7d371a48e7c4101cef077`; `visible_seeds.json` `117c4cb7c2f19eb47fe70949a4f7c3ba2c4ff48da89bfb204dae5b30a7e4528a`; starter `policy.py` `10c743af480c9274bb547a5a77000d0477836dfb951e0e99b0889a7181eb1e64`.
- Test counts: 70 on `main` today; 110 when pull request A is ready (70 + 7 + 5 + 8 + 4 + 16); 137 after Task 6; 146 after Task 7; 148 when pull request B is ready. The README status count (the gate, its modules, and the converter, excluding the profile's conformance suite) is 110.

## File structure

| Path | Responsibility |
| --- | --- |
| `gate/treedigest.py` (new) | `file_sha256`, `method_files`, `method_tree_sha256`: the grader's view of a policy directory (Python files only, no caches, no symlinks). |
| `gate/task_profile.py` (new) | `check_profile`, `load_profile`, `resolve_min_effect`: the per-rollout profile, schema `rsi-exam-gate-profile/v1`. |
| `gate/seeds.py` (new) | `derive_seeds`, `confirmation_size`, `write_suite`, `read_suite`, CLI: algorithm `rsi-exam-gate/hmac-seeds/1` and the planning rule. |
| `gate/evaluate_suite.py` (new) | The runner: parent process checks and publishes, child interpreter evaluates one policy directory on one suite under a pooled CPU budget, writes result plus receipt (schema `rsi-exam-gate-receipt/v1`). |
| `gate/restore.py` (new) | Replace `methods/main/` with a snapshot without nesting it, and check the restored digest. |
| `gate/decide.py` (rewrite) | Gated mode and replay mode; freezing, planning, suite derivation, receipt checks, re-derivation at confirmation; the seven gated line keys `confirm_policy`, `profile_sha256`, `look_index`, `parent_method_tree_sha256`, `candidate_method_tree_sha256`, `sizing`, `suite`. |
| `gate/trace_from_decisions.py` (rewrite) | Re-check every gated rule on conversion and carry the seven keys at the end of the `confidence` block. |
| `fixtures/task2048/` (new) | `environment/evaluate.py`, `environment/game2048.py`, `environment/visible_seeds.json`, `policy_weak/policy.py`, `policy_variant/policy.py`, `NOTICE`. |
| `tests/gate_fixtures.py` (new) | Shared helpers: result files in self-check shape, method trees, profiles, receipts, the fixture task's locations and real digests, the runner subprocess launcher. Not a test module. |
| `tests/test_treedigest.py`, `tests/test_task_profile.py`, `tests/test_seeds.py`, `tests/test_evaluate_suite.py`, `tests/test_restore.py`, `tests/test_gated_rollout.py` (new); `tests/test_decide.py`, `tests/test_trace_from_decisions.py` (replaced) | One test module per module; the end-to-end gated flow in `test_gated_rollout.py`. |
| `docs/decision-log-contract.md`, `docs/ROADMAP.md`, `README.md`, `CLAUDE.md` (modify); `docs/PREFLIGHT.md` (new) | Contract additions made normative; status; layout; the preflight record. |

**Branches and pull requests.** Tasks 1 to 5 on branch `feat/gate-modules` (pull request A: the five new modules, the shared test helpers, and the task fixture; `decide.py` and the converter are untouched). Tasks 6 to 9 on branch `feat/gate-confirmation`, created from `main` after pull request A merges (pull request B). Task 0 is an operator task and produces `docs/PREFLIGHT.md` on branch `docs/preflight` whenever it is run; it does not block Tasks 1 to 9.

---

### Task 0: Preflight (operator; run when Docker and a harness credential are available)

**Files:**
- Create: `docs/PREFLIGHT.md`

**Purpose.** Observe the real harbor job layout once, so Milestones 2 and 3 build on facts rather than on the task description. Nothing in Tasks 1 to 9 depends on this task, and this task changes no code. Milestone 1 does not make a gated rollout runnable: mounting the gate and the profile into the container, the trusted driver that runs the gate between snapshots, and the program overlay that tells the agent to call it are Milestone 3.

**How this task is run.** One script, run by the operator from inside a checkout of this repository. It records the implementation repository's path before it goes anywhere else, refuses to start without a harness credential, runs one baseline rollout in the background, stops it as soon as the harness has taken its first snapshot (or after fifteen minutes), writes `docs/PREFLIGHT.md`, and commits it. If it stops on a blocker it still writes and commits the file, naming the blocker; that is a complete outcome for this task.

- [ ] **Step 1: Set the harness command**

Open `https://github.com/aiming-lab/RSI-Exam` at revision `bc36dadb405b`, section "Harnesses & Models" of the README, and copy the `harbor run` command for the harness whose credential you hold. Export it, with the task path replaced by the pinned local checkout and `-n 1` kept:

```bash
export HARBOR_CMD='uvx harbor run <harness flags from the README> -n 1 --task ~/rsi-exam-runs/tasks/game2048_policy_search'
```

Do not put the credential in the command; the harness reads it from the environment.

- [ ] **Step 2: Run the preflight script**

```bash
cat > ~/rsi-exam-preflight.sh <<'SCRIPT'
#!/bin/bash
# Observe one real harbor job layout for game2048_policy_search and record it in this repository.
set -u
IMPL_REPO=$(git rev-parse --show-toplevel)
RUNS="$HOME/rsi-exam-runs"
HARNESS="$RUNS/RSI-Exam"
TASKS="$RUNS/tasks"
LOG="$RUNS/preflight.log"
DEADLINE=900
BLOCKER=""
JOB=""
SNAPSHOT=""
HARBOR_VERSION=""

docker info >/dev/null 2>&1 || BLOCKER="Docker is not running"

CREDENTIAL=""
for NAME in ANTHROPIC_API_KEY OPENAI_API_KEY XAI_API_KEY; do
  if [ -n "${!NAME:-}" ]; then CREDENTIAL="$NAME"; break; fi
done
if [ -z "$CREDENTIAL" ] && [ -z "$BLOCKER" ]; then
  BLOCKER="no harness credential is set: ANTHROPIC_API_KEY, OPENAI_API_KEY, XAI_API_KEY, or the variable the RSI-Exam README names for the harness you hold a key for"
fi
if [ -z "${HARBOR_CMD:-}" ] && [ -z "$BLOCKER" ]; then
  BLOCKER="HARBOR_CMD is not set; copy the harbor run command for your harness from the RSI-Exam README"
fi

if [ -z "$BLOCKER" ]; then
  mkdir -p "$RUNS"
  if [ ! -d "$HARNESS" ]; then
    git clone https://github.com/aiming-lab/RSI-Exam.git "$HARNESS" && git -C "$HARNESS" checkout bc36dadb405b
  fi
  if [ ! -d "$TASKS" ]; then
    git clone https://huggingface.co/datasets/RSI-Exam/RSI-Exam "$TASKS" && git -C "$TASKS" checkout 956025d7ecf6
  fi
  HARBOR_VERSION=$(uvx harbor --version 2>/dev/null || echo unknown)
  cd "$HARNESS"
  START_MARK=$(mktemp "$RUNS/.preflight-start.XXXXXX")
  setsid $HARBOR_CMD >"$LOG" 2>&1 &
  HARBOR_PID=$!
  WAITED=0
  while [ "$WAITED" -lt "$DEADLINE" ]; do
    sleep 15
    WAITED=$((WAITED + 15))
    SNAPSHOT=$(find "$RUNS" -type d -newer "$START_MARK" -path '*/artifacts/app/methods/versions/v*' -print -quit 2>/dev/null || true)
    if [ -n "$SNAPSHOT" ]; then break; fi
    kill -0 "$HARBOR_PID" 2>/dev/null || break
  done
  kill -- -"$HARBOR_PID" 2>/dev/null || true
  wait "$HARBOR_PID" 2>/dev/null || true
  if [ -n "$SNAPSHOT" ]; then
    JOB=${SNAPSHOT%/artifacts/app/methods/versions/*}
  else
    METHODS=$(find "$RUNS" -type d -newer "$START_MARK" -path '*/artifacts/app/methods' -print -quit 2>/dev/null || true)
    JOB=${METHODS%/artifacts/app/methods}
  fi
  if [ -z "$JOB" ]; then BLOCKER="the harness produced no artifacts/app/methods directory within $DEADLINE s; see $LOG"; fi
fi

mkdir -p "$IMPL_REPO/docs"
{
  echo "# Preflight: the real job layout (game2048_policy_search)"
  echo
  echo "Harness pinned at RSI-Exam bc36dadb405b; task materials at dataset revision 956025d7ecf6."
  echo
  if [ -n "$BLOCKER" ]; then
    echo "## Not yet run"
    echo
    echo "Blocker: $BLOCKER"
    echo
    echo "Nothing in Tasks 1 to 9 depends on this record. Re-run the preflight script once the blocker is gone."
  else
    echo "Harbor version: $HARBOR_VERSION"
    echo "Credential variable used: $CREDENTIAL (value never recorded)"
    echo "Harness command: $HARBOR_CMD"
    echo "Job directory: ~${JOB#$HOME}"
    echo "First snapshot seen: ${SNAPSHOT:-none within $DEADLINE s}"
    echo
    echo "## Files observed"
    echo
    echo "Entries under artifacts/app/methods:"
    echo
    ls -A "$JOB/artifacts/app/methods" 2>/dev/null | sed 's/^/    /'
    echo
    echo "- agent/trajectory.json: $([ -f "$JOB/agent/trajectory.json" ] && echo present || echo absent)"
    echo "- artifacts/app/methods/main/__pycache__: $([ -d "$JOB/artifacts/app/methods/main/__pycache__" ] && echo present || echo absent)"
    echo "- artifacts/app/visible_result.json: $([ -f "$JOB/artifacts/app/visible_result.json" ] && echo present || echo absent)"
    echo "- verifier/reward.json: $([ -f "$JOB/verifier/reward.json" ] && echo present || echo absent)"
    echo "- experiment log: $([ -f "$JOB/artifacts/app/methods/experiment_log.md" ] && echo present || echo absent)"
    echo
    echo "## Facts that matter for the gate"
    echo
    echo "- The starter was snapshotted as: FILL IN (version id, or 'not snapshotted')"
    echo "- Shape of the first experiment-log line, free text masked: FILL IN"
    echo "- Anything that contradicts docs/overview.md section 1 or 5: FILL IN"
  fi
} > "$IMPL_REPO/docs/PREFLIGHT.md"

MESSAGE="docs(preflight): record the harbor job layout for game2048_policy_search"
if [ -n "$BLOCKER" ]; then
  MESSAGE="docs(preflight): record what blocks the first observation of a harbor job layout"
fi
git -C "$IMPL_REPO" checkout -b docs/preflight 2>/dev/null || git -C "$IMPL_REPO" checkout docs/preflight
git -C "$IMPL_REPO" add docs/PREFLIGHT.md
git -C "$IMPL_REPO" diff --exit-code
git -C "$IMPL_REPO" commit -m "$MESSAGE"
echo "preflight written to $IMPL_REPO/docs/PREFLIGHT.md (blocker: ${BLOCKER:-none})"
SCRIPT
bash ~/rsi-exam-preflight.sh
```

Expected: the script prints the path it wrote and either `blocker: none` or the blocker. It never prints a credential value.

- [ ] **Step 3: Fill in the three observations and push**

Open `docs/PREFLIGHT.md`. If it has a "Facts that matter for the gate" section, replace each `FILL IN` from what you see in the job directory: paths only, no transcript content, no prompt text, no scores. Mask any free text in the experiment-log line. Then:

```bash
git add docs/PREFLIGHT.md
git diff --exit-code
git commit --amend --no-edit
git push -u origin docs/preflight
gh pr create --title "docs(preflight): record the real harbor job layout" --body "## Summary
Records the job directory layout observed on one baseline rollout of game2048_policy_search, stopped as soon as the harness took its first snapshot.

## Why
Milestones 2 and 3 bind files by path. The layout has to come from an observation of the pinned harness, not from the task description.

## Verification
Manual observation against the pinned harness revision and dataset revision; no code changed."
```

If the file says "Not yet run", commit and open the pull request anyway: the recorded blocker is the useful part, and Tasks 1 to 9 continue regardless.

---

### Task 1: Method-tree digests and the shared test helpers (`gate/treedigest.py`)

**Files:**
- Create: `gate/treedigest.py`, `tests/gate_fixtures.py`
- Test: `tests/test_treedigest.py`

**Interfaces:**
- Produces: `file_sha256(path: Path) -> str` (hex), `method_files(root: Path) -> list[str]` (sorted POSIX relpaths the digest covers), `method_tree_sha256(root: Path) -> str` (hex), `class TreeDigestError(ValueError)`. Every later task imports from this module.
- The digest covers `.py` files only. A symlink anywhere under the tree is refused, and the symlink check runs before the cache exclusions, so a symlink named `__pycache__` cannot hide. A regular non-`.py` file is refused, because the grader refuses it and scores such a submission 0.0. An empty tree is refused.
- `tests/gate_fixtures.py` is created here because Tasks 2, 4, 5, 6, and 8 import it. It is not a test module: `unittest discover` matches `test*.py` and ignores it.

- [ ] **Step 1: Create the branch and record the baseline commit**

```bash
git checkout main && git pull --ff-only && git checkout -b feat/gate-modules
BASELINE_SHA=$(git rev-parse HEAD) && echo "BASELINE_SHA=$BASELINE_SHA"
```
Write that hash into your report now. The final gate uses it to prove the golden fixture under `fixtures/valid` never moved.

- [ ] **Step 2: Create the shared test helpers**

Create `tests/gate_fixtures.py`:

```python
"""Shared helpers for the gate tests: result files in selfcheck shape, method trees, profiles, receipts.

Also carries the fixture task locations, the real evaluator digests the runner tests pin, and a
subprocess launcher for the runner (which arms ``RLIMIT_CPU`` for its own process and so may never
be called in-process from a test).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import treedigest  # noqa: E402

SEEDS = [104729, 130363, 155921, 181081, 205759, 232003, 260003, 287117]
PARENT = [3980, 4460, 3720, 4310, 4050, 4390, 4180, 3870]
DELTAS_INCONCLUSIVE = [1310, 820, 410, 200, 60, -190, -300, -230]
DELTAS_CLEAR = [610, 540, 480, 700, 390, 450, 520, 460]
DELTAS_BELOW = [-410, -220, -540, -300, -180, -350, -260, -290]
VISIBLE_SUITE_SHA = "3" * 64
EVALUATOR = {"evaluate.py": "a" * 64, "game2048.py": "b" * 64}
FIXTURE = REPO / "fixtures" / "task2048"
TASK_ROOT = FIXTURE / "environment"
VISIBLE_SUITE = TASK_ROOT / "visible_seeds.json"
POLICY_WEAK = FIXTURE / "policy_weak"
POLICY_VARIANT = FIXTURE / "policy_variant"
RUNNER = REPO / "gate" / "evaluate_suite.py"
EVALUATOR_FILES = ("evaluate.py", "game2048.py")
NO_CACHES = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def real_evaluator() -> dict[str, str]:
    """The digests of the fixture task's two evaluator files, as a profile pins them."""
    return {name: treedigest.file_sha256(TASK_ROOT / name) for name in EVALUATOR_FILES}


def real_visible_suite_sha() -> str:
    """The digest of the fixture task's visible seed file."""
    return treedigest.file_sha256(VISIBLE_SUITE)


def copy_policy(source: Path, target: Path) -> Path:
    """Copy a policy directory without bytecode caches, so a test can assert none appear."""
    shutil.copytree(source, target, ignore=NO_CACHES)
    return target


def run_runner(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run gate/evaluate_suite.py in a child process; returns the completed process."""
    return subprocess.run([sys.executable, str(RUNNER), *args], capture_output=True, text=True, env=env)


def write_result(path: Path, scores: Sequence[float], seeds: Sequence[int] = SEEDS) -> None:
    """Write a result file in the exact shape the task's selfcheck.py produces (extra keys included)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cpu_budget_per_game": 225,
        "cpu_seconds": 12.3,
        "cpu_seconds_per_game": 1.5,
        "mean_max_tile": 512.0,
        "mean_score": sum(scores) / len(scores),
        "median_score": sorted(scores)[len(scores) // 2],
        "valid_fraction": 1.0,
        "instances": [
            {"seed": s, "score": v, "max_tile": 512, "moves": 900, "error": None} for s, v in zip(seeds, scores)
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_tree(path: Path, text: str) -> None:
    """A one-file method tree (the gate digests trees; it never runs them here)."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "policy.py").write_text(text, encoding="utf-8")


def profile_document(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema": "rsi-exam-gate-profile/v1", "task": "game2048_policy_search", "rollout_id": "demo-rollout",
        "metric": "per_seed_2048_score", "unit": "game_score", "direction": "higher",
        "min_effect": {"kind": "fraction_of_parent_visible_mean", "fraction": 0.025},
        "level": 0.9, "resamples": 5000, "bootstrap_seed": 20260902, "confirm_policy": "always",
        "confirmation": {"floor": 4, "max_seeds": 8, "max_moves": 300, "cpu_seconds_per_game": 225},
        "visible_suite_sha256": VISIBLE_SUITE_SHA, "replication_key": "11" * 32,
        "audit_key_sha256": hashlib.sha256(b"audit").hexdigest(), "evaluator": dict(EVALUATOR),
    }
    doc.update(overrides)
    return doc


def write_profile(path: Path, **overrides: Any) -> str:
    """Write a valid profile with small confirmation bounds for tests; return its sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(profile_document(**overrides), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_receipt(result_path: Path, *, profile_sha: str, policy_digest: str, suite_sha: str, games: int,
                  max_moves: int = 300, **overrides: Any) -> Path:
    """A receipt next to a result, as the runner writes it, with the bound fields computed from the files."""
    receipt = {
        "schema": "rsi-exam-gate-receipt/v1", "metric": "per_seed_2048_score", "profile_sha256": profile_sha,
        "policy_method_tree_sha256": policy_digest, "suite_sha256": suite_sha, "max_moves": max_moves,
        "result_sha256": treedigest.file_sha256(result_path), "evaluator": dict(EVALUATOR), "games": games,
        "cpu_seconds": 0.1, "cpu_budget_per_game": 225, "python": "3.12.10", "timestamp": "2026-09-05T18:00:00+00:00",
    }
    receipt.update(overrides)
    path = result_path.with_name(result_path.name[:-5] + ".receipt.json")
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_treedigest.py`:

```python
"""Tests for gate/treedigest.py: cache-free method-tree digests under the grader's rules."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import treedigest  # noqa: E402


def _load_producer():
    spec = importlib.util.spec_from_file_location("rsi_exam_producer", REPO / "profile" / "build_capsule.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMethodTreeDigest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "v3"
        (self.root / "sub").mkdir(parents=True)
        (self.root / "policy.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "sub" / "helper.py").write_text("y = 2\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_digest_is_sha256_over_sorted_file_lines(self) -> None:
        lines = ""
        for rel in ("policy.py", "sub/helper.py"):
            lines += f"{hashlib.sha256((self.root / rel).read_bytes()).hexdigest()}  {rel}\n"
        self.assertEqual(treedigest.method_tree_sha256(self.root), hashlib.sha256(lines.encode("utf-8")).hexdigest())
        self.assertEqual(treedigest.method_files(self.root), ["policy.py", "sub/helper.py"])

    def test_bytecode_caches_do_not_change_the_digest(self) -> None:
        before = treedigest.method_tree_sha256(self.root)
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "policy.cpython-312.pyc").write_bytes(b"\x00\x01")
        (self.root / "sub" / "helper.pyo").write_bytes(b"\x02")
        (self.root / "sub" / "__pycache__").mkdir()
        (self.root / "sub" / "__pycache__" / "helper.cpython-313.pyc").write_bytes(b"\x03")
        self.assertEqual(treedigest.method_tree_sha256(self.root), before)

    def test_a_source_change_changes_the_digest(self) -> None:
        before = treedigest.method_tree_sha256(self.root)
        (self.root / "policy.py").write_text("x = 2\n", encoding="utf-8")
        self.assertNotEqual(treedigest.method_tree_sha256(self.root), before)

    def test_matches_the_producer_full_tree_digest_when_there_are_no_caches(self) -> None:
        producer = _load_producer()
        self.assertEqual(treedigest.method_tree_sha256(self.root), producer.tree_digest(self.root))

    def test_non_python_files_are_refused_as_the_grader_refuses_them(self) -> None:
        for name in ("notes.json", "weights", "sub/data.txt"):
            with self.subTest(name=name):
                target = self.root / name
                target.write_text("x", encoding="utf-8")
                with self.assertRaises(treedigest.TreeDigestError):
                    treedigest.method_tree_sha256(self.root)
                target.unlink()
        self.assertEqual(treedigest.method_files(self.root), ["policy.py", "sub/helper.py"])

    def test_symlinks_are_refused_even_under_excluded_names(self) -> None:
        os.symlink(self.root / "policy.py", self.root / "link.py")
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(self.root)
        (self.root / "link.py").unlink()
        os.symlink(self.root / "policy.py", self.root / "cache.pyc")
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(self.root)

    def test_missing_and_empty_trees_are_refused(self) -> None:
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(self.root / "missing")
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(empty)
        only_cache = Path(self.tmp.name) / "only_cache"
        (only_cache / "__pycache__").mkdir(parents=True)
        (only_cache / "__pycache__" / "a.pyc").write_bytes(b"\x00")
        with self.assertRaises(treedigest.TreeDigestError):
            treedigest.method_tree_sha256(only_cache)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_treedigest -v`
Expected: FAIL at import with `ModuleNotFoundError: No module named 'treedigest'`.

- [ ] **Step 5: Write the module**

Create `gate/treedigest.py`:

```python
#!/usr/bin/env python3
"""Method-tree digests: the grader's view of a policy directory.

Exports ``file_sha256(path)``, ``method_files(root)``, and ``method_tree_sha256(root)``. A method
tree is what the RSI-Exam grader stages from ``methods/main/``: regular ``.py`` files only. This
module applies the same rules the grader's ``policy_sandbox.py`` applies before it copies a tree:
a symlink anywhere is refused; a regular file that is not ``.py`` is refused (the grader scores such
a submission 0.0); ``__pycache__`` directories and ``*.pyc`` / ``*.pyo`` files are ignored because
they drift on every import. The digest is SHA-256 over the lines
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
        if child.is_symlink():
            raise TreeDigestError(f"method tree contains a symlink: {rel.as_posix()}")
        if EXCLUDED_DIR in rel.parts or child.suffix in EXCLUDED_SUFFIXES:
            continue
        if child.is_dir():
            continue
        if child.suffix != ".py":
            raise TreeDigestError(f"method tree contains a non-Python file the grader would reject: {rel.as_posix()}")
        rels.append(rel.as_posix())
    if not rels:
        raise TreeDigestError(f"method tree has no Python files: {root}")
    return sorted(rels)


def method_tree_sha256(root: Path) -> str:
    """Canonical cache-free digest of a method tree (see the module docstring)."""
    lines = [f"{file_sha256(root / rel)}  {rel}\n" for rel in method_files(root)]
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_treedigest -v`
Expected: `Ran 7 tests`, `OK`.

- [ ] **Step 7: Type-check and commit**

Run: `pyright gate/treedigest.py tests/gate_fixtures.py tests/test_treedigest.py`
Expected: `0 errors`.

```bash
git add gate/treedigest.py tests/gate_fixtures.py tests/test_treedigest.py
git diff --exit-code
git commit -m "feat(gate): add cache-free method-tree digests

method_tree_sha256 digests a policy directory the way the grader stages it:
Python files only, bytecode caches ignored because they drift on every
import, symlinks refused before any exclusion applies, and a regular
non-Python file refused outright because the grader scores such a submission
0.0. The line format matches the provenance record's full-tree digest, so a
Python-only tree without caches has the same digest under both.

tests/gate_fixtures.py carries the helpers the later gate tests share:
result files in the task's self-check shape, one-file method trees, profiles,
receipts, the fixture task's locations and real digests, and a subprocess
launcher for the runner.

Tests: seven cases including equality with the producer's tree digest on a
cache-free tree, invariance under added caches, and the two refusals."
```

---

### Task 2: The task profile (`gate/task_profile.py`)

**Files:**
- Create: `gate/task_profile.py`
- Test: `tests/test_task_profile.py`

**Interfaces:**
- Consumes: `treedigest.file_sha256`.
- Produces: `PROFILE_SCHEMA = "rsi-exam-gate-profile/v1"`, `class ProfileError(ValueError)`, `check_profile(profile: Any) -> dict[str, Any]`, `load_profile(path: Path) -> tuple[dict[str, Any], str]` (the validated profile and the hex SHA-256 of the file bytes), `resolve_min_effect(profile: Mapping[str, Any], parent_scores: Mapping[int, float]) -> float`.
- `confirm_policy` must be `always`. A profile always means confirmation on fresh seeds; the weaker screening-only rule exists only in replay mode, which has no profile. `evaluator` must map exactly `evaluate.py` and `game2048.py` to 64-hex digests. `confirmation` must have exactly the four keys below.

The profile document (all keys required):

```json
{
  "schema": "rsi-exam-gate-profile/v1",
  "task": "game2048_policy_search",
  "rollout_id": "demo-rollout",
  "metric": "per_seed_2048_score",
  "unit": "game_score",
  "direction": "higher",
  "min_effect": {"kind": "fraction_of_parent_visible_mean", "fraction": 0.025},
  "level": 0.9,
  "resamples": 5000,
  "bootstrap_seed": 20260902,
  "confirm_policy": "always",
  "confirmation": {"floor": 4, "max_seeds": 8, "max_moves": 300, "cpu_seconds_per_game": 225},
  "visible_suite_sha256": "<64 hex>",
  "replication_key": "<64 hex>",
  "audit_key_sha256": "<64 hex>",
  "evaluator": {"evaluate.py": "<64 hex>", "game2048.py": "<64 hex>"}
}
```

`min_effect` alternatively `{"kind": "absolute", "value": 120.0}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_task_profile.py`:

```python
"""Tests for gate/task_profile.py: the per-rollout task profile."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import task_profile  # noqa: E402
from tests.gate_fixtures import profile_document  # noqa: E402

VALID = profile_document()


def mutate(**changes):
    doc = copy.deepcopy(VALID)
    for dotted, value in changes.items():
        target = doc
        parts = dotted.split("__")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    return doc


class TestCheckProfile(unittest.TestCase):
    def test_valid_profile_passes_and_is_returned(self) -> None:
        self.assertEqual(task_profile.check_profile(copy.deepcopy(VALID)), VALID)

    def test_each_rule_is_enforced(self) -> None:
        bad = [
            mutate(schema="other/v1"),
            mutate(task=""),
            mutate(direction="up"),
            mutate(min_effect={"kind": "absolute", "value": 0}),
            mutate(min_effect={"kind": "absolute", "value": -1.0}),
            mutate(min_effect={"kind": "fraction_of_parent_visible_mean", "fraction": 1.0}),
            mutate(min_effect={"kind": "fraction_of_parent_visible_mean", "fraction": 0.0}),
            mutate(min_effect={"kind": "relative_to_parent_mean", "fraction": 0.1}),
            mutate(level=1.0),
            mutate(level=0.0),
            mutate(resamples=999),
            mutate(resamples=True),
            mutate(bootstrap_seed="20260902"),
            mutate(confirm_policy="inconclusive"),
            mutate(confirm_policy="sometimes"),
            mutate(confirmation__floor=1),
            mutate(confirmation__max_seeds=3),
            mutate(confirmation__max_moves=0),
            mutate(confirmation__cpu_seconds_per_game=0),
            mutate(confirmation={"floor": 4, "max_seeds": 8, "max_moves": 300}),
            mutate(visible_suite_sha256="short"),
            mutate(replication_key="11" * 31),
            mutate(replication_key="ZZ" * 32),
            mutate(audit_key_sha256="short"),
            mutate(evaluator={}),
            mutate(evaluator={"evaluate.py": "a" * 64}),
            mutate(evaluator={"evaluate.py": "a" * 64, "game2048.py": "b" * 64, "extra.py": "c" * 64}),
            mutate(evaluator={"evaluate.py": "not-hex", "game2048.py": "b" * 64}),
        ]
        for doc in bad:
            with self.subTest(doc=doc):
                with self.assertRaises(task_profile.ProfileError):
                    task_profile.check_profile(doc)
        with self.assertRaises(task_profile.ProfileError):
            task_profile.check_profile(["not", "an", "object"])

    def test_absolute_min_effect_is_accepted(self) -> None:
        doc = mutate(min_effect={"kind": "absolute", "value": 120.0})
        self.assertEqual(task_profile.check_profile(doc)["min_effect"]["value"], 120.0)


class TestLoadAndResolve(unittest.TestCase):
    def test_load_returns_profile_and_file_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            text = json.dumps(VALID, indent=2, sort_keys=True) + "\n"
            path.write_text(text, encoding="utf-8")
            profile, digest = task_profile.load_profile(path)
            self.assertEqual(profile, VALID)
            self.assertEqual(digest, hashlib.sha256(text.encode("utf-8")).hexdigest())
            with self.assertRaises(task_profile.ProfileError):
                task_profile.load_profile(Path(tmp) / "missing.json")
            (Path(tmp) / "bad.json").write_text("{not json", encoding="utf-8")
            with self.assertRaises(task_profile.ProfileError):
                task_profile.load_profile(Path(tmp) / "bad.json")

    def test_resolve_min_effect(self) -> None:
        scores = {1: 4000.0, 2: 4240.0}
        self.assertAlmostEqual(task_profile.resolve_min_effect(VALID, scores), 0.025 * 4120.0)
        absolute = mutate(min_effect={"kind": "absolute", "value": 120.0})
        self.assertEqual(task_profile.resolve_min_effect(absolute, scores), 120.0)
        with self.assertRaises(task_profile.ProfileError):
            task_profile.resolve_min_effect(VALID, {1: 0.0, 2: 0.0})
        with self.assertRaises(task_profile.ProfileError):
            task_profile.resolve_min_effect(VALID, {1: -10.0, 2: 5.0})
        with self.assertRaises(task_profile.ProfileError):
            task_profile.resolve_min_effect(VALID, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_task_profile -v`
Expected: FAIL at import with `ModuleNotFoundError: No module named 'task_profile'`.

- [ ] **Step 3: Write the module**

Create `gate/task_profile.py`:

```python
#!/usr/bin/env python3
"""The task profile: the per-rollout file that fixes what the agent may not choose.

Schema ``rsi-exam-gate-profile/v1``. The profile fixes the metric's direction and unit, the minimum
effect (absolute, or a fraction of the parent's visible mean resolved at screening), the interval
level, the bootstrap resamples and seed, the confirmation suite bounds, the digest of the task's
visible seed file, the replication key, the digest of the audit key kept outside the sandbox, and
the digests of the two evaluator files. A profile always means confirmation on fresh seeds
(``confirm_policy`` is ``always``); the weaker screening-only rule exists only in replay mode,
without a profile. The gate records the profile's file digest on every line, and the post-rollout
verifier compares it with the digest the operator mounted, so a substituted profile is visible.

Exports ``check_profile(profile)`` (returns the same dict, raises ``ProfileError``),
``load_profile(path) -> (profile, sha256_hex)``, and ``resolve_min_effect(profile, parent_scores)``.
Pure functions; standard library only.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeGuard

from treedigest import file_sha256

PROFILE_SCHEMA = "rsi-exam-gate-profile/v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROFILE_CONFIRM_POLICY = "always"
MIN_EFFECT_KINDS = ("absolute", "fraction_of_parent_visible_mean")
DIRECTIONS = ("higher", "lower")
EVALUATOR_FILES = ("evaluate.py", "game2048.py")
CONFIRMATION_KEYS = ("floor", "max_seeds", "max_moves", "cpu_seconds_per_game")


class ProfileError(ValueError):
    """The profile is missing, malformed, or violates a rule. Nothing proceeds."""


def _is_number(value: object) -> TypeGuard[float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_hex64(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and HEX64.match(value) is not None


def check_profile(profile: Any) -> dict[str, Any]:
    """Validate every rule of the schema; return the profile unchanged. Raises ``ProfileError``."""
    if not isinstance(profile, dict):
        raise ProfileError("profile must be a JSON object")
    p: dict[str, Any] = profile
    if p.get("schema") != PROFILE_SCHEMA:
        raise ProfileError(f"profile.schema must be {PROFILE_SCHEMA}")
    for key in ("task", "rollout_id", "metric", "unit"):
        text = p.get(key)
        if not isinstance(text, str) or not text.strip():
            raise ProfileError(f"profile.{key} must be a non-empty string")
    if p.get("direction") not in DIRECTIONS:
        raise ProfileError("profile.direction must be 'higher' or 'lower'")
    min_effect = p.get("min_effect")
    if not isinstance(min_effect, dict) or min_effect.get("kind") not in MIN_EFFECT_KINDS:
        raise ProfileError("profile.min_effect.kind must be 'absolute' or 'fraction_of_parent_visible_mean'")
    if min_effect["kind"] == "absolute":
        value = min_effect.get("value")
        if not _is_number(value) or value <= 0.0:
            raise ProfileError("profile.min_effect.value must be a finite number above zero")
    else:
        fraction = min_effect.get("fraction")
        if not _is_number(fraction) or not 0.0 < fraction < 1.0:
            raise ProfileError("profile.min_effect.fraction must lie strictly between 0 and 1")
    level = p.get("level")
    if not _is_number(level) or not 0.0 < level < 1.0:
        raise ProfileError("profile.level must lie strictly between 0 and 1")
    resamples = p.get("resamples")
    if not _is_int(resamples) or resamples < 1000:
        raise ProfileError("profile.resamples must be an integer of at least 1000")
    if not _is_int(p.get("bootstrap_seed")):
        raise ProfileError("profile.bootstrap_seed must be an integer")
    if p.get("confirm_policy") != PROFILE_CONFIRM_POLICY:
        raise ProfileError("profile.confirm_policy must be 'always'; the screening-only rule exists only in replay mode")
    confirmation = p.get("confirmation")
    if not isinstance(confirmation, dict) or set(confirmation) != set(CONFIRMATION_KEYS):
        raise ProfileError(f"profile.confirmation must have exactly the keys {', '.join(CONFIRMATION_KEYS)}")
    bounds: dict[str, int] = {}
    for key in CONFIRMATION_KEYS:
        count = confirmation.get(key)
        if not _is_int(count) or count < 1:
            raise ProfileError(f"profile.confirmation.{key} must be a positive integer")
        bounds[key] = count
    if bounds["floor"] < 2:
        raise ProfileError("profile.confirmation.floor must be at least 2")
    if bounds["max_seeds"] < bounds["floor"]:
        raise ProfileError("profile.confirmation.max_seeds must be at least the floor")
    if not _is_hex64(p.get("visible_suite_sha256")):
        raise ProfileError("profile.visible_suite_sha256 must be 64 lowercase hex characters")
    if not _is_hex64(p.get("replication_key")):
        raise ProfileError("profile.replication_key must be 64 lowercase hex characters")
    if not _is_hex64(p.get("audit_key_sha256")):
        raise ProfileError("profile.audit_key_sha256 must be 64 lowercase hex characters")
    evaluator = p.get("evaluator")
    if (not isinstance(evaluator, dict) or set(evaluator) != set(EVALUATOR_FILES)
            or not all(_is_hex64(v) for v in evaluator.values())):
        raise ProfileError("profile.evaluator must map exactly evaluate.py and game2048.py to 64-hex digests")
    return p


def load_profile(path: Path) -> tuple[dict[str, Any], str]:
    """Read, validate, and digest a profile file. Raises ``ProfileError`` on any problem."""
    if not path.is_file():
        raise ProfileError(f"profile not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError(f"profile is not valid JSON: {path}: {exc}") from exc
    return check_profile(data), file_sha256(path)


def resolve_min_effect(profile: Mapping[str, Any], parent_scores: Mapping[int, float]) -> float:
    """The minimum effect in the metric's units for one decision.

    ``absolute`` returns the profile's value. ``fraction_of_parent_visible_mean`` multiplies the
    fraction by the mean of the parent's visible per-seed scores, which must be positive; the
    resolved number is recorded on the screening line and reused unchanged by its confirmation.
    """
    rule = profile["min_effect"]
    if rule["kind"] == "absolute":
        return float(rule["value"])
    if not parent_scores:
        raise ProfileError("fraction_of_parent_visible_mean needs parent scores")
    mean = sum(parent_scores.values()) / len(parent_scores)
    if not math.isfinite(mean) or mean <= 0.0:
        raise ProfileError("fraction_of_parent_visible_mean needs a positive parent mean")
    return float(rule["fraction"]) * mean
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_task_profile -v`
Expected: `Ran 5 tests`, `OK`.

- [ ] **Step 5: Type-check and commit**

Run: `pyright gate/task_profile.py tests/test_task_profile.py`
Expected: `0 errors`.

```bash
git add gate/task_profile.py tests/test_task_profile.py
git diff --exit-code
git commit -m "feat(gate): add the task profile that fixes what the agent may not choose

A profile (schema rsi-exam-gate-profile/v1) carries direction, unit, the
minimum effect as an absolute value or a fraction of the parent's visible
mean, the interval level, bootstrap resamples and seed, the confirmation
bounds, the digest of the task's visible seed file, the replication key, the
digest of the audit key held outside the sandbox, and the digests of the two
evaluator files. confirm_policy is fixed to always: a profile always means
confirmation on fresh seeds, and the screening-only rule exists only in
replay mode. Every rule is checked on load and the file digest is returned so
the gate can record it on each line; a run under an unstated or agent-chosen
rule is the failure mode this closes.

Tests: one valid profile, one mutation per rule, load and digest, and both
minimum-effect kinds resolved against a parent's visible scores."
```

---

### Task 3: Fresh-suite derivation and the planning rule (`gate/seeds.py`)

**Files:**
- Create: `gate/seeds.py`
- Test: `tests/test_seeds.py`

**Interfaces:**
- Produces: `SEEDS_ALGORITHM = "rsi-exam-gate/hmac-seeds/1"`, `SIZING_RULE`, `class SeedsError(ValueError)`,
  `derive_seeds(*, key_hex: str, rollout_id: str, candidate_digest: str, look_index: int, size: int, exclude: set[int]) -> list[int]`,
  `confirmation_size(deltas: list[float], *, min_effect: float, level: float, floor: int, cap: int) -> dict[str, Any]` with keys `rule, size, planned, floor, cap, exploratory, screening_sd, z`,
  `suite_bytes(seeds, *, max_moves) -> bytes`, `write_suite(path: Path, seeds: list[int], *, max_moves: int) -> str` (hex SHA-256 of the written bytes; creates the file with `O_EXCL` and never overwrites),
  `read_suite(path: Path) -> tuple[list[int], int]`, and `main(argv) -> int`.

**The algorithm `rsi-exam-gate/hmac-seeds/1`.** `seed = int.from_bytes(HMAC-SHA256(key, f"{rollout_id}|{candidate_digest}|{look_index}|{counter}")[:4], "big") & 0x7FFFFFFF` for `counter = 0, 1, 2, ...`; a value of 0, a value already drawn, or a value in the exclusion set is skipped and the counter advances. The suite file is `{"max_moves": N, "seeds": [...]}` in derivation order, `json.dumps(indent=2, sort_keys=True) + "\n"`, which is the shape `environment/evaluate.py::load_suite` reads (unique ints under `seeds`, optional `max_moves`).

**The planning rule.** With `s` the sample standard deviation of the screening deltas (`statistics.stdev`, zero when fewer than two deltas) and `z = NormalDist().inv_cdf(0.5 + level / 2)`, `planned` is the smallest integer `n` with `z * s / sqrt(n) < min_effect / 2`, so `n > (2 z s / min_effect) ** 2`, computed as `floor(x) + 1`; then `planned = max(floor, that)`, or `floor` when `s == 0`; `size = min(planned, cap)`; `exploratory = size < planned`. It is a normal-approximation planning size computed from screening data, not a guarantee about the realized bootstrap interval, and the returned `rule` string says so. The gate never opens an exploratory confirmation: it reverts instead.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_seeds.py`:

```python
"""Tests for gate/seeds.py: deterministic fresh suites and the confirmation-size planning rule."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import seeds  # noqa: E402

KEY = "00" * 32
DIGEST = "a" * 64
DELTAS = [1310.0, 820.0, 410.0, 200.0, 60.0, -190.0, -300.0, -230.0]


class TestDerive(unittest.TestCase):
    def test_known_vectors(self) -> None:
        self.assertEqual(seeds.derive_seeds(key_hex=KEY, rollout_id="demo-rollout", candidate_digest=DIGEST,
                                            look_index=1, size=3, exclude=set()),
                         [976793988, 1809094229, 1101487377])
        self.assertEqual(seeds.derive_seeds(key_hex=KEY, rollout_id="demo-rollout", candidate_digest=DIGEST,
                                            look_index=1, size=3, exclude={976793988}),
                         [1809094229, 1101487377, 456647843])
        self.assertEqual(seeds.derive_seeds(key_hex=KEY, rollout_id="demo-rollout", candidate_digest=DIGEST,
                                            look_index=2, size=3, exclude=set()),
                         [1836097249, 1878888563, 1379785594])

    def test_inputs_change_the_suite_and_values_are_positive_31_bit(self) -> None:
        base = seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=16, exclude=set())
        self.assertEqual(len(set(base)), 16)
        self.assertTrue(all(1 <= s < 2 ** 31 for s in base))
        other_key = seeds.derive_seeds(key_hex="01" * 32, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=16, exclude=set())
        other_digest = seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest="b" * 64, look_index=1, size=16, exclude=set())
        other_rollout = seeds.derive_seeds(key_hex=KEY, rollout_id="r2", candidate_digest=DIGEST, look_index=1, size=16, exclude=set())
        for variant in (other_key, other_digest, other_rollout):
            self.assertNotEqual(variant, base)

    def test_exclusion_is_respected_and_bad_arguments_are_refused(self) -> None:
        first = seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=8, exclude=set())
        again = seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=8, exclude=set(first))
        self.assertFalse(set(first) & set(again))
        with self.assertRaises(seeds.SeedsError):
            seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=0, size=8, exclude=set())
        with self.assertRaises(seeds.SeedsError):
            seeds.derive_seeds(key_hex=KEY, rollout_id="r", candidate_digest=DIGEST, look_index=1, size=0, exclude=set())
        with self.assertRaises(seeds.SeedsError):
            seeds.derive_seeds(key_hex="zz", rollout_id="r", candidate_digest=DIGEST, look_index=1, size=1, exclude=set())


class TestSizing(unittest.TestCase):
    def test_worked_example_plans_327_and_is_exploratory_under_the_cap(self) -> None:
        out = seeds.confirmation_size(DELTAS, min_effect=103.0, level=0.9, floor=16, cap=64)
        self.assertEqual((out["size"], out["planned"], out["floor"], out["cap"], out["exploratory"]), (64, 327, 16, 64, True))
        self.assertAlmostEqual(out["screening_sd"], 565.4833583505606, places=6)
        self.assertAlmostEqual(out["z"], 1.6448536269514715, places=6)
        self.assertEqual(out["rule"], seeds.SIZING_RULE)
        self.assertEqual(seeds.confirmation_size(DELTAS, min_effect=103.0, level=0.9, floor=16, cap=32)["size"], 32)

    def test_floor_applies_when_the_deltas_are_tight_or_constant(self) -> None:
        out = seeds.confirmation_size([0.0] * 8, min_effect=103.0, level=0.9, floor=16, cap=64)
        self.assertEqual((out["size"], out["planned"], out["exploratory"]), (16, 16, False))
        out = seeds.confirmation_size(DELTAS, min_effect=412.0, level=0.9, floor=16, cap=64)
        self.assertEqual((out["planned"], out["exploratory"]), (21, False))
        out = seeds.confirmation_size(DELTAS, min_effect=700.0, level=0.9, floor=4, cap=8)
        self.assertEqual((out["planned"], out["size"], out["exploratory"]), (8, 8, False))
        self.assertEqual(seeds.confirmation_size([5.0], min_effect=1.0, level=0.9, floor=4, cap=8)["size"], 4)

    def test_bad_arguments_are_refused(self) -> None:
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(DELTAS, min_effect=0.0, level=0.9, floor=16, cap=64)
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(DELTAS, min_effect=1.0, level=0.9, floor=1, cap=64)
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(DELTAS, min_effect=1.0, level=0.9, floor=16, cap=8)
        with self.assertRaises(seeds.SeedsError):
            seeds.confirmation_size(DELTAS, min_effect=1.0, level=1.0, floor=16, cap=64)


class TestSuiteFiles(unittest.TestCase):
    def test_write_read_and_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results" / "v3" / "replication" / "seeds.json"
            digest = seeds.write_suite(path, [5, 3, 9], max_moves=300)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(digest, hashlib.sha256(text.encode("utf-8")).hexdigest())
            self.assertEqual(json.loads(text), {"max_moves": 300, "seeds": [5, 3, 9]})
            self.assertEqual(seeds.read_suite(path), ([5, 3, 9], 300))
            with self.assertRaises(seeds.SeedsError):
                seeds.write_suite(path, [1], max_moves=300)
            self.assertEqual(seeds.read_suite(path), ([5, 3, 9], 300))
            bad = Path(tmp) / "bad.json"
            bad.write_text('{"seeds": [1, 1]}', encoding="utf-8")
            with self.assertRaises(seeds.SeedsError):
                seeds.read_suite(bad)
            bad.write_text('{"max_moves": 5}', encoding="utf-8")
            with self.assertRaises(seeds.SeedsError):
                seeds.read_suite(bad)

    def test_cli_writes_a_suite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suite.json"
            code = seeds.main(["--key-hex", KEY, "--rollout", "demo-rollout", "--candidate-digest", DIGEST,
                               "--look-index", "1", "--size", "3", "--max-moves", "10000",
                               "--exclude", "976793988", "--output", str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["seeds"], [1809094229, 1101487377, 456647843])
            self.assertEqual(seeds.main(["--key-hex", KEY, "--rollout", "r", "--candidate-digest", DIGEST,
                                         "--look-index", "1", "--size", "3", "--output", str(out)]), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_seeds -v`
Expected: FAIL at import with `ModuleNotFoundError: No module named 'seeds'`.

- [ ] **Step 3: Write the module**

Create `gate/seeds.py`:

```python
#!/usr/bin/env python3
"""Fresh confirmation suites and the confirmation-size planning rule.

Algorithm ``rsi-exam-gate/hmac-seeds/1``: seed_k is the first four bytes of
HMAC-SHA256(key, "<rollout_id>|<candidate_method_tree_sha256>|<look_index>|<counter>") read as a
big-endian integer with the top bit cleared (1 <= seed < 2**31), for counter = 0, 1, 2, ...; a value
of zero, a value already in the suite, or a value in the exclusion set is skipped and the counter
advances. A suite is therefore a deterministic function of the committed key, the rollout, the
frozen candidate, and the look, and the gate re-derives it at confirmation. Anyone holding the key
can re-derive it, including the rollout agent: the derivation makes freshness checkable after the
fact, it does not hide the seeds. Compliance is measured, not assumed.

Planning rule: with s the sample standard deviation of the screening deltas and z the normal
quantile for the interval level, the planned suite size is the smallest n with z * s / sqrt(n)
below half the minimum effect, at least ``floor``. It is a normal-approximation planning size
computed from screening data, not a guarantee about the realized bootstrap interval. When the
profile's cap is below the planned size the plan is ``exploratory`` and the gate does not open a
confirmation: an under-planned confirmation is never allowed to keep.

Exports ``derive_seeds``, ``confirmation_size``, ``write_suite`` (creates one file exclusively),
``read_suite``, and a CLI. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any

SEEDS_ALGORITHM = "rsi-exam-gate/hmac-seeds/1"
SIZING_RULE = "normal-approximation planning size from screening SD: smallest n with z*s/sqrt(n) < min_effect/2"
MAX_COUNTER = 1_000_000


class SeedsError(ValueError):
    """A suite cannot be derived, sized, written, or read as asked."""


def derive_seeds(*, key_hex: str, rollout_id: str, candidate_digest: str, look_index: int, size: int,
                 exclude: set[int]) -> list[int]:
    """The confirmation seeds for one look (see the module docstring)."""
    if size < 1:
        raise SeedsError("size must be at least 1")
    if look_index < 1:
        raise SeedsError("look_index must be at least 1")
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise SeedsError("key must be hexadecimal") from exc
    prefix = f"{rollout_id}|{candidate_digest}|{look_index}|".encode("utf-8")
    seeds: list[int] = []
    counter = 0
    while len(seeds) < size:
        if counter >= MAX_COUNTER:
            raise SeedsError("seed derivation did not converge; the exclusion set is too large")
        digest = hmac.new(key, prefix + str(counter).encode("utf-8"), hashlib.sha256).digest()
        counter += 1
        seed = int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
        if seed == 0 or seed in exclude or seed in seeds:
            continue
        seeds.append(seed)
    return seeds


def confirmation_size(deltas: list[float], *, min_effect: float, level: float, floor: int, cap: int) -> dict[str, Any]:
    """The planning size and whether the cap makes the plan exploratory; every input and output is recorded."""
    if not min_effect > 0.0:
        raise SeedsError("min_effect must be above zero to size a confirmation suite")
    if floor < 2 or cap < floor:
        raise SeedsError("floor must be at least 2 and cap at least floor")
    if not 0.0 < level < 1.0:
        raise SeedsError("level must lie strictly between 0 and 1")
    sd = statistics.stdev(deltas) if len(deltas) >= 2 else 0.0
    z = statistics.NormalDist().inv_cdf(0.5 + level / 2.0)
    planned = floor if sd == 0.0 else max(floor, math.floor((2.0 * z * sd / min_effect) ** 2) + 1)
    size = min(planned, cap)
    return {"rule": SIZING_RULE, "size": size, "planned": planned, "floor": floor, "cap": cap,
            "exploratory": size < planned, "screening_sd": sd, "z": z}


def suite_bytes(seeds: list[int], *, max_moves: int) -> bytes:
    """The canonical bytes of a suite file."""
    return (json.dumps({"max_moves": max_moves, "seeds": seeds}, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_suite(path: Path, seeds: list[int], *, max_moves: int) -> str:
    """Create the suite file exclusively (never overwrite); return the hex SHA-256 of its bytes."""
    payload = suite_bytes(seeds, max_moves=max_moves)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise SeedsError(f"suite file already exists: {path}") from exc
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    return hashlib.sha256(payload).hexdigest()


def read_suite(path: Path) -> tuple[list[int], int]:
    """Seeds and max_moves of a suite file, in the shape the task evaluator reads."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        seeds = [int(s) for s in data["seeds"]]
        max_moves = int(data.get("max_moves", 10000))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise SeedsError(f"malformed suite file {path}: {exc}") from exc
    if not seeds or len(set(seeds)) != len(seeds):
        raise SeedsError(f"suite must contain unique seeds: {path}")
    return seeds, max_moves


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive and write a fresh seed suite (rsi-exam-gate/hmac-seeds/1).")
    parser.add_argument("--key-hex", required=True)
    parser.add_argument("--rollout", required=True)
    parser.add_argument("--candidate-digest", required=True)
    parser.add_argument("--look-index", type=int, required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--max-moves", type=int, default=10000)
    parser.add_argument("--exclude", type=int, nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        chosen = derive_seeds(key_hex=args.key_hex, rollout_id=args.rollout, candidate_digest=args.candidate_digest,
                              look_index=args.look_index, size=args.size, exclude=set(args.exclude))
        digest = write_suite(args.output, chosen, max_moves=args.max_moves)
    except SeedsError as exc:
        print(f"seeds refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"algorithm": SEEDS_ALGORITHM, "size": len(chosen), "sha256": digest, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_seeds -v`
Expected: `Ran 8 tests`, `OK`.

- [ ] **Step 5: Type-check and commit**

Run: `pyright gate/seeds.py tests/test_seeds.py`
Expected: `0 errors`.

```bash
git add gate/seeds.py tests/test_seeds.py
git diff --exit-code
git commit -m "feat(gate): derive fresh confirmation suites and plan their size

Confirmation seeds come from HMAC-SHA256 over the committed replication key,
the rollout id, the frozen candidate's method-tree digest, and the look index
(algorithm rsi-exam-gate/hmac-seeds/1), skipping the visible seeds and every
earlier suite, so a suite is disjoint from the seeds the search has already
used and can be re-derived from the key after the fact instead of promised.
The planning rule is a normal-approximation size from the screening standard
deviation: the smallest n whose half-width falls under half the minimum
effect, bounded below by a floor. A plan above the profile's cap is marked
exploratory, and the gate reverts rather than confirming under-planned.
Suite files are created exclusively, never overwritten.

Tests: fixed derivation vectors, exclusion, the worked-example plan and its
cap, the floor cases, refusals, suite file round trip, CLI."
```

---

### Task 4: The task fixture and the evaluation runner (`gate/evaluate_suite.py`)

**Files:**
- Create: `fixtures/task2048/environment/evaluate.py`, `fixtures/task2048/environment/game2048.py`, `fixtures/task2048/environment/visible_seeds.json`, `fixtures/task2048/policy_weak/policy.py` (all four fetched from the pinned dataset revision), `fixtures/task2048/policy_variant/policy.py`, `fixtures/task2048/NOTICE`
- Create: `gate/evaluate_suite.py`
- Test: `tests/test_evaluate_suite.py`

**Interfaces:**
- Consumes: `treedigest.file_sha256`, `treedigest.method_tree_sha256`, `treedigest.TreeDigestError`; `task_profile.load_profile`; `seeds.read_suite`; the task's `evaluate.evaluate(policy_path: Path, suite_path: Path) -> dict`.
- Produces: `RECEIPT_SCHEMA = "rsi-exam-gate-receipt/v1"`, `check_output_path(path) -> Path`, `receipt_path_for(output: Path) -> Path` (`x.json` becomes `x.receipt.json`), `validate_result`, `publish`, `run(...) -> dict` (the receipt), `child_main(...)`, `main(argv) -> int`.
- Exit codes: 0 written; 1 the evaluator raised; 2 bad input, a policy tree the grader would reject, or an evaluator file that differs from the profile; 4 the pooled CPU budget was exhausted; 5 a game was invalid; 6 the wall-clock limit was reached. Only exit 0 writes anything.
- **Two processes.** The parent holds the profile and does the bookkeeping: it checks the task root's two evaluator files against the digests the profile pins, digests the policy tree, reads the suite, refuses an output path that is not under a `results` directory or that passes through a symlink, refuses to overwrite existing evidence, validates the child's result, and publishes result and receipt through same-directory temporary files and `os.replace`. The child is a fresh interpreter started with `PYTHONHASHSEED=0` and `PYTHONDONTWRITEBYTECODE=1` in its own session; it loads `game2048` and `evaluate` from the task root **by exact path and registers them in `sys.modules` before** the policy directory goes first on `sys.path`, so a policy file named `game2048.py` cannot shadow the engine; it arms one pooled `RLIMIT_CPU` of `cpu_seconds_per_game * games`, as the task's `selfcheck.py` does. A wall-clock overrun kills the child's process group.
- **Validation before anything is written.** Every game must be valid: `valid_fraction` exactly 1.0, no per-game `error`, finite scores, and exactly the suite's seeds. Result files then have the shape of the task's `selfcheck.py` output (the evaluator's keys plus `cpu_seconds`, `cpu_seconds_per_game`, `cpu_budget_per_game`).
- The receipt records `schema`, `metric`, `profile_sha256`, `policy_method_tree_sha256`, `suite_sha256`, `max_moves`, `result_sha256`, `evaluator`, `games`, `cpu_seconds`, `cpu_budget_per_game`, `python`, `timestamp`. `DECIDE_FIXED_TIMESTAMP` fixes the timestamp for fixtures.
- After publishing, the runner runs `/app/budget.py` when that file exists, as `selfcheck.py` does; outside the container it does not exist and nothing happens.

- [ ] **Step 1: Fetch the four task files from the pinned dataset revision**

The digests are checked before anything is written, and a mismatch exits non-zero without writing that file.

```bash
python3 - <<'PY'
import hashlib
import sys
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/datasets/RSI-Exam/RSI-Exam/resolve/956025d7ecf6/game2048_policy_search"
FILES = [
    ("environment/evaluate.py", "fixtures/task2048/environment/evaluate.py",
     "642d194eab0c4f1e116a70d7d78d8b5e13197cbfb92e0d6a09dbba6c2a494c86"),
    ("environment/game2048.py", "fixtures/task2048/environment/game2048.py",
     "3c1059f3a26b5d5ee014ae51f19147e05a31ddf60fd7d371a48e7c4101cef077"),
    ("environment/visible_seeds.json", "fixtures/task2048/environment/visible_seeds.json",
     "117c4cb7c2f19eb47fe70949a4f7c3ba2c4ff48da89bfb204dae5b30a7e4528a"),
    ("environment/methods/main/policy.py", "fixtures/task2048/policy_weak/policy.py",
     "10c743af480c9274bb547a5a77000d0477836dfb951e0e99b0889a7181eb1e64"),
]
failed = 0
for source, target, expected in FILES:
    data = urllib.request.urlopen(f"{BASE}/{source}", timeout=60).read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        print(f"DIGEST MISMATCH {source}: {digest} != {expected}", file=sys.stderr)
        failed += 1
        continue
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"ok {target} {digest}")
sys.exit(1 if failed else 0)
PY
```

Expected: four `ok` lines and exit 0. Any `DIGEST MISMATCH` is a STOP (condition 3).

- [ ] **Step 2: Write the variant policy and the notice**

Create `fixtures/task2048/policy_variant/policy.py`:

```python
"""Variant of the weak baseline: prefer LEFT, then DOWN. Used only by tests."""

from game2048 import apply_move


def choose_move(board):
    for move in ("LEFT", "DOWN", "UP", "RIGHT"):
        if apply_move(board, move)[2]:
            return move
    return "LEFT"
```

Create `fixtures/task2048/NOTICE`:

```
The files under environment/ and policy_weak/ are copied unchanged from the RSI-Exam task
materials, dataset RSI-Exam/RSI-Exam on Hugging Face at revision 956025d7ecf6, task
game2048_policy_search (environment/evaluate.py, environment/game2048.py,
environment/visible_seeds.json, environment/methods/main/policy.py). They are distributed under
the MIT License of that dataset. They are test fixtures for the evaluation runner and the gate;
nothing in this repository modifies them, and the gate never ships them into a rollout.
policy_variant/policy.py is written here for tests and is Apache-2.0 like the rest of this repository.
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_evaluate_suite.py`:

```python
"""Tests for gate/evaluate_suite.py: the evaluation runner and its receipts.

The runner arms ``RLIMIT_CPU`` for its own process, so every test here runs it in a subprocess.
Metric, CPU budget, and evaluator digests come from a real profile file built per test class from
the fixture task's own digests; the runner is never handed a hand-written digest.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import evaluate_suite  # noqa: E402
import treedigest  # noqa: E402
from tests.gate_fixtures import (NO_CACHES, POLICY_WEAK, TASK_ROOT, copy_policy, real_evaluator,  # noqa: E402
                                 real_visible_suite_sha, run_runner, write_profile)

TWO_SEEDS = {"max_moves": 300, "seeds": [11, 22]}
ONE_SEED = {"max_moves": 300, "seeds": [11]}
RECEIPT_KEYS = {"schema", "metric", "profile_sha256", "policy_method_tree_sha256", "suite_sha256", "max_moves",
                "result_sha256", "evaluator", "games", "cpu_seconds", "cpu_budget_per_game", "python", "timestamp"}


def write_suite(path: Path, document: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


class RunnerCase(unittest.TestCase):
    """A temporary root with a real profile, the two-seed suite, and a cache-free copy of the weak policy."""

    profile_overrides: dict = {}

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.profile = self.root / "gate" / "profile.json"
        self.profile_sha = write_profile(self.profile, evaluator=real_evaluator(),
                                         visible_suite_sha256=real_visible_suite_sha(), **self.profile_overrides)
        self.suite = write_suite(self.root / "suite.json", TWO_SEEDS)
        self.policy = copy_policy(POLICY_WEAK, self.root / "policy_weak")
        self.output = self.root / "results" / "v1" / "replication" / "parent_result.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_weak(self, *extra: str, policy: Path | None = None, suite: Path | None = None,
                 output: Path | None = None, task_root: Path | None = None, profile: Path | None = None,
                 env: dict[str, str] | None = None):
        return run_runner("--profile", str(profile or self.profile), "--task-root", str(task_root or TASK_ROOT),
                          "--policy-dir", str(policy or self.policy), "--suite", str(suite or self.suite),
                          "--output", str(output or self.output), *extra, env=env)


class TestRunnerResultAndReceipt(RunnerCase):
    def test_writes_the_result_in_selfcheck_shape_and_a_binding_receipt(self) -> None:
        proc = self.run_weak()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        for key in ("mean_score", "median_score", "mean_max_tile", "valid_fraction", "instances",
                    "cpu_seconds", "cpu_seconds_per_game", "cpu_budget_per_game"):
            self.assertIn(key, result)
        self.assertEqual([i["seed"] for i in result["instances"]], [11, 22])
        self.assertEqual(result["mean_score"], 1400.0)
        self.assertEqual(result["instances"][0]["score"], 1892)
        self.assertEqual(result["valid_fraction"], 1.0)
        self.assertEqual(result["cpu_budget_per_game"], 225)

        receipt_path = self.output.with_name("parent_result.receipt.json")
        self.assertEqual(evaluate_suite.receipt_path_for(self.output), receipt_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(set(receipt), RECEIPT_KEYS)
        self.assertEqual(receipt["schema"], "rsi-exam-gate-receipt/v1")
        self.assertEqual(receipt["metric"], "per_seed_2048_score")
        self.assertEqual(receipt["profile_sha256"], treedigest.file_sha256(self.profile))
        self.assertEqual(receipt["profile_sha256"], self.profile_sha)
        self.assertEqual(receipt["policy_method_tree_sha256"], treedigest.method_tree_sha256(POLICY_WEAK))
        self.assertEqual(receipt["suite_sha256"], treedigest.file_sha256(self.suite))
        self.assertEqual(receipt["max_moves"], 300)
        self.assertEqual(receipt["result_sha256"], treedigest.file_sha256(self.output))
        self.assertEqual(receipt["evaluator"], real_evaluator())
        self.assertEqual(receipt["games"], 2)
        self.assertEqual(receipt["cpu_budget_per_game"], 225)
        self.assertTrue(receipt["python"].startswith(f"{sys.version_info.major}.{sys.version_info.minor}"))
        self.assertTrue(receipt["timestamp"].endswith("+00:00"))

        self.assertEqual(list(self.policy.rglob("__pycache__")), [],
                         "the runner must not write bytecode into a policy tree")
        self.assertEqual(json.loads(proc.stdout.strip().splitlines()[-1]), receipt)

    def test_fixed_timestamp_and_an_explicit_receipt_path(self) -> None:
        env = dict(os.environ, DECIDE_FIXED_TIMESTAMP="2026-09-05T18:00:00+00:00")
        receipt_path = self.root / "results" / "v1" / "replication" / "elsewhere.json"
        proc = self.run_weak("--receipt", str(receipt_path), env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["timestamp"], "2026-09-05T18:00:00+00:00")
        self.assertFalse(self.output.with_name("parent_result.receipt.json").exists())

    def test_an_existing_output_is_never_overwritten(self) -> None:
        self.assertEqual(self.run_weak().returncode, 0)
        before = self.output.read_bytes()
        receipt_before = self.output.with_name("parent_result.receipt.json").read_bytes()
        second = self.run_weak()
        self.assertEqual(second.returncode, 2)
        self.assertIn("already exists", second.stderr)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(self.output.with_name("parent_result.receipt.json").read_bytes(), receipt_before)


class TestRunnerRefusals(RunnerCase):
    def assert_refused(self, proc, *, message: str) -> None:
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn(message, proc.stderr)
        self.assertFalse(self.output.exists())

    def test_output_inside_a_policy_tree_is_refused(self) -> None:
        for component in ("versions", "main"):
            with self.subTest(component=component):
                target = self.root / "methods" / component / "v1" / "r.json"
                self.assert_refused(self.run_weak(output=target), message="must not live in a policy tree")
                self.assertFalse(target.exists())

    def test_output_outside_a_results_directory_is_refused(self) -> None:
        target = self.root / "elsewhere" / "r.json"
        self.assert_refused(self.run_weak(output=target), message="must live under a results directory")
        self.assertFalse(target.exists())

    def test_a_symlinked_results_directory_is_refused(self) -> None:
        real = self.root / "real_evidence"
        real.mkdir()
        link_root = self.root / "linked"
        link_root.mkdir()
        os.symlink(real, link_root / "results")
        target = link_root / "results" / "v1" / "r.json"
        self.assert_refused(self.run_weak(output=target), message="goes through a symlink")
        self.assertEqual(list(real.iterdir()), [])

    def test_a_missing_policy_directory_is_refused(self) -> None:
        self.assert_refused(self.run_weak(policy=self.root / "absent"), message="policy.py not found")

    def test_an_evaluator_that_differs_from_the_profile_is_refused(self) -> None:
        drifted = self.root / "drifted_task"
        shutil.copytree(TASK_ROOT, drifted, ignore=NO_CACHES)
        (drifted / "evaluate.py").write_text(
            (drifted / "evaluate.py").read_text(encoding="utf-8") + "# an edit the profile does not pin\n",
            encoding="utf-8")
        self.assert_refused(self.run_weak(task_root=drifted),
                            message="differs from the digest the profile pins")

    def test_a_missing_or_empty_suite_is_refused(self) -> None:
        self.assert_refused(self.run_weak(suite=self.root / "absent.json"), message="suite not found")
        empty = write_suite(self.root / "empty.json", {"max_moves": 300, "seeds": []})
        self.assert_refused(self.run_weak(suite=empty), message="unique seeds")

    def test_a_missing_profile_is_refused(self) -> None:
        self.assert_refused(self.run_weak(profile=self.root / "absent.json"), message="profile not found")


class TestRunnerBudgets(RunnerCase):
    profile_overrides = {"confirmation": {"floor": 4, "max_seeds": 8, "max_moves": 300, "cpu_seconds_per_game": 1}}

    def test_cpu_exhaustion_exits_4_and_writes_nothing(self) -> None:
        spinner = self.root / "spinner"
        spinner.mkdir()
        (spinner / "policy.py").write_text("def choose_move(board):\n    while True:\n        pass\n", encoding="utf-8")
        one = write_suite(self.root / "one.json", ONE_SEED)
        proc = self.run_weak(policy=spinner, suite=one)
        self.assertEqual(proc.returncode, 4, proc.stderr)
        self.assertIn("CPU budget", proc.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name("parent_result.receipt.json").exists())

    def test_a_wall_clock_overrun_exits_6_and_writes_nothing(self) -> None:
        sleeper = self.root / "sleeper"
        sleeper.mkdir()
        (sleeper / "policy.py").write_text(
            "import time\n\n\ndef choose_move(board):\n    time.sleep(30)\n    return 'UP'\n", encoding="utf-8")
        one = write_suite(self.root / "one.json", ONE_SEED)
        started = time.monotonic()
        proc = self.run_weak("--wall-seconds", "2", policy=sleeper, suite=one)
        self.assertEqual(proc.returncode, 6, proc.stderr)
        self.assertLess(time.monotonic() - started, 20.0)
        self.assertIn("wall-clock", proc.stderr)
        self.assertFalse(self.output.exists())


class TestRunnerEvaluatorOutcomes(RunnerCase):
    def test_an_invalid_game_exits_5_and_writes_nothing(self) -> None:
        sideways = self.root / "sideways"
        sideways.mkdir()
        (sideways / "policy.py").write_text("def choose_move(board):\n    return 'SIDEWAYS'\n", encoding="utf-8")
        proc = self.run_weak(policy=sideways)
        self.assertEqual(proc.returncode, 5, proc.stderr)
        self.assertIn("invalid game", proc.stderr)
        self.assertFalse(self.output.exists())

    def test_an_evaluator_that_raises_exits_1_and_writes_nothing(self) -> None:
        nameless = self.root / "nameless"
        nameless.mkdir()
        (nameless / "policy.py").write_text("VALUE = 1\n", encoding="utf-8")
        proc = self.run_weak(policy=nameless)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("choose_move", proc.stderr)
        self.assertFalse(self.output.exists())


class TestRunnerShadowing(RunnerCase):
    def test_a_policy_directory_cannot_shadow_the_pinned_evaluator_or_game_engine(self) -> None:
        shadow = self.root / "shadow"
        shadow.mkdir()
        shutil.copy(POLICY_WEAK / "policy.py", shadow / "policy.py")
        (shadow / "evaluate.py").write_text(
            "def evaluate(policy_path, suite_path):\n"
            "    return {'mean_score': 99999.0, 'valid_fraction': 1.0,\n"
            "            'instances': [{'seed': 11, 'score': 99999, 'max_tile': 2048, 'moves': 1, 'error': None},\n"
            "                          {'seed': 22, 'score': 99999, 'max_tile': 2048, 'moves': 1, 'error': None}]}\n",
            encoding="utf-8")
        (shadow / "game2048.py").write_text('raise SystemExit("shadowed")\n', encoding="utf-8")
        proc = self.run_weak(policy=shadow)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(result["mean_score"], 1400.0)
        self.assertEqual({i["seed"]: i["score"] for i in result["instances"]}, {11: 1892, 22: 908})
        receipt = json.loads(self.output.with_name("parent_result.receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["evaluator"], real_evaluator())
        self.assertEqual(receipt["policy_method_tree_sha256"], treedigest.method_tree_sha256(shadow))


class TestReceiptPath(RunnerCase):
    def test_receipt_must_differ_from_the_output(self) -> None:
        proc = self.run_weak("--receipt", str(self.output))
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_evaluate_suite -v`
Expected: FAIL at import with `ModuleNotFoundError: No module named 'evaluate_suite'`.

- [ ] **Step 5: Write the runner**

Create `gate/evaluate_suite.py`:

```python
#!/usr/bin/env python3
"""Evaluate one policy directory on one seed suite in a child interpreter; write the result and a receipt.

The parent process holds the profile and does the bookkeeping: it checks that the task root's
``evaluate.py`` and ``game2048.py`` have exactly the digests the profile pins, digests the policy
tree (which must be a Python-only tree the grader would accept), reads the suite, and refuses any
output path that is not under a ``results`` directory or that passes through a symlink. It then
runs the evaluation in a fresh child interpreter started with ``PYTHONHASHSEED=0`` and
``PYTHONDONTWRITEBYTECODE=1`` (as the grader's policy process is), with one pooled ``RLIMIT_CPU`` of
``cpu_seconds_per_game * games`` (as ``selfcheck.py`` arms it) and a wall-clock limit. The child loads
``game2048`` and ``evaluate`` from the task root by exact path before the policy directory is put
first on ``sys.path``, so a policy cannot shadow the evaluator. The parent then requires every game
to be valid (``valid_fraction`` 1.0, no per-game error, exactly the suite's seeds), publishes the
result and the receipt through same-directory temporary files, and finally runs ``/app/budget.py``
when it is mounted, as ``selfcheck.py`` does.

CLI: ``--profile`` (the task profile; metric, CPU budget, and evaluator digests come from it),
``--task-root`` (default /app), ``--policy-dir`` (normally methods/versions/v<N>), ``--suite``,
``--output``, ``--receipt`` (default: the output with ``.json`` replaced by ``.receipt.json``),
``--wall-seconds`` (default: CPU budget plus 60).

Exit codes: 0 written; 1 the evaluator raised; 2 bad input or an evaluator file that differs from
the profile; 4 CPU budget exhausted; 5 a game was invalid; 6 wall clock exceeded. Only exit 0
writes anything. ``DECIDE_FIXED_TIMESTAMP`` fixes the receipt's timestamp for fixtures. Standard
library only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import resource
import signal
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from seeds import SeedsError, read_suite
from task_profile import ProfileError, load_profile
from treedigest import TreeDigestError, file_sha256, method_tree_sha256

RECEIPT_SCHEMA = "rsi-exam-gate-receipt/v1"
EVALUATOR_FILES = ("evaluate.py", "game2048.py")
POLICY_TREES = ("main", "versions")
EVIDENCE_ROOT = "results"
BUDGET_HOOK = Path("/app/budget.py")
EXIT_EVALUATOR, EXIT_INPUT, EXIT_CPU, EXIT_INVALID, EXIT_WALL = 1, 2, 4, 5, 6


class RunnerError(ValueError):
    """A runner input is missing or malformed. Nothing is written (exit 2)."""


class InvalidGames(RunnerError):
    """The evaluator reported an invalid game. Nothing is written (exit 5)."""


class CpuExceeded(RunnerError):
    """The policy exhausted the CPU budget. Nothing is written (exit 4)."""


class WallClockExceeded(RunnerError):
    """The evaluation did not finish within the wall-clock limit. Nothing is written (exit 6)."""


class EvaluatorFailed(RunnerError):
    """The evaluator raised in the child. Nothing is written (exit 1)."""


def check_output_path(path: Path) -> Path:
    """The output must live under a ``results`` directory, outside every policy tree, with no symlink below it."""
    parts = path.parent.parts
    if any(part in POLICY_TREES for part in parts):
        raise RunnerError(f"output must not live in a policy tree: {path}")
    if EVIDENCE_ROOT not in parts:
        raise RunnerError(f"output must live under a {EVIDENCE_ROOT} directory: {path}")
    index = len(parts) - 1 - parts[::-1].index(EVIDENCE_ROOT)
    for depth in range(index, len(parts)):
        ancestor = Path(*parts[: depth + 1])
        if ancestor.is_symlink():
            raise RunnerError(f"output path goes through a symlink: {ancestor}")
    if path.is_symlink():
        raise RunnerError(f"output path is a symlink: {path}")
    return path


def receipt_path_for(output: Path) -> Path:
    """``<name>.json`` becomes ``<name>.receipt.json`` next to the result."""
    stem = output.name[:-5] if output.name.endswith(".json") else output.name
    return output.with_name(stem + ".receipt.json")


def validate_result(result: Any, seeds: list[int]) -> None:
    """Every game valid, exactly the suite's seeds, finite scores; otherwise ``InvalidGames``."""
    if not isinstance(result, dict) or not isinstance(result.get("instances"), list):
        raise InvalidGames("evaluator result lacks an instances list")
    instances = result["instances"]
    if len(instances) != len(seeds):
        raise InvalidGames(f"evaluator returned {len(instances)} games for {len(seeds)} seeds")
    seen: set[int] = set()
    for game in instances:
        if not isinstance(game, dict) or game.get("error") is not None:
            raise InvalidGames(f"invalid game: {game!r}"[:300])
        score = game.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise InvalidGames(f"non-finite or missing score: {game!r}"[:300])
        seen.add(int(game["seed"]))
    if seen != set(seeds):
        raise InvalidGames("evaluator games do not cover exactly the suite's seeds")
    if result.get("valid_fraction") != 1.0:
        raise InvalidGames(f"valid_fraction is {result.get('valid_fraction')!r}, not 1.0")


def publish(path: Path, payload: bytes) -> None:
    """Write through a same-directory temporary file and rename into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def run(*, profile_path: Path, task_root: Path, policy_dir: Path, suite: Path, output: Path, receipt: Path,
        wall_seconds: int | None) -> dict[str, Any]:
    """Parent side: check, evaluate in a child, validate, publish. Returns the receipt document."""
    profile, profile_sha = load_profile(profile_path)
    for name in EVALUATOR_FILES:
        candidate = task_root / name
        if not candidate.is_file():
            raise RunnerError(f"task root lacks {name}: {task_root}")
        if file_sha256(candidate) != profile["evaluator"][name]:
            raise RunnerError(f"{name} in {task_root} differs from the digest the profile pins")
    if not (policy_dir / "policy.py").is_file():
        raise RunnerError(f"policy.py not found in {policy_dir}")
    if not suite.is_file():
        raise RunnerError(f"suite not found: {suite}")
    seeds, max_moves = read_suite(suite)
    check_output_path(output)
    check_output_path(receipt)
    if receipt.resolve() == output.resolve():
        raise RunnerError("the receipt path must differ from the output path")
    if output.exists() or receipt.exists():
        raise RunnerError("output or receipt already exists; evidence is written once")
    policy_digest = method_tree_sha256(policy_dir)
    cpu_budget = int(profile["confirmation"]["cpu_seconds_per_game"])
    limit = wall_seconds if wall_seconds is not None else cpu_budget * len(seeds) + 60
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".evaluate.", dir=output.parent) as scratch:
        tmp_result = Path(scratch) / "result.json"
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = "0"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        child = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--child", str(task_root), str(policy_dir), str(suite),
             str(tmp_result), str(cpu_budget)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, start_new_session=True,
        )
        try:
            out, err = child.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise WallClockExceeded(f"evaluation exceeded the wall-clock limit of {limit} s") from None
        if child.returncode == EXIT_CPU:
            raise CpuExceeded(err.strip() or f"policy exhausted the CPU budget of {cpu_budget * len(seeds)} s")
        if child.returncode != 0:
            raise EvaluatorFailed(err.strip().splitlines()[-1] if err.strip() else f"child exited {child.returncode}")
        meta = json.loads(out.strip().splitlines()[-1])
        result = json.loads(tmp_result.read_text(encoding="utf-8"))
        validate_result(result, seeds)
        result_bytes = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    publish(output, result_bytes)
    document: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "metric": profile["metric"],
        "profile_sha256": profile_sha,
        "policy_method_tree_sha256": policy_digest,
        "suite_sha256": file_sha256(suite),
        "max_moves": max_moves,
        "result_sha256": file_sha256(output),
        "evaluator": dict(profile["evaluator"]),
        "games": len(seeds),
        "cpu_seconds": result["cpu_seconds"],
        "cpu_budget_per_game": cpu_budget,
        "python": meta["python"],
        "timestamp": os.environ.get("DECIDE_FIXED_TIMESTAMP") or datetime.now(UTC).isoformat(),
    }
    publish(receipt, (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    if BUDGET_HOOK.exists():
        sys.stdout.flush()
        subprocess.run([sys.executable, str(BUDGET_HOOK)], check=False)
    return document


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def child_main(task_root: Path, policy_dir: Path, suite: Path, out: Path, cpu_budget: int) -> int:
    """Child side: pinned evaluator by exact path, policy dir first on sys.path, CPU budget armed."""
    sys.dont_write_bytecode = True
    _load_module("game2048", task_root / "game2048.py")
    evaluate = _load_module("evaluate", task_root / "evaluate.py")
    sys.path.insert(0, str(policy_dir))
    games = len(json.loads(suite.read_text(encoding="utf-8"))["seeds"])
    budget = cpu_budget * games

    def exceeded(_signum: int, _frame: object) -> None:
        print(f"policy exhausted the CPU budget of {budget} s", file=sys.stderr)
        raise SystemExit(EXIT_CPU)

    signal.signal(signal.SIGXCPU, exceeded)
    resource.setrlimit(resource.RLIMIT_CPU, (budget, budget + 20))
    before = resource.getrusage(resource.RUSAGE_SELF)
    result = evaluate.evaluate(policy_dir / "policy.py", suite)
    after = resource.getrusage(resource.RUSAGE_SELF)
    used = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    result["cpu_seconds"] = round(used, 1)
    result["cpu_seconds_per_game"] = round(used / games, 1)
    result["cpu_budget_per_game"] = cpu_budget
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"python": platform.python_version()}))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--child"]:
        task_root, policy_dir, suite, out, cpu_budget = argv[1:6]
        return child_main(Path(task_root), Path(policy_dir), Path(suite), Path(out), int(cpu_budget))
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--task-root", type=Path, default=Path("/app"))
    parser.add_argument("--policy-dir", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--wall-seconds", type=int, default=None)
    args = parser.parse_args(argv)
    receipt = args.receipt or receipt_path_for(args.output)
    try:
        document = run(profile_path=args.profile, task_root=args.task_root, policy_dir=args.policy_dir,
                       suite=args.suite, output=args.output, receipt=receipt, wall_seconds=args.wall_seconds)
    except CpuExceeded as exc:
        print(f"runner: {exc}", file=sys.stderr)
        return EXIT_CPU
    except InvalidGames as exc:
        print(f"runner refused: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except WallClockExceeded as exc:
        print(f"runner: {exc}", file=sys.stderr)
        return EXIT_WALL
    except EvaluatorFailed as exc:
        print(f"runner failed: {exc}", file=sys.stderr)
        return EXIT_EVALUATOR
    except (RunnerError, ProfileError, SeedsError, TreeDigestError) as exc:
        print(f"runner refused: {exc}", file=sys.stderr)
        return EXIT_INPUT
    print(json.dumps(document, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_evaluate_suite -v`
Expected: `Ran 15 tests`, `OK`. The suite takes a few seconds: the budget tests really exhaust a CPU budget and really hit a wall-clock limit.

- [ ] **Step 7: Type-check and commit**

Run: `pyright gate/evaluate_suite.py tests/test_evaluate_suite.py`
Expected: `0 errors`.

```bash
git add fixtures/task2048 gate/evaluate_suite.py tests/test_evaluate_suite.py
git diff --exit-code
git commit -m "feat(gate): add the evaluation runner that writes receipts

evaluate_suite.py evaluates one policy directory on one seed suite and writes
a receipt (schema rsi-exam-gate-receipt/v1) binding the result to the profile,
the policy's method-tree digest, the suite digest, the evaluator digests, the
game length, and the game count. The evaluation runs in a child interpreter
that loads the pinned evaluator and game engine by exact path before the
policy directory joins sys.path, so a policy cannot shadow either; the child
runs with a fixed hash seed, writes no bytecode, and carries the same pooled
CPU budget selfcheck.py arms, with a wall-clock limit that kills its process
group. Nothing is written unless every game is valid and covers exactly the
suite; result and receipt are published through same-directory temporary
files. Output paths outside a results directory, inside a policy tree, or
through a symlink are refused, and evidence is never overwritten.

The fixture under fixtures/task2048 is the task's evaluator, game engine, seed
file, and starter policy at the pinned dataset revision (MIT; see NOTICE),
plus a variant policy written here for tests.

Tests: result shape and binding receipt, fixed timestamp, no overwrite, five
refusals, CPU exhaustion (exit 4), wall-clock overrun (exit 6), an invalid
game (exit 5), an evaluator that raises (exit 1), and a shadowing attempt."
```

---

### Task 5: The restore helper (`gate/restore.py`), then pull request A

**Files:**
- Create: `gate/restore.py`
- Test: `tests/test_restore.py`

**Interfaces:**
- Consumes: `treedigest.method_tree_sha256`, `treedigest.TreeDigestError`.
- Produces: `class RestoreError(ValueError)`, `restore(methods: Path, version: str) -> str` (the restored tree's digest), `main(argv) -> int` with `--methods` and `--version`, exit 2 on any refusal.
- **Why it exists.** The autoresearch program's literal revert command, `cp -r versions/v<K> main`, nests the snapshot inside `main/` when `main/` already exists: the old policy stays in place and the next gate call refuses, because `main/` no longer equals any snapshot. The helper copies the snapshot's Python files to a sibling staging directory, removes `main/`, renames the staging directory into place, and verifies that the restored tree's digest equals the snapshot's. Bytecode caches are not copied. Milestone 3's runbook uses it; Milestone 1 ships it and tests it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_restore.py`:

```python
"""Tests for gate/restore.py: restoring main/ from a snapshot without nesting."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import restore  # noqa: E402
import treedigest  # noqa: E402
from tests.gate_fixtures import write_tree  # noqa: E402


class TestRestore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_tree(self.methods / "main", "def choose_move(board):\n    return 'LEFT'\n")
        (self.methods / "main" / "extra.py").write_text("z = 3\n", encoding="utf-8")
        write_tree(self.methods / "versions" / "v1", "def choose_move(board):\n    return 'UP'\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_restore_replaces_main_with_the_snapshot_and_returns_its_digest(self) -> None:
        expected = treedigest.method_tree_sha256(self.methods / "versions" / "v1")
        self.assertEqual(restore.main(["--methods", str(self.methods), "--version", "v1"]), 0)
        self.assertEqual(treedigest.method_tree_sha256(self.methods / "main"), expected)
        self.assertFalse((self.methods / "main" / "extra.py").exists())
        self.assertFalse((self.methods / "main" / "v1").exists(), "the snapshot must not be nested inside main/")
        self.assertFalse((self.methods / "main.restoring").exists())

    def test_caches_are_not_copied_and_a_stale_staging_dir_is_removed(self) -> None:
        (self.methods / "versions" / "v1" / "__pycache__").mkdir()
        (self.methods / "versions" / "v1" / "__pycache__" / "policy.cpython-312.pyc").write_bytes(b"\x00")
        (self.methods / "main.restoring").mkdir()
        (self.methods / "main.restoring" / "junk.py").write_text("j = 1\n", encoding="utf-8")
        self.assertEqual(restore.restore(self.methods, "v1"), treedigest.method_tree_sha256(self.methods / "versions" / "v1"))
        self.assertFalse((self.methods / "main" / "__pycache__").exists())
        self.assertFalse((self.methods / "main" / "junk.py").exists())

    def test_missing_or_invalid_snapshots_are_refused_and_main_is_untouched(self) -> None:
        before = treedigest.method_tree_sha256(self.methods / "main")
        self.assertEqual(restore.main(["--methods", str(self.methods), "--version", "v9"]), 2)
        (self.methods / "versions" / "v1" / "notes.json").write_text("{}", encoding="utf-8")
        self.assertEqual(restore.main(["--methods", str(self.methods), "--version", "v1"]), 2)
        self.assertEqual(treedigest.method_tree_sha256(self.methods / "main"), before)


class TestRestoreVersionArgument(unittest.TestCase):
    def test_version_must_be_a_single_path_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            methods = Path(tmp) / "methods"
            write_tree(methods / "main", "x = 1\n")
            write_tree(Path(tmp) / "outside", "def choose_move(board):\n    return 'UP'\n")
            for bad in ("../../outside", "v1/..", "", "."):
                with self.subTest(version=bad):
                    self.assertEqual(restore.main(["--methods", str(methods), "--version", bad]), 2)
            self.assertEqual((methods / "main" / "policy.py").read_text(encoding="utf-8"), "x = 1\n")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_restore -v`
Expected: FAIL at import with `ModuleNotFoundError: No module named 'restore'`.

- [ ] **Step 3: Write the module**

Create `gate/restore.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_restore -v`
Expected: `Ran 4 tests`, `OK`.

- [ ] **Step 5: Type-check, run the whole suite, commit, open pull request A**

Run: `pyright gate profile tests && python3 -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: `0 errors`; `Ran 110 tests`, `OK` (70 already on `main`, plus 7 + 5 + 8 + 16 + 4 from this pull request).

```bash
git add gate/restore.py tests/test_restore.py
git diff --exit-code
git commit -m "feat(gate): restore a snapshot into main/ without nesting it

The program's literal revert command copies a snapshot inside main/ when
main/ already exists, which leaves the old policy in place and makes every
later gate call refuse, because main/ then matches no snapshot. restore.py
stages the snapshot's Python files beside main/, replaces main/ in one
rename, and verifies that the restored tree's method-tree digest equals the
snapshot's.

Tests: a restore over an existing main/, caches and a stale staging directory
handled, and refusals that leave main/ untouched."
git push -u origin feat/gate-modules
gh pr create --title "feat(gate): method-tree digests, task profile, seed derivation, the evaluation runner, and the restore helper" --body "## Summary
Five new standard-library modules under gate/, the helpers their tests share, and the 2048 task fixture they run against:
- treedigest.py: cache-free, Python-only method-tree digests (the grader's view of a policy directory), symlinks refused.
- task_profile.py: the per-rollout profile (schema rsi-exam-gate-profile/v1) that fixes direction, unit, minimum effect, level, resamples, the bootstrap seed, the confirmation bounds, the visible suite digest, the replication key, the audit key digest, and the evaluator digests. It always means confirmation on fresh seeds.
- seeds.py: fresh confirmation suites (rsi-exam-gate/hmac-seeds/1) and the normal-approximation planning rule that sizes them.
- evaluate_suite.py: the evaluation runner. A child interpreter loads the pinned evaluator and game engine by exact path before the policy joins sys.path, arms the pooled CPU budget selfcheck.py uses, and writes nothing unless every game is valid; the parent publishes the result and a receipt binding result, method tree, suite, evaluator, game length, and game count by digest.
- restore.py: replace main/ with a snapshot without nesting it, and verify the restored digest.

decide.py and the converter are untouched in this pull request; the gate integration follows separately.

## Why
The screening-and-confirmation rule in docs/decision-log-contract.md needs a frozen candidate digest, a suite disjoint from the seeds the search has already used, and evaluations whose numbers are tied to the exact method, seeds, and evaluator. Without receipts a screening is a number with no provenance; without the child interpreter a policy can shadow the evaluator that scores it; without the restore helper a revert leaves the reverted policy running.

## Verification
python3 -m unittest discover -s tests -t . (110 tests, OK); pyright gate profile tests (0 errors); the four fetched fixture files match the digests pinned at dataset revision 956025d7ecf6; the runner leaves no __pycache__ under a policy tree, exits 4 on CPU exhaustion, 5 on an invalid game, and 6 on a wall-clock overrun."
```

Wait for pull request A to be merged before Task 6. If it is not merged, STOP and tell the operator.

---

### Task 6: The gate in two modes (`gate/decide.py`)

**Files:**
- Replace: `gate/decide.py` (the whole file)
- Replace: `tests/test_decide.py` (the whole file)

**Interfaces:**
- Consumes: `treedigest.file_sha256`, `treedigest.method_tree_sha256`, `treedigest.TreeDigestError`; `task_profile.load_profile`, `task_profile.resolve_min_effect`, `task_profile.ProfileError`; `seeds.derive_seeds`, `seeds.confirmation_size`, `seeds.write_suite`, `seeds.read_suite`, `seeds.SEEDS_ALGORITHM`, `seeds.SeedsError`.
- Produces (kept for the converter and the tests): `sha256_of`, `check_locator`, `evidence_path`, `load_scores`, `paired_deltas`, `bootstrap_interval`, `get_verdict`, `get_disposition(verdict, holdout_verdict, confirm_policy="inconclusive")`, `read_log`, `get_open_provisional`, `check_stacked_provisional`, `measure`, `build_line(...)`, `load_receipt`, `check_receipt`, `check_python_parity`, `suite_seeds_in_log`, `log_lock`, `append_line`, `build_replay_line`, `build_gated_line`, `main`.
- **The seven gated keys on every line.** `confirm_policy` (`always` in gated mode, `inconclusive` in replay mode); `profile_sha256` (64 hex, or `null` in replay mode); `look_index` (positive int, or `null` when the line opens no confirmation); `parent_method_tree_sha256` and `candidate_method_tree_sha256` (64 hex, or `null` in replay mode); `sizing` (the plan: `rule`, `size`, `planned`, `floor`, `cap`, `exploratory`, `screening_sd`, `z`, or `null`); `suite` (`{"locator", "sha256", "derivation"}` with `derivation` carrying `algorithm`, `rollout_id`, `candidate_method_tree_sha256`, `look_index`, `size`, `max_moves`, or `null`). The confirmation line repeats its provisional line's `profile_sha256`, `look_index`, both digests, `sizing`, `suite`, and `min_effect`.
- **Receipts the gate requires.** Every gated line carries `receipt-parent` and `receipt-candidate` evidence. A receipt lives next to its result as `<name>.receipt.json`, must be a complete `rsi-exam-gate-receipt/v1` document, and the gate compares `profile_sha256`, `suite_sha256`, `result_sha256`, `policy_method_tree_sha256`, `evaluator`, `metric`, `cpu_budget_per_game`, `max_moves`, and `games` against the profile, the suite, the result file on disk, and the frozen snapshot digest for that role. At screening the suite digest compared is the profile's `visible_suite_sha256`; at confirmation it is the derived suite's. All four receipts of a confirmed decision must share a Python major.minor version. `cpu_seconds` and `timestamp` are recorded, never compared.
- **Gated screening.** The fixed flags (`--confirm`, `--direction`, `--level`, `--resamples`, `--seed`, `--min-effect`, `--unit`, and the four result-locator flags) are refused; the profile supplies all of them. Both snapshots are digested and `main/` must equal the candidate's. `below` reverts with no plan. Otherwise the plan is computed from the screening deltas; an exploratory plan reverts, recording the plan and no suite; a plan that fits the cap derives a fresh suite excluding the visible seeds and every seed of every earlier suite, writes it to `results/<version>/replication/seeds.json`, and the line is `provisional`.
- **Gated confirmation.** The open provisional line is re-verified from its evidence rather than trusted: both snapshot digests still equal the frozen ones, every screening evidence file still has the digest the line recorded, the minimum effect re-resolves from the profile and the parent's visible result, the plan recomputes from the screening deltas and is not exploratory, the exclusion set is rebuilt from the lines before the provisional one, the suite re-derives from the key, the frozen candidate digest, and the look index, and the derivation record matches. Both confirmation results must cover exactly the suite's seeds. `clears` keeps; anything else reverts.
- **Transaction.** The whole read-check-write runs under `fcntl.flock` on `<methods>/decisions.lock`. The suite file is created with `O_EXCL` and removed again if the append fails. Exit 0 with the line on stdout, 2 on a refusal, 3 on a stacked or duplicate provisional.

- [ ] **Step 1: Create the branch from `main` after pull request A merges**

Throughout this plan `<A>` and `<B>` are the two pull request numbers `gh pr create` printed in Task 5 and Task 9; substitute them.

```bash
gh pr view <A> --json state --jq .state
git checkout main && git pull --ff-only && git checkout -b feat/gate-confirmation
ls gate/treedigest.py gate/task_profile.py gate/seeds.py gate/evaluate_suite.py gate/restore.py tests/gate_fixtures.py
```
Expected: `MERGED`, and all six files listed. If the pull request is not merged, STOP and ask the operator to merge it.

- [ ] **Step 2: Replace the gate's tests**

Replace `tests/test_decide.py` with this file:

```python
"""Tests for gate/decide.py: the paired bootstrap gate in replay mode and in gated mode."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import decide  # noqa: E402
import seeds as seedsmod  # noqa: E402
import treedigest  # noqa: E402
from tests.gate_fixtures import (DELTAS_BELOW, DELTAS_CLEAR, DELTAS_INCONCLUSIVE, PARENT, SEEDS,  # noqa: E402
                                 VISIBLE_SUITE_SHA, write_profile, write_receipt, write_result, write_tree)

UP = "def choose_move(board):\n    return 'UP'\n"
LEFT = "def choose_move(board):\n    return 'LEFT'\n"
RIGHT = "def choose_move(board):\n    return 'RIGHT'\n"
DOWN = "def choose_move(board):\n    return 'DOWN'\n"
GATED_KEYS = ("confirm_policy", "profile_sha256", "look_index", "parent_method_tree_sha256",
              "candidate_method_tree_sha256", "sizing", "suite")
ABSOLUTE_700 = {"kind": "absolute", "value": 700.0}
FRACTION_MIN_EFFECT = 0.025 * sum(PARENT) / len(PARENT)  # 103.0 on the PARENT visible scores


def shifted(base: Sequence[float], deltas: Sequence[float]) -> list[float]:
    return [b + d for b, d in zip(base, deltas)]


def bound_receipt_fields(overrides: dict[str, Any], **defaults: Any) -> dict[str, Any]:
    """Split receipt keyword arguments into the four fields the gate binds and the rest of the document.

    Mutates ``overrides`` in place: what it leaves behind goes into the receipt verbatim.
    """
    for key in list(defaults):
        if key in overrides:
            defaults[key] = overrides.pop(key)
    return defaults


def run_gate(argv: list[str]) -> tuple[int, str]:
    """Call the gate in process; return its exit code and what it refused with."""
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = decide.main(argv)
    return code, err.getvalue()


def gate_main(argv: list[str]) -> int:
    """The gate's exit code, with the appended line and any refusal kept off the test output."""
    return run_gate(argv)[0]


class TestStatistics(unittest.TestCase):
    def test_paired_deltas_align_by_seed(self) -> None:
        parent = dict(zip(SEEDS, PARENT))
        candidate = {s: p + d for s, p, d in zip(SEEDS, PARENT, DELTAS_INCONCLUSIVE)}
        self.assertEqual(decide.paired_deltas(parent, candidate), [float(d) for d in DELTAS_INCONCLUSIVE])

    def test_direction_lower_negates(self) -> None:
        parent = dict(zip(SEEDS, PARENT))
        candidate = {s: p + d for s, p, d in zip(SEEDS, PARENT, DELTAS_INCONCLUSIVE)}
        self.assertEqual(decide.paired_deltas(parent, candidate, "lower"), [-float(d) for d in DELTAS_INCONCLUSIVE])

    def test_paired_deltas_reject_seed_mismatch(self) -> None:
        parent = dict(zip(SEEDS, PARENT))
        candidate = dict(zip(SEEDS[:-1] + [999], PARENT))
        with self.assertRaises(decide.GateError):
            decide.paired_deltas(parent, candidate)

    def test_bootstrap_interval_is_deterministic_and_inconclusive(self) -> None:
        low, high = decide.bootstrap_interval([float(d) for d in DELTAS_INCONCLUSIVE], level=0.9, resamples=5000,
                                              seed=20260902)
        self.assertEqual((round(low, 1), round(high, 1)), (-30.0, 583.8))
        self.assertEqual(decide.get_verdict((low, high), 0.0), "inconclusive")

    def test_verdict_clears_and_below(self) -> None:
        low, high = decide.bootstrap_interval([float(d) for d in DELTAS_CLEAR], level=0.9, resamples=5000, seed=20260902)
        self.assertEqual(decide.get_verdict((low, high), 0.0), "clears")
        low, high = decide.bootstrap_interval([float(d) for d in DELTAS_BELOW], level=0.9, resamples=5000, seed=20260902)
        self.assertEqual(decide.get_verdict((low, high), 0.0), "below")

    def test_min_effect_can_turn_a_clear_into_a_straddle(self) -> None:
        self.assertEqual(decide.get_verdict((10.0, 40.0), 20.0), "inconclusive")

    def test_negative_min_effect_is_refused(self) -> None:
        with self.assertRaises(decide.GateError):
            decide.get_verdict((10.0, 40.0), -1.0)

    def test_disposition_follows_verdict_and_holdout(self) -> None:
        self.assertEqual(decide.get_disposition("clears", None), "keep")
        self.assertEqual(decide.get_disposition("below", None), "revert")
        self.assertEqual(decide.get_disposition("inconclusive", None), "provisional")
        self.assertEqual(decide.get_disposition("clears", "inconclusive"), "provisional")
        self.assertEqual(decide.get_disposition("clears", "clears"), "keep")

    def test_disposition_under_always_makes_every_non_revert_provisional(self) -> None:
        self.assertEqual(decide.get_disposition("clears", None, "always"), "provisional")
        self.assertEqual(decide.get_disposition("inconclusive", None, "always"), "provisional")
        self.assertEqual(decide.get_disposition("below", None, "always"), "revert")
        with self.assertRaises(decide.GateError):
            decide.get_disposition("clears", None, "sometimes")


class TestCli(unittest.TestCase):
    """Replay mode: explicit locators, the weaker screening-only rule, nothing frozen."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_result(self.methods / "results" / "v6" / "visible_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "visible_result.json", shifted(PARENT, DELTAS_INCONCLUSIVE))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_gate(self, *extra: str) -> int:
        return gate_main(["--methods", str(self.methods), "--version", "v7", "--parent", "v6",
                          "--confirm", "inconclusive", *extra])

    def lines(self) -> list[dict[str, Any]]:
        return [json.loads(x) for x in (self.methods / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_appends_one_line_in_the_contract_shape(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        lines = self.lines()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line["schema"], "rsi-exam-decision-log/v1")
        self.assertEqual(line["line"], 1)
        self.assertEqual((line["version_id"], line["parent_id"], line["replicates"]), ("v7", "v6", None))
        self.assertEqual(line["verdict"], "inconclusive")
        self.assertEqual(line["disposition"], "provisional")
        self.assertEqual(line["sample_size"], 8)
        self.assertEqual(line["direction"], "higher")
        self.assertEqual(line["interval"]["level"], 0.9)
        self.assertLessEqual(line["interval"]["lower"], line["estimate"])
        self.assertLessEqual(line["estimate"], line["interval"]["upper"])
        self.assertEqual(line["method"], {"name": "percentile_bootstrap", "algorithm": "rsi-exam-gate/percentile-bootstrap/1",
                                          "resamples": 5000, "seed": 20260902})
        self.assertEqual([e["role"] for e in line["evidence"]], ["parent", "candidate"])
        self.assertEqual([e["locator"] for e in line["evidence"]],
                         ["results/v6/visible_result.json", "results/v7/visible_result.json"])
        for ref in line["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
            self.assertEqual(line["evidence_digests"][ref["role"]], "sha256:" + ref["sha256"])
        self.assertTrue(line["timestamp"].endswith("+00:00"))
        self.assertIsNone(line["holdout"])
        # every gated key is present on every line; in replay mode only the policy is stated
        for key in GATED_KEYS:
            self.assertIn(key, line)
        self.assertEqual(line["confirm_policy"], "inconclusive")
        self.assertIsNone(line["profile_sha256"])
        self.assertIsNone(line["look_index"])
        self.assertIsNone(line["parent_method_tree_sha256"])
        self.assertIsNone(line["candidate_method_tree_sha256"])
        self.assertIsNone(line["sizing"])
        self.assertIsNone(line["suite"])

    def test_refuses_to_stack_on_an_unreplicated_provisional(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v8" / "visible_result.json",
                     [p + d + 20 for p, d in zip(PARENT, DELTAS_INCONCLUSIVE)])
        code = gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v7",
                            "--confirm", "inconclusive"])
        self.assertEqual(code, 3)
        self.assertEqual(len(self.lines()), 1)

    def test_refuses_a_second_open_provisional_on_another_parent(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v8" / "visible_result.json", shifted(PARENT, DELTAS_INCONCLUSIVE))
        code = gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6",
                            "--confirm", "inconclusive"])
        self.assertEqual(code, 3)
        self.assertEqual(len(self.lines()), 1)

    def test_a_clear_keep_on_another_parent_is_allowed_while_one_provisional_is_open(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v8" / "visible_result.json", shifted(PARENT, DELTAS_CLEAR))
        code = gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6",
                            "--confirm", "inconclusive"])
        self.assertEqual(code, 0)
        self.assertEqual(self.lines()[1]["disposition"], "keep")

    def test_replication_resolves_the_provisional(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "replication" / "candidate_result.json",
                     shifted(PARENT, DELTAS_CLEAR))
        self.assertEqual(self.run_gate("--replicates", "v7"), 0)
        lines = self.lines()
        self.assertEqual(lines[1]["replicates"], "v7")
        self.assertEqual(lines[1]["disposition"], "keep")
        self.assertEqual(lines[1]["line"], 2)
        self.assertEqual(lines[1]["evidence"][0]["locator"], "results/v7/replication/parent_result.json")
        self.assertIsNone(lines[1]["suite"])
        # the provisional is now resolved, so building on v7 is allowed
        write_result(self.methods / "results" / "v8" / "visible_result.json",
                     [p + d + 600 for p, d in zip(PARENT, DELTAS_CLEAR)])
        self.assertEqual(gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v7",
                                      "--confirm", "inconclusive"]), 0)

    def test_replication_without_an_open_provisional_is_refused(self) -> None:
        write_result(self.methods / "results" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "replication" / "candidate_result.json", PARENT)
        self.assertEqual(self.run_gate("--replicates", "v7"), 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_replication_with_wrong_parent_is_refused(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "replication" / "candidate_result.json", PARENT)
        code = gate_main(["--methods", str(self.methods), "--version", "v7", "--parent", "v5",
                            "--replicates", "v7", "--confirm", "inconclusive"])
        self.assertEqual(code, 2)
        self.assertEqual(len(self.lines()), 1)

    def test_replication_with_non_clearing_holdout_reverts(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        write_result(self.methods / "results" / "v7" / "replication" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "replication" / "candidate_result.json",
                     shifted(PARENT, DELTAS_CLEAR))
        write_result(self.methods / "results" / "v7" / "holdout" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "holdout" / "candidate_result.json",
                     shifted(PARENT, DELTAS_INCONCLUSIVE))
        code = self.run_gate("--replicates", "v7",
                             "--holdout-parent-result", "results/v7/holdout/parent_result.json",
                             "--holdout-candidate-result", "results/v7/holdout/candidate_result.json")
        self.assertEqual(code, 0)
        lines = self.lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual((lines[1]["verdict"], lines[1]["holdout"]["verdict"], lines[1]["disposition"]),
                         ("clears", "inconclusive", "revert"))
        # the provisional is resolved, so a new line on v6 may open a fresh provisional
        write_result(self.methods / "results" / "v8" / "visible_result.json", shifted(PARENT, DELTAS_INCONCLUSIVE))
        self.assertEqual(gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6",
                                      "--confirm", "inconclusive"]), 0)

    def test_holdout_forces_provisional_and_is_recorded(self) -> None:
        write_result(self.methods / "results" / "v7" / "visible_result.json", shifted(PARENT, DELTAS_CLEAR))
        write_result(self.methods / "results" / "v7" / "holdout" / "parent_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "holdout" / "candidate_result.json",
                     shifted(PARENT, DELTAS_INCONCLUSIVE))
        code = self.run_gate("--holdout-parent-result", "results/v7/holdout/parent_result.json",
                             "--holdout-candidate-result", "results/v7/holdout/candidate_result.json")
        self.assertEqual(code, 0)
        line = self.lines()[0]
        self.assertEqual(line["verdict"], "clears")
        self.assertEqual(line["disposition"], "provisional")
        self.assertEqual(line["holdout"]["verdict"], "inconclusive")
        self.assertEqual([e["role"] for e in line["holdout"]["evidence"]], ["holdout-parent", "holdout-candidate"])
        self.assertEqual(set(line["holdout"]["evidence_digests"]), {"holdout-parent", "holdout-candidate"})

    def test_missing_result_file_fails_loud(self) -> None:
        code = gate_main(["--methods", str(self.methods), "--version", "v9", "--parent", "v6",
                            "--confirm", "inconclusive"])
        self.assertEqual(code, 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_negative_min_effect_flag_is_refused(self) -> None:
        self.assertEqual(self.run_gate("--min-effect", "-5"), 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_locator_escaping_methods_is_refused(self) -> None:
        self.assertEqual(self.run_gate("--parent-result", "../outside.json"), 2)
        self.assertEqual(self.run_gate("--parent-result", "results\\v6\\visible_result.json"), 2)
        self.assertEqual(self.run_gate("--parent-result", "results/%2e%2e/v6.json"), 2)

    def test_evidence_inside_the_policy_tree_is_refused(self) -> None:
        write_result(self.methods / "versions" / "v6" / "visible_result.json", PARENT)
        self.assertEqual(self.run_gate("--parent-result", "versions/v6/visible_result.json"), 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_corrupt_log_is_refused(self) -> None:
        self.assertEqual(self.run_gate(), 0)
        log = self.methods / "decisions.jsonl"
        log.write_text(log.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        write_result(self.methods / "results" / "v8" / "visible_result.json", shifted(PARENT, DELTAS_CLEAR))
        self.assertEqual(gate_main(["--methods", str(self.methods), "--version", "v8", "--parent", "v6",
                                      "--confirm", "inconclusive"]), 2)


class TestReplayModeFlags(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_result(self.methods / "results" / "v6" / "visible_result.json", PARENT)
        write_result(self.methods / "results" / "v7" / "visible_result.json", shifted(PARENT, DELTAS_CLEAR))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_confirm_policy_must_be_stated(self) -> None:
        code = gate_main(["--methods", str(self.methods), "--version", "v7", "--parent", "v6"])
        self.assertEqual(code, 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())

    def test_always_needs_a_profile(self) -> None:
        code = gate_main(["--methods", str(self.methods), "--version", "v7", "--parent", "v6",
                            "--confirm", "always"])
        self.assertEqual(code, 2)
        self.assertFalse((self.methods / "decisions.jsonl").exists())


class GatedCase(unittest.TestCase):
    """A methods directory with v1 (parent) and v2 (candidate) snapshots, main/ matching v2, and a profile."""

    profile_overrides: dict[str, Any] = {}
    candidate_deltas: Sequence[float] = DELTAS_INCONCLUSIVE

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        write_tree(self.methods / "versions" / "v1", UP)
        write_tree(self.methods / "versions" / "v2", LEFT)
        write_tree(self.methods / "main", LEFT)
        self.profile = self.methods / "gate" / "profile.json"
        self.profile_sha = write_profile(self.profile, **self.profile_overrides)
        self.write_visible("v1", PARENT)
        self.write_visible("v2", shifted(PARENT, self.candidate_deltas))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def digest(self, version: str) -> str:
        return treedigest.method_tree_sha256(self.methods / "versions" / version)

    def visible_path(self, version: str) -> Path:
        return self.methods / "results" / version / "visible_result.json"

    def write_visible(self, version: str, scores: Sequence[float], **receipt_overrides: Any) -> Path:
        """A visible result for one version with the runner receipt the gated screening requires."""
        path = self.visible_path(version)
        write_result(path, scores)
        self.write_visible_receipt(version, **receipt_overrides)
        return path

    def write_visible_receipt(self, version: str, **overrides: Any) -> None:
        bound = bound_receipt_fields(overrides, profile_sha=self.profile_sha, policy_digest=self.digest(version),
                                     suite_sha=VISIBLE_SUITE_SHA, games=len(SEEDS))
        write_receipt(self.visible_path(version), **bound, **overrides)

    def reprofile(self, **overrides: Any) -> None:
        """Rewrite the profile in place and re-bind both visible receipts to its new digest."""
        self.profile_sha = write_profile(self.profile, **overrides)
        for version in ("v1", "v2"):
            self.write_visible_receipt(version)

    def gate(self, version: str, parent: str, *extra: str, profile: Path | None = None) -> int:
        code, _ = self.gate_with_stderr(version, parent, *extra, profile=profile)
        return code

    def gate_with_stderr(self, version: str, parent: str, *extra: str, profile: Path | None = None) -> tuple[int, str]:
        return run_gate(["--methods", str(self.methods), "--version", version, "--parent", parent,
                         "--profile", str(profile or self.profile), *extra])

    def lines(self) -> list[dict[str, Any]]:
        log = self.methods / "decisions.jsonl"
        if not log.exists():
            return []
        return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]

    def suite_file(self, version: str) -> Path:
        return self.methods / "results" / version / "replication" / "seeds.json"


class TestGatedScreening(GatedCase):
    def test_fixed_flags_are_refused_in_gated_mode(self) -> None:
        for extra in (("--confirm", "always"), ("--confirm", "inconclusive"), ("--direction", "lower"),
                      ("--min-effect", "5"), ("--level", "0.8"), ("--resamples", "5000"), ("--seed", "1"),
                      ("--unit", "x"), ("--parent-result", "results/v1/visible_result.json"),
                      ("--candidate-result", "results/v2/visible_result.json"),
                      ("--holdout-parent-result", "results/v1/h.json",
                       "--holdout-candidate-result", "results/v2/h.json")):
            with self.subTest(extra=extra):
                code, err = self.gate_with_stderr("v2", "v1", *extra)
                self.assertEqual(code, 2)
                self.assertIn("fixed by the profile", err)
        self.assertEqual(self.lines(), [])

    def test_an_under_planned_confirmation_reverts_and_records_its_plan(self) -> None:
        self.assertEqual(self.gate("v2", "v1"), 0)
        line = self.lines()[0]
        self.assertEqual((line["verdict"], line["disposition"], line["confirm_policy"]),
                         ("inconclusive", "revert", "always"))
        self.assertAlmostEqual(line["min_effect"], FRACTION_MIN_EFFECT)
        self.assertEqual(line["profile_sha256"], self.profile_sha)
        self.assertEqual(line["parent_method_tree_sha256"], self.digest("v1"))
        self.assertEqual(line["candidate_method_tree_sha256"], self.digest("v2"))
        sizing = line["sizing"]
        self.assertEqual(set(sizing), {"rule", "size", "planned", "floor", "cap", "exploratory", "screening_sd", "z"})
        self.assertEqual((sizing["planned"], sizing["size"], sizing["floor"], sizing["cap"], sizing["exploratory"]),
                         (327, 8, 4, 8, True))
        self.assertEqual(sizing["rule"], seedsmod.SIZING_RULE)
        self.assertIsNone(line["suite"])
        self.assertIsNone(line["look_index"])
        self.assertFalse(self.suite_file("v2").exists())
        self.assertEqual([e["role"] for e in line["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])
        self.assertEqual([e["locator"] for e in line["evidence"]],
                         ["results/v1/visible_result.json", "results/v2/visible_result.json",
                          "results/v1/visible_result.receipt.json", "results/v2/visible_result.receipt.json"])
        for ref in line["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
            self.assertEqual(line["evidence_digests"][ref["role"]], "sha256:" + ref["sha256"])

    def test_a_plan_that_fits_the_cap_opens_a_provisional_with_a_fresh_suite(self) -> None:
        self.reprofile(min_effect=ABSOLUTE_700)
        self.assertEqual(self.gate("v2", "v1"), 0)
        line = self.lines()[0]
        self.assertEqual((line["verdict"], line["disposition"]), ("inconclusive", "provisional"))
        self.assertEqual(line["min_effect"], 700.0)
        self.assertEqual((line["sizing"]["planned"], line["sizing"]["size"], line["sizing"]["exploratory"]),
                         (8, 8, False))
        self.assertEqual(line["look_index"], 1)
        suite = line["suite"]
        self.assertEqual(set(suite), {"locator", "sha256", "derivation"})
        self.assertEqual(suite["locator"], "results/v2/replication/seeds.json")
        path = self.suite_file("v2")
        self.assertEqual(decide.sha256_of(path), suite["sha256"])
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["max_moves"], 300)
        self.assertEqual(len(document["seeds"]), 8)
        self.assertEqual(len(set(document["seeds"])), 8)
        self.assertFalse(set(document["seeds"]) & set(SEEDS))
        self.assertEqual(suite["derivation"],
                         {"algorithm": seedsmod.SEEDS_ALGORITHM, "rollout_id": "demo-rollout",
                          "candidate_method_tree_sha256": self.digest("v2"), "look_index": 1, "size": 8,
                          "max_moves": 300})
        self.assertEqual(document["seeds"],
                         seedsmod.derive_seeds(key_hex="11" * 32, rollout_id="demo-rollout",
                                               candidate_digest=self.digest("v2"), look_index=1, size=8,
                                               exclude=set(SEEDS)))

    def test_constant_clear_deltas_plan_the_floor(self) -> None:
        write_result(self.visible_path("v2"), [p + 500 for p in PARENT])
        self.write_visible_receipt("v2")
        self.assertEqual(self.gate("v2", "v1"), 0)
        line = self.lines()[0]
        self.assertEqual((line["interval"]["lower"], line["interval"]["upper"]), (500.0, 500.0))
        self.assertEqual((line["verdict"], line["disposition"]), ("clears", "provisional"))
        self.assertEqual(line["sizing"]["screening_sd"], 0.0)
        self.assertEqual((line["sizing"]["planned"], line["sizing"]["size"], line["sizing"]["exploratory"]),
                         (4, 4, False))
        self.assertEqual(line["suite"]["derivation"]["size"], 4)
        document = json.loads(self.suite_file("v2").read_text(encoding="utf-8"))
        self.assertEqual(len(document["seeds"]), 4)
        self.assertFalse(set(document["seeds"]) & set(SEEDS))

    def test_below_reverts_with_no_plan_and_no_suite(self) -> None:
        write_result(self.visible_path("v2"), shifted(PARENT, DELTAS_BELOW))
        self.write_visible_receipt("v2")
        self.assertEqual(self.gate("v2", "v1"), 0)
        line = self.lines()[0]
        self.assertEqual((line["verdict"], line["disposition"]), ("below", "revert"))
        self.assertIsNone(line["sizing"])
        self.assertIsNone(line["suite"])
        self.assertIsNone(line["look_index"])
        self.assertFalse((self.methods / "results" / "v2" / "replication").exists())

    def test_a_missing_visible_receipt_is_refused(self) -> None:
        self.visible_path("v2").with_name("visible_result.receipt.json").unlink()
        code, err = self.gate_with_stderr("v2", "v1")
        self.assertEqual(code, 2)
        self.assertIn("receipt not found", err)
        self.assertEqual(self.lines(), [])

    def test_each_bound_receipt_field_is_compared(self) -> None:
        for field, value in (("policy_digest", "0" * 64), ("suite_sha", "0" * 64), ("profile_sha", "0" * 64),
                             ("games", 3), ("metric", "other"), ("max_moves", 10000),
                             ("cpu_budget_per_game", 5), ("result_sha256", "0" * 64),
                             ("evaluator", {"evaluate.py": "0" * 64, "game2048.py": "b" * 64})):
            with self.subTest(field=field):
                self.write_visible_receipt("v2", **{field: value})
                code, err = self.gate_with_stderr("v2", "v1")
                self.assertEqual(code, 2)
                self.assertIn("candidate receipt", err)
                self.write_visible_receipt("v2")
        self.assertEqual(self.lines(), [])

    def test_receipts_from_different_python_minors_are_refused(self) -> None:
        self.write_visible_receipt("v1", python="3.11.9")
        code, err = self.gate_with_stderr("v2", "v1")
        self.assertEqual(code, 2)
        self.assertIn("different Python versions", err)
        self.assertEqual(self.lines(), [])

    def test_main_must_match_the_candidate_snapshot(self) -> None:
        self.reprofile(min_effect=ABSOLUTE_700)
        write_tree(self.methods / "main", DOWN)
        code, err = self.gate_with_stderr("v2", "v1")
        self.assertEqual(code, 2)
        self.assertIn("main/ does not match versions/v2", err)
        self.assertEqual(self.lines(), [])
        self.assertFalse(self.suite_file("v2").exists())

    def test_missing_snapshots_are_refused(self) -> None:
        self.assertEqual(self.gate("v3", "v1"), 2)
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        self.assertEqual(self.gate("v3", "v9"), 2)
        self.assertEqual(self.lines(), [])

    def test_a_replay_line_and_a_gated_line_never_share_one_log(self) -> None:
        replay = ["--methods", str(self.methods), "--version", "v2", "--parent", "v1", "--confirm", "inconclusive"]
        self.assertEqual(gate_main(replay), 0)
        code, err = self.gate_with_stderr("v2", "v1")
        self.assertEqual(code, 2)
        self.assertIn("one profile per log", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_gated_line_refuses_a_later_replay_line_and_a_second_profile(self) -> None:
        write_result(self.visible_path("v2"), shifted(PARENT, DELTAS_BELOW))
        self.write_visible_receipt("v2")
        self.assertEqual(self.gate("v2", "v1"), 0)
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        write_result(self.visible_path("v3"), shifted(PARENT, DELTAS_CLEAR))
        code, err = run_gate(["--methods", str(self.methods), "--version", "v3", "--parent", "v1",
                              "--confirm", "inconclusive"])
        self.assertEqual(code, 2)
        self.assertIn("written in gated mode", err)
        other = self.methods / "gate" / "other.json"
        write_profile(other, rollout_id="another-rollout")
        code, err = self.gate_with_stderr("v3", "v1", profile=other)
        self.assertEqual(code, 2)
        self.assertIn("one profile per log", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_second_provisional_is_refused_and_writes_no_suite(self) -> None:
        self.reprofile(min_effect=ABSOLUTE_700)
        self.assertEqual(self.gate("v2", "v1"), 0)
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        write_result(self.visible_path("v3"), shifted(PARENT, DELTAS_INCONCLUSIVE))
        self.write_visible_receipt("v3")
        code, err = self.gate_with_stderr("v3", "v1")
        self.assertEqual(code, 3)
        self.assertIn("one open provisional decision", err)
        self.assertFalse(self.suite_file("v3").exists())
        # and building on the open provisional's own version is refused too
        code, err = self.gate_with_stderr("v3", "v2")
        self.assertEqual(code, 3)
        self.assertIn("unreplicated provisional decision", err)
        self.assertEqual(len(self.lines()), 1)
        self.assertFalse(self.suite_file("v3").exists())


class TestGatedConfirmation(GatedCase):
    """Line 1 is a provisional with an eight-seed suite; every test resolves or refuses it."""

    profile_overrides = {"min_effect": ABSOLUTE_700}

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.gate("v2", "v1"), 0)
        self.line1 = self.lines()[0]
        self.assertEqual(self.line1["disposition"], "provisional")
        self.suite_seeds, _ = seedsmod.read_suite(self.suite_file("v2"))
        self.assertEqual(len(self.suite_seeds), 8)
        self.base = self.methods / "results" / "v2" / "replication"

    def confirmation_path(self, role: str) -> Path:
        return self.base / f"{role}_result.json"

    def write_confirmation(self, parent_scores: Sequence[float], candidate_scores: Sequence[float],
                           seeds: Sequence[int] | None = None) -> None:
        chosen = list(seeds if seeds is not None else self.suite_seeds)
        write_result(self.confirmation_path("parent"), parent_scores, chosen)
        write_result(self.confirmation_path("candidate"), candidate_scores, chosen)
        self.write_confirmation_receipt("parent")
        self.write_confirmation_receipt("candidate")

    def write_confirmation_receipt(self, role: str, **overrides: Any) -> None:
        version = "v1" if role == "parent" else "v2"
        bound = bound_receipt_fields(overrides, profile_sha=self.profile_sha, policy_digest=self.digest(version),
                                     suite_sha=self.line1["suite"]["sha256"], games=len(self.suite_seeds))
        write_receipt(self.confirmation_path(role), **bound, **overrides)

    def replicate(self, *extra: str) -> tuple[int, str]:
        return self.gate_with_stderr("v2", "v1", "--replicates", "v2", *extra)

    def test_a_clearing_confirmation_keeps_and_repeats_the_frozen_record(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        self.assertEqual(self.replicate()[0], 0)
        line1, line2 = self.lines()
        self.assertEqual((line2["replicates"], line2["verdict"], line2["disposition"]), ("v2", "clears", "keep"))
        self.assertEqual(line2["sample_size"], 8)
        self.assertEqual((line2["interval"]["lower"], line2["interval"]["upper"]), (800.0, 800.0))
        for key in ("suite", "sizing", "look_index", "profile_sha256", "parent_method_tree_sha256",
                    "candidate_method_tree_sha256", "min_effect"):
            self.assertEqual(line2[key], line1[key], key)
        self.assertEqual(line2["confirm_policy"], "always")
        self.assertEqual([e["role"] for e in line2["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])
        self.assertEqual([e["locator"] for e in line2["evidence"]],
                         ["results/v2/replication/parent_result.json",
                          "results/v2/replication/candidate_result.json",
                          "results/v2/replication/parent_result.receipt.json",
                          "results/v2/replication/candidate_result.receipt.json"])
        for ref in line2["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
            self.assertEqual(line2["evidence_digests"][ref["role"]], "sha256:" + ref["sha256"])
        # v2 is resolved, so a candidate may build on it; the next look is the second
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        self.write_visible("v3", shifted(shifted(PARENT, DELTAS_INCONCLUSIVE), DELTAS_INCONCLUSIVE))
        self.assertEqual(self.gate("v3", "v2"), 0)
        line3 = self.lines()[2]
        self.assertEqual((line3["disposition"], line3["look_index"]), ("provisional", 2))
        fresh, _ = seedsmod.read_suite(self.suite_file("v3"))
        self.assertFalse(set(fresh) & (set(SEEDS) | set(self.suite_seeds)))

    def test_an_inconclusive_confirmation_reverts_and_frees_the_next_provisional(self) -> None:
        self.write_confirmation(PARENT, shifted(PARENT, DELTAS_INCONCLUSIVE))
        self.assertEqual(self.replicate()[0], 0)
        line2 = self.lines()[1]
        self.assertEqual((line2["verdict"], line2["disposition"]), ("inconclusive", "revert"))
        write_tree(self.methods / "versions" / "v3", RIGHT)
        write_tree(self.methods / "main", RIGHT)
        self.write_visible("v3", shifted(PARENT, DELTAS_INCONCLUSIVE))
        self.assertEqual(self.gate("v3", "v1"), 0)
        self.assertEqual(self.lines()[2]["disposition"], "provisional")

    def test_a_missing_confirmation_receipt_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        self.confirmation_path("candidate").with_name("candidate_result.receipt.json").unlink()
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("receipt not found", err)
        self.assertEqual(len(self.lines()), 1)

    def test_each_bound_confirmation_receipt_field_is_compared(self) -> None:
        for field, value in (("suite_sha", "0" * 64), ("policy_digest", "0" * 64), ("profile_sha", "0" * 64),
                             ("games", 3), ("metric", "other"), ("max_moves", 10000),
                             ("cpu_budget_per_game", 5), ("result_sha256", "0" * 64),
                             ("evaluator", {"evaluate.py": "0" * 64, "game2048.py": "b" * 64})):
            with self.subTest(field=field):
                self.write_confirmation(PARENT, [p + 800 for p in PARENT])
                self.write_confirmation_receipt("candidate", **{field: value})
                code, err = self.replicate()
                self.assertEqual(code, 2)
                self.assertIn("candidate receipt", err)
        self.assertEqual(len(self.lines()), 1)

    def test_results_must_cover_exactly_the_confirmation_suite(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT], seeds=SEEDS)
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("does not cover exactly the confirmation suite", err)
        self.assertEqual(len(self.lines()), 1)

    def test_an_altered_suite_file_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        path = self.suite_file("v2")
        document = json.loads(path.read_text(encoding="utf-8"))
        document["seeds"][0] = 5
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("missing or altered", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_coherently_rewritten_suite_still_fails_to_re_derive(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        path = self.suite_file("v2")
        document = json.loads(path.read_text(encoding="utf-8"))
        document["seeds"][0] = 5
        payload = json.dumps(document, indent=2, sort_keys=True) + "\n"
        path.write_text(payload, encoding="utf-8")
        line1 = dict(self.line1)
        line1["suite"] = dict(line1["suite"], sha256=decide.sha256_of(path))
        log = self.methods / "decisions.jsonl"
        log.write_text(json.dumps(line1, sort_keys=True) + "\n", encoding="utf-8")
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("does not re-derive", err)
        self.assertEqual(len(self.lines()), 1)

    def test_screening_evidence_edited_after_the_freeze_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        write_result(self.visible_path("v2"), shifted(PARENT, DELTAS_CLEAR))
        self.write_visible_receipt("v2")
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("changed since the provisional line was written", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_candidate_edited_after_the_freeze_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        write_tree(self.methods / "main", DOWN)
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("main/ does not match versions/v2", err)
        write_tree(self.methods / "versions" / "v2", DOWN)
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("changed", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_parent_edited_after_the_screening_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        write_tree(self.methods / "versions" / "v1", DOWN)
        code, err = self.replicate()
        self.assertEqual(code, 2)
        self.assertIn("versions/v1 changed after the screening that froze it", err)
        self.assertEqual(len(self.lines()), 1)

    def test_a_wrong_parent_or_version_is_refused(self) -> None:
        self.write_confirmation(PARENT, [p + 800 for p in PARENT])
        write_tree(self.methods / "versions" / "v0", UP)
        self.assertEqual(self.gate("v2", "v0", "--replicates", "v2"), 2)
        self.assertEqual(self.gate("v2", "v1", "--replicates", "v1"), 2)
        self.assertEqual(len(self.lines()), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_decide -v`
Expected: FAIL. The current gate has no `--profile` or `--confirm` flag, so argparse exits 2 and the calls raise `SystemExit`; the statistics tests that pass `confirm_policy` fail with `TypeError`.

- [ ] **Step 4: Replace the gate**

Replace `gate/decide.py` with this file:

```python
#!/usr/bin/env python3
"""Decision gate for RSI-Exam rollouts: a paired bootstrap interval on per-seed deltas.

Reads per-seed result files for a parent version and a candidate version, pairs the scores,
bootstraps a confidence interval on the mean delta, applies the rule, and appends one JSON line to
``<methods>/decisions.jsonl`` (contract: docs/decision-log-contract.md, schema id
``rsi-exam-decision-log/v1``). Two modes.

Gated mode (``--profile <task profile>``): the profile fixes direction, unit, the minimum effect,
level, resamples, the bootstrap seed, and the confirmation bounds; the flags for those, the result
locator overrides, and the held-out flags are refused. Screening (no ``--replicates``): the two
visible results under ``results/<parent>/`` and ``results/<version>/`` must carry runner receipts
that bind them to the parent and candidate snapshots, the profile's visible suite, and the
profile's evaluator; the snapshots' method-tree digests are recorded and ``main/`` must equal the
candidate's; ``below`` reverts; otherwise the confirmation is planned from the screening deltas,
and when the plan fits under the profile's cap a fresh suite is derived and written to
``results/<version>/replication/seeds.json`` and the line is ``provisional`` (an under-planned
confirmation reverts instead: it is never allowed to keep). Confirmation (``--replicates
<version>``): the open provisional line is re-verified from its evidence (digests, minimum effect,
plan, exclusion set, and the suite re-derived from the key), the two confirmation results and their
receipts are checked against the frozen digests, the suite, and the profile, and the decision
resolves to ``keep`` or ``revert``.

Replay mode (no ``--profile``; ``--confirm inconclusive`` is required so the weaker rule is stated
on the command line): the screening rule for shadow replay and fixtures. Locators may be
overridden, a held-out pair may be supplied, nothing is frozen, and no suite is derived. A log
written in one mode refuses lines from the other.

The whole read-check-write transaction runs under an exclusive lock on ``<methods>/decisions.lock``.
Evidence locators must live under ``results/`` with no symlink on the way; a suite file is created
exclusively and removed again if the line cannot be appended.

Outputs: exit 0 with the appended line on stdout; exit 2 on a missing or malformed input or a
contract violation (nothing appended); exit 3 when the log already carries an unresolved
provisional decision that this line would build on or duplicate (nothing appended).
``DECIDE_FIXED_TIMESTAMP`` overrides the timestamp for fixtures. Standard library only.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import random
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seeds import SEEDS_ALGORITHM, SeedsError, confirmation_size, derive_seeds, read_suite, write_suite
from task_profile import ProfileError, load_profile, resolve_min_effect
from treedigest import TreeDigestError, file_sha256, method_tree_sha256

SCHEMA = "rsi-exam-decision-log/v1"
LOG_NAME = "decisions.jsonl"
LOCK_NAME = "decisions.lock"
SUITE_NAME = "seeds.json"
EVIDENCE_ROOT = "results"
METHOD_NAME = "percentile_bootstrap"
ALGORITHM = "rsi-exam-gate/percentile-bootstrap/1"
STATISTIC = "mean_paired_delta"
RECEIPT_SCHEMA = "rsi-exam-gate-receipt/v1"
RECEIPT_KEYS = ("profile_sha256", "policy_method_tree_sha256", "suite_sha256", "max_moves", "result_sha256",
                "evaluator", "metric", "cpu_budget_per_game", "games", "python")
CONFIRM_POLICIES = ("always", "inconclusive")
LINE_KEYS = ("schema", "line", "timestamp", "version_id", "parent_id", "replicates", "statistic", "unit",
             "direction", "estimate", "interval", "method", "sample_size", "min_effect", "verdict", "disposition",
             "evidence", "evidence_digests", "holdout")
DEFAULT_DIRECTION = "higher"
DEFAULT_LEVEL = 0.9
DEFAULT_RESAMPLES = 5000
DEFAULT_SEED = 20260902
DEFAULT_MIN_EFFECT = 0.0
DEFAULT_UNIT = "game_score"
GATED_FIXED_FLAGS = ("confirm", "direction", "level", "resamples", "seed", "min_effect", "unit", "parent_result",
                     "candidate_result", "holdout_parent_result", "holdout_candidate_result")


class GateError(ValueError):
    """A gate input is missing, malformed, or inconsistent. Nothing is written (exit 2)."""


class StackedProvisional(GateError):
    """The log holds an unresolved provisional decision this line would stack on (exit 3)."""


INPUT_ERRORS = (GateError, ProfileError, SeedsError, TreeDigestError)


def sha256_of(path: Path) -> str:
    """Hex SHA-256 of a file's bytes."""
    return file_sha256(path)


def check_locator(locator: str) -> str:
    """A locator is a canonical relative POSIX path under ``results/``.

    Rules: no leading slash, no backslash, no percent escape, no drive prefix, no ``..`` or empty
    segment, no control characters, first segment ``results`` (never ``versions/`` or ``main/``: the
    sealed grader rejects non-Python files in the policy tree, so evidence stays out of every snapshot).
    """
    bad = (not locator or locator.startswith("/") or "\\" in locator or "%" in locator or ":" in locator
           or any(ord(c) < 32 for c in locator) or any(part in ("..", "", ".") for part in locator.split("/")))
    if bad:
        raise GateError(f"bad locator: {locator!r}")
    if locator.split("/", 1)[0] != EVIDENCE_ROOT:
        raise GateError(f"evidence locator must live under {EVIDENCE_ROOT}/: {locator!r}")
    return locator


def evidence_path(methods: Path, locator: str) -> Path:
    """The file a locator names, after checking that no component from ``results`` down is a symlink."""
    check_locator(locator)
    current = methods
    for part in locator.split("/"):
        current = current / part
        if current.is_symlink():
            raise GateError(f"evidence path goes through a symlink: {locator!r}")
    return current


def load_scores(path: Path) -> dict[int, float]:
    """Per-seed scores from a task self-check result file (``instances`` list with ``seed`` and ``score``)."""
    if not path.is_file():
        raise GateError(f"result file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        instances = data["instances"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GateError(f"malformed result file {path}: {exc}") from exc
    scores: dict[int, float] = {}
    for inst in instances:
        try:
            seed = int(inst["seed"])
            score = float(inst["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GateError(f"malformed instance in {path}: {exc}") from exc
        if seed in scores:
            raise GateError(f"duplicate seed {seed} in {path}")
        if not math.isfinite(score):
            raise GateError(f"non-finite score for seed {seed} in {path}")
        scores[seed] = score
    if not scores:
        raise GateError(f"result file has no instances: {path}")
    return scores


def paired_deltas(parent: Mapping[int, float], candidate: Mapping[int, float], direction: str = "higher") -> list[float]:
    """Candidate minus parent for every seed, oriented so a positive value favours the candidate."""
    if set(parent) != set(candidate):
        raise GateError("parent and candidate result files cover different seed sets")
    if direction not in ("higher", "lower"):
        raise GateError(f"direction must be 'higher' or 'lower', got {direction!r}")
    sign = 1.0 if direction == "higher" else -1.0
    return [sign * (candidate[s] - parent[s]) for s in sorted(parent)]


def bootstrap_interval(deltas: list[float], *, level: float, resamples: int, seed: int) -> tuple[float, float]:
    """Percentile bootstrap interval on the mean of ``deltas``. Deterministic for a given seed."""
    if not deltas:
        raise GateError("no deltas to bootstrap")
    if not 0.0 < level < 1.0:
        raise GateError("level must lie strictly between 0 and 1")
    if resamples < 1:
        raise GateError("resamples must be at least 1")
    rng = random.Random(seed)
    n = len(deltas)
    means = sorted(sum(rng.choice(deltas) for _ in range(n)) / n for _ in range(resamples))
    alpha = (1.0 - level) / 2.0
    low = means[int(alpha * resamples)]
    high = means[int((1.0 - alpha) * resamples) - 1]
    return low, high


def get_verdict(interval: tuple[float, float], min_effect: float) -> str:
    """``clears`` when the lower bound exceeds the minimum effect, ``below`` when the upper bound is under zero, else ``inconclusive``.

    ``inconclusive`` means neither condition holds: the interval establishes neither an effect above the
    minimum nor harm. It is not "straddles zero": an interval entirely positive but under ``min_effect``
    is ``inconclusive``.
    """
    if min_effect < 0.0:
        raise GateError("min_effect must be at or above zero")
    low, high = interval
    if low > min_effect:
        return "clears"
    if high < 0.0:
        return "below"
    return "inconclusive"


def get_disposition(verdict: str, holdout_verdict: str | None, confirm_policy: str = "inconclusive") -> str:
    """The action for a screening line.

    ``below`` reverts. Under ``inconclusive`` (the replay rule) a clear win keeps unless a held-out
    measurement fails to clear. Under ``always`` (the gated rule) every non-reverting candidate is
    provisional until a confirmation on fresh seeds resolves it.
    """
    if confirm_policy not in CONFIRM_POLICIES:
        raise GateError(f"confirm_policy must be 'always' or 'inconclusive', got {confirm_policy!r}")
    if verdict == "below":
        return "revert"
    if confirm_policy == "inconclusive" and verdict == "clears" and holdout_verdict in (None, "clears"):
        return "keep"
    return "provisional"


def read_log(path: Path) -> list[dict[str, Any]]:
    """Existing decision-log lines, validated as objects of this schema with consecutive line numbers and the contract's keys."""
    if not path.exists():
        return []
    lines: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            raise GateError(f"{path}:{number}: blank line in decision log")
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GateError(f"{path}:{number}: not JSON: {exc}") from exc
        if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
            raise GateError(f"{path}:{number}: not a {SCHEMA} line")
        if obj.get("line") != number:
            raise GateError(f"{path}:{number}: line field {obj.get('line')!r} does not match position")
        missing = [key for key in LINE_KEYS if key not in obj]
        if missing:
            raise GateError(f"{path}:{number}: line lacks {', '.join(missing)}")
        lines.append(obj)
    return lines


def get_open_provisional(log_lines: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The unresolved provisional line, if any. More than one open at once is a corrupt log."""
    open_by_version: dict[str, dict[str, Any]] = {}
    for line in log_lines:
        vid = line["version_id"]
        if line.get("replicates"):
            if line["replicates"] not in open_by_version:
                raise GateError(f"line {line['line']} replicates {line['replicates']} but no provisional decision is open")
            del open_by_version[line["replicates"]]
        elif line.get("disposition") == "provisional":
            if open_by_version:
                raise GateError(f"line {line['line']} opens a second provisional decision")
            open_by_version[vid] = line
    if len(open_by_version) > 1:
        raise GateError("more than one provisional decision is open")
    return next(iter(open_by_version.values()), None)


def check_stacked_provisional(log_lines: list[dict[str, Any]], parent_id: str) -> None:
    """Refuse to build on a parent whose decision is provisional and unreplicated."""
    open_line = get_open_provisional(log_lines)
    if open_line is not None and open_line["version_id"] == parent_id:
        raise StackedProvisional(
            f"parent {parent_id} carries an unreplicated provisional decision (line {open_line['line']}); "
            "replicate it before building on it"
        )


def measure(methods: Path, parent_locator: str, candidate_locator: str, *, direction: str, level: float,
            resamples: int, seed: int, min_effect: float) -> dict[str, Any]:
    """Interval, verdict, and evidence references for one parent/candidate pair."""
    parent_path = evidence_path(methods, parent_locator)
    candidate_path = evidence_path(methods, candidate_locator)
    deltas = paired_deltas(load_scores(parent_path), load_scores(candidate_path), direction)
    low, high = bootstrap_interval(deltas, level=level, resamples=resamples, seed=seed)
    estimate = sum(deltas) / len(deltas)
    evidence = [
        {"role": "parent", "locator": parent_locator, "sha256": file_sha256(parent_path)},
        {"role": "candidate", "locator": candidate_locator, "sha256": file_sha256(candidate_path)},
    ]
    return {
        "estimate": estimate,
        "interval": {"lower": low, "upper": high, "level": level},
        "sample_size": len(deltas),
        "verdict": get_verdict((low, high), min_effect),
        "evidence": evidence,
        "evidence_digests": {e["role"]: "sha256:" + e["sha256"] for e in evidence},
    }


def build_line(*, line_number: int, version_id: str, parent_id: str, replicates: str | None,
               main: dict[str, Any], holdout: dict[str, Any] | None, disposition: str, unit: str, direction: str,
               resamples: int, seed: int, min_effect: float, confirm_policy: str, profile_sha256: str | None,
               look_index: int | None, parent_digest: str | None, candidate_digest: str | None,
               sizing: dict[str, Any] | None, suite: dict[str, Any] | None) -> dict[str, Any]:
    """Assemble one decision-log line from a measurement (and an optional held-out measurement)."""
    if replicates is not None and replicates != version_id:
        raise GateError("a replication line must carry replicates equal to its own version_id")
    if disposition not in ("keep", "revert", "provisional"):
        raise GateError(f"unknown disposition {disposition!r}")
    return {
        "schema": SCHEMA,
        "line": line_number,
        "timestamp": os.environ.get("DECIDE_FIXED_TIMESTAMP") or datetime.now(UTC).isoformat(),
        "version_id": version_id,
        "parent_id": parent_id,
        "replicates": replicates,
        "statistic": STATISTIC,
        "unit": unit,
        "direction": direction,
        "estimate": main["estimate"],
        "interval": main["interval"],
        "method": {"name": METHOD_NAME, "algorithm": ALGORITHM, "resamples": resamples, "seed": seed},
        "sample_size": main["sample_size"],
        "min_effect": min_effect,
        "verdict": main["verdict"],
        "disposition": disposition,
        "evidence": main["evidence"],
        "evidence_digests": main["evidence_digests"],
        "holdout": (
            {k: holdout[k] for k in ("estimate", "interval", "sample_size", "verdict", "evidence", "evidence_digests")}
            if holdout else None
        ),
        "confirm_policy": confirm_policy,
        "profile_sha256": profile_sha256,
        "look_index": look_index,
        "parent_method_tree_sha256": parent_digest,
        "candidate_method_tree_sha256": candidate_digest,
        "sizing": sizing,
        "suite": suite,
    }


def load_receipt(path: Path) -> dict[str, Any]:
    """A runner receipt (schema rsi-exam-gate-receipt/v1) with every key the gate compares."""
    if not path.is_file():
        raise GateError(f"receipt not found: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GateError(f"malformed receipt {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != RECEIPT_SCHEMA or any(key not in doc for key in RECEIPT_KEYS):
        raise GateError(f"receipt {path} is not a complete {RECEIPT_SCHEMA} document")
    return doc


def python_minor(version: Any) -> str:
    return ".".join(str(version).split(".")[:2])


def check_receipt(methods: Path, result_locator: str, *, role: str, profile: Mapping[str, Any], profile_sha: str,
                  suite_sha: str, policy_digest: str, games: int) -> tuple[dict[str, Any], dict[str, str]]:
    """The receipt next to a result; every bound field must match. Returns the receipt and its evidence entry."""
    receipt_locator = result_locator[: -len(".json")] + ".receipt.json"
    receipt_path = evidence_path(methods, receipt_locator)
    receipt = load_receipt(receipt_path)
    expected: dict[str, Any] = {
        "profile_sha256": profile_sha,
        "suite_sha256": suite_sha,
        "result_sha256": file_sha256(evidence_path(methods, result_locator)),
        "policy_method_tree_sha256": policy_digest,
        "evaluator": profile["evaluator"],
        "metric": profile["metric"],
        "cpu_budget_per_game": profile["confirmation"]["cpu_seconds_per_game"],
        "max_moves": profile["confirmation"]["max_moves"],
        "games": games,
    }
    for key, want in expected.items():
        if receipt.get(key) != want:
            raise GateError(f"{role} receipt {key} does not match: {receipt.get(key)!r} != {want!r}")
    return receipt, {"role": f"receipt-{role}", "locator": receipt_locator, "sha256": file_sha256(receipt_path)}


def check_python_parity(receipts: list[dict[str, Any]]) -> None:
    versions = {python_minor(r["python"]) for r in receipts}
    if len(versions) != 1:
        raise GateError(f"receipts were produced under different Python versions: {sorted(versions)}")


def suite_seeds_in_log(methods: Path, log_lines: list[dict[str, Any]]) -> set[int]:
    """Every seed of every suite an earlier line derived; each suite file is re-checked against its digest."""
    seen: set[int] = set()
    checked: set[str] = set()
    for line in log_lines:
        suite = line.get("suite")
        if not isinstance(suite, dict) or suite["locator"] in checked:
            continue
        path = evidence_path(methods, suite["locator"])
        if not path.is_file() or file_sha256(path) != suite["sha256"]:
            raise GateError(f"suite referenced by line {line['line']} is missing or altered: {suite['locator']}")
        chosen, _ = read_suite(path)
        seen.update(chosen)
        checked.add(suite["locator"])
    return seen


@contextmanager
def log_lock(methods: Path) -> Iterator[None]:
    """Exclusive lock for the read-check-write transaction on one decision log."""
    methods.mkdir(parents=True, exist_ok=True)
    fd = os.open(methods / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def append_line(log_path: Path, line: dict[str, Any]) -> None:
    """One line per ``os.write`` on an ``O_APPEND`` descriptor, then fsync."""
    payload = (json.dumps(line, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        if os.write(fd, payload) != len(payload):
            raise OSError("short write to the decision log")
        os.fsync(fd)
    finally:
        os.close(fd)


def build_replay_line(args: argparse.Namespace, methods: Path, log_lines: list[dict[str, Any]],
                      open_line: dict[str, Any] | None) -> dict[str, Any]:
    """Replay mode: the screening rule with explicit locators; nothing frozen, no suite."""
    if args.confirm is None:
        raise GateError("replay mode requires --confirm inconclusive; a gated run passes --profile instead")
    if args.confirm != "inconclusive":
        raise GateError("--confirm always requires --profile: freezing and fresh suites need the task profile")
    if any(prior.get("profile_sha256") is not None for prior in log_lines):
        raise GateError("this log was written in gated mode; pass the same --profile")
    direction: str = args.direction if args.direction is not None else DEFAULT_DIRECTION
    level: float = args.level if args.level is not None else DEFAULT_LEVEL
    resamples: int = args.resamples if args.resamples is not None else DEFAULT_RESAMPLES
    seed: int = args.seed if args.seed is not None else DEFAULT_SEED
    min_effect: float = args.min_effect if args.min_effect is not None else DEFAULT_MIN_EFFECT
    unit: str = args.unit if args.unit is not None else DEFAULT_UNIT
    if not math.isfinite(min_effect) or min_effect < 0.0:
        raise GateError("min_effect must be a finite number at or above zero")
    if args.replicates is not None:
        parent_locator = args.parent_result or f"results/{args.version}/replication/parent_result.json"
        candidate_locator = args.candidate_result or f"results/{args.version}/replication/candidate_result.json"
        if open_line is None or open_line["version_id"] != args.replicates:
            raise GateError(f"no open provisional decision for {args.replicates} to replicate")
        if open_line["parent_id"] != args.parent:
            raise GateError(f"replication parent {args.parent} differs from the provisional line's parent {open_line['parent_id']}")
    else:
        parent_locator = args.parent_result or f"results/{args.parent}/visible_result.json"
        candidate_locator = args.candidate_result or f"results/{args.version}/visible_result.json"
        check_stacked_provisional(log_lines, args.parent)
    main_measure = measure(methods, parent_locator, candidate_locator, direction=direction, level=level,
                           resamples=resamples, seed=seed, min_effect=min_effect)
    holdout = None
    if args.holdout_parent_result or args.holdout_candidate_result:
        if not (args.holdout_parent_result and args.holdout_candidate_result):
            raise GateError("both held-out result files are required when one is given")
        holdout = measure(methods, args.holdout_parent_result, args.holdout_candidate_result, direction=direction,
                          level=level, resamples=resamples, seed=seed, min_effect=min_effect)
        holdout["evidence"] = [dict(e, role="holdout-" + e["role"]) for e in holdout["evidence"]]
        holdout["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in holdout["evidence"]}
    holdout_verdict = holdout["verdict"] if holdout else None
    if args.replicates is not None:
        disposition = "keep" if main_measure["verdict"] == "clears" and holdout_verdict in (None, "clears") else "revert"
    else:
        disposition = get_disposition(main_measure["verdict"], holdout_verdict, "inconclusive")
        if disposition == "provisional" and open_line is not None:
            raise StackedProvisional(
                f"{open_line['version_id']} already holds the one open provisional decision (line {open_line['line']}); "
                "replicate it before opening another"
            )
    return build_line(line_number=len(log_lines) + 1, version_id=args.version, parent_id=args.parent,
                      replicates=args.replicates, main=main_measure, holdout=holdout, disposition=disposition,
                      unit=unit, direction=direction, resamples=resamples, seed=seed, min_effect=min_effect,
                      confirm_policy="inconclusive", profile_sha256=None, look_index=None, parent_digest=None,
                      candidate_digest=None, sizing=None, suite=None)


def _gated_screening_inputs(methods: Path, parent_id: str, version_id: str, profile: Mapping[str, Any],
                            profile_sha: str, parent_digest: str, candidate_digest: str) -> dict[str, Any]:
    """Load and bind the two visible results of a screening; shared by screening and its re-verification."""
    parent_locator = f"results/{parent_id}/visible_result.json"
    candidate_locator = f"results/{version_id}/visible_result.json"
    parent_scores = load_scores(evidence_path(methods, parent_locator))
    candidate_scores = load_scores(evidence_path(methods, candidate_locator))
    if set(parent_scores) != set(candidate_scores):
        raise GateError("parent and candidate visible results cover different seed sets")
    games = len(parent_scores)
    receipts: list[dict[str, Any]] = []
    entries: list[dict[str, str]] = []
    for role, locator, digest in (("parent", parent_locator, parent_digest), ("candidate", candidate_locator, candidate_digest)):
        receipt, entry = check_receipt(methods, locator, role=role, profile=profile, profile_sha=profile_sha,
                                       suite_sha=profile["visible_suite_sha256"], policy_digest=digest, games=games)
        receipts.append(receipt)
        entries.append(entry)
    check_python_parity(receipts)
    min_effect = resolve_min_effect(profile, parent_scores)
    main_measure = measure(methods, parent_locator, candidate_locator, direction=profile["direction"],
                           level=float(profile["level"]), resamples=int(profile["resamples"]),
                           seed=int(profile["bootstrap_seed"]), min_effect=min_effect)
    main_measure["evidence"] = list(main_measure["evidence"]) + entries
    main_measure["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in main_measure["evidence"]}
    return {"measure": main_measure, "parent_scores": parent_scores, "candidate_scores": candidate_scores,
            "min_effect": min_effect, "receipts": receipts}


def build_gated_line(args: argparse.Namespace, methods: Path, log_lines: list[dict[str, Any]],
                     open_line: dict[str, Any] | None) -> tuple[dict[str, Any], Path | None]:
    """Gated mode. Returns the line and the suite file this call created (to remove if the append fails)."""
    for name in GATED_FIXED_FLAGS:
        if getattr(args, name) is not None:
            raise GateError(f"--{name.replace('_', '-')} is fixed by the profile and may not be passed in gated mode")
    profile, profile_sha = load_profile(args.profile)
    for prior in log_lines:
        if prior.get("profile_sha256") != profile_sha:
            raise GateError(f"line {prior['line']} was written under a different profile or in replay mode; one profile per log")
    conf = profile["confirmation"]
    direction: str = profile["direction"]
    level = float(profile["level"])
    resamples = int(profile["resamples"])
    seed = int(profile["bootstrap_seed"])
    parent_digest = method_tree_sha256(methods / "versions" / args.parent)
    candidate_digest = method_tree_sha256(methods / "versions" / args.version)
    if method_tree_sha256(methods / "main") != candidate_digest:
        raise GateError(f"main/ does not match versions/{args.version}: snapshot main/ before running the gate, "
                        "and do not edit it between screening and confirmation")
    line_number = len(log_lines) + 1

    if args.replicates is None:
        check_stacked_provisional(log_lines, args.parent)
        inputs = _gated_screening_inputs(methods, args.parent, args.version, profile, profile_sha, parent_digest, candidate_digest)
        main_measure, min_effect = inputs["measure"], inputs["min_effect"]
        disposition = get_disposition(main_measure["verdict"], None, "always")
        look_index: int | None = None
        plan: dict[str, Any] | None = None
        derived: dict[str, Any] | None = None
        created: Path | None = None
        if disposition == "provisional":
            if open_line is not None:
                raise StackedProvisional(
                    f"{open_line['version_id']} already holds the one open provisional decision (line {open_line['line']}); "
                    "replicate it before opening another"
                )
            deltas = paired_deltas(inputs["parent_scores"], inputs["candidate_scores"], direction)
            plan = confirmation_size(deltas, min_effect=min_effect, level=level, floor=int(conf["floor"]),
                                     cap=int(conf["max_seeds"]))
            if plan["exploratory"]:
                disposition = "revert"
            else:
                look_index = 1 + sum(1 for prior in log_lines if prior.get("replicates"))
                exclude = set(inputs["parent_scores"]) | suite_seeds_in_log(methods, log_lines)
                chosen = derive_seeds(key_hex=profile["replication_key"], rollout_id=profile["rollout_id"],
                                      candidate_digest=candidate_digest, look_index=look_index,
                                      size=int(plan["size"]), exclude=exclude)
                locator = f"results/{args.version}/replication/{SUITE_NAME}"
                created = evidence_path(methods, locator)
                suite_sha = write_suite(created, chosen, max_moves=int(conf["max_moves"]))
                derived = {"locator": locator, "sha256": suite_sha,
                           "derivation": {"algorithm": SEEDS_ALGORITHM, "rollout_id": profile["rollout_id"],
                                          "candidate_method_tree_sha256": candidate_digest, "look_index": look_index,
                                          "size": int(plan["size"]), "max_moves": int(conf["max_moves"])}}
        line = build_line(line_number=line_number, version_id=args.version, parent_id=args.parent, replicates=None,
                          main=main_measure, holdout=None, disposition=disposition, unit=profile["unit"],
                          direction=direction, resamples=resamples, seed=seed, min_effect=min_effect,
                          confirm_policy="always", profile_sha256=profile_sha, look_index=look_index,
                          parent_digest=parent_digest, candidate_digest=candidate_digest, sizing=plan, suite=derived)
        return line, created

    if args.replicates != args.version:
        raise GateError("a replication line must carry replicates equal to its own version_id")
    if open_line is None or open_line["version_id"] != args.version:
        raise GateError(f"no open provisional decision for {args.version} to replicate")
    if open_line["parent_id"] != args.parent:
        raise GateError(f"replication parent {args.parent} differs from the provisional line's parent {open_line['parent_id']}")
    open_suite = open_line.get("suite")
    open_sizing = open_line.get("sizing")
    if not isinstance(open_suite, dict) or not isinstance(open_sizing, dict) or open_line.get("look_index") is None:
        raise GateError("the open provisional line carries no confirmation plan; gated confirmation needs one")
    suite: dict[str, Any] = open_suite
    sizing: dict[str, Any] = open_sizing
    if open_line.get("parent_method_tree_sha256") != parent_digest:
        raise GateError(f"versions/{args.parent} changed after the screening that froze it")
    if open_line.get("candidate_method_tree_sha256") != candidate_digest:
        raise GateError(f"versions/{args.version} changed after it was frozen")
    # Re-verify the provisional line from its evidence rather than trusting it.
    for entry in open_line["evidence"]:
        if file_sha256(evidence_path(methods, entry["locator"])) != entry["sha256"]:
            raise GateError(f"screening evidence {entry['locator']} changed since the provisional line was written")
    inputs = _gated_screening_inputs(methods, args.parent, args.version, profile, profile_sha, parent_digest, candidate_digest)
    if not math.isclose(inputs["min_effect"], float(open_line["min_effect"]), rel_tol=0.0, abs_tol=1e-9):
        raise GateError("the provisional line's min_effect does not follow from the profile and the parent's visible result")
    deltas = paired_deltas(inputs["parent_scores"], inputs["candidate_scores"], direction)
    expected_sizing = confirmation_size(deltas, min_effect=float(open_line["min_effect"]), level=level,
                                        floor=int(conf["floor"]), cap=int(conf["max_seeds"]))
    if expected_sizing != sizing or sizing["exploratory"]:
        raise GateError("the provisional line's confirmation plan does not follow from its screening deltas")
    earlier = log_lines[: int(open_line["line"]) - 1]
    exclude = set(inputs["parent_scores"]) | suite_seeds_in_log(methods, earlier)
    expected_seeds = derive_seeds(key_hex=profile["replication_key"], rollout_id=profile["rollout_id"],
                                  candidate_digest=candidate_digest, look_index=int(open_line["look_index"]),
                                  size=int(sizing["size"]), exclude=exclude)
    suite_path = evidence_path(methods, suite["locator"])
    if not suite_path.is_file() or file_sha256(suite_path) != suite["sha256"]:
        raise GateError(f"confirmation suite missing or altered: {suite['locator']}")
    suite_seeds, suite_max_moves = read_suite(suite_path)
    if suite_seeds != expected_seeds or suite_max_moves != int(conf["max_moves"]):
        raise GateError("the confirmation suite does not re-derive from the key, the frozen candidate, and the look")
    derivation = suite.get("derivation")
    if derivation != {"algorithm": SEEDS_ALGORITHM, "rollout_id": profile["rollout_id"],
                      "candidate_method_tree_sha256": candidate_digest, "look_index": int(open_line["look_index"]),
                      "size": int(sizing["size"]), "max_moves": int(conf["max_moves"])}:
        raise GateError("the provisional line's suite derivation record does not match")
    min_effect = float(open_line["min_effect"])
    base = f"results/{args.version}/replication/"
    parent_locator, candidate_locator = base + "parent_result.json", base + "candidate_result.json"
    main_measure = measure(methods, parent_locator, candidate_locator, direction=direction, level=level,
                           resamples=resamples, seed=seed, min_effect=min_effect)
    receipts: list[dict[str, Any]] = list(inputs["receipts"])
    entries: list[dict[str, str]] = []
    for role, locator, digest in (("parent", parent_locator, parent_digest), ("candidate", candidate_locator, candidate_digest)):
        scores = load_scores(evidence_path(methods, locator))
        if set(scores) != set(suite_seeds):
            raise GateError(f"{role} confirmation result does not cover exactly the confirmation suite")
        receipt, entry = check_receipt(methods, locator, role=role, profile=profile, profile_sha=profile_sha,
                                       suite_sha=suite["sha256"], policy_digest=digest, games=len(suite_seeds))
        receipts.append(receipt)
        entries.append(entry)
    check_python_parity(receipts)
    main_measure["evidence"] = list(main_measure["evidence"]) + entries
    main_measure["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in main_measure["evidence"]}
    disposition = "keep" if main_measure["verdict"] == "clears" else "revert"
    line = build_line(line_number=line_number, version_id=args.version, parent_id=args.parent, replicates=args.version,
                      main=main_measure, holdout=None, disposition=disposition, unit=profile["unit"],
                      direction=direction, resamples=resamples, seed=seed, min_effect=min_effect,
                      confirm_policy="always", profile_sha256=profile_sha, look_index=int(open_line["look_index"]),
                      parent_digest=parent_digest, candidate_digest=candidate_digest, sizing=sizing, suite=suite)
    return line, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--methods", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--replicates", default=None)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--confirm", choices=CONFIRM_POLICIES, default=None)
    parser.add_argument("--parent-result", default=None)
    parser.add_argument("--candidate-result", default=None)
    parser.add_argument("--holdout-parent-result", default=None)
    parser.add_argument("--holdout-candidate-result", default=None)
    parser.add_argument("--direction", choices=("higher", "lower"), default=None)
    parser.add_argument("--level", type=float, default=None)
    parser.add_argument("--resamples", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--min-effect", type=float, default=None)
    parser.add_argument("--unit", default=None)
    args = parser.parse_args(argv)

    methods: Path = args.methods
    log_path = methods / LOG_NAME
    created: Path | None = None
    try:
        with log_lock(methods):
            log_lines = read_log(log_path)
            open_line = get_open_provisional(log_lines)
            if args.profile is not None:
                line, created = build_gated_line(args, methods, log_lines, open_line)
            else:
                line = build_replay_line(args, methods, log_lines, open_line)
            try:
                append_line(log_path, line)
            except OSError:
                if created is not None and created.exists():
                    created.unlink()
                raise
    except StackedProvisional as exc:
        print(f"gate refused: {exc}", file=sys.stderr)
        return 3
    except INPUT_ERRORS as exc:
        print(f"gate refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(line, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the gate tests and the whole suite**

Run: `python3 -m unittest tests.test_decide -v`
Expected: `Ran 49 tests`, `OK`. If a test fails, read the failure and fix `gate/decide.py`; do not weaken an assertion.

Run: `python3 -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: `Ran 137 tests`, `OK`. The converter's own tests still pass here: they build their lines by hand and the converter is not touched until Task 7.

- [ ] **Step 6: Type-check and commit**

Run: `pyright gate/decide.py tests/test_decide.py`
Expected: `0 errors`.

```bash
git add gate/decide.py tests/test_decide.py
git diff --exit-code
git commit -m "feat(gate): gated mode with a task profile, freezing, and fresh confirmation suites

decide.py now runs in two modes. Gated mode (--profile) takes direction,
unit, minimum effect, level, resamples, seed, and the confirmation bounds
from the task profile and refuses the flags that would let the agent choose
them. A screening requires runner receipts binding both visible results to
the two snapshots, the profile's visible suite, the evaluator, the metric,
the budget, the game length, and the game count; it records both snapshot
digests and requires main/ to equal the candidate's. A screening that is not
below zero plans its confirmation from the screening deltas: a plan the
profile's cap cannot cover reverts with the plan recorded, and a plan that
fits derives a fresh suite under rsi-exam-gate/hmac-seeds/1, writes it under
results/<version>/replication/, and leaves the line provisional. Confirmation
re-verifies the provisional line from its evidence rather than trusting it
(digests unchanged, minimum effect re-resolved, plan recomputed, exclusion
set rebuilt, suite re-derived from the key) and requires both confirmation
results to cover exactly the suite.

Replay mode requires --confirm inconclusive so the weaker rule is stated
rather than defaulted, and one log never mixes the two modes. The whole
read-check-write transaction holds an exclusive lock on decisions.lock, and a
suite written for a line that cannot be appended is removed again.

Tests: replay flags and the disposition table, gated screening (freeze, plan,
suite, refusals of the fixed flags, receipt field matrix, Python parity,
main/ mismatch, missing snapshots, mixed modes, second provisional), and
gated confirmation (keep, revert, tampered suite, rewritten suite, edited
candidate, edited parent, edited screening evidence, wrong parent)."
```

---

### Task 7: The converter re-checks the gated rules (`gate/trace_from_decisions.py`)

**Files:**
- Replace: `gate/trace_from_decisions.py` (the whole file)
- Replace: `tests/test_trace_from_decisions.py` (the whole file)

**Interfaces:**
- Consumes: decision-log lines with or without the gated keys. A line without `confirm_policy` is read as a replay-mode line, so logs written before this milestone convert unchanged.
- Produces: the `confidence` block gains, after `holdout`, the keys `confirm_policy`, `profile_sha256`, `look_index`, `parent_method_tree_sha256`, `candidate_method_tree_sha256`, `sizing`, `suite`. ProofPress ignores them; TRACE preserves them as extras.
- **Rules re-checked on conversion.** A gated line carries 64-hex digests for the profile and both snapshots, a well-formed plan and suite whose derivation matches the line, and receipt evidence for both results. A replay-mode line carries `null` in all six of the other gated keys. A gated screening carries no holdout; `below` plans nothing; an exploratory plan is a revert with no suite and no look index; a plan that fits is provisional and must carry both. A gated confirmation repeats its provisional line's profile digest, look index, both snapshot digests, plan, suite, minimum effect, and parent, and carries no holdout. Every suite must have been derived for the rollout being converted. A violation refuses the whole conversion with exit 2.
- The revert note distinguishes the two reverts: an interval entirely below zero, or a confirmation the profile's cap cannot cover.

- [ ] **Step 1: Replace the converter's tests**

Replace `tests/test_trace_from_decisions.py` with this file:

```python
"""Tests for gate/trace_from_decisions.py: decision log to TRACE session document."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import seeds as seedsmod  # noqa: E402
import trace_from_decisions as conv  # noqa: E402

D = "a" * 64
PROFILE_SHA = "9" * 64
PARENT_DIGEST = "6" * 64
CANDIDATE_DIGEST = "8" * 64
INTERVALS = {"inconclusive": (-30.0, 583.8, 260.0), "clears": (467.5, 575.0, 518.75),
             "below": (-382.5, -258.8, -318.75)}
UNSET: Any = object()
SIZING = {"rule": seedsmod.SIZING_RULE, "size": 8, "planned": 8, "floor": 4, "cap": 8, "exploratory": False,
          "screening_sd": 565.4833583505606, "z": 1.6448536269514715}
SIZING_EXPLORATORY = dict(SIZING, planned=327, exploratory=True)
SUITE = {"locator": "results/v3/replication/seeds.json", "sha256": "7" * 64,
         "derivation": {"algorithm": conv.SEEDS_ALGORITHM, "rollout_id": "game2048__abc123",
                        "candidate_method_tree_sha256": CANDIDATE_DIGEST, "look_index": 1, "size": 8,
                        "max_moves": 300}}


def line(n: int, version: str, parent: str, verdict: str, disposition: str, replicates: str | None = None,
         holdout_verdict: str | None = None, confirm_policy: str | None = None, suite: dict | None = None,
         look_index: int | None = None, sizing: dict | None = None, min_effect: float = 0.0,
         profile_sha256: Any = UNSET, parent_digest: Any = UNSET, candidate_digest: Any = UNSET,
         receipts: Any = UNSET) -> dict[str, Any]:
    """One decision-log line.

    Passing ``confirm_policy`` adds the seven gated keys; ``confirm_policy="always"`` also defaults the
    three digests to the constants above and adds the two receipt evidence entries a gated line carries.
    """
    gated = confirm_policy == "always"
    low, high, est = INTERVALS[verdict]
    evidence = [{"role": "parent", "locator": f"results/{parent}/visible_result.json", "sha256": D},
                {"role": "candidate", "locator": f"results/{version}/visible_result.json", "sha256": D}]
    if receipts is UNSET:
        receipts = gated
    if receipts:
        evidence += [{"role": "receipt-parent", "locator": f"results/{parent}/visible_result.receipt.json",
                      "sha256": "c" * 64},
                     {"role": "receipt-candidate", "locator": f"results/{version}/visible_result.receipt.json",
                      "sha256": "d" * 64}]
    holdout = None
    if holdout_verdict:
        hl, hh, he = INTERVALS[holdout_verdict]
        hev = [{"role": "holdout-parent", "locator": f"results/{version}/holdout/parent_result.json", "sha256": "e" * 64},
               {"role": "holdout-candidate", "locator": f"results/{version}/holdout/candidate_result.json", "sha256": "f" * 64}]
        holdout = {"estimate": he, "interval": {"lower": hl, "upper": hh, "level": 0.9}, "sample_size": 8,
                   "verdict": holdout_verdict, "evidence": hev,
                   "evidence_digests": {e["role"]: "sha256:" + e["sha256"] for e in hev}}
    doc: dict[str, Any] = {
        "schema": "rsi-exam-decision-log/v1", "line": n, "timestamp": f"2026-09-03T18:0{n}:00+00:00",
        "version_id": version, "parent_id": parent, "replicates": replicates,
        "statistic": "mean_paired_delta", "unit": "game_score", "direction": "higher", "estimate": est,
        "interval": {"lower": low, "upper": high, "level": 0.9},
        "method": {"name": "percentile_bootstrap", "algorithm": "rsi-exam-gate/percentile-bootstrap/1",
                   "resamples": 5000, "seed": 20260902},
        "sample_size": 8, "min_effect": min_effect, "verdict": verdict, "disposition": disposition,
        "evidence": evidence, "evidence_digests": {e["role"]: "sha256:" + e["sha256"] for e in evidence},
        "holdout": holdout,
    }
    if confirm_policy is not None:
        doc["confirm_policy"] = confirm_policy
        doc["profile_sha256"] = (PROFILE_SHA if gated else None) if profile_sha256 is UNSET else profile_sha256
        doc["look_index"] = look_index
        doc["parent_method_tree_sha256"] = (PARENT_DIGEST if gated else None) if parent_digest is UNSET else parent_digest
        doc["candidate_method_tree_sha256"] = ((CANDIDATE_DIGEST if gated else None)
                                               if candidate_digest is UNSET else candidate_digest)
        doc["sizing"] = sizing
        doc["suite"] = suite
    return doc


def provisional(n: int = 1, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {"confirm_policy": "always", "sizing": SIZING, "suite": SUITE, "look_index": 1}
    fields.update(overrides)
    return line(n, "v3", "v1", "inconclusive", "provisional", **fields)


def replication(n: int = 2, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {"replicates": "v3", "confirm_policy": "always", "sizing": SIZING, "suite": SUITE,
                              "look_index": 1}
    fields.update(overrides)
    return line(n, "v3", "v1", "clears", "keep", **fields)


class TestCanonicalKey(unittest.TestCase):
    def test_spec_algorithm(self) -> None:
        self.assertEqual(conv.canonical_project_key("  RSI Exam/Rollouts_2026 "), "rsi-exam-rollouts-2026")
        self.assertEqual(conv.canonical_project_key("trace-mcp"), "trace-mcp")
        with self.assertRaises(ValueError):
            conv.canonical_project_key("---")
        with self.assertRaises(ValueError):
            conv.canonical_project_key("auto")


class TestMapping(unittest.TestCase):
    def build(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        return conv.build_session(lines, project="RSI-Exam rollouts", rollout_id="game2048__abc123",
                                  task="game2048_policy_search", harness="claude-code", model="claude-opus-5",
                                  decision_log_sha256=D)

    def test_a_gated_provisional_and_its_replication_convert(self) -> None:
        doc = self.build([provisional(), replication()])
        events = doc["events"]
        self.assertEqual([e["decision"]["disposition"] for e in events], ["accepted", "accepted"])
        self.assertEqual(events[0]["decision"]["revision_note"], "Resolved by replication evt_002.")
        conf = events[0]["decision"]["confidence"]
        self.assertEqual(list(conf)[-7:], list(conv.GATED_KEYS))
        self.assertEqual(conf["confirm_policy"], "always")
        self.assertEqual(conf["profile_sha256"], PROFILE_SHA)
        self.assertEqual(conf["look_index"], 1)
        self.assertEqual(conf["parent_method_tree_sha256"], PARENT_DIGEST)
        self.assertEqual(conf["candidate_method_tree_sha256"], CANDIDATE_DIGEST)
        self.assertEqual(conf["sizing"], SIZING)
        self.assertEqual(conf["suite"], SUITE)
        self.assertEqual([e["role"] for e in conf["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])

    def test_an_under_planned_confirmation_reverts_with_its_own_note(self) -> None:
        doc = self.build([line(1, "v3", "v1", "inconclusive", "revert", confirm_policy="always",
                               sizing=SIZING_EXPLORATORY)])
        decision = doc["events"][0]["decision"]
        self.assertEqual(decision["disposition"], "rejected")
        self.assertEqual(decision["revision_note"],
                         "Confirmation would need more games than the profile allows; reverted without confirming.")
        self.assertEqual(decision["confidence"]["sizing"], SIZING_EXPLORATORY)
        self.assertIsNone(decision["confidence"]["suite"])
        self.assertIsNone(decision["confidence"]["look_index"])

    def test_a_gated_below_line_reverts_on_the_interval(self) -> None:
        doc = self.build([line(1, "v3", "v1", "below", "revert", confirm_policy="always")])
        self.assertEqual(doc["events"][0]["decision"]["revision_note"], "Interval entirely below zero.")

    def test_replay_lines_without_the_gated_keys_still_convert(self) -> None:
        doc = self.build([line(1, "v1", "v0", "clears", "keep")])
        conf = doc["events"][0]["decision"]["confidence"]
        for key in conv.GATED_KEYS:
            self.assertIn(key, conf)
            self.assertIsNone(conf[key])

    def test_gated_rule_violations_are_refused(self) -> None:
        bad: list[tuple[str, list[dict[str, Any]]]] = [
            ("empty confirm_policy", [provisional(confirm_policy="")]),
            ("unknown confirm_policy", [provisional(confirm_policy="sometimes")]),
            ("no receipt evidence", [provisional(receipts=False)]),
            ("provisional without a suite", [provisional(suite=None)]),
            ("provisional without a look index", [provisional(look_index=None, suite=None)]),
            ("screening without a plan", [provisional(sizing=None, suite=None)]),
            ("exploratory plan carrying a suite",
             [line(1, "v3", "v1", "inconclusive", "revert", confirm_policy="always", sizing=SIZING_EXPLORATORY,
                   suite=SUITE, look_index=1)]),
            ("below line carrying a plan",
             [line(1, "v3", "v1", "below", "revert", confirm_policy="always", sizing=SIZING)]),
            ("suite locator inside the policy tree",
             [provisional(suite=dict(SUITE, locator="versions/v3/seeds.json"))]),
            ("suite size disagrees with the plan",
             [provisional(suite=dict(SUITE, derivation=dict(SUITE["derivation"], size=4)))]),
            ("short profile digest", [provisional(profile_sha256="short")]),
            ("short parent digest", [provisional(parent_digest="short")]),
            ("look index below one", [provisional(look_index=0, suite=None)]),
            ("replication under another profile",
             [provisional(), replication(profile_sha256="1" * 64)]),
            ("replication under another look",
             [provisional(), replication(look_index=2, suite=dict(SUITE, derivation=dict(SUITE["derivation"],
                                                                                         look_index=2)))]),
            ("replication under another minimum effect", [provisional(), replication(min_effect=100.0)]),
            ("replication under another suite", [provisional(), replication(suite=dict(SUITE, sha256="0" * 64))]),
            ("replay line carrying a suite",
             [line(1, "v3", "v1", "inconclusive", "provisional", confirm_policy="inconclusive", suite=SUITE)]),
            ("replay line that should have kept",
             [line(1, "v1", "v0", "clears", "provisional", confirm_policy="inconclusive")]),
        ]
        for name, lines in bad:
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    self.build(lines)

    def test_keep_revert_provisional_dispositions(self) -> None:
        doc = self.build([line(1, "v1", "v0", "clears", "keep"), line(2, "v2", "v1", "below", "revert"),
                          line(3, "v3", "v1", "inconclusive", "provisional")])
        ev = doc["events"]
        self.assertEqual([e["id"] for e in ev], ["evt_001", "evt_002", "evt_003"])
        self.assertEqual([e["decision"]["disposition"] for e in ev], ["accepted", "rejected", "proposed"])
        self.assertEqual(ev[0]["decision"]["resolved_by"]["type"], "system")
        self.assertEqual(ev[0]["decision"]["proposed_by"]["type"], "ai")
        self.assertIsNone(ev[2]["decision"].get("resolved_by"))
        self.assertEqual(ev[1]["decision"]["revision_note"], "Interval entirely below zero.")
        self.assertEqual(ev[2]["decision"]["description"], "Keep v3 provisionally (parent v1)")
        self.assertEqual(doc["metadata"]["project_key"], "rsi-exam-rollouts")
        self.assertEqual(doc["metadata"]["experiment_id"], "game2048__abc123")
        self.assertEqual(doc["metadata"]["custom"]["source"], "rsi-exam-decision-log/v1")
        self.assertEqual(doc["status"], "completed")
        self.assertEqual(doc["trace_version"], "0.5.0")
        self.assertEqual(doc["summary"], "RSI-Exam rollout game2048__abc123 (game2048_policy_search, claude-code, "
                                         "claude-opus-5): 1 kept, 1 reverted, 1 provisional, 0 replicated.")

    def test_confidence_block_carries_the_proofpress_readable_keys_first(self) -> None:
        doc = self.build([line(1, "v1", "v0", "clears", "keep")])
        conf = doc["events"][0]["decision"]["confidence"]
        self.assertEqual(conf["interval"], {"lower": 467.5, "upper": 575.0, "level": 0.9})
        self.assertEqual(conf["method"], {"name": "percentile_bootstrap", "algorithm": "rsi-exam-gate/percentile-bootstrap/1",
                                          "resamples": 5000, "seed": 20260902})
        self.assertEqual(conf["sample_size"], 8)
        self.assertEqual(conf["evidence_digests"], {"parent": "sha256:" + D, "candidate": "sha256:" + D})
        self.assertEqual(conf["verdict"], "clears")
        self.assertEqual(conf["estimate"], 518.75)
        self.assertEqual(conf["min_effect"], 0.0)
        self.assertEqual(conf["direction"], "higher")
        self.assertEqual(conf["contract"], "rsi-exam-decision-log/v1")
        self.assertEqual(list(conf)[:5], ["interval", "method", "sample_size", "evidence_digests", "contract"])
        self.assertEqual([e["locator"] for e in conf["evidence"]],
                         ["results/v0/visible_result.json", "results/v1/visible_result.json"])
        self.assertIsNone(conf["holdout"])

    def test_rationale_template(self) -> None:
        doc = self.build([line(1, "v3", "v1", "inconclusive", "provisional")])
        self.assertEqual(doc["events"][0]["decision"]["rationale"],
                         "Mean paired delta +260.0 game_score (n=8); 90 percent percentile bootstrap interval "
                         "[-30.0, +583.8]; verdict inconclusive.")

    def test_holdout_is_preserved(self) -> None:
        doc = self.build([line(1, "v3", "v1", "clears", "provisional", holdout_verdict="inconclusive")])
        conf = doc["events"][0]["decision"]["confidence"]
        self.assertEqual(conf["holdout"]["verdict"], "inconclusive")
        self.assertEqual(set(conf["holdout"]["evidence_digests"]), {"holdout-parent", "holdout-candidate"})
        self.assertEqual(doc["events"][0]["decision"]["disposition"], "proposed")

    def test_replication_resolves_the_provisional(self) -> None:
        doc = self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                          line(2, "v3", "v1", "clears", "keep", replicates="v3")])
        ev = doc["events"]
        self.assertEqual(ev[0]["decision"]["disposition"], "accepted")
        self.assertEqual(ev[0]["decision"]["revision_note"], "Resolved by replication evt_002.")
        self.assertEqual(ev[1]["decision"]["revises_event_id"], "evt_001")
        self.assertEqual(ev[1]["decision"]["disposition"], "accepted")
        self.assertTrue(ev[1]["decision"]["description"].startswith("Replication of v3"))
        self.assertEqual(doc["summary"].split(": ")[1], "0 kept, 0 reverted, 1 provisional, 1 replicated.")

    def test_replication_that_fails_rejects_both(self) -> None:
        doc = self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                          line(2, "v3", "v1", "inconclusive", "revert", replicates="v3")])
        ev = doc["events"]
        self.assertEqual([e["decision"]["disposition"] for e in ev], ["rejected", "rejected"])
        doc = self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                          line(2, "v3", "v1", "clears", "revert", replicates="v3", holdout_verdict="inconclusive")])
        ev = doc["events"]
        self.assertEqual([e["decision"]["disposition"] for e in ev], ["rejected", "rejected"])
        self.assertEqual(ev[1]["decision"]["revision_note"], "Replication did not clear the minimum effect.")

    def test_contract_violations_are_refused(self) -> None:
        bad_verdict = line(1, "v1", "v0", "clears", "keep")
        bad_verdict["verdict"] = "inconclusive"
        with self.assertRaises(ValueError):
            self.build([bad_verdict])
        bad_digest = line(1, "v1", "v0", "clears", "keep")
        bad_digest["evidence_digests"]["parent"] = "sha256:" + "b" * 64
        with self.assertRaises(ValueError):
            self.build([bad_digest])
        with self.assertRaises(ValueError):
            self.build([line(1, "v3", "v1", "clears", "keep", replicates="v3")])
        with self.assertRaises(ValueError):
            self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                        line(2, "v3", "v2", "clears", "keep", replicates="v3")])
        with self.assertRaises(ValueError):
            self.build([line(1, "v3", "v1", "inconclusive", "provisional"), line(2, "v4", "v3", "clears", "keep")])
        alias = line(1, "v3", "v1", "clears", "provisional", holdout_verdict="inconclusive")
        alias["holdout"]["evidence"] = [dict(e, role="holdout-" + e["role"]) for e in alias["evidence"]]
        alias["holdout"]["evidence_digests"] = {e["role"]: "sha256:" + e["sha256"] for e in alias["holdout"]["evidence"]}
        with self.assertRaises(ValueError):
            self.build([alias])
        unknown = line(1, "v1", "v0", "clears", "keep")
        unknown["evidence"].append({"role": "mystery", "locator": "results/x.json", "sha256": "c" * 64})
        unknown["evidence_digests"]["mystery"] = "sha256:" + "c" * 64
        with self.assertRaises(ValueError):
            self.build([unknown])
        dup = line(1, "v1", "v0", "clears", "keep")
        dup["evidence"].append(dict(dup["evidence"][0]))
        with self.assertRaises(ValueError):
            self.build([dup])
        with self.assertRaises(ValueError):
            self.build([line(1, "v3", "v1", "inconclusive", "provisional"),
                        line(2, "v4", "v1", "inconclusive", "provisional")])
        with self.assertRaises(ValueError):
            self.build([line(2, "v1", "v0", "clears", "keep")])

    def test_no_free_text_beyond_the_template(self) -> None:
        doc = self.build([provisional(), replication()])
        for event in doc["events"]:
            self.assertIsNone(event["context"]["reasoning_summary"])
            self.assertIsNone(event["context"]["conversation_snippet"])
        blob = json.dumps(doc)
        for banned in ("prompt", "transcript"):
            self.assertNotIn(banned, blob)

    def test_cli_writes_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "decisions.jsonl"
            log.write_text(json.dumps(line(1, "v1", "v0", "clears", "keep")) + "\n", encoding="utf-8")
            out = Path(tmp) / "session.json"
            code = conv.main([str(log), "--project", "p", "--rollout", "r1", "--task", "t", "--harness", "h",
                              "--model", "m", "--output", str(out)])
            self.assertEqual(code, 0)
            doc = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(doc["metadata"]["custom"]["decision_log_sha256"], conv.sha256_of(log))
            self.assertEqual(doc["metadata"]["custom"]["locator_base"], "artifacts/app/methods")

    def test_cli_refuses_a_gated_log_that_violates_the_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "decisions.jsonl"
            log.write_text(json.dumps(provisional(receipts=False)) + "\n", encoding="utf-8")
            out = Path(tmp) / "session.json"
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = conv.main([str(log), "--project", "p", "--rollout", "r1", "--task", "t",
                                  "--harness", "h", "--model", "m", "--output", str(out)])
            self.assertEqual(code, 2)
            self.assertIn("receipt evidence", err.getvalue())
            self.assertFalse(out.exists())


class TestRolloutIdentity(unittest.TestCase):
    def test_a_suite_derived_for_another_rollout_is_refused(self) -> None:
        provisional = line(1, "v3", "v1", "clears", "provisional", confirm_policy="always", suite=dict(SUITE), look_index=1)
        provisional["suite"] = dict(SUITE, derivation=dict(SUITE["derivation"], rollout_id="another-rollout"))
        with self.assertRaises(ValueError):
            conv.build_session([provisional], project="p", rollout_id="game2048__abc123", task="t", harness="h",
                               model="m", decision_log_sha256="a" * 64)


class TestLogWideRules(unittest.TestCase):
    def build(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        return conv.build_session(lines, project="p", rollout_id="game2048__abc123", task="t", harness="h",
                                  model="m", decision_log_sha256="a" * 64)

    def test_one_mode_and_one_profile_per_log(self) -> None:
        gated = line(1, "v3", "v1", "clears", "provisional", confirm_policy="always", suite=dict(SUITE), look_index=1,
                     sizing=dict(SIZING))
        replay_replication = line(2, "v3", "v1", "clears", "keep", replicates="v3")
        with self.assertRaises(ValueError):
            self.build([gated, replay_replication])
        other_profile = line(2, "v4", "v1", "below", "revert", confirm_policy="always", profile_sha256="1" * 64)
        with self.assertRaises(ValueError):
            self.build([line(1, "v2", "v1", "below", "revert", confirm_policy="always"), other_profile])
        with self.assertRaises(ValueError):
            self.build([line(1, "v2", "v1", "below", "revert"), line(2, "v4", "v1", "below", "revert", confirm_policy="always")])

    def test_sizing_must_follow_the_planning_rule(self) -> None:
        for bad in (dict(SIZING, size=7), dict(SIZING, exploratory=True), dict(SIZING, floor=1),
                    dict(SIZING, cap=3), dict(SIZING, planned=3), dict(SIZING, z=-1.0), dict(SIZING, screening_sd="x")):
            with self.subTest(sizing=bad):
                bad_line = line(1, "v3", "v1", "clears", "provisional", confirm_policy="always", suite=dict(SUITE),
                                look_index=1, sizing=bad)
                with self.assertRaises(ValueError):
                    self.build([bad_line])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_trace_from_decisions -v`
Expected: FAIL at import with `AttributeError: module 'trace_from_decisions' has no attribute 'SEEDS_ALGORITHM'`. The current converter has neither that constant nor the gated keys and rules the new tests exercise.

- [ ] **Step 3: Replace the converter**

Replace `gate/trace_from_decisions.py` with this file:

```python
#!/usr/bin/env python3
"""Convert an RSI-Exam decision log into a TRACE 0.5.0 session document.

One ``decision`` event per log line: the rollout agent proposes, the gate resolves; ``keep`` is
``accepted``, ``revert`` is ``rejected``, ``provisional`` stays ``proposed`` until its replication
event revises it. Each event carries a ``confidence`` block whose first four keys are the ones the
ProofPress evidence adapter reads (``interval``, ``method``, ``sample_size``, ``evidence_digests``),
followed by the contract id and the rest of the line, including the gated-mode fields
(``confirm_policy``, ``profile_sha256``, ``look_index``, ``parent_method_tree_sha256``,
``candidate_method_tree_sha256``, ``sizing``, ``suite``), which TRACE preserves as extras.

Every cross-field rule of the contract is re-checked on conversion, including the gated rules: a
gated screening line carries the profile and snapshot digests and receipt evidence; an
under-planned confirmation is a revert with no suite; a provisional line carries its plan and
suite; a replication line repeats its provisional line's profile digest, look index, digests, plan,
suite, and minimum effect; every line of a log is in one mode under one profile; every suite was
derived for the rollout being converted. A violation
refuses the whole conversion (exit 2). The document carries
numbers, identifiers, locators, and digests only. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

TRACE_VERSION = "0.5.0"
CONTEXT = "https://trace-protocol.org/v0.3"
SOURCE_SCHEMA = "rsi-exam-decision-log/v1"
IMPORTER = "rsi-exam-provenance/trace_from_decisions.py 0.2"
LOCATOR_BASE = "artifacts/app/methods"
GATE_ACTOR = {"type": "system", "id": "rsi-exam-gate/decide.py", "role": "decision-gate"}
CONFIDENCE_KEYS = ("interval", "method", "sample_size", "evidence_digests", "contract", "statistic", "unit",
                   "direction", "estimate", "min_effect", "verdict", "evidence", "holdout",
                   "confirm_policy", "profile_sha256", "look_index", "parent_method_tree_sha256",
                   "candidate_method_tree_sha256", "sizing", "suite")
GATED_KEYS = ("confirm_policy", "profile_sha256", "look_index", "parent_method_tree_sha256",
              "candidate_method_tree_sha256", "sizing", "suite")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CONFIRM_POLICIES = ("always", "inconclusive")
ROLES = ("parent", "candidate", "holdout-parent", "holdout-candidate", "receipt-parent", "receipt-candidate")
HOLDOUT_KEYS = ("estimate", "interval", "sample_size", "verdict", "evidence", "evidence_digests")
SIZING_KEYS = {"rule", "size", "planned", "floor", "cap", "exploratory", "screening_sd", "z"}
DERIVATION_KEYS = {"algorithm", "rollout_id", "candidate_method_tree_sha256", "look_index", "size", "max_moves"}
SEEDS_ALGORITHM = "rsi-exam-gate/hmac-seeds/1"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_project_key(label: str) -> str:
    """The TRACE specification's canonical key algorithm (section 3.2.2)."""
    key = unicodedata.normalize("NFC", label).strip().casefold()
    key = re.sub(r"[\s/_]+", "-", key)
    key = re.sub(r"[^\w.-]+", "-", key)
    key = re.sub(r"\.{2,}", ".", key)
    key = re.sub(r"-{2,}", "-", key)
    key = key.strip(".-")
    if not key or key in ("auto", "shared"):
        raise ValueError(f"label {label!r} does not name a project")
    return key


def _sanitize_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", text)


def _fail(line: dict[str, Any], message: str) -> ValueError:
    return ValueError(f"line {line.get('line')}: {message}")


def _check_locator(locator: Any, what: str, line: dict[str, Any]) -> None:
    """The evidence-locator rule: canonical relative POSIX path under results/."""
    bad = (not isinstance(locator, str) or not locator or locator.startswith("/") or "\\" in locator
           or "%" in locator or ":" in locator
           or any(part in ("..", "", ".") for part in locator.split("/"))
           or locator.split("/", 1)[0] != "results")
    if bad:
        raise _fail(line, f"bad {what} locator {locator!r}")


def _is_hex(value: Any) -> bool:
    return isinstance(value, str) and HEX64.match(value) is not None


def _is_pos_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _check_measurement(line: dict[str, Any]) -> None:
    interval = line["interval"]
    low, high, level = interval["lower"], interval["upper"], interval["level"]
    if not all(math.isfinite(x) for x in (low, high, level, line["estimate"], line["min_effect"])):
        raise _fail(line, "non-finite number")
    if low > high:
        raise _fail(line, "interval lower exceeds upper")
    if not 0.0 < level < 1.0:
        raise _fail(line, "level outside the open unit interval")
    if line["min_effect"] < 0.0:
        raise _fail(line, "negative min_effect")
    expected_verdict = "clears" if low > line["min_effect"] else ("below" if high < 0.0 else "inconclusive")
    if line["verdict"] != expected_verdict:
        raise _fail(line, f"verdict {line['verdict']} contradicts the interval")
    roles = [e["role"] for e in line["evidence"]]
    if len(set(roles)) != len(roles) or roles[:2] != ["parent", "candidate"] or any(r not in ROLES for r in roles):
        raise _fail(line, "evidence roles must be unique, known, and start with parent, candidate")
    for e in line["evidence"]:
        _check_locator(e["locator"], "evidence", line)
        if not _is_hex(e["sha256"]):
            raise _fail(line, "evidence sha256 must be 64 hex characters")
    if line["evidence_digests"] != {e["role"]: "sha256:" + e["sha256"] for e in line["evidence"]}:
        raise _fail(line, "evidence_digests do not match evidence")
    holdout = line.get("holdout")
    if holdout:
        hroles = [e["role"] for e in holdout["evidence"]]
        if len(set(hroles)) != len(hroles) or any(r not in ROLES for r in hroles):
            raise _fail(line, "holdout evidence roles must be unique and known")
        if set(e["sha256"] for e in holdout["evidence"]) & set(e["sha256"] for e in line["evidence"]):
            raise _fail(line, "holdout evidence aliases the primary evidence")
        if holdout["interval"]["level"] != level:
            raise _fail(line, "holdout level differs from the primary level")


def _check_gated_shapes(line: dict[str, Any]) -> None:
    """Shape rules for the seven gated keys on a line written under a profile."""
    for key in ("profile_sha256", "parent_method_tree_sha256", "candidate_method_tree_sha256"):
        if not _is_hex(line.get(key)):
            raise _fail(line, f"{key} must be 64 hex characters on a gated line")
    look = line.get("look_index")
    if look is not None and not _is_pos_int(look):
        raise _fail(line, "look_index must be a positive integer or null")
    sizing = line.get("sizing")
    if sizing is not None:
        if (not isinstance(sizing, dict) or set(sizing) != SIZING_KEYS or not isinstance(sizing["exploratory"], bool)
                or not all(_is_pos_int(sizing[k]) for k in ("size", "planned", "floor", "cap"))
                or not all(isinstance(sizing[k], (int, float)) and not isinstance(sizing[k], bool)
                           and math.isfinite(sizing[k]) and sizing[k] >= 0 for k in ("screening_sd", "z"))):
            raise _fail(line, "malformed sizing")
        if (sizing["floor"] < 2 or sizing["cap"] < sizing["floor"] or sizing["planned"] < sizing["floor"]
                or sizing["size"] != min(sizing["planned"], sizing["cap"])
                or sizing["exploratory"] != (sizing["size"] < sizing["planned"])):
            raise _fail(line, "sizing does not follow the planning rule")
    suite = line.get("suite")
    if suite is not None:
        if (not isinstance(suite, dict) or set(suite) != {"locator", "sha256", "derivation"} or not _is_hex(suite["sha256"])
                or not isinstance(suite["derivation"], dict) or set(suite["derivation"]) != DERIVATION_KEYS):
            raise _fail(line, "malformed suite")
        _check_locator(suite["locator"], "suite", line)
        d = suite["derivation"]
        if (d["algorithm"] != SEEDS_ALGORITHM or d["candidate_method_tree_sha256"] != line["candidate_method_tree_sha256"]
                or d["look_index"] != look or sizing is None or d["size"] != sizing["size"]):
            raise _fail(line, "suite derivation does not match the line")
    roles = [e["role"] for e in line["evidence"]]
    if "receipt-parent" not in roles or "receipt-candidate" not in roles:
        raise _fail(line, "a gated line must carry receipt evidence for both results")


def _check_line(line: dict[str, Any], opened: dict[str, Any] | None) -> None:
    """Every cross-field rule of the contract; ``opened`` is the provisional line a replication resolves."""
    if line.get("schema") != SOURCE_SCHEMA:
        raise ValueError(f"line {line.get('line')}: schema is not {SOURCE_SCHEMA}")
    _check_measurement(line)
    policy = line.get("confirm_policy")
    if policy is None:
        policy = "inconclusive"
    if policy not in CONFIRM_POLICIES:
        raise _fail(line, f"unknown confirm_policy {policy!r}")
    gated = policy == "always"
    if gated:
        _check_gated_shapes(line)
    else:
        for key in GATED_KEYS[1:]:
            if line.get(key) is not None:
                raise _fail(line, f"{key} must be null on a replay-mode line")
    holdout = line.get("holdout")
    holdout_verdict = holdout["verdict"] if holdout else None
    if line.get("replicates"):
        if line["replicates"] != line["version_id"]:
            raise _fail(line, "replicates must equal version_id")
        if line["disposition"] == "provisional":
            raise _fail(line, "a replication line cannot be provisional")
        if opened is None:
            raise _fail(line, "replication without an open provisional decision")
        if gated:
            for key in ("profile_sha256", "look_index", "parent_method_tree_sha256", "candidate_method_tree_sha256",
                        "sizing", "suite", "min_effect", "parent_id"):
                if line.get(key) != opened.get(key):
                    raise _fail(line, f"replication {key} differs from the provisional line it resolves")
            if holdout is not None:
                raise _fail(line, "a gated confirmation carries no holdout")
        expected = "keep" if line["verdict"] == "clears" and holdout_verdict in (None, "clears") else "revert"
    elif gated:
        if holdout is not None:
            raise _fail(line, "a gated screening carries no holdout")
        sizing, suite, look = line.get("sizing"), line.get("suite"), line.get("look_index")
        if line["verdict"] == "below":
            expected = "revert"
            if sizing is not None or suite is not None or look is not None:
                raise _fail(line, "a screening that reverts on below plans no confirmation")
        elif sizing is None:
            raise _fail(line, "a gated screening that does not revert must carry its confirmation plan")
        elif sizing["exploratory"]:
            expected = "revert"
            if suite is not None or look is not None:
                raise _fail(line, "an under-planned confirmation is a revert without a suite")
        else:
            expected = "provisional"
            if suite is None or look is None:
                raise _fail(line, "a provisional line must carry its confirmation suite and look index")
    else:
        if line["verdict"] == "below":
            expected = "revert"
        elif line["verdict"] == "clears" and holdout_verdict in (None, "clears"):
            expected = "keep"
        else:
            expected = "provisional"
    if line["disposition"] != expected:
        raise _fail(line, f"disposition {line['disposition']} contradicts the rule ({expected})")


def _confidence(line: dict[str, Any]) -> dict[str, Any]:
    holdout = line.get("holdout")
    block: dict[str, Any] = {}
    for key in CONFIDENCE_KEYS:
        if key == "contract":
            block[key] = SOURCE_SCHEMA
        elif key == "holdout":
            block[key] = {k: holdout[k] for k in HOLDOUT_KEYS} if holdout else None
        else:
            block[key] = line.get(key)
    return block


def _rationale(line: dict[str, Any]) -> str:
    low, high = line["interval"]["lower"], line["interval"]["upper"]
    statistic = line["statistic"].replace("_", " ")
    statistic = statistic[:1].upper() + statistic[1:]
    unit = f" {line['unit']}" if line.get("unit") else ""
    level = f"{line['interval']['level'] * 100:g}"
    method = line["method"]["name"].replace("_", " ")
    return (
        f"{statistic} {line['estimate']:+.1f}{unit} (n={line['sample_size']}); "
        f"{level} percent {method} interval [{low:+.1f}, {high:+.1f}]; verdict {line['verdict']}."
    )


def _event(event_id: str, session_id: str, line: dict[str, Any], agent: dict[str, Any],
           description: str, disposition: str, revision_note: str | None, revises: str | None) -> dict[str, Any]:
    decision: dict[str, Any] = {
        "description": description,
        "rationale": _rationale(line),
        "proposed_by": agent,
        "disposition": disposition,
        "resolved_by": None if disposition == "proposed" else GATE_ACTOR,
        "revision_note": revision_note,
        "revises_event_id": revises,
        "suggestion_type": "proactive",
        "tags": ["rsi-exam", "decision-gate", line["version_id"]],
        "warnings": [],
        "confidence": _confidence(line),
    }
    return {
        "id": event_id,
        "timestamp": line["timestamp"],
        "session_id": session_id,
        "type": "decision",
        "actor": agent,
        "tool_call": None,
        "decision": decision,
        "annotation": None,
        "state_change": None,
        "contribution": None,
        "context": {"conversation_turn": None, "reasoning_summary": None, "conversation_snippet": None,
                    "related_event_ids": []},
    }


def _revert_note(line: dict[str, Any]) -> str:
    sizing = line.get("sizing")
    if isinstance(sizing, dict) and sizing.get("exploratory"):
        return "Confirmation would need more games than the profile allows; reverted without confirming."
    return "Interval entirely below zero."


def build_session(lines: list[dict[str, Any]], *, project: str, rollout_id: str, task: str, harness: str,
                  model: str, decision_log_sha256: str, importer: str = IMPORTER,
                  locator_base: str = LOCATOR_BASE) -> dict[str, Any]:
    """Map decision-log lines (in file order) onto one completed TRACE session document."""
    if not lines:
        raise ValueError("decision log is empty")
    session_id = _sanitize_id(f"rsiexam_{rollout_id}")
    agent = {"type": "ai", "id": f"{harness}:{model}", "role": "rollout-agent"}
    events: list[dict[str, Any]] = []
    open_provisional: dict[str, tuple[str, str, dict[str, Any]]] = {}
    counts = {"keep": 0, "revert": 0, "provisional": 0, "replicated": 0}

    log_mode: str | None = None
    log_profile: str | None = None
    for number, line in enumerate(lines, start=1):
        if line.get("line") != number:
            raise ValueError(f"line {number}: line field {line.get('line')!r} does not match position")
        mode = "gated" if line.get("confirm_policy") == "always" else "replay"
        if log_mode is None:
            log_mode, log_profile = mode, line.get("profile_sha256")
        elif mode != log_mode or line.get("profile_sha256") != log_profile:
            raise ValueError(f"line {number}: a log is written in one mode under one profile; this line differs from line 1")
        opened_entry = open_provisional.get(line["replicates"]) if line.get("replicates") else None
        _check_line(line, opened_entry[2] if opened_entry else None)
        suite = line.get("suite")
        if isinstance(suite, dict) and suite["derivation"]["rollout_id"] != rollout_id:
            raise ValueError(f"line {number}: suite was derived for rollout {suite['derivation']['rollout_id']!r}, "
                             f"not {rollout_id!r}")
        event_id = f"evt_{len(events) + 1:03d}"
        version, parent = line["version_id"], line["parent_id"]
        if line.get("replicates"):
            if opened_entry is None:
                raise ValueError(f"line {number} replicates {line['replicates']} but no provisional decision is open")
            original_id, original_parent, _ = opened_entry
            if parent != original_parent:
                raise ValueError(f"line {number}: replication parent {parent} differs from the provisional line's parent {original_parent}")
            original = next(e for e in events if e["id"] == original_id)
            disposition = "accepted" if line["disposition"] == "keep" else "rejected"
            note = None if disposition == "accepted" else "Replication did not clear the minimum effect."
            events.append(_event(event_id, session_id, line, agent,
                                 f"Replication of {version} on fresh seeds (parent {parent})",
                                 disposition, note, original_id))
            original["decision"]["disposition"] = disposition
            original["decision"]["resolved_by"] = GATE_ACTOR
            original["decision"]["revision_note"] = f"Resolved by replication {event_id}."
            del open_provisional[line["replicates"]]
            counts["replicated"] += 1
            continue
        if line["disposition"] == "provisional" and open_provisional:
            raise ValueError(f"line {number} opens a second provisional decision")
        if any(parent == v for v in open_provisional):
            raise ValueError(f"line {number} builds on {parent} while its provisional decision is unresolved")
        if line["disposition"] == "keep":
            events.append(_event(event_id, session_id, line, agent, f"Keep {version} (parent {parent})",
                                 "accepted", None, None))
        elif line["disposition"] == "revert":
            events.append(_event(event_id, session_id, line, agent, f"Revert {version} (parent {parent})",
                                 "rejected", _revert_note(line), None))
        else:
            events.append(_event(event_id, session_id, line, agent,
                                 f"Keep {version} provisionally (parent {parent})", "proposed", None, None))
            open_provisional[version] = (event_id, parent, line)
        counts[line["disposition"]] += 1

    summary = (f"RSI-Exam rollout {rollout_id} ({task}, {harness}, {model}): {counts['keep']} kept, "
               f"{counts['revert']} reverted, {counts['provisional']} provisional, {counts['replicated']} replicated.")
    return {
        "context": CONTEXT,
        "trace_version": TRACE_VERSION,
        "id": session_id,
        "created": events[0]["timestamp"],
        "ended": events[-1]["timestamp"],
        "status": "completed",
        "metadata": {
            "project": project,
            "project_key": canonical_project_key(project),
            "experiment_id": rollout_id,
            "description": f"Decision-gate record for RSI-Exam rollout {rollout_id}",
            "participants": [agent, GATE_ACTOR],
            "environment": None,
            "tags": ["rsi-exam", "decision-gate"],
            "doi": None,
            "custom": {"source": SOURCE_SCHEMA, "importer": importer, "rollout_id": rollout_id, "task": task,
                       "harness": harness, "model": model, "decision_log_sha256": decision_log_sha256,
                       "locator_base": locator_base},
        },
        "summary": summary,
        "events": events,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("log", type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--rollout", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--importer", default=IMPORTER)
    parser.add_argument("--locator-base", default=LOCATOR_BASE)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        raw_lines = args.log.read_text(encoding="utf-8").splitlines()
        if any(not raw.strip() for raw in raw_lines):
            raise ValueError("blank line in decision log")
        lines = [json.loads(raw) for raw in raw_lines]
        doc = build_session(lines, project=args.project, rollout_id=args.rollout, task=args.task,
                            harness=args.harness, model=args.model, decision_log_sha256=sha256_of(args.log),
                            importer=args.importer, locator_base=args.locator_base)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"conversion failed: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_trace_from_decisions -v`
Expected: `Ran 19 tests`, `OK`.

Run: `python3 -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: `Ran 146 tests`, `OK`.

- [ ] **Step 5: Type-check and commit**

Run: `pyright gate/trace_from_decisions.py tests/test_trace_from_decisions.py`
Expected: `0 errors`.

```bash
git add gate/trace_from_decisions.py tests/test_trace_from_decisions.py
git diff --exit-code
git commit -m "feat(converter): re-check the gated rules and carry the gated fields

The converter now applies confirm_policy when it re-derives the expected
disposition (under always, a screening that does not revert is provisional,
never a keep), checks the shapes of the profile digest, look index, both
snapshot digests, the plan, and the suite, requires receipt evidence on every
gated line, treats an under-planned confirmation as a revert that carries no
suite, requires a confirmation line to repeat its provisional line's profile
digest, look index, digests, plan, suite, and minimum effect, and refuses a
suite derived for another rollout. The seven fields ride at the end of the
confidence block, where ProofPress ignores them and TRACE preserves them as
extras. Replay-mode lines without the fields convert as before.

Tests: gated provisional and its confirmation, the under-planned revert and
its note, a gated below line, replay lines, the rule-violation matrix, and
the rollout-identity refusal."
```

---

### Task 8: End-to-end gated rollout on the real evaluator (`tests/test_gated_rollout.py`)

**Files:**
- Create: `tests/test_gated_rollout.py`

**Interfaces:**
- Consumes: `gate/evaluate_suite.py` (through a subprocess, because it arms `RLIMIT_CPU` for its own process), `decide.main`, `trace_from_decisions.build_session`, `fixtures/task2048/`, `tests/gate_fixtures.py`.
- Both cases are deterministic: the fixture policies are deterministic on the fixture seeds, and every number the test asserts is pinned. Nothing branches on a measured outcome.

- [ ] **Step 1: Write the test**

Create `tests/test_gated_rollout.py`:

```python
"""End to end: a gated rollout on the real 2048 evaluator, from screening to the TRACE document.

Uses the fixture task files, the runner in a subprocess (it arms ``RLIMIT_CPU``), the gate in gated
mode, and the converter. Every number asserted here is the deterministic outcome of the fixture
policies on the fixture seeds. Nothing here talks to TRACE or ProofPress; the run report does that.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gate"))
import decide  # noqa: E402
import seeds as seedsmod  # noqa: E402
import trace_from_decisions as conv  # noqa: E402
import treedigest  # noqa: E402
from tests.gate_fixtures import (POLICY_VARIANT, POLICY_WEAK, TASK_ROOT, VISIBLE_SUITE, copy_policy,  # noqa: E402
                                 real_evaluator, real_visible_suite_sha, run_runner, write_profile)

VISIBLE_SEEDS = json.loads(VISIBLE_SUITE.read_text(encoding="utf-8"))["seeds"]
CONFIRMATION = {"floor": 4, "max_seeds": 8, "max_moves": 10000, "cpu_seconds_per_game": 225}
WEAK_VISIBLE_MEAN = 2060.0
VARIANT_VISIBLE_MEAN = 2386.5
MIN_EFFECT = 0.025 * WEAK_VISIBLE_MEAN  # 51.5 game score


class GatedRollout(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.methods = Path(self.tmp.name) / "methods"
        self.methods.mkdir(parents=True)
        copy_policy(POLICY_WEAK, self.methods / "main")
        copy_policy(POLICY_WEAK, self.methods / "versions" / "v1")
        self.profile = self.methods / "gate" / "profile.json"
        self.profile_sha = write_profile(self.profile, rollout_id="e2e-rollout", confirmation=CONFIRMATION,
                                         min_effect={"kind": "fraction_of_parent_visible_mean", "fraction": 0.025},
                                         replication_key="22" * 32, evaluator=real_evaluator(),
                                         visible_suite_sha256=real_visible_suite_sha())
        self.evaluate("v1", VISIBLE_SUITE, self.methods / "results" / "v1" / "visible_result.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def evaluate(self, version: str, suite: Path, output: Path) -> dict[str, Any]:
        """Run the pinned evaluator on one snapshot; the runner also writes the receipt the gate requires."""
        proc = run_runner("--profile", str(self.profile), "--task-root", str(TASK_ROOT),
                          "--policy-dir", str(self.methods / "versions" / version), "--suite", str(suite),
                          "--output", str(output))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(output.read_text(encoding="utf-8"))

    def install_candidate(self, source: Path, version: str) -> dict[str, Any]:
        shutil.rmtree(self.methods / "main")
        copy_policy(source, self.methods / "main")
        copy_policy(source, self.methods / "versions" / version)
        return self.evaluate(version, VISIBLE_SUITE,
                             self.methods / "results" / version / "visible_result.json")

    def gate(self, *args: str) -> int:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = decide.main(["--methods", str(self.methods), "--profile", str(self.profile), *args])
        self.assertEqual(code, 0, err.getvalue())
        return code

    def lines(self) -> list[dict[str, Any]]:
        return [json.loads(x) for x in (self.methods / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]

    def confirm(self, version: str, parent: str) -> list[int]:
        """Evaluate the parent and the candidate on the suite the provisional line derived."""
        line = self.lines()[-1]
        suite = self.methods / line["suite"]["locator"]
        base = self.methods / "results" / version / "replication"
        self.evaluate(parent, suite, base / "parent_result.json")
        self.evaluate(version, suite, base / "candidate_result.json")
        chosen, _ = seedsmod.read_suite(suite)
        return chosen

    def assert_no_bytecode_in_policy_trees(self) -> None:
        for tree in [self.methods / "main", *sorted((self.methods / "versions").iterdir())]:
            self.assertEqual(list(tree.rglob("__pycache__")), [], f"bytecode written under {tree}")
            self.assertEqual(treedigest.method_files(tree), ["policy.py"])

    def test_an_identical_candidate_is_provisional_then_reverted(self) -> None:
        parent = json.loads((self.methods / "results" / "v1" / "visible_result.json").read_text(encoding="utf-8"))
        self.assertEqual(parent["mean_score"], WEAK_VISIBLE_MEAN)
        candidate = self.install_candidate(POLICY_WEAK, "v2")
        self.assertEqual(candidate["mean_score"], WEAK_VISIBLE_MEAN)

        self.gate("--version", "v2", "--parent", "v1")
        line1 = self.lines()[0]
        self.assertEqual((line1["verdict"], line1["disposition"]), ("inconclusive", "provisional"))
        self.assertEqual(line1["estimate"], 0.0)
        self.assertEqual((line1["interval"]["lower"], line1["interval"]["upper"]), (0.0, 0.0))
        self.assertEqual(line1["sample_size"], 8)
        self.assertAlmostEqual(line1["min_effect"], MIN_EFFECT)
        self.assertEqual(line1["sizing"]["screening_sd"], 0.0)
        self.assertEqual((line1["sizing"]["planned"], line1["sizing"]["size"], line1["sizing"]["exploratory"]),
                         (4, 4, False))
        self.assertEqual(line1["look_index"], 1)
        self.assertEqual(line1["suite"]["derivation"]["size"], 4)
        self.assertEqual(line1["suite"]["derivation"]["max_moves"], 10000)

        suite_seeds = self.confirm("v2", "v1")
        self.assertEqual(len(suite_seeds), 4)
        self.assertFalse(set(suite_seeds) & set(VISIBLE_SEEDS))
        self.gate("--version", "v2", "--parent", "v1", "--replicates", "v2")
        line2 = self.lines()[1]
        self.assertEqual((line2["verdict"], line2["disposition"], line2["estimate"]), ("inconclusive", "revert", 0.0))
        self.assertEqual(line2["sample_size"], 4)
        self.assertEqual([e["role"] for e in line2["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])
        for ref in line2["evidence"]:
            self.assertEqual(decide.sha256_of(self.methods / ref["locator"]), ref["sha256"])
        self.assert_no_bytecode_in_policy_trees()

    def test_the_variant_candidate_is_too_noisy_to_confirm_and_reverts(self) -> None:
        candidate = self.install_candidate(POLICY_VARIANT, "v2")
        self.assertEqual(candidate["mean_score"], VARIANT_VISIBLE_MEAN)
        self.gate("--version", "v2", "--parent", "v1")
        line1 = self.lines()[0]
        self.assertEqual(line1["sample_size"], 8)
        self.assertEqual(line1["estimate"], 326.5)
        self.assertEqual((line1["interval"]["lower"], line1["interval"]["upper"]), (-569.5, 1191.0))
        self.assertAlmostEqual(line1["min_effect"], MIN_EFFECT)
        self.assertEqual(line1["verdict"], "inconclusive")
        # the spread of the per-seed deltas needs far more games than the profile's cap of 8 allows,
        # so the plan is exploratory and the candidate reverts without a confirmation
        self.assertEqual((line1["sizing"]["planned"], line1["sizing"]["size"], line1["sizing"]["exploratory"]),
                         (10586, 8, True))
        self.assertEqual(line1["disposition"], "revert")
        self.assertIsNone(line1["suite"])
        self.assertIsNone(line1["look_index"])
        self.assertFalse((self.methods / "results" / "v2" / "replication").exists())
        self.assertEqual(line1["candidate_method_tree_sha256"], treedigest.method_tree_sha256(POLICY_VARIANT))
        self.assertEqual(line1["parent_method_tree_sha256"], treedigest.method_tree_sha256(POLICY_WEAK))
        self.assertEqual(line1["profile_sha256"], self.profile_sha)

        log = self.methods / "decisions.jsonl"
        doc = conv.build_session(self.lines(), project="rsi-exam-provenance", rollout_id="e2e-rollout",
                                 task="game2048_policy_search", harness="test", model="none",
                                 decision_log_sha256=conv.sha256_of(log))
        self.assertEqual(doc["trace_version"], "0.5.0")
        decision = doc["events"][0]["decision"]
        self.assertEqual(decision["disposition"], "rejected")
        self.assertEqual(decision["revision_note"],
                         "Confirmation would need more games than the profile allows; reverted without confirming.")
        confidence = decision["confidence"]
        self.assertEqual(confidence["confirm_policy"], "always")
        self.assertEqual(confidence["profile_sha256"], self.profile_sha)
        self.assertEqual(confidence["parent_method_tree_sha256"], line1["parent_method_tree_sha256"])
        self.assertEqual(confidence["candidate_method_tree_sha256"], line1["candidate_method_tree_sha256"])
        self.assertEqual([e["role"] for e in confidence["evidence"]],
                         ["parent", "candidate", "receipt-parent", "receipt-candidate"])
        self.assert_no_bytecode_in_policy_trees()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it**

Run: `python3 -m unittest tests.test_gated_rollout -v`
Expected: `Ran 2 tests`, `OK`.

The identical-candidate case: every paired delta is zero, so the interval is `[0.0, 0.0]`, the verdict is `inconclusive` (zero is not above a positive minimum effect), the standard deviation is zero, the plan falls to the floor of 4 and is not exploratory, the line is provisional with look 1, and the four derived seeds are disjoint from the visible seeds. The confirmation on those seeds measures the same policy twice, so the estimate is again zero, the verdict is `inconclusive`, and the decision reverts.

The variant case: the per-seed deltas are large in both directions, so the estimate is 326.5 with a 90 percent interval of `[-569.5, 1191.0]` and the verdict is `inconclusive`; the plan asks for 10586 games against a cap of 8, which makes it exploratory, so the candidate reverts on the screening line with no suite, no look index, and no `replication` directory. The converted TRACE document carries that as a rejected decision whose revision note names the cap.

- [ ] **Step 3: Type-check and commit**

Run: `pyright tests/test_gated_rollout.py`
Expected: `0 errors`.

```bash
git add tests/test_gated_rollout.py
git diff --exit-code
git commit -m "test(gate): end-to-end gated rollout on the real 2048 evaluator

Screening, freezing, planning, suite derivation, two runner evaluations with
receipts, confirmation, and conversion to a TRACE document, on the task's own
evaluator at the pinned dataset revision. The identical-candidate case runs
the whole path and reverts on a confirmation that measures no difference; the
variant case is too noisy for the profile's cap and reverts on the screening
line without a suite. Both assert the frozen digests, the receipt evidence
roles, seed disjointness, and that no bytecode lands in a policy tree."
```

---

### Task 9: Contract, roadmap, README, and layout

**Files:**
- Modify: `docs/decision-log-contract.md`, `docs/ROADMAP.md`, `README.md`, `CLAUDE.md`

Each edit below gives the exact block to find and the exact block to put in its place. Every "before" block appears once in the file as it stands on `main`; if one does not match, STOP rather than guessing.

- [ ] **Step 1: Make the gated-mode fields normative in the contract**

In `docs/decision-log-contract.md`, replace this block:

```markdown
### Planned additions (same schema id until a real rollout record exists)

`profile_sha256` (the task profile that fixed `direction`, `unit`, `min_effect`, level, resamples,
and the seed-derivation key), `confirm_policy` (`always` or `inconclusive`), `look_index` (count
of confirmations in the rollout), `candidate_method_tree_sha256` (frozen before confirmation seeds
are derived), `suite {locator, sha256, derivation}` for confirmation and audit suites, and receipt
digests in `evidence`.
```

with this block:

```markdown
### Gated-mode fields (same schema id)

Every line carries seven more keys. A line written in replay mode (`decide.py --confirm
inconclusive`, used for shadow replay and fixtures) has `confirm_policy` `inconclusive` and `null`
in the other six. One log is written in one mode under one profile; a line from the other mode, or
under another profile, is refused.

- `confirm_policy`: `always` (the gated rule, and the only value a profile may state: a screening
  that does not revert is `provisional` until a confirmation on fresh seeds resolves it) or
  `inconclusive` (the replay rule of the disposition table above).
- `profile_sha256`: the SHA-256 of the task profile file the line was written under, or `null`.
- `look_index`: the 1-based index of the confirmation look this line belongs to; the provisional
  line and the confirmation that resolves it carry the same value. `null` on a line that opens no
  confirmation.
- `parent_method_tree_sha256`, `candidate_method_tree_sha256`: the method-tree digests of
  `versions/<parent_id>` and `versions/<version_id>` at gate time (see "Method-tree digest"), or
  `null` in replay mode. In gated mode `main/` must equal the candidate's digest, at screening and
  again at confirmation, and a confirmation refuses unless both digests still equal the frozen
  ones: neither policy can change between being measured and being confirmed.
- `sizing`: the confirmation plan, `{rule, size, planned, floor, cap, exploratory, screening_sd,
  z}`, or `null` on a line that plans no confirmation.
- `suite`: `null`, or `{locator, sha256, derivation}` for the confirmation suite the screening line
  derived (`results/<version_id>/replication/seeds.json`, a file of the shape `{"max_moves": N,
  "seeds": [...]}` that the task evaluator reads), repeated unchanged on the confirmation line.
  `derivation` records `algorithm` (`rsi-exam-gate/hmac-seeds/1`), `rollout_id`,
  `candidate_method_tree_sha256`, `look_index`, `size`, and `max_moves`.

**Method-tree digest.** SHA-256 over the lines `<sha256 of file><two spaces><posix relpath>\n`,
sorted by relpath, over the `.py` files under the directory, skipping any path with a `__pycache__`
component and any `*.pyc` or `*.pyo` file. A symlink anywhere under the tree is refused, and that
check runs before the exclusions; a regular file that is not `.py` is refused, because the grader
refuses it and scores such a submission 0.0. The digest equals the provenance record's full-tree
digest for a Python-only tree without caches.

**Task profile** (`rsi-exam-gate-profile/v1`, `gate/task_profile.py`). One file per rollout,
mounted with the gate scripts, never under `main/` or `versions/`. Keys: `schema`, `task`,
`rollout_id`, `metric`, `unit`, `direction` (`higher` or `lower`), `min_effect` (`{"kind":
"absolute", "value": V > 0}` or `{"kind": "fraction_of_parent_visible_mean", "fraction": F}` with
`0 < F < 1`), `level` in `(0, 1)`, `resamples >= 1000`, `bootstrap_seed`, `confirm_policy` (fixed
to `always`), `confirmation {floor >= 2, max_seeds >= floor, max_moves, cpu_seconds_per_game}`,
`visible_suite_sha256` (the digest of the task's visible seed file), `replication_key` (64 hex),
`audit_key_sha256` (64 hex; the audit key itself stays outside the sandbox), and `evaluator`, which
maps exactly `evaluate.py` and `game2048.py` to 64-hex digests. A fraction is resolved once, at
screening, against the mean of the parent's visible per-seed scores, which must be positive; the
resolved absolute number is what the line records under `min_effect` and what its confirmation
reuses unchanged. In gated mode the command-line flags for direction, unit, minimum effect, level,
resamples, seed, result locators, and held-out results are refused.

**Fresh suites** (`rsi-exam-gate/hmac-seeds/1`, `gate/seeds.py`). `seed_k` is the first four bytes
of `HMAC-SHA256(replication_key, "<rollout_id>|<candidate_method_tree_sha256>|<look_index>|<counter>")`
as a big-endian integer with the top bit cleared, for `counter = 0, 1, 2, ...`, skipping zero,
repeats, the visible seeds, and every seed of every earlier suite in the log. The claim this
supports is exact and narrow: the suite is disjoint from the visible suite and from every earlier
suite, and anyone holding the key can re-derive it from the log. The key is mounted with the
profile and is readable inside the sandbox, so the seeds are auditable, not secret; whether a
candidate was tuned on them is measured after the fact by the verifier (Milestone 2) and the audit
suite (Milestone 3), never assumed here.

**Confirmation size.** With `s` the sample standard deviation of the screening deltas and `z` the
normal quantile for the level, `planned` is the smallest `n` with `z s / sqrt(n) < min_effect / 2`,
at least `floor`; `size = min(planned, max_seeds)`; `exploratory` is `true` when the cap binds. It
is a normal-approximation planning size computed from screening data, not a statement about the
interval the confirmation will produce. An exploratory plan never keeps: the gate reverts the
candidate on the screening line, records the plan, and derives no suite.

**Receipts** (`rsi-exam-gate-receipt/v1`, written by `gate/evaluate_suite.py` next to each result as
`<name>.receipt.json`): `schema`, `metric`, `profile_sha256`, `policy_method_tree_sha256`,
`suite_sha256`, `max_moves`, `result_sha256`, `evaluator`, `games`, `cpu_seconds`,
`cpu_budget_per_game`, `python`, `timestamp`. The gate requires a receipt beside every result it
reads and compares `profile_sha256`, `suite_sha256`, `result_sha256`, `policy_method_tree_sha256`,
`evaluator`, `metric`, `cpu_budget_per_game`, `max_moves`, and `games` against the profile, the
suite file, the result on disk, and the frozen snapshot digest for that role; at screening the
suite compared is the profile's `visible_suite_sha256`, at confirmation the derived suite's. All
four receipts of a confirmed decision must share a Python major.minor version. `cpu_seconds` and
`timestamp` are recorded, never compared. Receipts enter `evidence` under `receipt-parent` and
`receipt-candidate`.

**Confirmation line.** Before it resolves a provisional line the gate re-verifies that line from
its evidence: both snapshot digests unchanged, every screening evidence file still at its recorded
digest, the minimum effect re-resolved from the profile and the parent's visible result, the plan
recomputed from the screening deltas and not exploratory, the exclusion set rebuilt from the lines
before it, the suite re-derived from the key, the frozen candidate digest, and the look index, and
the derivation record equal to what those inputs imply.
`results/<version_id>/replication/{parent,candidate}_result.json` must cover exactly the suite's
seeds; `min_effect` is the provisional line's value; `keep` on `clears`, otherwise `revert`.

**Restore.** A reverted candidate is put back with `gate/restore.py --methods <methods dir>
--version v<K>`, which stages the snapshot's Python files beside `main/`, replaces `main/` in one
rename, and checks that the restored tree's digest equals the snapshot's. The literal `cp -r
versions/v<K> main` nests the snapshot inside `main/` instead, leaves the reverted policy running,
and makes every later gate call refuse.

**Further limits of Milestone 1.** The evaluation child runs as the same user as the agent, so policy
code could write to files the agent can write to; the grader's own sandbox drops privileges to an
unprivileged user, and Milestone 3 adds the same drop (and the per-move time limit) to the runner
before the first gated rollout. The runner publishes the result and then the receipt as two files; a
crash between them leaves a result the next run refuses to overwrite, which the operator removes by
hand. The gate accepts whichever profile path it is given; the post-rollout verifier's comparison of
`profile_sha256` with the operator's mounted digest is the check that the intended profile was used.

**Limits.** Coverage is per candidate: each interval holds at its own level for its own decision,
and no error rate is controlled across the many decisions of a rollout. `look_index` is recorded so
a multiple-look schedule can be added later; it is not one yet. The profile, the gate scripts, and
the replication key are all reachable by the agent inside the sandbox, so a substituted profile is
possible; what makes it visible is that every line and every receipt records `profile_sha256`,
which the post-rollout verifier compares with the digest of the profile the operator mounted. The
record is tamper-evident relative to the exported job directory and that operator-held digest,
never tamper-proof. `DECIDE_FIXED_TIMESTAMP` is a fixture hook, and timestamps are not evidence
anywhere in this contract. `audit_key_sha256` is recorded now and used by the audit suite in
Milestone 3.
```

- [ ] **Step 2: List the gated keys in the block's key order (section 2 of the same file)**

In `docs/decision-log-contract.md`, replace this block:

```markdown
Keys in this order: `interval`, `method`, `sample_size`, `evidence_digests` (the four keys the
ProofPress evidence adapter reads and keeps), then `contract` (this schema id), `statistic`, `unit`,
`direction`, `estimate`, `min_effect`, `verdict`, `evidence`, `holdout`. Unknown keys are ignored
by ProofPress. The generic measurement keys (`interval`, `method`, `sample_size`,
`evidence_digests`, `contract`, `statistic`, `unit`, `direction`, `estimate`, `evidence`) are the
part TRACE types, in exactly this nested shape, when its typed model ships; until then the
document is a valid 0.5.0 session carrying an additive extension. The rule-state keys
(`min_effect`, `verdict`, `holdout`, and the planned `confirm_policy`) remain an identified
extension that TRACE preserves but does not interpret. TRACE's own checks on the block are
structural only: ordered interval bounds, a level in the open unit interval, a positive sample
size, finite numbers, well-formed digests, a role on every evidence entry, and `evidence_digests`
keys equal to the evidence roles. The verdict and disposition rules are checked by the profile
verifier (section 4), never by TRACE.
```

with this block:

```markdown
Keys in this order: `interval`, `method`, `sample_size`, `evidence_digests` (the four keys the
ProofPress evidence adapter reads and keeps), then `contract` (this schema id), `statistic`, `unit`,
`direction`, `estimate`, `min_effect`, `verdict`, `evidence`, `holdout`, `confirm_policy`,
`profile_sha256`, `look_index`, `parent_method_tree_sha256`, `candidate_method_tree_sha256`,
`sizing`, `suite`. Unknown keys are ignored by ProofPress. The generic measurement keys
(`interval`, `method`, `sample_size`, `evidence_digests`, `contract`, `statistic`, `unit`,
`direction`, `estimate`, `evidence`) are the part TRACE types, in exactly this nested shape, when
its typed model ships; until then the document is a valid 0.5.0 session carrying an additive
extension. The rule-state keys (`min_effect`, `verdict`, `holdout`) and the gated keys
(`confirm_policy`, `profile_sha256`, `look_index`, `parent_method_tree_sha256`,
`candidate_method_tree_sha256`, `sizing`, `suite`) remain an identified extension that TRACE
preserves but does not interpret. TRACE's own checks on the block are structural only: ordered
interval bounds, a level in the open unit interval, a positive sample size, finite numbers,
well-formed digests, a role on every evidence entry, and `evidence_digests` keys equal to the
evidence roles. The verdict and disposition rules are checked by the gate on write and the
converter on read, and by the profile verifier (section 4), never by TRACE.
```

- [ ] **Step 3: Update the roadmap status table and the milestone heading**

In `docs/ROADMAP.md`, replace this block:

```markdown
| Decision gate (`gate/decide.py`) | Built, 21 tests | Screening, one open provisional at a time, replication, evidence-location refusal. Task profile, confirmation policy, freeze, seed derivation, and receipts are next. |
| TRACE converter (`gate/trace_from_decisions.py`) | Built, 10 tests | Output validates under TRACE 0.5.0 and round-trips through TRACE's typed models unchanged. |
```

with this block:

```markdown
| Decision gate (`gate/decide.py`) and its modules | Built, 91 tests | Gated mode with a task profile, freezing, confirmation planning, fresh-suite derivation (`gate/seeds.py`), the evaluation runner with receipts (`gate/evaluate_suite.py`), cache-free method-tree digests (`gate/treedigest.py`), and the restore helper (`gate/restore.py`). Replay mode for shadow replay and fixtures. |
| TRACE converter (`gate/trace_from_decisions.py`) | Built, 17 tests | Re-checks every contract rule, including the gated ones, and carries the gated fields as extras. Output validates under TRACE 0.5.0 and round-trips through TRACE's typed models unchanged. |
```

In `docs/ROADMAP.md`, replace this block:

```markdown
## Milestone 1: preflight, then finish the gate (target: early September 2026)
```

with this block:

```markdown
## Milestone 1: the gate, the runner, receipts, and the restore helper (built)

Status: Milestone 1 delivers the gate, the runner, receipts, and the restore helper. Mounting them
into the container, the trusted driver that runs the gate between snapshots, and the program overlay
that tells the agent to call it are Milestone 3, so no gated rollout runs before then. The preflight
observation is recorded in `docs/PREFLIGHT.md` once it has been made.
```

- [ ] **Step 4: Update the README**

In `README.md`, replace this block:

```markdown
Fixture-verified, no real rollout yet. The gate and converter have 31 tests, the profile has a
38-case conformance suite, and `docs/RUN_REPORT.md` records a full run on a demo lineage: gate
decisions, `trace-mcp validate` passing, a byte-equal typed TRACE round-trip, and a successful
`proofpress evidence import`. What comes next, milestone by milestone, is in `docs/ROADMAP.md`:
the task profile and confirmation policy, deterministic fresh-seed derivation, evaluation
receipts, the verifier's decision checks, the decision-evidence report, then the first real
rollout on `game2048_policy_search`.
```

with this block:

```markdown
Fixture-verified, no real rollout yet. The gate, its modules, and the converter have 110 tests, the
profile has a 38-case conformance suite, and `docs/RUN_REPORT.md` records a full run on a demo
lineage: gate decisions, `trace-mcp validate` passing, a byte-equal typed TRACE round-trip, and a
successful `proofpress evidence import`. What comes next, milestone by milestone, is in
`docs/ROADMAP.md`: the verifier's decision checks and cache-free digests, the decision-evidence
report, then the first real rollout on `game2048_policy_search`. A gated rollout waits for
Milestone 3, which mounts the gate and its profile into the container and adds the trusted driver
and the program overlay that call it.
```

In `README.md`, replace this block:

```text
python3 -m unittest discover -s tests -t .          # 70 tests
```

with this block:

```text
python3 -m unittest discover -s tests -t .          # 148 tests
```

- [ ] **Step 5: Update the layout in CLAUDE.md**

In `CLAUDE.md`, replace this block:

```text
gate/decide.py                 the decision gate (screen, confirm, keep or revert)
gate/trace_from_decisions.py   decision log -> TRACE 0.5.0 session document
```

with this block:

```text
gate/decide.py                 the decision gate (gated mode with a task profile; replay mode)
gate/treedigest.py             cache-free, Python-only method-tree digests
gate/task_profile.py           the per-rollout task profile (rsi-exam-gate-profile/v1)
gate/seeds.py                  fresh confirmation suites (rsi-exam-gate/hmac-seeds/1) and the planning rule
gate/evaluate_suite.py         the evaluation runner that writes receipts (rsi-exam-gate-receipt/v1)
gate/restore.py                put a snapshot back into main/ without nesting it
gate/trace_from_decisions.py   decision log -> TRACE 0.5.0 session document
```

In `CLAUDE.md`, replace this block:

```text
fixtures/valid/                a harbor-shaped job directory with its golden record
```

with this block:

```text
fixtures/valid/                a harbor-shaped job directory with its golden record
fixtures/task2048/             the 2048 task's evaluator, engine, seed file, and starter policy at the pinned revision (MIT; see NOTICE), plus a variant policy
```

- [ ] **Step 6: Run everything, check the links, commit, open pull request B**

Run: `python3 -m unittest discover -s tests -t . 2>&1 | tail -3 && pyright gate profile tests`
Expected: `Ran 148 tests`, `OK`, and `0 errors`.

Then check that every relative link still resolves:

```bash
python3 - <<'PY'
import re, pathlib
bad = 0
for md in ["README.md", "docs/overview.md", "docs/ROADMAP.md", "docs/decision-log-contract.md", "CLAUDE.md"]:
    text = pathlib.Path(md).read_text()
    for m in re.finditer(r"\]\(([^)]+)\)", text):
        t = m.group(1)
        if t.startswith("http"): continue
        if not (pathlib.Path(md).parent / t).exists(): bad += 1; print("MISSING", md, t)
print("missing:", bad)
PY
```
Expected: `missing: 0`.

```bash
git add docs/decision-log-contract.md docs/ROADMAP.md README.md CLAUDE.md
git diff --exit-code
git commit -m "docs: make the gated-mode fields normative and record the milestone

The contract now states the seven gated-mode line keys, the method-tree
digest, the task profile, the fresh-suite algorithm, the planning rule and
its no-keep consequence, the receipt and the fields the gate compares, the
re-derivation a confirmation performs, the restore helper, and the limits:
per-candidate coverage with no rollout-wide error control, a look index
recorded for a schedule that does not exist yet, a profile the agent can
substitute and a recorded digest that makes the substitution visible, and
timestamps that are not evidence. Section 2 lists the seven keys at the end
of the confidence block. The roadmap marks the gate and its modules built and
says a gated rollout waits for Milestone 3; the README and CLAUDE.md name the
new modules and the task fixture."
git push -u origin feat/gate-confirmation
gh pr create --title "feat(gate): screening and confirmation with a task profile, freezing, fresh suites, and receipts" --body "## Summary
- decide.py gains a gated mode. A task profile fixes direction, unit, minimum effect, level, resamples, the bootstrap seed, and the confirmation bounds, and always means confirmation on fresh seeds. A screening requires runner receipts binding both visible results to the two snapshots, the profile's visible suite, the evaluator, the metric, the budget, the game length, and the game count; it freezes both snapshot digests and requires main/ to equal the candidate's.
- A screening that does not revert plans its confirmation from the screening deltas. A plan the profile's cap cannot cover reverts with the plan recorded: an under-planned confirmation is never allowed to keep. A plan that fits derives a fresh suite (rsi-exam-gate/hmac-seeds/1), disjoint from the visible seeds and every earlier suite, and leaves the line provisional.
- A confirmation re-verifies the provisional line from its evidence before resolving it: digests unchanged, minimum effect re-resolved, plan recomputed, exclusion set rebuilt, suite re-derived from the key, results covering exactly the suite.
- Replay mode (--confirm inconclusive) keeps the screening-only rule for shadow replay and fixtures and refuses to share a log with gated lines.
- Seven new line keys (confirm_policy, profile_sha256, look_index, parent_method_tree_sha256, candidate_method_tree_sha256, sizing, suite), carried at the end of the TRACE confidence block; the converter re-checks every gated rule and refuses a suite derived for another rollout.
- End-to-end test on the task's own evaluator: screening, freezing, planning, suite derivation, two runner evaluations with receipts, confirmation, and conversion.
- Contract, roadmap, README, and layout updated, including the limits the record does not cover.

## Why
Eight adaptively reused visible seeds are screening evidence, not acceptance evidence. A keep has to rest on a frozen candidate measured on seeds disjoint from the ones the search has already used, with every number tied to the exact method, suite, and evaluator by digest. This lands that rule and refuses the ways it can be bypassed: agent-chosen thresholds, a candidate or parent edited after the freeze, a missing or altered receipt, a result that does not cover the suite, a suite that does not re-derive, a second open provisional, and a confirmation too small to detect the effect it claims.

## Verification
python3 -m unittest discover -s tests -t . (148 tests, OK); pyright gate profile tests (0 errors); both end-to-end cases are deterministic on the pinned fixture files, and the tamper matrix refuses each tampering with nothing appended."
```

---

## Final gate before handing back (executor)

STOP here until both pull requests report `MERGED`. Do not run the rest of this section on an unmerged branch, and do not merge them yourself unless the operator asked you to.

- [ ] Both pull requests are merged (`<A>` and `<B>` are their numbers):

```bash
gh pr view <A> --json state,mergeCommit
gh pr view <B> --json state,mergeCommit
```
Expected: `"state": "MERGED"` and a merge commit hash on each. Record both hashes.

- [ ] `main` carries both merges:

```bash
git fetch origin main && git switch main && git reset --hard origin/main
git merge-base --is-ancestor <merge commit of A> HEAD && echo "A: in main"
git merge-base --is-ancestor <merge commit of B> HEAD && echo "B: in main"
```
Expected: both lines print.

- [ ] The suite and the type check pass on that `main`:

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -3
pyright gate profile tests
```
Expected: `Ran 148 tests`, `OK`, and `0 errors`. A different count means something did not land; STOP.

- [ ] The gate's own help lists the profile flag, and the other two entry points still run:

```bash
python3 gate/decide.py --help | grep -- --profile
python3 gate/seeds.py --help >/dev/null && python3 gate/evaluate_suite.py --help >/dev/null && python3 gate/restore.py --help >/dev/null && echo "entry points ok"
```
Expected: a line containing `--profile`, then `entry points ok`.

- [ ] The golden fixture never moved, measured from the baseline commit recorded in Task 1, Step 1:

```bash
git diff --exit-code "$BASELINE_SHA"..HEAD -- fixtures/valid
```
Expected: no output and exit 0.

- [ ] No bytecode is tracked, and none is left lying about:

```bash
git ls-files | grep -E '(__pycache__|\.py[co]$)'
find gate profile fixtures \( -name __pycache__ -o -name '*.pyc' -o -name '*.pyo' \) -print
```
Expected: the first command prints nothing (a match is a STOP). The second is informational: untracked caches from local runs are normal, and the digest functions ignore them; report what it prints.

- [ ] Report to the operator: the two pull request URLs, the merge commit hash of pull request B, the test count, whether Task 0 ran and what it recorded, and any STOP that fired. The TRACE repository's decision-log importer refuses log lines with unknown top-level keys and is re-derived from this repository's converter at a named commit, so the operator passes pull request B's merge hash on.

## Self-review notes (plan author)

- Spec coverage: the task profile and its fixed confirmation policy, the freeze of both snapshots, the planning rule and its no-keep consequence, fresh-seed derivation, the runner and its receipts, the re-derivation a confirmation performs, the restore helper, the contract additions, and the converter's re-checks are Tasks 1 to 9. Preflight is Task 0 and blocks nothing. The verifier's decision checks and the producer's cache-free digests are Milestone 2; mounting, the trusted driver, the program overlay, and the audit suite are Milestone 3. This milestone does not make a gated rollout runnable, and the roadmap says so.
- Type consistency: `file_sha256`, `method_files`, `method_tree_sha256`, `check_profile`, `load_profile`, `resolve_min_effect`, `derive_seeds`, `confirmation_size`, `write_suite`, `read_suite`, `receipt_path_for`, `check_output_path`, `restore`, and `build_line(..., confirm_policy, profile_sha256, look_index, parent_digest, candidate_digest, sizing, suite)` are named identically in every task that uses them. The line keys for the frozen digests are `parent_method_tree_sha256` and `candidate_method_tree_sha256`; the `build_line` keywords are `parent_digest` and `candidate_digest`.
- Every module and test file in Tasks 1 to 8 is given in full, so nothing depends on a surgical edit landing in the right place. The two files that change shape completely, `gate/decide.py` and `gate/trace_from_decisions.py`, are replaced whole together with their test modules, and each commit stages the module and its tests together so a half-applied change cannot pass.
- Known limitations, all stated in the contract rather than only here: coverage is per candidate with no rollout-wide error control; the replication key is readable inside the sandbox, so seeds are auditable rather than secret; the profile can be substituted inside the sandbox, and what makes that visible is the recorded profile digest compared against the operator's; the record is tamper-evident relative to the exported job directory, never tamper-proof.
