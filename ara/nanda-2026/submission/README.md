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

The paper consumes the bounded values in `../evidence/results/paper-results.json`. Update the TeX table only after regenerating that file and re-running the paper-result tests.
