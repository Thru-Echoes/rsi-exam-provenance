# IEEE review build

This directory contains the anonymous working review source for NANDA 2026.

Build from the repository root:

```bash
mkdir -p output/pdf
SOURCE_DATE_EPOCH=1789526400 tectonic \
  --outdir output/pdf \
  --keep-logs \
  ara/nanda-2026/submission/main.tex
mv output/pdf/main.pdf output/pdf/nanda-2026-track3-ieee-review.pdf
```

The source uses the standard `IEEEtran` conference class. It remains anonymous because the public CFP and pre-authentication EasyChair page do not state the review anonymity or artifact-link policy. Do not add author-controlled repository links or publish the ARA until that policy is resolved.

The primary table consumes `studies/decision-audit/fault-results.json` from the
repository root. `tests.test_nanda_ara` checks every row against those results;
`tests.test_decision_audit` reruns the study and compares exact case records.
The older `../evidence/results/paper-results.json` supplies historical context only.

Regenerate the readable manuscript after editing TeX:

```bash
pandoc -f latex -t gfm ara/nanda-2026/submission/main.tex -o ara/nanda-2026/submission/manuscript.md
```

See `../REVIEW.md` for scientific limitations and author decisions. The internal
review copy is anonymous; the full ARA repository is not an anonymized artifact.
