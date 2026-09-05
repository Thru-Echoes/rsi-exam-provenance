# Conformance vectors

One adversarial decision log per vector, and what each implementation must do with it.

These are the normative examples that hold three repositories together. Nobody copies code between
the gate, TRACE and ProofPress; they agree because they agree about these documents. When an
implementation changes, the vector that changes with it is the record of what was decided.

Every vector is **one mutation of `valid_baseline`**, which is the gated fixture's own decision log
(a revert on an interval entirely below zero, a provisional on an inconclusive one, and the
replication that resolves it). A difference in outcome is therefore attributable to the mutation and
nothing else.

## Shape

```json
{
  "description": "what the document does",
  "why": "why an implementation should care",
  "expect": {
    "gate_loader": "accept" | "reject",
    "converter": "accept" | "reject",
    "profile_verifier": "accept" | "reject",
    "trace_mcp_validate": "accept" | "reject" | "n/a",
    "proofpress_adapter": "accept" | "reject" | "n/a"
  },
  "lines": [ ... the decision log ... ]
}
```

`n/a` means the document never reaches that implementation, because something upstream refuses it
first. It is not a way to avoid stating an expectation.

## The three that run here

`tests/test_conformance.py` runs them on every vector:

- **`gate_loader`** — `gate/decide.py:read_log`. Would the gate accept this log as one it could
  append to?
- **`converter`** — `gate/trace_from_decisions.py:build_session`, which re-checks every contract
  rule on read.
- **`profile_verifier`** — the log is put in place of the gated fixture's own, a record is built
  with `profile/build_capsule.py`, and `profile/verify_capsule.py` verifies it. The vectors are
  mutations of that fixture's log, so the evidence they name is really there.

```sh
python3 -m unittest tests.test_conformance -v
```

## The two that run elsewhere

Both consume the TRACE document the converter produces, so run the converter first:

```sh
python3 gate/trace_from_decisions.py <(python3 - <<'PY'
import json, sys
print("\n".join(json.dumps(l) for l in
      json.load(open("tests/conformance/vectors/<name>.json"))["lines"]))
PY
) --project conformance --rollout conformance --task game2048_policy_search \
  --harness test --model none --output /tmp/<name>.trace.json
```

- **`trace_mcp_validate`** — in a checkout of TRACE at the release this repository pins:
  `python3 -m trace_mcp.server validate /tmp/<name>.trace.json`.
- **`proofpress_adapter`** — in a checkout of ProofPress, inside a fresh git repository:
  `PYTHONPATH=<proofpress>/src python3 -m proofpress.cli evidence import /tmp/<name>.trace.json`.

`docs/RUN_REPORT.md` records the pinned revisions those two were last run at.

## Why the vectors that separate implementations matter most

`lower_is_better_orientation` is the one to read first. The converter **accepts** it: nothing about
the line's shape is wrong. The profile verifier **refuses** it, because it recomputes the interval
from the evidence and the deltas under that orientation are not the ones the line records. That
split is the point of having both.

`non_canonical_locator` was the first thing this matrix found. The converter refused a locator with
dot segments and the profile verifier accepted it, because resolving the path reached the same file
and the digest matched. One document, two readings. The verifier now applies the same rule.

## Changing an expectation

An expectation is a record of what was decided, not a description of current behaviour. Changing one
to match a change in an implementation is a contract decision, and the pull request that does it
should say which implementation changed and why the new outcome is the right one. A test refuses a
vector that every implementation accepts, because relaxing an expectation until nothing refuses the
document is the shape this mistake takes.
