"""Derive a small review download from the verified full offline bundle."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

original, destination = map(Path, sys.argv[1:])
if destination.exists():
    raise SystemExit("Preserve existing snapshots; select another destination")
with zipfile.ZipFile(original) as z:
    manifest = json.loads(z.read("CONTENTS.json"))
    entries = {name: z.read(name) for name in manifest["sha256"]}
for name, data in entries.items():
    assert hashlib.sha256(data).hexdigest() == manifest["sha256"][name]
entries.pop("repository.bundle")
revision = manifest["source_revision"]
entries["START_HERE.md"] = f"""# Capture, Verify, Govern — review snapshot

Open paper.pdf first, then source/ara/nanda-2026/REVIEW.md.
This snapshot includes the four-page IEEE paper, ARA, study inputs and receipts.
It deliberately excludes Git history to keep the public review download small.
The original source instructions describe the separate full offline bundle.

Frozen source: {revision}
Review only, not approval, submission or an anonymized artifact.

## Reproduce directly from this source snapshot

From source/:

```sh
python3 -m unittest tests.test_nanda_ara tests.test_conformance -q
python3 studies/handoff-case-review/review_cases.py --check
python3 ara/nanda-2026/src/execution/check_review_snapshot.py --check
```

These are structure, conformance, retained-case and saved-receipt checks. The
primary fault runner records Git HEAD and needs a real checkout; the historical
table check also needs pinned Git history. For both, obtain the complete offline
bundle from the author or clone the repository and select:

```sh
git clone https://github.com/Thru-Echoes/rsi-exam-provenance
cd rsi-exam-provenance
git checkout --detach {revision}
python3 -m unittest tests.test_decision_audit tests.test_paper_results -q
```

Re-executing E07 additionally requires the pinned external Proofpress commit and
its dependency, documented in source/studies/framework-boundary/README.md. The
portable suite checks the saved E07 receipt, not external-code execution. No human
approval, downstream agent run or full-framework effectiveness is demonstrated.
""".encode()
manifest["distribution_kind"] = "review-source-snapshot-without-git-history"
manifest["sha256"] = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(entries.items())}
entries["CONTENTS.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
    for name, data in sorted(entries.items()):
        z.writestr(name, data)
with zipfile.ZipFile(destination) as z:
    assert z.testzip() is None
    for name, expected in manifest["sha256"].items():
        assert hashlib.sha256(z.read(name)).hexdigest() == expected
print(json.dumps({"path": str(destination), "bytes": destination.stat().st_size,
                  "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                  "source_revision": revision, "verified_entries": len(manifest["sha256"])}, indent=2))
