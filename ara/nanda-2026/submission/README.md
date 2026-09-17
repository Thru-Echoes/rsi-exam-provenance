# IEEE review build

This directory contains the four-page framework-first review source for NANDA 2026.

Build from the repository root:

```bash
paper_build=$(mktemp -d)
SOURCE_DATE_EPOCH=1789612800 tectonic \
  --outdir "$paper_build" \
  --keep-logs \
  ara/nanda-2026/submission/main.tex
cp "$paper_build/main.pdf" output/pdf/nanda-2026-track3-ieee-review.pdf
```

The source uses the standard `IEEEtran` conference class and retains an anonymous author block. Named implementations can still identify contributors; the public PR and ARA are not anonymized. The public CFP does not specify anonymity/artifact-link policy, which authors must resolve before submission.

The primary table consumes `studies/decision-audit/fault-results.json` from the
repository root. `tests.test_nanda_ara` checks every row against those results;
`tests.test_decision_audit` reruns the study and compares exact case records.
The older `../evidence/results/paper-results.json` supplies historical context only.

Regenerate the readable manuscript after editing TeX:

```bash
python3 ara/nanda-2026/src/execution/render_manuscript.py
python3 ara/nanda-2026/src/execution/render_manuscript.py --check
```

See `../REVIEW.md` for scientific limitations and author decisions. The internal
review copy has an anonymous author block; neither it nor the full ARA is guaranteed anonymized.

The renderer prints the replacement Markdown; save its output to manuscript.md when regenerating. Unlike bare Pandoc conversion it preserves the title, abstract and bibliography labels.
