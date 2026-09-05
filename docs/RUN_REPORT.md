# Run report: gate, converter, and ProofPress import on a demo lineage (2026-09-05)

Scope: a local proof that the decision gate, the decision-log to TRACE converter, TRACE 0.5.1
validation, and the ProofPress evidence adapter fit together. Everything below ran on one machine
against fixture data; no RSI-Exam rollout was executed, and nothing here shows that the gate improves
rollout outcomes.

This re-runs the chain first recorded on 2026-09-02, on the same lineage, after three pins moved:
TRACE released the typed `confidence` model as 0.5.1, ProofPress widened its exact version pin to
accept 0.5.0 and 0.5.1, and this converter now stamps `0.5.1`. Every interval, disposition, and
digest below reproduces the earlier run; what changed is the declared version and what the consumer
accepts. The gate also now requires an explicit `--confirm inconclusive` in replay mode, which the
2026-09-02 commands predate.

The 2026-09-04 run recorded here previously was made against the ProofPress branch that carried the
version acceptance, because it had not merged yet. It has now: this run is against ProofPress
`main`, and it is the first time the three repositories have run end to end at the same pins.

## What this report does and does not establish

Establishes:
- the gate applies the keep / revert / provisional rule and refuses to build on an unreplicated
  provisional decision;
- a replication on fresh evidence resolves the provisional decision;
- the converter's output validates under TRACE 0.5.1, both through `trace-mcp validate` and through
  a typed round-trip that leaves every `confidence` block byte-equal;
- ProofPress imports the 0.5.1 document, projects the four confidence fields its adapter reads
  (`interval`, `method`, `sample_size`, `evidence_digests`), records the wire version as `0.5.1`,
  refuses a malformed interval, refuses an unpinned version, and is idempotent on re-import;
- ProofPress fails closed when a session it has already imported comes back under a different
  version stamp with the same session and event identities.

Does not establish:
- that the interval has its nominal coverage on adaptively reused visible seeds (it is a screening
  statistic; acceptance rests on fresh-seed replication);
- that ProofPress verifies digests, recomputes intervals, or reads `estimate`, `verdict`,
  `min_effect`, locators, or `holdout` (its projection drops them);
- that TRACE interprets the rule-state keys (0.5.1 types the measurement only and preserves the
  rest without reading them);
- anything about hidden-set performance.

## Environment

- Python 3.12.10, standard library only for the gate and converter.
- TRACE at release `v0.5.1`, commit `a97d4e81fb3b4ec5134e992882d28a6cf97fac04`, whose
  `trace-v0.5.json` has SHA-256
  `ce7b5bf03b31ab669d12018b0d64fa2421d03b7e7ab2da156f98581e4d62c544`.
- ProofPress `main` at `0c6d26f`, the merge of pull request 122, used via
  `PYTHONPATH=<tree>/src python3 -m proofpress.cli`. That is the commit that added 0.5.1 to the
  adapter's accepted versions.
- Repository state: `346ec53`; `python3 -m unittest discover -s tests -t .` prints `Ran 255
  tests` and `OK`; `pyright` on `profile/`, `report/` and the tests reports 0 errors.

## Lineage

Result files in the exact shape of the task's `selfcheck.py` output (`instances[].seed`,
`instances[].score`, plus the other keys), eight visible seeds:

- `results/v1/visible_result.json`: the parent scores.
- `results/v2/visible_result.json`: every seed worse (deltas -410 to -180).
- `results/v3/visible_result.json`: two seeds carry the gain, three got worse (deltas +1310 to -300).
- `results/v3/replication/{parent,candidate}_result.json`: the fresh-seed replication
  (deltas +390 to +700).

## Commands and outputs

```
$ DECIDE_FIXED_TIMESTAMP=2026-09-05T04:01:00+00:00 python3 gate/decide.py --methods $M \
    --version v2 --parent v1 --confirm inconclusive
verdict below, disposition revert, interval {level: 0.9, lower: -382.5, upper: -258.75}

$ DECIDE_FIXED_TIMESTAMP=2026-09-05T04:02:00+00:00 python3 gate/decide.py --methods $M \
    --version v3 --parent v1 --confirm inconclusive
verdict inconclusive, disposition provisional, interval {level: 0.9, lower: -30.0, upper: 583.75}

$ python3 gate/decide.py --methods $M --version v4 --parent v3 --confirm inconclusive
gate refused: parent v3 carries an unreplicated provisional decision (line 2); replicate it before building on it
exit=3

$ DECIDE_FIXED_TIMESTAMP=2026-09-05T04:03:00+00:00 python3 gate/decide.py --methods $M \
    --version v3 --parent v1 --replicates v3 --confirm inconclusive
verdict clears, disposition keep, interval {level: 0.9, lower: 467.5, upper: 575.0}, replicates v3

$ python3 -c "..."   # dispositions in decisions.jsonl
['revert', 'provisional', 'keep']

$ python3 gate/trace_from_decisions.py $M/decisions.jsonl --project rsi-exam-provenance \
    --rollout demo-rollout --task game2048_policy_search --harness claude-code --model claude-opus-5 \
    --output trace_session.json

$ python3 -c "..."   # the document's decision events
trace_version: 0.5.1 | events: 3
evt_001 rejected  revises None     note "Interval entirely below zero."
evt_002 accepted  revises None     note "Resolved by replication evt_003."
evt_003 accepted  revises evt_002  note None
summary: RSI-Exam rollout demo-rollout (game2048_policy_search, claude-code, claude-opus-5): 0 kept, 1 reverted, 1 provisional, 1 replicated.

$ python3 -m trace_mcp.server validate trace_session.json      # TRACE at v0.5.1
  PASS  trace_session.json
1/1 files valid.

$ python3 - trace_session.json   # Session.model_validate -> model_dump_json, TRACE at v0.5.1
confidence present after typed round-trip: [True, True, True] | byte-equal blocks: [True, True, True]

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import trace_session.json      # inside a fresh git repository
{'ok': True, 'events_added': 6, 'evidence': ['evd_39b12bb5b91a6c50', 'evd_3fddc6c91e67c9f0', 'evd_48169c64cf58d481']}

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import trace_session.json      # second import
events_added 6 | evidence 3        # the ledger does not grow

$ PYTHONPATH=$PP python3 - <<'PY'   # proofpress.kernel.operations.v2_projection()
decision source rows: 3 | schema: {'0.5.1'}
evt_001 rejected | revises None | confidence: {"evidence_digests": {...}, "interval": {"level": 0.9, "lower": -382.5, "upper": -258.75}, "method": {"name": "percentile_bootstrap", "resamples": 5000}, "sample_size": 8}
evt_002 accepted | revises None | confidence: {..., "interval": {"level": 0.9, "lower": -30.0, "upper": 583.75}, ...}
evt_003 accepted | revises trace:rsiexam_demo-rollout#evt_002 | confidence: {..., "interval": {"level": 0.9, "lower": 467.5, "upper": 575.0}, ...}
conclusions: {} | admissions: {}
history envelopes: True | ledger events: 6
PY

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import malformed.json      # interval.lower set above upper
proofpress: error: TRACE decision confidence interval.lower must not exceed interval.upper

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import v052.json           # trace_version "0.5.2"
proofpress: error: unsupported TRACE trace_version: 0.5.2; accepted: 0.5.0, 0.5.1

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import restamped.json      # same session, stamped 0.5.0 after the 0.5.1 import
proofpress: error: immutable source_recorded conflict for src_8156a6c441184e3c
```

## Observations worth carrying forward

1. ProofPress's projection keeps only the four fields its adapter validates; `method.algorithm`,
   `method.seed`, `estimate`, `min_effect`, `verdict`, `direction`, `evidence` (with locators), and
   `holdout` are dropped from the evidence record. Anyone reading the ProofPress ledger alone sees an
   interval and digests, not the rule that produced the decision. The TRACE document and the
   rollout record carry the rest.
2. The `trace_version` pin is still exact; it is now a two-entry allowlist rather than one value,
   and each entry names the upstream release commit and that release's schema digest. An unpinned
   version is refused before any event field is projected. The next TRACE release needs the same
   coordination, in the same order: consumer first, producer second. That order was not held on this
   one. The converter's stamp merged before the consumer's acceptance did, so for part of a day this
   repository emitted documents ProofPress `main` refused. Nothing was lost, because no rollout was
   running, but the window was real and the next release should not have one.
3. A session already imported under one `trace_version` cannot be re-imported under another. The
   identities are unchanged but the recorded content is not, so the immutable source rule refuses
   it. This is the right behavior and it means the version stamp is a property of a converted
   document, not something to be revised in place: sessions converted before this change keep the
   stamp they were imported with, and only new conversions carry `0.5.1`.
4. The gate's worked example reproduces `[-30.0, 583.75]` (rounded `583.8` in the planning notes) with
   `seed 20260902`, `5000` resamples, and the index-floor quantile rule named
   `rsi-exam-gate/percentile-bootstrap/1`.
