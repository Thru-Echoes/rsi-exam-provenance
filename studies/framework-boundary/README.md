# Capture--verify--govern boundary demonstration

This is E07: a **local synthetic integration demonstration**, separate from the
nine-fault Verify characterization. It uses the same fixture, not a second task
or a real rollout. No provider, hosted service, credentials, human approval or
downstream agent is involved.

## Reproduce

Use Python >=3.11 with the pinned Proofpress dependency (`cryptography>=44,<47`).
Provide a clone of https://github.com/chenmingtang830/proofpress containing commit
`7fad672321ae00d7c7af350e7b26000846b37895`:

```sh
python studies/framework-boundary/run_demo.py --proofpress-root /path/to/proofpress --check
```

The runner exports that commit with `git archive`; it does not use the checkout's
working files. All writes occur in disposable repositories. The subprocess has a
minimal environment without provider credentials. `--write` regenerates the
retained `results.json`; ordinary `--check` compares it exactly without updating it.
Obtaining the external dependency initially may require network access; executing
the demonstration does not. The RSI-only suite checks the retained receipt and
source hashes without claiming to re-execute external Proofpress code.

## Observations

| Boundary | Observed outcome |
| --- | --- |
| Clean full-package verification | Accept, complete supplied-directory coverage |
| Convert to TRACE 0.5.1, then first import | 3 source records, 3 evidence items, 0 claims, 0 admissions, empty context |
| Repeat identical import | No ledger growth |
| Unsupported 0.5.2, malformed interval, restamped existing identity | Each refused for its specified reason; no ledger growth |
| Existing E05 mean-delta fault | Full verifier refuses; converter and first import into fresh receiver accept |
| Explicit synthetic claim proposal | 1 candidate, 0 admissions, empty governed context |

The wrong-estimate example is not another fault counted in the 1/3/9 result. Its
estimate is absent from the structured imported confidence projection; no raw
result files are opened or recalculated by the adapter. The original TRACE record
and RSI package remain needed to inspect the complete decision.

The first development probe tried to import the changed numerical record over
the same previously imported identity. It was correctly refused because its
normalized rationale changed. The final demonstration uses a fresh receiver to
test **first-time evidence intake**, and explicitly retains the immutable-identity
negative case. This correction is not independent or preregistered evaluation.

## Pins and limits

`results.json` binds the runner, converter, verifier, fixture and Proofpress commit.
Its TRACE release/schema pin is read from that adapter's registry; upstream schema
conformance was **not rerun**. Historical TRACE validation is in `docs/RUN_REPORT.md`.

No verifier-receipt requirement was added to Proofpress. No authorizing human was
simulated. Candidate existence is not governance effectiveness or permission to
reuse. This demonstration exercises only the pre-admission boundary of Govern.
