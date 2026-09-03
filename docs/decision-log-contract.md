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
  `upper = means[floor((1 - alpha) * resamples) - 1]` with `alpha = (1 - level) / 2`;
  `estimate` = the mean of the deltas (recorded, not asserted to lie inside the interval).
- **Verdict**: `clears` when `interval.lower > min_effect`; `below` when `interval.upper < 0`;
  otherwise `inconclusive` (which includes an interval that is entirely positive but under the
  minimum effect). `min_effect >= 0`; every number finite.
- **Disposition on a non-replication line**: `below` gives `revert`; `clears` gives `keep`, or
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

### Planned additions (same schema id until a real rollout record exists)

`profile_sha256` (the task profile that fixed `direction`, `unit`, `min_effect`, level, resamples,
and the seed-derivation key), `confirm_policy` (`always` or `inconclusive`), `look_index` (count
of confirmations in the rollout), `candidate_method_tree_sha256` (frozen before confirmation seeds
are derived), `suite {locator, sha256, derivation}` for confirmation and audit suites, and receipt
digests in `evidence`.

## 2. The `confidence` block on a TRACE decision

Keys in this order: `interval`, `method`, `sample_size`, `evidence_digests` (the four keys the
ProofPress evidence adapter reads and keeps), then `contract` (this schema id), `statistic`, `unit`,
`direction`, `estimate`, `min_effect`, `verdict`, `evidence`, `holdout`. Unknown keys are ignored
by ProofPress; the generic measurement keys are what TRACE would type first; the rule-state keys
remain an identified extension until then.

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
`0.5.0` (the document is valid under the shipped TRACE 0.5.0 schema; `confidence` is an additive
property there).

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
algorithm), `receipt:missing` and `receipt:mismatch` (integrity failures on gated runs, coverage
notes on official-protocol rollouts), `protocol:stacked_provisional`,
`protocol:unresolved_provisional_submitted`, `protocol:kept_against_verdict`,
`protocol:unconfirmed_keep`, `protocol:action_contradiction` (experiment-log status or final tree
contradicts the resolved decision), `identity:ambiguous` (more than one snapshot matches `main/`
and no selection receipt names one), and `log:score_mismatch` (a parseable experiment-log score
differs from the bound result's mean by more than half a unit of its last printed decimal).
