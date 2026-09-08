# Roadmap

What is built, what comes next, and how the pieces fit across the three repositories involved.
Milestone dates are targets. Everything here follows the rules in `CLAUDE.md`: standard library
only, fail loud, evidence outside the policy tree, cache-free digests, tamper-evident vocabulary,
one branch and pull request per task, tests and pyright clean before every push.

## Where things stand

| Piece | Status | Notes |
| --- | --- | --- |
| Provenance record: schema, producer, verifier, fixtures (`profile/`) | Built, profile v3 | Cache-free method-tree identity, the decision log carried and checked against its own bytes, every interval recomputed from its evidence, and all fourteen of the contract's section 4 checks. |
| Decision gate (`gate/decide.py`) and its modules | Built, 91 tests | Gated mode with a task profile, freezing, confirmation planning, fresh-suite derivation (`gate/seeds.py`), the evaluation runner with receipts (`gate/evaluate_suite.py`), cache-free method-tree digests (`gate/treedigest.py`), and the restore helper (`gate/restore.py`). Replay mode for shadow replay and fixtures. |
| TRACE converter (`gate/trace_from_decisions.py`) | Built, 17 tests | Re-checks every contract rule, including the gated ones, and carries the gated fields as extras. Output validates under the TRACE 0.5.1 typed models and schema and round-trips with every producer key preserved. |
| ProofPress import | Verified on fixture data against `main` | The evidence adapter accepts the 0.5.1 document, keeps four fields, refuses a malformed interval and an unpinned version, and is idempotent (`docs/RUN_REPORT.md`). |
| Decision-evidence report (`report/`) | Built | One row per decision from the record and the verifier's output, with the limits printed beside the table. |
| Real rollouts | Ten trials run (four `claude-haiku-4-5`, six `claude-opus-5`); the record builds for five | The job layout is in `docs/PREFLIGHT.md`. The rest of Milestone 3 below: the host-side shadow audit over these records, and four more trials under the program overlay. |

## Milestone 1: the gate, the runner, receipts, and the restore helper (built)

Status: Milestone 1 delivers the gate, the runner, receipts, and the restore helper. Running the gate
over real rollouts is Milestone 3, on the host after the rollout; an in-container instrument is
deferred to Milestone 4. The preflight observation is recorded in `docs/PREFLIGHT.md`.

**Preflight (first engineering task).** Docker up; a model key in the harness environment; a
short-budget `harbor` run of `game2048_policy_search`; observe the real job layout (where the
trajectory, the methods tree, the reward file, and `visible_result.json` land; whether
`__pycache__` is present). The layout is recorded in `docs/PREFLIGHT.md`. The job directory stays
outside the repository; the trajectory is bound by digest and never committed.

**Gate remainder** (`gate/decide.py`, contract additions under the same schema id):

- `--profile <task profile json>`: direction, unit, `min_effect` (must be positive), level,
  resamples, replication and audit keys; `profile_sha256` on every line.
- `--confirm always|inconclusive`: `confirm_policy` on every line; `always` is the default for
  gated runs, `inconclusive` is retained for shadow replay only.
- `freeze`: records `candidate_method_tree_sha256` before confirmation seeds are derived;
  `look_index` on the line.
- `gate/seeds.py`: deterministic fresh-suite derivation from rollout id, candidate digest, look
  index, and the committed key; disjoint from the visible suite and every earlier suite; writes
  `{"max_moves", "seeds"}`; `suite {locator, sha256, derivation}` on the line.

**Runner and receipts** (`gate/evaluate_suite.py`): evaluates a named policy on a named suite
with the self-check's CPU limit, records CPU use, and writes a receipt next to each result
(policy method-tree digest, suite digest, result digest, metric, evaluator digests, CPU seconds,
timestamp). Receipt digests enter `evidence` under the `receipt-parent` and `receipt-candidate`
roles. Receipts are required on gated runs and are a coverage note on official-protocol
rollouts.

Acceptance: end-to-end tests on the fixture lineage for every flag and refusal; the contract
document updated in the same pull request; pyright clean.

## Milestone 2: the record, the verifier, the report (built)

Status: the producer, the verifier's checks, the golden fixtures, the conformance matrix and
the report are built. Three fixtures cover the three shapes a rollout takes: `fixtures/valid`
for a rollout that ran no gate, `fixtures/gated` for replay mode, and `fixtures/gated_mode`
for a rollout the gate really ran in gated mode, with the runner's own receipts and every
gated field a value rather than a null. What remains belongs to Milestone 3: the run report
regenerated on a real record.

**Producer** (`profile/build_capsule.py`): method-tree digest per snapshot and for `main/`
excluding `__pycache__/`, `*.pyc`, `*.pyo` (`source.exclusions` recorded; full tree digest
alongside); submitted version by method-tree equality; an ambiguous match fails unless
`methods/results/final_selection.json` names one candidate; `decisions[]` per version with
`log_line`, `kind`, `resolves_log_line`; `source.decision_log` bound by digest; status from the
resolved decision state (`provisional` is a status; a provisional resolved by a revert
replication is `reverted`).

**Verifier** (`profile/verify_capsule.py`): the `decision:*`, `receipt:*`, `protocol:*`,
`identity:ambiguous`, `log:score_mismatch`, and `semantic:final:method_tree_mismatch` checks
listed in `docs/decision-log-contract.md` section 4, with integrity, protocol, and coverage
reported separately.

**Golden fixture**: results under `results/<id>/`, snapshots pure, the golden record regenerated
with the new producer, the 38-case suite green.

**Conformance matrix** (`tests/conformance/`): adversarial documents (duplicate roles,
digest-list disagreement, non-canonical locators, lower-is-better orientation, aliased holdout,
descendant of an open provisional, replication reduction, ambiguous submission, mixed contracts
under 0.5.1), each with the expected outcome for the gate loader, the converter,
`trace-mcp validate`, the profile verifier, and the ProofPress adapter at a pinned commit. These
are the normative vectors that hold the three implementations together; nobody copies code
between repositories.

**Decision-evidence report** (`report/`): one row per decision event from the verifier's output
plus the record (rollout id and version id together, parent, score, interval, verdict, action,
confirmed by, digests checked). It assists a human audit and never claims to answer whether a
score moved for a real reason.

## Milestone 3: the record on real rollouts, and a host-side shadow audit (target: September 2026)

Status: ten real rollouts exist (four `claude-haiku-4-5` preflight trials, six `claude-opus-5`
trials through a gateway); after the lineage fixes below the record producer builds five of them,
and refuses the rest for reasons their logs carry (no log, a log with no rows, a snapshot the log
never names, a version whose disposition the log never states). A second-model review of the
in-container gate design found that a driver sharing the agent's container is not a trust boundary
and that a confirmation suite derived from a key the agent can read is not a holdout, so the
in-container gate is withdrawn in its strong form and deferred to Milestone 4. Milestone 3 is the
part that carries no in-rollout trust problem:

- **Record lineage.** Version ids may carry a lowercase suffix (`v1a`); ordinals follow the order
  the experiment log declares versions; a parent the log declares but never snapshotted is recorded
  in `unsnapshotted_parent_ids`. A missing or truncated log stays a refusal.
- **Runbook and program overlay** (`runbook/`): the gateway run script, a fail-loud cost script, a
  replay-configuration generator, the runbook, and our copy of the program text with the
  conventions the record depends on (snapshot the inherited `main/` as `v0`, name snapshots
  `v<N>`, log a version immediately after snapshotting it, state parent and disposition). A run
  under the overlay is a modified-program run.
- **Host-side shadow audit** (`gate/shadow_replay.py`). After a rollout, on the operator's machine,
  the gate runs over the record-recoverable candidate-parent pairs of a verified record, with a
  replication key the agent never had, evaluating policy code inside a throwaway container. Per
  pair it reports why the gate ended where it did (screening below, exploratory, confirmed keep or
  revert, or a named failure) and, over comparable record-backed pairs, a descriptive and
  directionless agree or disagree count against the disposition the agent recorded. Its inputs
  manifest is committed and pushed before any evaluation. It is a shadow audit, not an in-rollout
  gate; its pairs are record-recoverable tuples, not the agent's action history; and it does not
  authenticate anything that happened inside the rollout.
- **Diagnostics** (`gate/calibrate.py`): the gate's rule simulated on synthetic paired deltas so
  that a replay configuration's floor, cap and minimum effect are chosen with their consequences in
  view. Under the accepted planning rule a candidate whose per-seed spread is large relative to the
  minimum effect plans far more confirmation seeds than any cap allows and is reverted as
  exploratory; the audit reports that as a finding about the rule, and a change to the rule is a
  separate proposal.
- **A descriptive campaign**: four `claude-opus-5` trials under the overlay, one at a time under a
  spend guard, reported as counts (records built, `v0` present, log present) beside the earlier
  trials as non-comparable context, then audited the same way. No rate, reliability, or efficacy
  claim.
- `docs/PREFLIGHT.md` carries the record's outcome over every real rollout, the audit tables with
  their coverage denominators, and the limits.

## Milestone 4: a cooperative in-container instrument (deferred, undecided)

An in-container gate can only be a cooperative instrument, and only with the mechanical fixes the
review named: the gate and its profile mounted read-only as one directory outside the artifact
root; confirmation seeds from fresh entropy rather than a mounted key; an enforced state machine
(one accepted head, a parent that must equal it, one-time version ids, `main/` validated after
every evaluation and last of all); a crash-safe restore; a privilege drop and a per-move limit in
the runner; rendered-compose checks that the network mode survives the overlay. Its claim is
internal consistency of the exported record; it never establishes that the recorded evaluations
occurred as described. Whether to build it is an open decision, taken after Milestone 3 reports.

A comparative study comes only after RSI-Exam expresses interest and with a preregistered
design; see `docs/overview.md`, section 7.

## How the three repositories fit

- **One semantic model, three projections.** `methods/decisions.jsonl`
  (`rsi-exam-decision-log/v1`, written by the gate) is the source of truth. The `confidence`
  block on a TRACE decision and the record's `decisions[]` are projections; the contract document
  states each mapping. This repository owns the contract.
- **ProofPress** is an evidence-indexing consumer. It reads four keys (`interval`, `method`,
  `sample_size`, `evidence_digests`), drops the rest, and creates no claim or admission. The
  profile verifier is the semantic authority.
- **TRACE** carries the document as a valid 0.5.1 session. TRACE 0.5.1 types the generic
  measurement keys in this contract's nested shape; the rule-state keys stay an identified
  extension, named by the `contract` key, that TRACE preserves but does not interpret, and TRACE's
  checks on the block are structural only (contract document, section 2). A decision-log importer
  in TRACE, if built, is keyed to this contract.
- **Version pin path.** TRACE released the typed model as 0.5.1 (release `v0.5.1`, commit
  `a97d4e81fb3b4ec5134e992882d28a6cf97fac04`, schema digest
  `ce7b5bf03b31ab669d12018b0d64fa2421d03b7e7ab2da156f98581e4d62c544`), ProofPress widened its exact
  version pin to accept 0.5.0 and 0.5.1 with a per-version release commit and schema digest
  (`chenmingtang830/proofpress` `0c6d26f`), and the converter now stamps `0.5.1`. That order is
  load-bearing: ProofPress refuses an unpinned version before projecting any event field, so a
  producer that stamps ahead of the consumer stops importing. On this release the order was not
  held. The converter's stamp merged before the consumer's acceptance did, and for part of a day
  this repository emitted documents ProofPress `main` refused. Nothing was lost because no rollout
  was running; the next release should have no such window.
- **Re-emitting a session under a changed stamp.** ProofPress records an imported session by
  identity and fails closed when the same session and event identities come back with changed
  content, so a document already imported under one `trace_version` cannot be re-imported under
  another. Sessions converted before this change keep the stamp they were imported with; only new
  conversions carry `0.5.1`.

## Changes to propose in ProofPress

All three are proposed; the version acceptance is merged.

Small, self-contained pull requests, each explaining the failure mode it closes:

1. ~~**Fixture correction.** The adapter's example document predates this contract, carrying an
   earlier worked-example interval, the method name `paired_bootstrap`, and the labels
   `parent_results` / `candidate_results`.~~ Regenerated from this repository's converter in
   ProofPress pull request 123.
2. ~~**Additive-tolerance guard.** A test that a `confidence` block carrying the full contract
   imports and projects to the same four keys, so a future adapter change cannot silently start
   rejecting the fuller record; one line in the adapter's documentation naming the `contract` key
   as the extension identifier.~~ Both in ProofPress pull request 123; the regenerated example
   carries twenty keys, which is what makes the guard real.
3. ~~**Version acceptance** for TRACE 0.5.1 alongside 0.5.0, with a per-version release commit
   and schema digest.~~ Merged as `0c6d26f`; `docs/RUN_REPORT.md` records the chain running end to
   end against it.

## Upstream

The offer to RSI-Exam and the asks are in `docs/overview.md`, section 8: the post-rollout verifier
and evidence report, the gate as an optional protocol step, the submitted method's digest inside
`reward.json`, a published digest per released job directory, per-seed visible results preserved
per snapshot, and a fix or note for the only-Python trap.
