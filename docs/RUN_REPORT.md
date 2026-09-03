# Run report: gate, converter, and ProofPress import on a demo lineage (2026-09-02)

Scope: a local proof that the decision gate, the decision-log to TRACE converter, TRACE 0.5.0
validation, and the ProofPress evidence adapter fit together. Everything below ran on one machine
against fixture data; no RSI-Exam rollout was executed, and nothing here shows that the gate improves
rollout outcomes.

## What this report does and does not establish

Establishes:
- the gate applies the keep / revert / provisional rule and refuses to build on an unreplicated
  provisional decision;
- a replication on fresh evidence resolves the provisional decision;
- the converter's output validates under the published TRACE 0.5.0 schema and survives a typed
  round-trip through the TRACE models with the `confidence` block unchanged;
- ProofPress `main` at `e911b34` imports the document, projects the four confidence fields its
  adapter reads (`interval`, `method`, `sample_size`, `evidence_digests`), refuses a malformed
  interval, refuses a document declaring `trace_version` `0.5.1`, and is idempotent on re-import.

Does not establish:
- that the interval has its nominal coverage on adaptively reused visible seeds (it is a screening
  statistic; acceptance rests on fresh-seed replication);
- that ProofPress verifies digests, recomputes intervals, or reads `estimate`, `verdict`,
  `min_effect`, locators, or `holdout` (its projection drops them);
- that TRACE has adopted a typed `confidence` field (the block is an additive extra under 0.5.0);
- anything about hidden-set performance.

## Environment

- Python 3.12.10, standard library only for the gate and converter.
- TRACE at `~/Developer/TRACE` (`origin/main` `f5e60fa`), invoked with `uv run trace-mcp validate`.
- ProofPress `origin/main` `e911b34` extracted with `git archive` and used via
  `PYTHONPATH=<tree>/src python3 -m proofpress.cli`.
- Repository state: commits `00fd7ca` (seed), `f1e1c13` (gate and converter), and the evidence-location fix; `python3 -m unittest
  discover -s tests -t .` prints `Ran 70 tests` and `OK`; `pyright` on `gate/` and the two new test
  files reports 0 errors.

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
$ DECIDE_FIXED_TIMESTAMP=2026-09-03T18:01:00+00:00 python3 gate/decide.py --methods $M --version v2 --parent v1
verdict below, disposition revert, interval {lower: -382.5, upper: -258.75, level: 0.9}

$ DECIDE_FIXED_TIMESTAMP=2026-09-03T18:02:00+00:00 python3 gate/decide.py --methods $M --version v3 --parent v1
verdict inconclusive, disposition provisional, interval {lower: -30.0, upper: 583.75, level: 0.9}

$ python3 gate/decide.py --methods $M --version v4 --parent v3
gate refused: parent v3 carries an unreplicated provisional decision (line 2); replicate it before building on it
exit=3

$ DECIDE_FIXED_TIMESTAMP=2026-09-03T18:03:00+00:00 python3 gate/decide.py --methods $M --version v3 --parent v1 --replicates v3
verdict clears, disposition keep, interval {lower: 467.5, upper: 575.0, level: 0.9}, replicates v3

$ python3 -c "..."   # dispositions in decisions.jsonl
['revert', 'provisional', 'keep']

$ python3 gate/trace_from_decisions.py $M/decisions.jsonl --project rsi-exam-provenance \
    --rollout demo-rollout --task game2048_policy_search --harness claude-code --model claude-opus-5 \
    --output trace_session.json
evt_001 rejected  Revert v2 (parent v1)                       revises None     note "Interval entirely below zero."
evt_002 accepted  Keep v3 provisionally (parent v1)           revises None     note "Resolved by replication evt_003."
evt_003 accepted  Replication of v3 on fresh seeds (parent v1) revises evt_002  note None
summary: RSI-Exam rollout demo-rollout (game2048_policy_search, claude-code, claude-opus-5): 0 kept, 1 reverted, 1 provisional, 1 replicated.

$ (cd ~/Developer/TRACE && uv run trace-mcp validate trace_session.json)
1/1 files valid.

$ (cd ~/Developer/TRACE && uv run python - trace_session.json)   # Session.model_validate -> model_dump_json
confidence present after typed round-trip: [True, True, True] | byte-equal blocks: [True, True, True]

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import trace_session.json      # inside a fresh git repository
{'ok': True, 'events_added': 6, 'evidence': ['evd_0b475c066a0bddb1', 'evd_1995585e077ce309', 'evd_ab770d77d63315df']}

$ PYTHONPATH=$PP python3 - <<'PY'   # proofpress.kernel.operations.v2_projection()
decision source rows: 3 | schema: {'0.5.0'}
evt_001 rejected | revises None | confidence: {"evidence_digests": {...}, "interval": {"level": 0.9, "lower": -382.5, "upper": -258.75}, "method": {"name": "percentile_bootstrap", "resamples": 5000}, "sample_size": 8}
evt_002 accepted | revises None | confidence: {..., "interval": {"level": 0.9, "lower": -30.0, "upper": 583.75}, ...}
evt_003 accepted | revises trace:rsiexam_demo-rollout#evt_002 | confidence: {..., "interval": {"level": 0.9, "lower": 467.5, "upper": 575.0}, ...}
conclusions: {} | admissions: {}
PY

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import malformed.json      # interval.lower set above upper
proofpress: error: TRACE decision confidence interval.lower must not exceed interval.upper
exit=2

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import v051.json           # trace_version "0.5.1"
proofpress: error: unsupported TRACE trace_version: 0.5.1
exit=2

$ PYTHONPATH=$PP python3 -m proofpress.cli evidence import trace_session.json  # third import
events before 6 after 6 | evidence ids ['evd_0b475c066a0bddb1', 'evd_1995585e077ce309', 'evd_ab770d77d63315df']

$ PYTHONPATH=$PP python3 - <<'PY'   # verify_history_envelopes
{'ok': True, 'events': 6, 'head': 'sha256:05e134bf...'}
PY
```

## Observations worth carrying forward

1. ProofPress's projection keeps only the four fields its adapter validates; `method.algorithm`,
   `method.seed`, `estimate`, `min_effect`, `verdict`, `direction`, `evidence` (with locators), and
   `holdout` are dropped from the evidence record. Anyone reading the ProofPress ledger alone sees an
   interval and digests, not the rule that produced the decision. The TRACE document and the
   rollout record carry the rest.
2. The `trace_version` pin is exact (`0.5.0`). A document stamped `0.5.1` is refused before any
   field is read. Coordination item, not a defect in either repository.
3. The gate's worked example reproduces `[-30.0, 583.75]` (rounded `583.8` in the planning notes) with
   `seed 20260902`, `5000` resamples, and the index-floor quantile rule now named
   `rsi-exam-gate/percentile-bootstrap/1`.
