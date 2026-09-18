# Environment

## Frozen source

- Format: repository-backed `ARA-Labs/Agent-Native-Research-Artifact` conventions, with a short manifest and logic, src, trace, and evidence layers. No official compiler or Seal was run; do not confuse the local checks with certification.
- Study repository commit at scaffold creation: `727b9b821d7814d7467a29c1e740ce92eea7e219`.
- RSI-Exam derivation pin declared by the study: `bc36dadb405b`.
- TRACE schema pin declared by the study: `0.5.1`, release commit `a97d4e81fb3b4ec5134e992882d28a6cf97fac04`.

## Runtime

- Primary audit reproduction: Python 3.14.6 locally, standard library only. Historical container versions belong to the campaign reports.
- Test runner: `python3 -m unittest discover -s tests -t .`.
- Static analysis: `pyright` in basic mode. The local binary was absent, so the draft was checked with an ephemeral `npx --yes pyright` invocation; a pinned toolchain is still required for the frozen artifact.
- Campaign runner: `harbor` 0.22.0 and the pinned RSI-Exam checkout.

## Reproduction boundary

The public repository contains code, manifests, generated summaries, audit inputs, and selected reports. Raw job directories may live outside the repository. A reproduction claim must state whether it is based on committed fixtures, committed generated tables, or access to the original job directories.

No secret, gateway token, raw private trace, or absolute operator path belongs in this artifact.

## Paper-result reproduction

Primary study (no credentials or fresh agent rollout required):

```bash
python3 studies/decision-audit/run_faults.py
python3 -m unittest tests.test_decision_audit tests.test_nanda_ara -v
```

The regression compares all case outcomes, diagnostics, changed-file hashes,
fixture hashes, and source hashes with a fresh run. Git HEAD may change after
committing. The diagnostic mismatch remains a failed study expectation;
regression success means that outcome reproduced faithfully.

Historical secondary results:

From the repository root:

```bash
python3 ara/nanda-2026/src/execution/build_paper_results.py \
  --source-revision 727b9b821d7814d7467a29c1e740ce92eea7e219 \
  --check
python3 -m unittest tests.test_paper_results -v
```

Without `--check`, the first command regenerates `evidence/results/paper-results.json` and `.md`. It first compares every input byte with the pinned Git revision. It intentionally refuses to infer the missing Opus secondary results.

## IEEE review build

The review source uses the standard `IEEEtran` conference class and an anonymous author block. From the repository root:

```bash
paper_build=$(mktemp -d)
SOURCE_DATE_EPOCH=1789612800 tectonic \
  --outdir "$paper_build" \
  --keep-logs \
  ara/nanda-2026/submission/main.tex
cp "$paper_build/main.pdf" output/pdf/nanda-2026-track3-ieee-review.pdf
```

The current review build is four US-letter pages including references with embedded, subset fonts. It is not approved or submitted. Named implementations can identify contributors despite the anonymous author block; re-check the venue's anonymity and artifact-link policy.

## Framework integration demonstration (E07)

Fresh execution uses Python 3.11.13 and cryptography 46.0.7, with Proofpress source
exported from commit `7fad672321ae00d7c7af350e7b26000846b37895` into a disposable
directory. TRACE wire 0.5.1 is declared by the converter and accepted by the pinned
adapter. Upstream schema validation is not rerun. See studies/framework-boundary/README.md.

This is a source-commit pin, not an npm or PyPI release claim. The pinned
`pyproject.toml` identifies `proofpress-local` with metadata version `0.6.0a1`;
metadata alone does not establish package publication. The paper therefore cites
the Proofpress project without a product release number.
The external source/dependency is not bundled with the RSI-only artifact. A local
clone containing the exact commit is required to re-execute E07; checking its saved
receipt and hashes is a separate portable operation. No hosted or model calls.
