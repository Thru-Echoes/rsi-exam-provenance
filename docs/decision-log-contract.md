# The decision-log contract (`rsi-exam-decision-log/v1`)

One semantic model, three projections: the decision-log line (the source of truth, written by the
gate), the `confidence` block on a TRACE decision (written by the converter), and the `decisions[]`
entries on a version in the provenance record (written by the producer). This page defines the
line and the two projections. Every rule is enforced by the gate on write and by the converter on
read; the verifier re-checks them against the bound files.

## 1. The line

One JSON object per physical line, appended, never edited. Locators are relative to the `methods/`
directory.

```json
{"schema": "rsi-exam-decision-log/v1", "line": 3, "timestamp": "2026-09-03T18:03:00+00:00",
 "version_id": "v3", "parent_id": "v1", "replicates": "v3",
 "statistic": "mean_paired_delta", "unit": "game_score", "direction": "higher",
 "estimate": 518.75,
 "interval": {"lower": 467.5, "upper": 575.0, "level": 0.9},
 "method": {"name": "percentile_bootstrap", "algorithm": "rsi-exam-gate/percentile-bootstrap/1", "resamples": 5000, "seed": 20260902},
 "sample_size": 8, "min_effect": 0.0, "verdict": "clears", "disposition": "keep",
 "evidence": [
   {"role": "parent", "locator": "results/v3/replication/parent_result.json", "sha256": "<64 hex>"},
   {"role": "candidate", "locator": "results/v3/replication/candidate_result.json", "sha256": "<64 hex>"}],
 "evidence_digests": {"parent": "sha256:<64 hex>", "candidate": "sha256:<64 hex>"},
 "holdout": null}
```

### Rules

- `line` equals the physical 1-based position; no blank lines; `timestamp` is timezone-aware.
- **Algorithm** `rsi-exam-gate/percentile-bootstrap/1`: seeds sorted ascending; delta = candidate
  minus parent per seed (negated when `direction` is `lower`, so a positive value always favours
  the candidate); resamples drawn with Python `random.Random(seed).choice` in the reference
  implementation's loop order; `lower = means[floor(alpha * resamples)]`,
  `upper = means[floor((1 - alpha) * resamples) - 1]` with `alpha = (1 - level) / 2`. **Both
  indices are computed in exact arithmetic, not binary floating point.** Through floats
  `(1.0 - 0.9) / 2.0` is a shade under `0.05`, so `int(alpha * 5000)` is `249` where this rule says
  `250`: an implementation that indexes in floats sits one order statistic below the specification
  at the level and resample count this project uses, and on suites of a few dozen seeds that moves
  the reported lower bound essentially every time. Take `alpha` from the decimal the level is
  written as (`(Fraction(1) - Fraction(str(level))) / 2`) and index with that.
  `estimate` = the mean of the deltas (recorded, not asserted to lie inside the interval).
- **Verdict**: `clears` when `interval.lower > min_effect`; `below` when `interval.upper < 0`;
  otherwise `inconclusive` (which includes an interval that is entirely positive but under the
  minimum effect). `min_effect >= 0`; every number finite.
- **Disposition on a non-replication line**: an exploratory confirmation plan (gated mode; see "Confirmation size") takes precedence and gives `revert`; otherwise `below` gives `revert`; `clears` gives `keep`, or
  `provisional` when the gate runs with confirmation required or a `holdout` block is present and
  does not clear; `inconclusive` gives `provisional`.
- **Replication line**: `replicates == version_id`, the same `parent_id` as the open provisional
  line for that version; it resolves that line. `clears` (and a clearing `holdout` if present)
  gives `keep`; anything else gives `revert`; never `provisional`.
- **One at a time**: at most one provisional line is unresolved; a line that builds on a version
  whose provisional decision is open is refused; a line that would open a second is refused.
- **Evidence**: roles from the closed vocabulary `parent`, `candidate`, `holdout-parent`,
  `holdout-candidate`, `receipt-parent`, `receipt-candidate`; unique; `parent` then `candidate`
  first. Locators are canonical relative POSIX paths (no leading slash, backslash, percent escape,
  drive prefix, or dot segment) and never under `versions/` or `main/`.
  `evidence_digests == {role: "sha256:" + sha256}`.
- **`holdout`** (optional): the same measurement on a second suite, `{estimate, interval,
  sample_size, verdict, evidence, evidence_digests}`, under the same `min_effect` and the same
  level; its evidence digests must differ from the primary evidence.
- **Writing**: one line per `os.write` on an `O_APPEND` descriptor. `DECIDE_FIXED_TIMESTAMP`
  injects the clock for fixtures.

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
  z}`, or `null` on a line that plans no confirmation. When the profile selects the `estimate-aware`
  planning rule the plan also carries `planning_rule`, `planning_effect` and `screening_mean`, and
  `rule` names that rule; a plan without them was made under the accepted rule.
- `suite`: `null`, or `{locator, sha256, derivation}` for the confirmation suite the screening line
  derived (`results/<version_id>/replication/seeds.json`, a file of the shape `{"max_moves": N,
  "seeds": [...]}` that the task evaluator reads), repeated unchanged on the confirmation line.
  `derivation` records `algorithm` (`rsi-exam-gate/hmac-seeds/1`), `rollout_id`,
  `candidate_method_tree_sha256`, `look_index`, `size`, and `max_moves`.

**Method-tree digest.** SHA-256 over the lines `<sha256 of file><two spaces><posix relpath>\n`,
sorted by relpath, over the `.py` files under the directory.

The rules and their order are the grader's, read from `tests/policy_sandbox.py` in the task at the
pinned dataset revision. Its `_stage_policy` skips any path with a `__pycache__` component and any
`*.pyc` or `*.pyo` file **first**, then refuses a symlink, then refuses any remaining file that is
not a regular `.py`, and caps the staged source at 10 MB in total. Two consequences follow from the
ordering, and both matter: a `.py` file under `__pycache__` is not staged and is not an error, and
neither is a symlink there. A regular non-`.py` file elsewhere in the tree is refused, because the
grader refuses it and such a submission scores 0.0.

The digest equals the provenance record's full-tree digest for a Python-only tree without caches.

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
normal quantile for the level, `planned` is the smallest `n` with `z s / sqrt(n) < e / 2`, at least
`floor`, where `e` is the planning effect: `min_effect` under the accepted rule, and
`max(min_effect, screening_mean - min_effect)` under the `estimate-aware` rule a profile may select
with `confirmation.planning_rule`; `size = min(planned, max_seeds)`; `exploratory` is `true` when the cap binds. It
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
code could write to files the agent can write to; the grader's own sandbox drops privileges to an unprivileged user; the host-side shadow audit runs the
runner inside a throwaway container with no network and the operator's uid instead, and a privilege drop and a grader-equivalent per-move limit in the runner remain undone: the in-rollout instrument (the instrument overlay) runs the runner and this gate inside the agent's container as the agent's user, with the profile and its key readable there, and it cannot close a confirmation the runner refuses, because this contract resolves a provisional decision only by a confirmation line; the post-rollout verifier's comparison of every line's and receipt's profile_sha256 with the operator's copy remains the check that the intended profile was used. The runner publishes the result and then the receipt as two files; a
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
anywhere in this contract. `audit_key_sha256` is recorded now; nothing consumes it yet, and a replay
configuration fills it with the digest of a documented literal.

## 2. The `confidence` block on a TRACE decision

Keys in this order: `interval`, `method`, `sample_size`, `evidence_digests` (the four keys the
ProofPress evidence adapter reads and keeps), then `contract` (this schema id), `statistic`, `unit`,
`direction`, `estimate`, `min_effect`, `verdict`, `evidence`, `holdout`, `confirm_policy`,
`profile_sha256`, `look_index`, `parent_method_tree_sha256`, `candidate_method_tree_sha256`,
`sizing`, `suite`. Unknown keys are ignored by ProofPress. The generic measurement keys
(`interval`, `method`, `sample_size`, `evidence_digests`, `contract`, `statistic`, `unit`,
`direction`, `estimate`, `evidence`) are the part TRACE types, in exactly this nested shape, as of
TRACE 0.5.1; a document is a valid 0.5.1 session whose measurement is typed and whose remaining
keys are a preserved extension. The rule-state keys (`min_effect`, `verdict`, `holdout`) and the gated keys
(`confirm_policy`, `profile_sha256`, `look_index`, `parent_method_tree_sha256`,
`candidate_method_tree_sha256`, `sizing`, `suite`) remain an identified extension that TRACE
preserves but does not interpret. TRACE's own checks on the block are structural only: ordered
interval bounds, a level in the open unit interval, a positive sample size, finite numbers,
well-formed digests, a role on every evidence entry, and `evidence_digests` keys equal to the
evidence roles. The verdict and disposition rules are checked by the gate on write and the
converter on read, and by the profile verifier (section 4), never by TRACE.

Event mapping: one `decision` event per line; `proposed_by` = the rollout agent
(`{"type": "ai", "id": "<harness>:<model>", "role": "rollout-agent"}`); `resolved_by` = the gate
(`{"type": "system", "id": "rsi-exam-gate/decide.py", "role": "decision-gate"}`); `keep` =
`accepted`; `revert` = `rejected` with `revision_note` "Interval entirely below zero." or
"Replication did not clear the minimum effect."; `provisional` stays `proposed` until the
replication event revises it (`revises_event_id`), after which the original is resolved with
"Resolved by replication evt_NNN."; `rationale` is built from the line's own numbers by a fixed
template; `tags` = `["rsi-exam", "decision-gate", "<version_id>"]`. Session metadata: `project`,
`project_key`, `experiment_id` = rollout id, `participants` = both actors, `custom` = `{source,
importer, rollout_id, task, harness, model, decision_log_sha256, locator_base}`; `trace_version`
`0.5.1` (the document is valid under the TRACE 0.5.1 schema, which types the measurement keys of
`confidence` and preserves the rest).

## 3. The record's `decisions[]` per version

Every log line for the version, in order, each carrying `log_line`, `kind` (`screening` or
`confirmation`), the section 1 fields minus `statistic` and `unit` (inherited from the record's
benchmark block), and `resolves_log_line` on a confirmation. The version's status is derived from
the resolved state: a provisional resolved by a revert replication is `reverted`; an unresolved
provisional is `provisional` and cannot be `submitted` without a protocol failure. The record's
`source.decision_log` binds the log file by digest; `source.exclusions` records the cache paths
excluded from method-tree digests.

## 4. Verifier checks added for decisions

`decision:missing_for_kept_version`, `decision:log_line_mismatch`, `decision:verdict_inconsistent`,
`decision:disposition_inconsistent`, `decision:evidence_digest_mismatch`,
`decision:interval_not_reproducible` (recomputed from the bound result files under the recorded
algorithm), `decision:sizing_inconsistent` (the plan's `exploratory` flag does not equal `size < planned`, or an exploratory screening carries a suite), `receipt:missing` and `receipt:mismatch` (integrity failures on gated runs, coverage
notes on official-protocol rollouts), `protocol:stacked_provisional`,
`protocol:unresolved_provisional_submitted`, `protocol:kept_against_verdict`,
`protocol:unconfirmed_keep`, `protocol:action_contradiction` (experiment-log prose contradicts the
resolved decision), and `log:score_mismatch` (a parseable experiment-log score
differs from the bound result's mean by more than half a unit of its last printed decimal).

Snapshots that share a method tree are not disambiguated here. The grader cannot tell them apart
either, so the record names the whole class in `final_submission.version_ids` and the verifier
checks that class rather than a guess: `semantic:final:class_mismatch`,
`semantic:final:not_canonical`, and `identity:unrecorded_match` for a snapshot on disk that shares
the submitted method tree and is missing from the record.
