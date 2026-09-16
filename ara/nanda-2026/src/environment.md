# Environment

## Frozen source

- Repository: `ARA-Labs/Agent-Native-Research-Artifact` conventions are used for this directory; the compiler/reviewer version must be pinned before submission.
- Study repository commit at scaffold creation: `727b9b821d7814d7467a29c1e740ce92eea7e219`.
- RSI-Exam derivation pin declared by the study: `bc36dadb405b`.
- TRACE schema pin declared by the study: `0.5.1`, release commit `a97d4e81fb3b4ec5134e992882d28a6cf97fac04`.

## Runtime

- Python: 3.12 locally and 3.13 in the RSI-Exam sandbox/evaluation container, as documented by the campaign plans.
- Test runner: `python3 -m unittest discover -s tests -t .`.
- Static analysis: `pyright` in basic mode. The local binary was absent, so the draft was checked with an ephemeral `npx --yes pyright` invocation; a pinned toolchain is still required for the frozen artifact.
- Campaign runner: `harbor` 0.22.0 and the pinned RSI-Exam checkout.

## Reproduction boundary

The public repository contains code, manifests, generated summaries, audit inputs, and selected reports. Raw job directories may live outside the repository. A reproduction claim must state whether it is based on committed fixtures, committed generated tables, or access to the original job directories.

No secret, gateway token, raw private trace, or absolute operator path belongs in this artifact.
